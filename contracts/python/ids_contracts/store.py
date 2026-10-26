"""C-04 Anomaly Store: Cassandra table `ids.window_scores` — columns, key derivation, row validation, drift rule.

Contract: contracts/C-04_anomaly_store.md (owner M4 — PROVISIONAL REPLICA authored by M1, to be replaced at v1.0)
DDL: contracts/schemas/ids_schema.cql (a contract test checks it matches COLUMNS).
Row representation for validation: timestamps as epoch milliseconds (int).
"""
from __future__ import annotations

import datetime as dt
from typing import List, Mapping, Tuple

CONTRACT_ID = "C-04"
CONTRACT_VERSION = "0.1.0-replica"

KEYSPACE = "ids"
TABLE = "window_scores"
TTL_S = 604_800                       # 7 days
WRITE_CONSISTENCY = "LOCAL_ONE"
PARTITION_KEY = ("date_bucket", "hour")
CLUSTERING = (("window_end", "DESC"), ("src_ip", "ASC"))
COLUMNS = (
    ("date_bucket", "text"), ("hour", "int"), ("window_end", "timestamp"), ("src_ip", "text"),
    ("window_start", "timestamp"), ("total_bytes", "bigint"), ("unique_ports", "int"), ("syn_ack_ratio", "double"),
    ("packet_rate", "double"), ("event_count", "int"), ("anomaly_score", "double"), ("ml_flag", "boolean"),
    ("rule_flag", "boolean"), ("rule_ids", "text"), ("is_anomaly", "boolean"), ("max_event_ts", "timestamp"),
    ("detected_at", "timestamp"), ("bundle_version", "text"), ("run_id", "text"),
    ("label_attack", "boolean"), ("label_type", "text"),
)
EVAL_ONLY = ("label_attack", "label_type")
DRIFT_WINDOW_S = 300
DRIFT_THRESHOLD = 0.15                # banner when anomalous / total > 0.15 over the last 300 s (G6, F5)

_PY = {"text": str, "int": int, "bigint": int, "double": float, "boolean": bool, "timestamp": int}


def partition_key(window_end_ms: int) -> Tuple[str, int]:
    """(date_bucket 'YYYY-MM-DD', hour 0..23) of window_end in UTC."""
    t = dt.datetime.fromtimestamp(window_end_ms / 1000, tz=dt.timezone.utc)
    return t.strftime("%Y-%m-%d"), t.hour


def drift_alert(anomalous: int, total: int) -> bool:
    return total > 0 and anomalous / total > DRIFT_THRESHOLD


def validate_row(row: Mapping) -> List[str]:
    errors = [f"missing '{c}'" for c, _ in COLUMNS if c not in row]
    if errors:
        return errors
    for c, cql in COLUMNS:
        v, typ = row[c], _PY[cql]
        if v is None:
            if c in PARTITION_KEY or c in ("window_end", "src_ip"):
                errors.append(f"key column {c} is null")
            continue
        ok = isinstance(v, bool) if typ is bool else (isinstance(v, typ) and not isinstance(v, bool)) or \
            (typ is float and isinstance(v, int) and not isinstance(v, bool))
        if not ok:
            errors.append(f"{c} has type {type(v).__name__}, expected {cql}")
    if errors:
        return errors
    if (row["date_bucket"], row["hour"]) != partition_key(row["window_end"]):
        errors.append("date_bucket/hour do not match window_end (UTC)")
    if row["window_end"] - row["window_start"] != 30_000:
        errors.append("window_end - window_start != 30 s")
    if row["is_anomaly"] != (row["ml_flag"] or row["rule_flag"]):
        errors.append("is_anomaly != ml_flag OR rule_flag")
    if row["rule_flag"] != bool(row["rule_ids"]):
        errors.append("rule_flag inconsistent with rule_ids")
    return errors
