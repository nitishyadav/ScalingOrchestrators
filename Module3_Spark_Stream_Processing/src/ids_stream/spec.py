"""Pure (no PySpark) definitions for the stream job (M3, REPLICA): C-01 schema/validity, C-02 aggregate SQL,
C-03 rules → SQL, C-04/C-05 columns, metrics rows, bundle metadata. Shared by the host CLI, the tests and the driver.
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

# ---- C-01 input -------------------------------------------------------------------------------
_SPARK_TYPES = {"event_id": "STRING", "timestamp": "BIGINT", "src_ip": "STRING", "dst_ip": "STRING", "dst_port": "INT",
                "bytes_sent": "BIGINT", "syn_flag": "INT", "ack_flag": "INT", "orig_ts": "STRING", "label": "STRING",
                "is_injected": "BOOLEAN"}
EVENT_DDL = ", ".join(f"{f} {_SPARK_TYPES[f]}" for f in ev.ALL_FIELDS)
_IP_RE = r"'^[0-9A-Fa-f:.]{2,45}$'"           # IPv4/IPv6 shape (the producer validates fully, C-01 §7)
VALID_EVENT_SQL = (f"event_id IS NOT NULL AND timestamp >= {ev.MIN_TIMESTAMP_MS} AND src_ip RLIKE {_IP_RE} "
                   f"AND dst_ip RLIKE {_IP_RE} AND dst_port BETWEEN 0 AND 65535 AND bytes_sent >= 0 "
                   "AND syn_flag >= 0 AND ack_flag >= 0")

# ---- C-02 aggregates --------------------------------------------------------------------------
WINDOW = f"{F.WINDOW_S} seconds"
SLIDE = f"{F.SLIDE_S} seconds"
WATERMARK = f"{F.WATERMARK_S} seconds"
FEATURE_AGG_SQL = {                       # model inputs + auxiliaries (never eval-only fields, Art. VII)
    "total_bytes": "sum(bytes_sent)",
    "unique_ports": "size(collect_set(dst_port))",
    "syn_sum": "sum(syn_flag)",
    "ack_sum": "sum(ack_flag)",
    "event_count": "count(1)",
    "max_event_ts": "max(timestamp)",
}
ATTACK_LABELS = tuple(sorted(ev.LABELS - {ev.BENIGN_LABEL}))


def label_count_column(label: str) -> str:
    return "lbl_" + re.sub(r"[^0-9A-Za-z]+", "_", label).strip("_").lower()


LABEL_AGG_SQL = {label_count_column(l): f"sum(CASE WHEN label = '{l}' THEN 1 ELSE 0 END)" for l in ATTACK_LABELS}


def label_type_sql() -> str:
    """Most frequent non-benign label, ties alphabetical (C-02 `window_label`); BENIGN if none."""
    structs = ", ".join(f"named_struct('n', -{label_count_column(l)}, 'l', '{l}')" for l in ATTACK_LABELS)
    return f"coalesce(filter(array_sort(array({structs})), x -> x.n < 0)[0].l, '{ev.BENIGN_LABEL}')"


# ---- C-03 rules -------------------------------------------------------------------------------
_SQL_OPS = {">=": ">=", ">": ">", "<=": "<=", "<": "<", "==": "="}
_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def rule_condition_sql(rule: Mapping) -> str:
    parts = []
    for c in rule["all"]:
        if c["feature"] not in F.RULE_FEATURES or c["op"] not in _SQL_OPS or not isinstance(c["value"], (int, float)) \
                or isinstance(c["value"], bool) or not math.isfinite(c["value"]):
            raise ValueError(f"invalid rule condition {c}")
        parts.append(f"{c['feature']} {_SQL_OPS[c['op']]} {c['value']!r}")
    return "(" + " AND ".join(parts) + ")"


def rules_sql(rules: Mapping) -> Tuple[str, str]:
    """(rule_flag SQL, rule_ids SQL) from a parsed rules.yaml (C-03 §4/§5); ids in file order."""
    errors = B.validate_rules(rules)
    if errors:
        raise ValueError(f"rules violate C-03: {errors}")
    conds = []
    for r in rules["rules"]:
        if not _ID_RE.match(r["id"]):
            raise ValueError(f"rule id {r['id']!r} has characters not allowed in SQL literals")
        conds.append((r["id"], rule_condition_sql(r)))
    joiner = " AND " if rules["combine"] == "all" else " OR "
    flag = "(" + joiner.join(c for _, c in conds) + ")"
    ids = "concat_ws(',', " + ", ".join(f"CASE WHEN {c} THEN '{i}' END" for i, c in conds) + ")"
    return flag, ids


class BundleMetaError(RuntimeError):
    pass


def read_bundle_meta(path) -> Tuple[dict, dict]:
    path = Path(path)
    try:
        manifest = json.loads((path / "manifest.json").read_text())
        rules = yaml.safe_load((path / "rules.yaml").read_text())
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise BundleMetaError(f"cannot read C-03 bundle at {path}: {exc}") from None
    if not (path / "model.joblib").is_file():
        raise BundleMetaError(f"bundle at {path} has no model.joblib")
    errors = B.validate_manifest(manifest) + B.validate_rules(rules or {})
    if errors:
        raise BundleMetaError(f"bundle at {path} violates C-03: {errors}")
    return manifest, rules


# ---- C-04 / C-05 output -----------------------------------------------------------------------
STORE_COLUMNS = tuple(c for c, _ in S.COLUMNS)
METRICS_COLUMNS = tuple(c for c, _ in M.METRICS_COLUMNS)
RUN_COLUMNS = tuple(c for c, _ in M.RUNS_COLUMNS)


def _iso_ms(text: str) -> int:
    t = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(t.timestamp() * 1000 + 0.5) if t.microsecond % 1000 else int(t.timestamp()) * 1000 + t.microsecond // 1000


def _num(v) -> float:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def batch_stats(latencies_ms: Sequence[float], anomalies: int) -> dict:
    lat = [float(x) for x in latencies_ms]
    return {"latency_p50_ms": M.percentile(lat, 50), "latency_p95_ms": M.percentile(lat, 95),
            "latency_max_ms": max(lat) if lat else None, "windows_written": len(lat), "anomalies_written": int(anomalies)}


def metrics_row(run_id: str, progress: Mapping, stats: Optional[Mapping], executors: int) -> dict:
    """One C-05 `pipeline_metrics` row from a StreamingQueryProgress (as dict) + this batch's write stats."""
    stats = stats or batch_stats([], 0)
    partitions = 0
    for src in progress.get("sources") or []:
        try:
            end = src.get("endOffset")
            end = json.loads(end) if isinstance(end, str) else end
            partitions += sum(len(p) for p in (end or {}).values() if isinstance(p, dict))
        except (TypeError, ValueError):
            pass
    row = {"run_id": run_id, "batch_ts": _iso_ms(progress["timestamp"]), "batch_id": int(progress["batchId"]),
           "input_rows": int(progress.get("numInputRows") or 0), "input_rows_per_sec": _num(progress.get("inputRowsPerSecond")),
           "processed_rows_per_sec": _num(progress.get("processedRowsPerSecond")),
           "batch_duration_ms": int((progress.get("durationMs") or {}).get("triggerExecution") or 0),
           "kafka_partitions": partitions, "executors": int(executors)}
    row.update({k: stats[k] for k in ("latency_p50_ms", "latency_p95_ms", "latency_max_ms", "windows_written", "anomalies_written")})
    return {c: row[c] for c in METRICS_COLUMNS}


def container_path(host_path, workspace_root) -> str:
    """Map a host path under the workspace to its path inside the platform containers (/workspace/…)."""
    rel = Path(host_path).resolve().relative_to(Path(workspace_root).resolve())     # ValueError if outside
    return "/workspace/" + rel.as_posix() if rel.as_posix() != "." else "/workspace"
