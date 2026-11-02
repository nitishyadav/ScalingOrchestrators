"""C-04 Anomaly Store: Cassandra table `ids.window_scores` — columns, key derivation, row validation, drift rule.

Contract: contracts/C-04_anomaly_store.md (owner M4, Vidhi Kant Gupta). Key design: M4-ADR-001 (5-minute buckets).
DDL: contracts/schemas/ids_schema.cql (a contract test checks it matches COLUMNS).
Row representation for validation: timestamps as epoch milliseconds (int).
"""
from __future__ import annotations

import datetime as dt
from typing import List, Mapping, Tuple

CONTRACT_ID = "C-04"
CONTRACT_VERSION = "1.0.0-rc.1"

KEYSPACE = "ids"
TABLE = "window_scores"
TTL_S = 604_800                       # 7 days
WRITE_CONSISTENCY = "LOCAL_ONE"
BUCKET_S = 300                        # partition = one 5-minute UTC bucket of window_end (M4-ADR-001)
BUCKET_MS = BUCKET_S * 1000
BUCKETS_PER_DAY = 86_400 // BUCKET_S  # 288 -> bucket in 0..287
WINDOW_MS = 30_000                    # C-02 window length
SLIDE_MS = 10_000                     # C-02 slide: window_start and window_end are multiples of this
PARTITION_KEY = ("date_bucket", "bucket")
CLUSTERING = (("window_end", "DESC"), ("src_ip", "ASC"))
COLUMNS = (
    ("date_bucket", "text"), ("bucket", "int"), ("window_end", "timestamp"), ("src_ip", "text"),
    ("window_start", "timestamp"), ("total_bytes", "bigint"), ("unique_ports", "int"), ("syn_ack_ratio", "double"),
    ("packet_rate", "double"), ("event_count", "int"), ("anomaly_score", "double"), ("ml_flag", "boolean"),
    ("rule_flag", "boolean"), ("rule_ids", "text"), ("is_anomaly", "boolean"), ("max_event_ts", "timestamp"),
    ("detected_at", "timestamp"), ("bundle_version", "text"), ("run_id", "text"),
    ("label_attack", "boolean"), ("label_type", "text"),
)
KEY_COLUMNS = ("date_bucket", "bucket", "window_end", "src_ip")
EVAL_ONLY = ("label_attack", "label_type")
NULLABLE = EVAL_ONLY                  # every other column is required (non-null)
DRIFT_WINDOW_S = 300
DRIFT_THRESHOLD = 0.15                # banner when anomalous / total > 0.15 over the last 300 s (G6, F5, ADR-013)

_PY = {"text": str, "int": int, "bigint": int, "double": float, "boolean": bool, "timestamp": int}


def partition_key(window_end_ms: int) -> Tuple[str, int]:
    """(date_bucket 'YYYY-MM-DD', bucket 0..287) of window_end in UTC. A boundary instant opens its bucket."""
    t = dt.datetime.fromtimestamp(window_end_ms // 1000, tz=dt.timezone.utc)
    return t.strftime("%Y-%m-%d"), (t.hour * 3600 + t.minute * 60 + t.second) // BUCKET_S


def partition_keys(start_ms: int, end_ms: int) -> List[Tuple[str, int]]:
    """Every partition that can hold a window_end in [start_ms, end_ms], newest first. Empty if start > end."""
    if start_ms > end_ms:
        return []
    first = start_ms - start_ms % BUCKET_MS
    return [partition_key(b) for b in range(end_ms - end_ms % BUCKET_MS, first - 1, -BUCKET_MS)]


def drift_alert(anomalous: int, total: int) -> bool:
    return total > 0 and anomalous / total > DRIFT_THRESHOLD


def validate_row(row: Mapping) -> List[str]:
    errors = [f"missing '{c}'" for c, _ in COLUMNS if c not in row]
    if errors:
        return errors
    for c, cql in COLUMNS:
        v, typ = row[c], _PY[cql]
        if v is None:
            if c not in NULLABLE:
                errors.append(f"{c} is null")
            continue
        ok = isinstance(v, bool) if typ is bool else (isinstance(v, typ) and not isinstance(v, bool)) or \
            (typ is float and isinstance(v, int) and not isinstance(v, bool))
        if not ok:
            errors.append(f"{c} has type {type(v).__name__}, expected {cql}")
    if errors:
        return errors
    if (row["date_bucket"], row["bucket"]) != partition_key(row["window_end"]):
        errors.append("date_bucket/bucket do not match window_end (UTC, 5-minute buckets)")
    if row["window_end"] - row["window_start"] != WINDOW_MS:
        errors.append("window_end - window_start != 30 s")
    if row["window_start"] % SLIDE_MS:
        errors.append("window_start is not aligned to the 10 s slide")
    if row["is_anomaly"] != (row["ml_flag"] or row["rule_flag"]):
        errors.append("is_anomaly != ml_flag OR rule_flag")
    if row["rule_flag"] != bool(row["rule_ids"]):
        errors.append("rule_flag inconsistent with rule_ids")
    return errors
