"""C-05 Pipeline Metrics: `ids.pipeline_metrics` + `ids.runs` — columns, latency definition, percentile method.

Contract: contracts/C-05_pipeline_metrics.md (owner M3 — PROVISIONAL REPLICA authored by M1, to be replaced at v1.0)
DDL: contracts/schemas/metrics_schema.cql.
"""
from __future__ import annotations

import math
from typing import List, Mapping, Sequence

CONTRACT_ID = "C-05"
CONTRACT_VERSION = "0.1.0-replica"

KEYSPACE = "ids"
METRICS_TABLE, RUNS_TABLE = "pipeline_metrics", "runs"
RUNS_BUCKET = "all"
METRICS_COLUMNS = (
    ("run_id", "text"), ("batch_ts", "timestamp"), ("batch_id", "bigint"), ("input_rows", "bigint"),
    ("input_rows_per_sec", "double"), ("processed_rows_per_sec", "double"), ("batch_duration_ms", "bigint"),
    ("latency_p50_ms", "double"), ("latency_p95_ms", "double"), ("latency_max_ms", "double"),
    ("windows_written", "int"), ("anomalies_written", "int"), ("kafka_partitions", "int"), ("executors", "int"),
)
METRICS_KEY = (("run_id",), (("batch_ts", "DESC"),))
RUNS_COLUMNS = (("bucket", "text"), ("started_at", "timestamp"), ("run_id", "text"), ("config_json", "text"))
RUNS_KEY = (("bucket",), (("started_at", "DESC"),))
LATENCY_DEFINITION = ("per written window row: detected_at - max_event_ts (ms, D-01); "
                      "p50/p95/max over the rows written in one micro-batch, nearest-rank percentiles")
NULLABLE_WHEN_NO_ROWS = ("latency_p50_ms", "latency_p95_ms", "latency_max_ms")

_PY = {"text": str, "int": int, "bigint": int, "double": float, "timestamp": int}


def percentile(values: Sequence[float], p: float):
    """Nearest-rank percentile (p in (0, 100]); None for an empty list. All modules use this definition."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def _validate(row: Mapping, columns, nullable=()) -> List[str]:
    errors = [f"missing '{c}'" for c, _ in columns if c not in row]
    for c, cql in columns:
        if c not in row:
            continue
        v = row[c]
        if v is None:
            if c not in nullable:
                errors.append(f"{c} is null")
            continue
        typ = _PY[cql]
        if not ((isinstance(v, typ) and not isinstance(v, bool)) or (typ is float and isinstance(v, int) and not isinstance(v, bool))):
            errors.append(f"{c} has type {type(v).__name__}, expected {cql}")
    return errors


def validate_metrics_row(row: Mapping) -> List[str]:
    errors = _validate(row, METRICS_COLUMNS, NULLABLE_WHEN_NO_ROWS)
    if errors:
        return errors
    if row["windows_written"] == 0 and row["latency_p95_ms"] is not None:
        errors.append("latency must be null when no rows were written")
    if row["latency_p95_ms"] is not None and not row["latency_p50_ms"] <= row["latency_p95_ms"] <= row["latency_max_ms"]:
        errors.append("latency percentiles not ordered p50 ≤ p95 ≤ max")
    if row["anomalies_written"] > row["windows_written"]:
        errors.append("anomalies_written > windows_written")
    return errors


def validate_run_row(row: Mapping) -> List[str]:
    errors = _validate(row, RUNS_COLUMNS)
    if not errors and row["bucket"] != RUNS_BUCKET:
        errors.append(f"bucket must be '{RUNS_BUCKET}'")
    return errors
