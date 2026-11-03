"""Pure (no PySpark) definitions for the M3 stream job: C-01 schema/validity, C-02 aggregate SQL,
C-03 rules → SQL, C-04/C-05 columns, metrics rows, bundle metadata. Shared by the host CLI, the tests and the driver.
Owner: Kumari Priyanka.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

import yaml

from ids_contracts import bundle as B
from ids_contracts import events as ev
from ids_contracts import features as F
from ids_contracts import metrics as M
from ids_contracts import store as S

# ---- C-01 input (M3-F01) ----------------------------------------------------------------------
# Spark SQL types for each C-01 field (C-01 §3.1).
# Field order must follow ev.ALL_FIELDS so that from_json produces columns in contract order.
_SPARK_TYPES = {
    "event_id":    "STRING",
    "timestamp":   "BIGINT",    # epoch ms; C-01 requires >= MIN_TIMESTAMP_MS to reject stray seconds values
    "src_ip":      "STRING",
    "dst_ip":      "STRING",
    "dst_port":    "INT",
    "bytes_sent":  "BIGINT",
    "syn_flag":    "INT",
    "ack_flag":    "INT",
    "orig_ts":     "STRING",    # optional, opaque text — never parsed (ADR-006)
    "label":       "STRING",    # eval-only field; never used in features/rules (Art. VII)
    "is_injected": "BOOLEAN",   # eval-only field; never used in features/rules (Art. VII)
}

EVENT_DDL = ", ".join(f"{field} {_SPARK_TYPES[field]}" for field in ev.ALL_FIELDS)

# Rough IP shape check (IPv4 dotted-decimal or IPv6 hex+colon). The producer fully validates with
# ipaddress.ip_address; this regex is a lightweight second filter inside the Spark SQL expression.
_IP_RE = r"'^[0-9A-Fa-f:.]{2,45}$'"

# Spark SQL boolean expression used to filter out records that violate C-01 range rules (M3-FR-002).
# coalesce(..., false) in parse_events handles the case where the whole JSON parse failed (all fields null).
VALID_EVENT_SQL = (
    f"event_id IS NOT NULL "
    f"AND timestamp >= {ev.MIN_TIMESTAMP_MS} "
    f"AND src_ip RLIKE {_IP_RE} "
    f"AND dst_ip RLIKE {_IP_RE} "
    f"AND dst_port BETWEEN 0 AND 65535 "
    f"AND bytes_sent >= 0 "
    f"AND syn_flag >= 0 "
    f"AND ack_flag >= 0"
)

# ---- C-02 aggregates (M3-F02) -----------------------------------------------------------------
# Spark duration strings for windowing and watermark (values come from ids_contracts.features).
WINDOW    = f"{F.WINDOW_S} seconds"     # 30 s window length
SLIDE     = f"{F.SLIDE_S} seconds"      # 10 s slide — each event falls into 3 overlapping windows
WATERMARK = f"{F.WATERMARK_S} seconds"  # 60 s — late events up to 60 s after the window close are still included

# Aggregations run inside groupBy(window, src_ip).agg(...).
# syn_sum and ack_sum are intermediate; syn_ack_ratio is derived in finalize().
# unique_ports uses collect_set because countDistinct is not supported on streaming aggregations.
# label and is_injected are eval-only fields (Art. VII) and must never appear here.
FEATURE_AGG_SQL = {
    "total_bytes":  "sum(bytes_sent)",
    "unique_ports": "size(collect_set(dst_port))",  # collect_set → distinct ports; size() counts them
    "syn_sum":      "sum(syn_flag)",
    "ack_sum":      "sum(ack_flag)",
    "event_count":  "count(1)",
    "max_event_ts": "max(timestamp)",               # epoch ms; used to compute latency in C-05
}

# All attack labels (everything except BENIGN), sorted alphabetically for deterministic column order.
ATTACK_LABELS = tuple(sorted(ev.LABELS - {ev.BENIGN_LABEL}))


def label_count_column(label: str) -> str:
    """Convert a C-01 label string into a valid SQL column name, e.g. 'Web Attack - XSS' → 'lbl_web_attack_xss'."""
    return "lbl_" + re.sub(r"[^0-9A-Za-z]+", "_", label).strip("_").lower()


# Per-label event counts in the window (eval-only, ADR-007). One integer counter per label = bounded state.
# Using collect_list(label) would be unbounded; this approach stores exactly 17 integers per window.
LABEL_AGG_SQL = {
    label_count_column(label): f"sum(CASE WHEN label = '{label}' THEN 1 ELSE 0 END)"
    for label in ATTACK_LABELS
}


def label_type_sql() -> str:
    """SQL expression: most frequent non-benign label in the window (ties broken alphabetically), else BENIGN.

    Strategy: build an array of (negated_count, label) structs, sort ascending by negated_count
    (= descending by real count), pick the first entry where count > 0 (i.e. n < 0 after negation).
    coalesce returns BENIGN when no attack labels are present.
    """
    structs = ", ".join(
        f"named_struct('n', -{label_count_column(l)}, 'l', '{l}')"
        for l in ATTACK_LABELS
    )
    return (
        f"coalesce("
        f"filter(array_sort(array({structs})), x -> x.n < 0)[0].l, "
        f"'{ev.BENIGN_LABEL}')"
    )


# ---- C-03 rules (M3-F03) ----------------------------------------------------------------------
# Map from rules.yaml operator strings to their Spark SQL equivalents.
# Note: "==" in the rule maps to "=" in SQL (not "==").
_SQL_OPS = {">=": ">=", ">": ">", "<=": "<=", "<": "<", "==": "="}

# Rule IDs may only contain characters safe to embed in a SQL string literal (no quotes, semicolons, etc.).
_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def rule_condition_sql(rule: Mapping) -> str:
    """Compile one rule's conditions into a Spark SQL boolean expression.

    Each condition in rule["all"] becomes: `feature op value`.
    All conditions are AND-ed together, wrapped in parentheses.
    Raises ValueError if a feature is not in C-02 RULE_FEATURES (prevents reading eval-only fields)
    or if the rule ID contains characters unsafe for SQL literals (SQL injection guard).
    """
    parts = []
    for condition in rule["all"]:
        feature = condition["feature"]
        op      = condition["op"]
        value   = condition["value"]
        if feature not in F.RULE_FEATURES:
            raise ValueError(f"invalid rule condition {condition}: feature must be one of {F.RULE_FEATURES}")
        if op not in _SQL_OPS:
            raise ValueError(f"invalid rule condition {condition}: op must be one of {list(_SQL_OPS)}")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f"invalid rule condition {condition}: value must be a finite number")
        parts.append(f"{feature} {_SQL_OPS[op]} {value!r}")
    return "(" + " AND ".join(parts) + ")"


def rules_sql(rules: Mapping) -> Tuple[str, str]:
    """Compile a parsed rules.yaml into two Spark SQL expressions: (rule_flag_sql, rule_ids_sql).

    rule_flag_sql:  boolean — True if any (combine=any) or all (combine=all) rules fire.
    rule_ids_sql:   string  — comma-separated IDs of fired rules in file order (empty string if none).

    Thresholds and rule conditions live only in rules.yaml, never in Python code (Art. VII).
    """
    errors = B.validate_rules(rules)
    if errors:
        raise ValueError(f"rules violate C-03: {errors}")

    # Build (id, condition_sql) pairs for every rule in file order.
    conds = []
    for rule in rules["rules"]:
        if not _ID_RE.match(rule["id"]):
            raise ValueError(f"rule id {rule['id']!r} contains characters not safe for SQL literals")
        conds.append((rule["id"], rule_condition_sql(rule)))

    # rule_flag: join all rule conditions with OR (combine=any) or AND (combine=all).
    joiner = " AND " if rules["combine"] == "all" else " OR "
    flag_sql = "(" + joiner.join(condition for _, condition in conds) + ")"

    # rule_ids: concat_ws picks fired rule IDs in file order; CASE WHEN returns NULL for non-firing
    # rules, and concat_ws ignores NULLs — so only fired IDs appear in the result.
    ids_sql = (
        "concat_ws(',', "
        + ", ".join(f"CASE WHEN {condition} THEN '{rule_id}' END" for rule_id, condition in conds)
        + ")"
    )
    return flag_sql, ids_sql


class BundleMetaError(RuntimeError):
    """Raised when the C-03 bundle at MODEL_BUNDLE_PATH cannot be loaded or fails validation."""
    pass


def read_bundle_meta(path) -> Tuple[dict, dict]:
    """Load and validate the C-03 bundle manifest and rules from the given directory path.

    Returns (manifest dict, rules dict).
    Raises BundleMetaError if any file is missing, unreadable, or violates C-03 contracts.
    """
    path = Path(path)
    try:
        manifest = json.loads((path / "manifest.json").read_text())
        rules    = yaml.safe_load((path / "rules.yaml").read_text())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise BundleMetaError(f"cannot read C-03 bundle at {path}: {exc}") from None

    if not (path / "model.joblib").is_file():
        raise BundleMetaError(f"bundle at {path} has no model.joblib")

    errors = B.validate_manifest(manifest) + B.validate_rules(rules or {})
    if errors:
        raise BundleMetaError(f"bundle at {path} violates C-03: {errors}")

    return manifest, rules


# ---- C-04 / C-05 output (M3-F04) --------------------------------------------------------------
# Column name tuples derived from ids_contracts so this file stays in sync automatically.
STORE_COLUMNS   = tuple(c for c, _ in S.COLUMNS)
METRICS_COLUMNS = tuple(c for c, _ in M.METRICS_COLUMNS)
RUN_COLUMNS     = tuple(c for c, _ in M.RUNS_COLUMNS)


def _iso_ms(text: str) -> int:
    """Parse a Spark StreamingQueryProgress timestamp string (ISO-8601 with Z or +00:00) to epoch ms."""
    t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    # fromisoformat gives microseconds; convert to ms rounding to nearest (not truncating).
    return int(t.timestamp() * 1000 + 0.5) if t.microsecond % 1000 else int(t.timestamp()) * 1000 + t.microsecond // 1000


def _num(v) -> float:
    """Coerce a Spark progress field to float, returning 0.0 for None, NaN, or Infinity (C-05 safe default)."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def batch_stats(latencies_ms: Sequence[float], anomalies: int) -> dict:
    """Compute latency percentiles and counts for one micro-batch (C-05 §3).

    latencies_ms: list of (detected_at - max_event_ts) values, one per C-04 row written (D-01).
    Returns null latency fields when the list is empty (no rows written in this batch).
    Uses ids_contracts.metrics.percentile (nearest-rank) so M3 and M4 agree on the definition.
    """
    lat = [float(x) for x in latencies_ms]
    return {
        "latency_p50_ms":     M.percentile(lat, 50),
        "latency_p95_ms":     M.percentile(lat, 95),
        "latency_max_ms":     max(lat) if lat else None,
        "windows_written":    len(lat),
        "anomalies_written":  int(anomalies),
    }


