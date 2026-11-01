"""Synthetic C-04 / C-05 data: the M4 mock of M3's output (M4-T024, M4-FR-010/011, Const. IV).

    python -m ids_monitor.synthetic [--n-ips 50] [--windows 30] [--anomaly-share 0.1] [--seed 42]
                                    [--run-id DEV-synthetic] [--end-ms MS] [--follow SECONDS]

Each window_end is generated from its own RNG seeded by (seed, window_end), so a run is reproducible and
follow mode extends it consistently. Exactly round(share × n_ips) windows per window_end are anomalous.
Not a model: scores and flags are made up, only their shape and contract validity matter.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import validate_run_id

from ids_monitor import cli, db
from ids_monitor.store import Store, current_ms

COMMAND = "ids_monitor.synthetic"
DEFAULT_RUN_ID = "DEV-synthetic"
BUNDLE_VERSION = "0.0.0-synthetic"
RULES = ("R-SYN-FLOOD", "R-PORT-SCAN", "R-HIGH-RATE")
KAFKA_PARTITIONS, EXECUTORS = 8, 2                         # tags only (C-05); synthetic data has no real config


@dataclass(frozen=True)
class SyntheticRun:
    windows: List[Dict[str, Any]]
    metrics: List[Dict[str, Any]]
    run: Dict[str, Any]


def _check(n_ips: int, anomaly_share: float, run_id: str) -> None:
    if n_ips < 1:
        raise ValueError("n_ips must be ≥ 1")
    if not 0.0 <= anomaly_share <= 1.0:
        raise ValueError("anomaly_share must be in [0, 1]")
    if not validate_run_id(run_id):
        raise ValueError(f"run_id {run_id!r} does not match the C-06 RUN_ID pattern")


def _ip(i: int) -> str:
    return f"10.0.{i // 250}.{i % 250 + 1}"


def generate_batch(window_end: int, seed: int, n_ips: int, anomaly_share: float, run_id: str,
                   batch_id: int = 0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """All windows ending at `window_end` (one per IP) and the C-05 row of the batch that wrote them."""
    rng = random.Random(f"{seed}:{window_end}")
    db_, bucket = S.partition_key(window_end)
    batch_ts = window_end + rng.randint(200, 1_500)        # the sink writes shortly after the window closes
    anomalous = set(rng.sample(range(n_ips), round(anomaly_share * n_ips)))
    rows = []
    for i in range(n_ips):
        bad = i in anomalous
        events = rng.randint(40, 400) if bad else rng.randint(1, 60)
        ports = min(events, rng.randint(20, 200) if bad else rng.randint(1, 5))
        ml = bad and rng.random() < 0.6
        rule_ids = ",".join(sorted(rng.sample(RULES, rng.randint(1, 2)))) if bad and (not ml or rng.random() < 0.4) else ""
        max_event_ts = window_end - rng.randint(1, 3_000)
        rows.append({
            "date_bucket": db_, "bucket": bucket, "window_end": window_end, "src_ip": _ip(i),
            "window_start": window_end - S.WINDOW_MS, "total_bytes": events * rng.randint(60, 1_500),
            "unique_ports": ports, "syn_ack_ratio": round(rng.uniform(2.0, 30.0) if bad else rng.uniform(0.0, 1.0), 4),
            "packet_rate": events / 30, "event_count": events,
            "anomaly_score": round(rng.uniform(0.62, 0.95) if ml else rng.uniform(0.30, 0.55), 4),
            "ml_flag": ml, "rule_flag": bool(rule_ids), "rule_ids": rule_ids, "is_anomaly": bad,
            "max_event_ts": max_event_ts, "detected_at": batch_ts, "bundle_version": BUNDLE_VERSION, "run_id": run_id,
            "label_attack": bad if rng.random() > 0.1 else not bad, "label_type": "SYNTHETIC" if bad else "BENIGN",
        })
    latencies = [r["detected_at"] - r["max_event_ts"] for r in rows]
    input_rows = sum(r["event_count"] for r in rows) // 3 or 1
    duration = rng.randint(300, 900)
    metrics = {
        "run_id": run_id, "batch_ts": batch_ts, "batch_id": batch_id, "input_rows": input_rows,
        "input_rows_per_sec": input_rows / 10, "processed_rows_per_sec": round(input_rows * 1000 / duration, 1),
        "batch_duration_ms": duration, "latency_p50_ms": float(M.percentile(latencies, 50)),
        "latency_p95_ms": float(M.percentile(latencies, 95)), "latency_max_ms": float(max(latencies)),
        "windows_written": len(rows), "anomalies_written": len(anomalous),
        "kafka_partitions": KAFKA_PARTITIONS, "executors": EXECUTORS,
    }
    return rows, metrics


def generate_run(end_ms: int, seed: int, n_ips: int, n_windows: int, anomaly_share: float,
                 run_id: str) -> SyntheticRun:
    """`n_windows` consecutive window_ends (10 s apart), the last one ≤ end_ms on the slide grid."""
    _check(n_ips, anomaly_share, run_id)
    if n_windows < 1:
        raise ValueError("n_windows must be ≥ 1")
    last = end_ms - end_ms % S.SLIDE_MS
    windows: List[Dict[str, Any]] = []
    metrics: List[Dict[str, Any]] = []
    for k, end in enumerate(range(last - (n_windows - 1) * S.SLIDE_MS, last + 1, S.SLIDE_MS)):
        rows, m = generate_batch(end, seed, n_ips, anomaly_share, run_id, batch_id=k)
        windows += rows
        metrics.append(m)
    run = {"bucket": M.RUNS_BUCKET, "started_at": windows[0]["window_start"], "run_id": run_id,
           "config_json": json.dumps({"source": "synthetic", "seed": seed, "n_ips": n_ips,
                                      "anomaly_share": anomaly_share}, sort_keys=True)}
    return SyntheticRun(windows, metrics, run)


def next_window_ends(last_end: int, now_ms: int) -> List[int]:
    """Window ends after `last_end` that have closed by `now_ms` (follow mode)."""
    return list(range(last_end + S.SLIDE_MS, now_ms + 1, S.SLIDE_MS))


# ---- CLI ---------------------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"python -m {COMMAND}", description=__doc__.split("\n\n")[0])
    p.add_argument("--n-ips", type=int, default=50)
    p.add_argument("--windows", type=int, default=30, help="window_ends to write ending now (30 = last 300 s)")
    p.add_argument("--anomaly-share", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--run-id", default=None, help=f"→ RUN_ID (default {DEFAULT_RUN_ID} when RUN_ID is unset)")
    p.add_argument("--end-ms", type=int, default=None, help="last window_end (epoch ms, default now)")
    p.add_argument("--follow", type=int, default=0, metavar="SECONDS", help="keep writing new windows for SECONDS")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    def handler(cfg):
        run_id = args.run_id or (DEFAULT_RUN_ID if cfg.run_id == "DEV-local" else cfg.run_id)
        try:
            run = generate_run(args.end_ms or current_ms(), args.seed, args.n_ips, args.windows,
                               args.anomaly_share, run_id)
        except ValueError as exc:
            raise cli.UsageError(str(exc)) from None
        if args.follow < 0:
            raise cli.UsageError("--follow must be ≥ 0")
        cluster, session = db.connect(cfg)
        try:
            store = Store(session, cfg.cassandra_keyspace)
            store.write_run(run.run)
            n_w = store.write_windows(run.windows)
            n_m = store.write_metrics(run.metrics)
            last = run.windows[-1]["window_end"]
            deadline = time.monotonic() + args.follow
            batch_id = len(run.metrics)
            while time.monotonic() < deadline:
                time.sleep(min(1.0, max(0.0, deadline - time.monotonic())))
                for end in next_window_ends(last, current_ms()):
                    rows, m = generate_batch(end, args.seed, args.n_ips, args.anomaly_share, run_id, batch_id)
                    n_w += store.write_windows(rows)
                    n_m += store.write_metrics([m])
                    batch_id += 1
                    last = end
        finally:
            db.close(cluster)
        return {"run_id": run_id, "windows": n_w, "metrics": n_m, "seed": args.seed, "n_ips": args.n_ips,
                "anomaly_share": args.anomaly_share, "first_window_end": run.windows[0]["window_end"],
                "last_window_end": last, "followed_s": args.follow, "keyspace": cfg.cassandra_keyspace}

    return cli.run(COMMAND, handler, overrides={"RUN_ID": args.run_id})


if __name__ == "__main__":
    sys.exit(main())
