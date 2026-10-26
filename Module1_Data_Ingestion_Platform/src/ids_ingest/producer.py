"""`python -m ids_ingest.producer` — replay C-01 events into Kafka at a constant rate (M1-F03).

Sources yield C-01 record dicts; `run()` paces, stamps (uuid4 + emission time), samples validation and sends via a sink.
The clock and sink are injectable so pacing is unit-tested deterministically. M1-F04 wraps the source to inject attacks.
"""
from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, List, Mapping, Optional, Sequence

import pyarrow.parquet as pq

from ids_contracts import FIXTURES_DIR
from ids_contracts import events as ev
from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, RuntimeConfig,
                                  load_runtime_config, summary_line)

from .injector import InjectingSource

RECORD_FIELDS = ("orig_ts", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag", "label")
FIXTURE_PATH = FIXTURES_DIR / "events_golden.jsonl"
BATCH_ROWS = 8192
EARLY_S = 0.002                 # may emit up to 2 ms early; never sleeps for less (average rate stays exact)
VALIDATE_FIRST, VALIDATE_EVERY = 1000, 1000
MAX_ERROR_RATIO = 0.001         # C-01 §8: > 0.1 % failed/invalid → exit 1

KAFKA_PRODUCER_CONFIG = {
    "partitioner": ev.LIBRDKAFKA_PARTITIONER,   # murmur2, same as Java/Spark (C-01 §2.1)
    "linger.ms": 5,
    "compression.type": "lz4",
    "acks": "1",
    "queue.buffering.max.messages": 500_000,
    "broker.address.family": "v4",               # Colima forwards IPv4 only
}


class ProducerError(RuntimeError):
    """Source or setup problem (exit 1)."""


class SinkError(ProducerError):
    """Broker unreachable or topic missing (exit 1)."""


class Clock:
    def monotonic(self) -> float:
        return time.monotonic()

    def wall_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def sleep(self, s: float) -> None:
        time.sleep(s)


def make_event(record: Mapping, ts_ms: int, injected: Optional[bool] = None) -> dict:
    event = {"event_id": str(uuid.uuid4()), "timestamp": ts_ms}
    event.update(record)
    event["is_injected"] = bool(record.get("is_injected", False)) if injected is None else injected
    return event


# ---- sources -----------------------------------------------------------------------------------
class ReplaySource:
    """C-01 replay dataset in day order, then row_idx order; loops unless loop=False (FR-021, FR-024)."""

    def __init__(self, data_dir: Path, days: Optional[Sequence[str]] = None, loop: bool = True,
                 allow_unverified: bool = False):
        root = Path(data_dir) / "replay"
        try:
            manifest = json.loads((root / ev.REPLAY_MANIFEST_NAME).read_text())
        except (OSError, ValueError):
            raise ProducerError(f"no replay dataset at {root}; run `python -m ids_ingest.prepare` first") from None
        errors = ev.validate_manifest(manifest)
        if errors:
            raise ProducerError(f"replay manifest invalid: {errors}")
        wanted = set(days) if days else set(ev.REPLAY_DAYS)
        self.days = [d for d in ev.REPLAY_DAYS if d in wanted and d in manifest["days"]]
        if not self.days:
            raise ProducerError(f"none of the requested days {sorted(wanted)} are in the replay dataset")
        mismatched = [d for d in self.days if manifest["days"][d]["content_sha256"] != ev.REPLAY_CONTENT_SHA256.get(d)]
        if mismatched and not allow_unverified:
            raise ProducerError(f"replay data for {mismatched} differs from the C-01 §2.2 reference hashes; re-run "
                                f"`python -m ids_ingest.prepare --force`, or pass --allow-unverified")
        self.paths = [root / manifest["days"][d]["path"] for d in self.days]
        self.loop = loop
        self.loops = 0
        self.exhausted = False

    def __iter__(self) -> Iterator[dict]:
        while True:
            yielded = False
            for path in self.paths:
                for batch in pq.ParquetFile(path).iter_batches(batch_size=BATCH_ROWS, columns=list(RECORD_FIELDS)):
                    cols = [batch.column(i).to_pylist() for i in range(len(RECORD_FIELDS))]
                    for row in zip(*cols):
                        yielded = True
                        yield dict(zip(RECORD_FIELDS, row))
            if not self.loop or not yielded:
                self.exhausted = True
                return
            self.loops += 1


class FixtureSource:
    """Golden events with their offsets from the first event (FR-025)."""

    def __init__(self, path: Path = FIXTURE_PATH):
        self.events = list(ev.iter_jsonl(path))
        self.loops, self.exhausted = 0, False

    def __iter__(self):
        base = self.events[0]["timestamp"]
        for e in self.events:
            yield e["timestamp"] - base, {k: v for k, v in e.items() if k not in ("event_id", "timestamp")}
        self.exhausted = True


# ---- sink --------------------------------------------------------------------------------------
class KafkaSink:
    def __init__(self, bootstrap: str, topic: str):
        from confluent_kafka import Producer
        self.bootstrap, self.topic = bootstrap, topic
        self.delivered = self.failed = 0
        self._p = Producer({"bootstrap.servers": bootstrap, **KAFKA_PRODUCER_CONFIG})

    def check(self, timeout: float = 10.0) -> int:
        from confluent_kafka import KafkaException
        try:
            md = self._p.list_topics(topic=self.topic, timeout=timeout)
        except KafkaException as exc:
            raise SinkError(f"cannot reach Kafka at {self.bootstrap}: {exc}. Is the platform up? "
                            f"(`python -m ids_ingest.platform status`)") from None
        t = md.topics.get(self.topic)
        if t is None or t.error is not None:
            raise SinkError(f"topic '{self.topic}' does not exist; create it with "
                            f"`python -m ids_ingest.topic_admin --partitions N`")
        return len(t.partitions)

    def _on_delivery(self, err, _msg) -> None:
        if err is None:
            self.delivered += 1
        else:
            self.failed += 1

    def send(self, key: bytes, value: bytes) -> None:
        while True:
            try:
                self._p.produce(self.topic, value=value, key=key, on_delivery=self._on_delivery)
                return
            except BufferError:
                self._p.poll(0.05)

    def poll(self) -> None:
        self._p.poll(0)

    def flush(self, timeout: float = 30.0) -> int:
        return self._p.flush(timeout)


# ---- run loop ----------------------------------------------------------------------------------
@dataclass
class RunStats:
    source: str = "replay"
    produced: int = 0
    sent: int = 0
    failed: int = 0
    invalid: int = 0
    validated: int = 0
    injected: int = 0
    loops: int = 0
    exhausted: bool = False
    stopped: bool = False
    duration_s: float = 0.0
    partitions: int = 0
    per_second: List[int] = field(default_factory=list)

    def error_ratio(self) -> float:
        return (self.failed + self.invalid) / max(self.produced, 1)

    def summary(self, target_rate: int) -> dict:
        full = sorted(self.per_second)

        def pct(p):
            return full[min(len(full) - 1, int(math.floor(p * len(full))))] if full else None

        status = "error" if self.error_ratio() > MAX_ERROR_RATIO else ("stopped" if self.stopped else "ok")
        return {"source": self.source, "status": status, "produced": self.produced, "sent": self.sent,
                "failed": self.failed, "invalid": self.invalid, "injected": self.injected,
                "target_rate": target_rate if self.source == "replay" else None,
                "achieved_rate": round(self.sent / self.duration_s, 1) if self.duration_s else 0.0,
                "rate_p05": pct(0.05), "rate_p50": pct(0.5), "rate_p95": pct(0.95),
                "loops": self.loops, "exhausted": self.exhausted, "partitions": self.partitions,
                "duration_s": round(self.duration_s, 2)}


def _should_validate(i: int, mode: str) -> bool:
    return mode == "fixture" or i < VALIDATE_FIRST or i % VALIDATE_EVERY == 0


def run(source: Iterable, sink, *, mode: str, rate: int, duration_s: float, clock: Optional[Clock] = None,
        stop: Callable[[], bool] = lambda: False) -> RunStats:
    """Replay mode: event i is due at start + i/rate. Fixture mode: source yields (offset_ms, record)."""
    clock = clock or Clock()
    stats = RunStats(source=mode)
    counts: List[int] = []
    start, start_ms = clock.monotonic(), clock.wall_ms()
    it = iter(source)
    i = -1

    def finish_at_duration():
        # the run ends at its full duration, not at the last event (keeps rate and per-second stats exact)
        clock.sleep(max(0.0, duration_s - (clock.monotonic() - start)))

    while True:
        i += 1
        if stop():
            stats.stopped = True
            break
        if mode != "fixture" and i / rate >= duration_s:      # decide before pulling: nothing is fetched unsent
            finish_at_duration()
            break
        try:
            item = next(it)
        except StopIteration:
            break
        if mode == "fixture":
            offset_ms, record = item
            due = offset_ms / 1000.0
            if due >= duration_s:
                finish_at_duration()
                break
        else:
            record, due = item, i / rate
        ahead = due - (clock.monotonic() - start)
        if ahead > EARLY_S:
            clock.sleep(ahead)
        if stop():
            stats.stopped = True
            break
        elapsed = clock.monotonic() - start
        event = make_event(record, start_ms + offset_ms if mode == "fixture" else clock.wall_ms())
        stats.produced += 1
        if _should_validate(i, mode):
            stats.validated += 1
            if ev.validate_event(event, strict=True):
                stats.invalid += 1
                continue
        sink.send(ev.event_key(event), ev.encode_event(event))
        stats.injected += event["is_injected"]
        sec = int(elapsed)
        while len(counts) <= sec:
            counts.append(0)
        counts[sec] += 1
        if stats.produced % 1000 == 0:
            sink.poll()
    remaining = sink.flush(30.0)
    stats.duration_s = clock.monotonic() - start
    stats.sent, stats.failed = sink.delivered, sink.failed + max(0, remaining)
    stats.loops = getattr(source, "loops", 0)
    stats.exhausted = getattr(source, "exhausted", False)
    stats.per_second = counts[: int(stats.duration_s)]          # full seconds only
    return stats


def attack_summary(source: Optional[InjectingSource], cfg: RuntimeConfig, seed: int) -> dict:
    if source is None:
        return {"attack_mode": "none", "attack_share": 0.0, "achieved_share": 0.0, "injected_by_type": {},
                "seed": seed, "attack_window_s": None}
    return {"attack_mode": cfg.attack_mode, "attack_share": cfg.attack_share, "achieved_share": source.achieved_share,
            "injected_by_type": dict(sorted(source.counts.items())), "seed": seed, "attack_window_s": source.window}


# ---- CLI ---------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ids_ingest.producer", description="Replay C-01 events into Kafka (C-06 §5).")
    p.add_argument("--source", choices=("replay", "fixture"), default="replay")
    p.add_argument("--rate", type=int, help="events/s (→ PRODUCER_RATE)")
    p.add_argument("--duration", type=int, help="seconds (→ RUN_DURATION_S)")
    p.add_argument("--days", help="comma-separated, e.g. Monday,Friday (default: all)")
    p.add_argument("--no-loop", action="store_true", help="stop when the replay data runs out")
    p.add_argument("--allow-unverified", action="store_true", help="replay data whose hashes differ from C-01")
    p.add_argument("--attack-mode", help="none|ddos|synflood|portscan|mixed (→ ATTACK_MODE)")
    p.add_argument("--attack-share", type=float, help="share of all events while the attack is active, 0..1 (→ ATTACK_SHARE)")
    p.add_argument("--attack-start", type=float, default=0.0, help="seconds from run start when injection begins")
    p.add_argument("--attack-duration", type=float, help="seconds of injection (default: until the end)")
    p.add_argument("--seed", type=int, default=42, help="seed for reproducible injection")
    p.add_argument("--run-id", help="→ RUN_ID")
    return p


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         sink_factory: Optional[Callable[[RuntimeConfig], object]] = None, clock: Optional[Clock] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_runtime_config(env=env, overrides={
            "PRODUCER_RATE": args.rate, "RUN_DURATION_S": args.duration, "ATTACK_MODE": args.attack_mode,
            "ATTACK_SHARE": args.attack_share, "RUN_ID": args.run_id})
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    attacking = cfg.attack_mode != "none"
    if attacking and args.source == "fixture":
        print("attack injection works with --source replay only (the fixture already contains an injected SYN flood)",
              file=sys.stderr)
        return EXIT_USAGE_ERROR
    if args.attack_start < 0 or (args.attack_duration is not None and args.attack_duration <= 0):
        print("--attack-start must be ≥ 0 and --attack-duration > 0", file=sys.stderr)
        return EXIT_USAGE_ERROR
    days = [d.strip() for d in args.days.split(",")] if args.days else None
    unknown = [d for d in days or [] if d not in ev.REPLAY_DAYS]
    if unknown:
        print(f"unknown day(s) {unknown}; choose from {list(ev.REPLAY_DAYS)}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    stop_flag = {"stop": False}

    def _handle(signum, _frame):
        stop_flag["stop"] = True

    previous = {}
    try:
        source = (FixtureSource() if args.source == "fixture"
                  else ReplaySource(cfg.data_dir, days, loop=not args.no_loop, allow_unverified=args.allow_unverified))
        if attacking:
            source = InjectingSource(source, mode=cfg.attack_mode, share=cfg.attack_share, rate=cfg.producer_rate,
                                     seed=args.seed, start_s=args.attack_start, duration_s=args.attack_duration)
        sink = sink_factory(cfg) if sink_factory else KafkaSink(cfg.kafka_bootstrap, cfg.kafka_topic)
        partitions = sink.check()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous[sig] = signal.signal(sig, _handle)
            except ValueError:          # not in the main thread (e.g. embedded use)
                pass
        stats = run(source, sink, mode=args.source, rate=cfg.producer_rate, duration_s=cfg.run_duration_s,
                    clock=clock, stop=lambda: stop_flag["stop"])
    except ProducerError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    stats.partitions = partitions
    summary = stats.summary(cfg.producer_rate)
    summary.update(attack_summary(source if attacking else None, cfg, args.seed))
    print(summary_line("producer", cfg.run_id, **summary))
    if summary["status"] == "error":
        print(f"{stats.failed} failed + {stats.invalid} invalid of {stats.produced} produced exceeds 0.1 %", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