def metrics_row(run_id: str, progress: Mapping, stats: Optional[Mapping], executors: int) -> dict:
    """Build one C-05 pipeline_metrics row from a StreamingQueryProgress dict and batch write stats.

    progress: the dict produced by json.loads(event.progress.json) in _ProgressListener.
    stats: output of batch_stats() from process(); None if the batch finished before process() ran.
    kafka_partitions: counted from the endOffset map (one key per assigned partition per source).
    processedRowsPerSecond is coerced to 0.0 when Spark reports NaN (idle batch with no input).
    """
    stats = stats or batch_stats([], 0)

    # Count Kafka partitions from the endOffset map: {topic: {partition_id: offset, ...}, ...}
    partitions = 0
    for src in progress.get("sources") or []:
        try:
            end = src.get("endOffset")
            end = json.loads(end) if isinstance(end, str) else end
            partitions += sum(len(p) for p in (end or {}).values() if isinstance(p, dict))
        except (TypeError, ValueError):
            pass

    row = {
        "run_id":                    run_id,
        "batch_ts":                  _iso_ms(progress["timestamp"]),
        "batch_id":                  int(progress["batchId"]),
        "input_rows":                int(progress.get("numInputRows") or 0),
        "input_rows_per_sec":        _num(progress.get("inputRowsPerSecond")),
        "processed_rows_per_sec":    _num(progress.get("processedRowsPerSecond")),
        "batch_duration_ms":         int((progress.get("durationMs") or {}).get("triggerExecution") or 0),
        "kafka_partitions":          partitions,
        "executors":                 int(executors),
    }
    row.update({k: stats[k] for k in (
        "latency_p50_ms", "latency_p95_ms", "latency_max_ms",
        "windows_written", "anomalies_written",
    )})
    # Return only C-05 columns in the declared order (extra keys are silently dropped).
    return {c: row[c] for c in METRICS_COLUMNS}


def container_path(host_path, workspace_root) -> str:
    """Map a host path under the workspace to its path inside the platform containers (/workspace/…)."""
    rel = Path(host_path).resolve().relative_to(Path(workspace_root).resolve())     # ValueError if outside
    return "/workspace/" + rel.as_posix() if rel.as_posix() != "." else "/workspace"
