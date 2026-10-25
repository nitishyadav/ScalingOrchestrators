"""`python -m ids_monitor.synthetic` — M4's mock: contract-valid synthetic C-04/C-05 rows (M4-F01, REPLICA).

Lets the dashboard and benchmark tooling be developed before the Spark job (M3) exists. Deterministic per seed.
Synthetic source IPs use 10.0.x.y; anomalous windows carry INJ_* labels as synthetic ground truth (eval-only).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from typing import Callable, Mapping, Optional, Sequence

from ids_contracts import store as S
from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

WINDOW_STEP_MS, METRICS_STEP_MS = 10_000, 5_000
THRESHOLD = 0.55
PROFILES = ("ddos", "synflood", "portscan")
RULES = {"ddos": "R-DDOS-RATE", "synflood": "R-SYN-FLOOD", "portscan": "R-PORT-SCAN"}


def _ip(i: int) -> str:
    return f"10.0.{i // 250}.{i % 250 + 1}"


def _window_rows(rng: random.Random, end: int, n_ips: int, share: float, run_id: str) -> list:
    anomalous = set(rng.sample(range(n_ips), round(share * n_ips)))
    db, hour = S.partition_key(end)
    rows = []
    for i in range(n_ips):
        bad = i in anomalous
        kind = rng.choice(PROFILES) if bad else None
        n = rng.randint(200, 3000) if kind in ("ddos", "synflood") else rng.randint(50, 1500) if bad else rng.randint(5, 300)
        ports = min(n, rng.randint(100, 1000)) if kind == "portscan" else 1 if bad else min(n, rng.randint(1, 5))
        syn = n if kind in ("synflood", "portscan") else rng.randint(0, n)
        ack = 0 if kind in ("synflood", "portscan") else rng.randint(max(0, syn - 2), n)
        nbytes = rng.randint(1_000_000, 6_000_000) if kind == "ddos" else rng.randint(0, 60 * n) if bad else rng.randint(1_000, 200_000)
        score = rng.uniform(THRESHOLD + 0.01, 0.85) if bad else rng.uniform(0.30, THRESHOLD - 0.05)
        rule = bad and rng.random() < 0.6
        max_ts = end - rng.randint(1, 9_999)
        rows.append({
            "date_bucket": db, "hour": hour, "window_end": end, "src_ip": _ip(i), "window_start": end - 30_000,
            "total_bytes": nbytes, "unique_ports": ports, "syn_ack_ratio": syn / (ack + 1), "packet_rate": n / 30,
            "event_count": n, "anomaly_score": score, "ml_flag": score >= THRESHOLD, "rule_flag": rule,
            "rule_ids": RULES[kind] if rule else "", "is_anomaly": bad, "max_event_ts": max_ts,
            "detected_at": max_ts + rng.randint(80, 450), "bundle_version": "0.0.0-dummy", "run_id": run_id,
            "label_attack": bad, "label_type": f"INJ_{kind.upper()}" if bad else "BENIGN",
        })
    return rows


def _metrics_row(rng: random.Random, ts: int, batch_id: int, n_ips: int, share: float, run_id: str) -> dict:
    lat = sorted(rng.uniform(80, 450) for _ in range(n_ips))
    rows = rng.randint(24_000, 26_000)
    return {"run_id": run_id, "batch_ts": ts, "batch_id": batch_id, "input_rows": rows,
            "input_rows_per_sec": rows / 5.0, "processed_rows_per_sec": rows / 5.0 * rng.uniform(1.05, 1.6),
            "batch_duration_ms": rng.randint(300, 900), "latency_p50_ms": lat[len(lat) // 2],
            "latency_p95_ms": lat[max(0, int(0.95 * len(lat)) - 1)], "latency_max_ms": lat[-1],
            "windows_written": n_ips, "anomalies_written": round(share * n_ips), "kafka_partitions": 8, "executors": 2}


def generate(now_ms: int, seconds: int, n_ips: int, anomaly_share: float, run_id: str, seed: int = 42) -> dict:
    rng = random.Random(seed)
    last = (now_ms // WINDOW_STEP_MS) * WINDOW_STEP_MS
    ends = [last - k * WINDOW_STEP_MS for k in range(seconds * 1000 // WINDOW_STEP_MS)][::-1]
    windows = [r for end in ends for r in _window_rows(rng, end, n_ips, anomaly_share, run_id)]
    start = now_ms - seconds * 1000
    metrics = [_metrics_row(rng, start + (i + 1) * METRICS_STEP_MS, i, n_ips, anomaly_share, run_id)
               for i in range(seconds * 1000 // METRICS_STEP_MS)]
    run = {"bucket": "all", "started_at": start, "run_id": run_id,
           "config_json": json.dumps({"synthetic": True, "ips": n_ips, "anomaly_share": anomaly_share, "seed": seed})}
    return {"windows": windows, "metrics": metrics, "run": run}


def follow(writer, seconds: int, n_ips: int, anomaly_share: float, run_id: str, seed: int,
           now: Callable[[], int], sleep: Callable[[float], None], first_batch_id: int = 10_000) -> int:
    """Keep writing a new 10 s window batch (plus two 5 s metrics rows) in real time for `seconds`."""
    rng = random.Random(seed + 1)
    start = now()
    end = (start // WINDOW_STEP_MS + 1) * WINDOW_STEP_MS
    batch, written = first_batch_id, 0
    while end <= start + seconds * 1000:
        sleep(max(0.0, (end - now()) / 1000))
        writer.write_windows(_window_rows(rng, end, n_ips, anomaly_share, run_id))
        writer.write_metrics([_metrics_row(rng, end - METRICS_STEP_MS, batch, n_ips, anomaly_share, run_id),
                              _metrics_row(rng, end, batch + 1, n_ips, anomaly_share, run_id)])
        batch, written, end = batch + 2, written + n_ips, end + WINDOW_STEP_MS
    return written


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         writer_factory: Optional[Callable] = None, now: Callable[[], int] = lambda: int(time.time() * 1000)) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_monitor.synthetic", description="Write synthetic C-04/C-05 rows (M4 mock).")
    p.add_argument("--seconds", type=int, default=600, help="history to write, ending now (≥ 10)")
    p.add_argument("--ips", type=int, default=30, help="source IPs per window (≥ 1)")
    p.add_argument("--anomaly-share", type=float, default=0.2, help="anomalous share of windows, 0..1")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--run-id", default="DEV-synthetic")
    p.add_argument("--follow", type=int, default=0, help="then keep writing live windows for this many seconds")
    args = p.parse_args(argv)
    if args.seconds < 10 or args.ips < 1 or not 0 <= args.anomaly_share <= 1 or args.follow < 0:
        print("need --seconds ≥ 10, --ips ≥ 1, 0 ≤ --anomaly-share ≤ 1, --follow ≥ 0", file=sys.stderr)
        return EXIT_USAGE_ERROR
    try:
        cfg = load_runtime_config(env=env, overrides={"RUN_ID": args.run_id})
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    from .store import StoreUnavailable, StoreWriter, connect
    try:
        writer = writer_factory(cfg) if writer_factory else StoreWriter(connect(cfg))
    except StoreUnavailable as exc:
        print(f"{exc}\nIs the platform running? (`python -m ids_ingest.platform status`)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    data = generate(now(), args.seconds, args.ips, args.anomaly_share, args.run_id, args.seed)
    writer.write_run(data["run"])
    writer.write_windows(data["windows"])
    writer.write_metrics(data["metrics"])
    live = follow(writer, args.follow, args.ips, args.anomaly_share, args.run_id, args.seed, now,
                  lambda s: time.sleep(s)) if args.follow else 0
    print(summary_line("synthetic", args.run_id, windows_written=len(data["windows"]) + live,
                       metrics_written=len(data["metrics"]), anomaly_share=args.anomaly_share, follow_s=args.follow))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
