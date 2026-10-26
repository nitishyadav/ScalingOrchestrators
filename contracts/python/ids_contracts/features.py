"""C-02 Feature Definition: windowing constants, formulas and validators.

Contract: contracts/C-02_feature_definition.md (owner M2 — PROVISIONAL REPLICA authored by M1, to be replaced at v1.0)
These helpers *define* the formulas; M2 (pandas, offline) and M3 (Spark, online) must reproduce
contracts/fixtures/features_golden.csv from contracts/fixtures/events_golden.jsonl.
"""
from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Mapping, Tuple, Union

from .events import BENIGN_LABEL

CONTRACT_ID = "C-02"
CONTRACT_VERSION = "0.2.0-replica"

WINDOW_S, SLIDE_S, WATERMARK_S = 30, 10, 60
WINDOW_MS, SLIDE_MS, WATERMARK_MS = WINDOW_S * 1000, SLIDE_S * 1000, WATERMARK_S * 1000
WINDOWS_PER_EVENT = WINDOW_S // SLIDE_S                       # 3

KEY_COLUMNS = ("window_start", "window_end", "src_ip")
BASE_FEATURES = ("total_bytes", "unique_ports", "syn_ack_ratio", "packet_rate")      # stored in C-04
RATIO_FEATURES = ("bytes_per_flow", "port_ratio", "syn_share")                       # 0.2.0: rate-invariant (D-14)
FEATURE_ORDER = ("bytes_per_flow", "port_ratio", "syn_ack_ratio", "syn_share")       # MODEL INPUT order (0.2.0, D-14 V3)
RULE_FEATURES = BASE_FEATURES + RATIO_FEATURES                                       # what rules.yaml may reference (C-03)
AUX_COLUMNS = ("event_count", "max_event_ts")
EVAL_COLUMNS = ("label_attack", "label_type")                                        # eval-only (ADR-007)
GOLDEN_COLUMNS = KEY_COLUMNS + BASE_FEATURES + RATIO_FEATURES + AUX_COLUMNS + EVAL_COLUMNS
COLUMN_TYPES = {"window_start": int, "window_end": int, "src_ip": str, "total_bytes": int, "unique_ports": int,
                "syn_ack_ratio": float, "packet_rate": float, "bytes_per_flow": float, "port_ratio": float,
                "syn_share": float, "event_count": int, "max_event_ts": int, "label_attack": bool, "label_type": str}
FLOAT_TOLERANCE = 1e-9


def window_starts(ts_ms: int) -> Tuple[int, ...]:
    """Epoch-aligned sliding windows [start, start+30 s) containing ts (same as Spark `window(ts, '30 seconds', '10 seconds')`)."""
    first = (ts_ms // SLIDE_MS) * SLIDE_MS
    return tuple(first - k * SLIDE_MS for k in range(WINDOWS_PER_EVENT))


def replay_timestamp(i: int, t0_ms: int, rate: int) -> int:
    """ADR-011 offline timing for the i-th replay row: t0 + floor(i·1000/R) ms (5 rows per ms at R = 5000)."""
    return t0_ms + (i * 1000) // rate


def syn_ack_ratio(syn_sum: int, ack_sum: int) -> float:
    return syn_sum / (ack_sum + 1)


def packet_rate(event_count: int) -> float:
    return event_count / WINDOW_S


def bytes_per_flow(total_bytes: int, event_count: int) -> float:
    return total_bytes / event_count


def port_ratio(unique_ports: int, event_count: int) -> float:
    return unique_ports / event_count


def syn_share(syn_sum: int, event_count: int) -> float:
    return syn_sum / event_count


def window_label(labels: Iterable[str]) -> Tuple[bool, str]:
    """(label_attack, label_type): attack if any non-BENIGN event; type = most frequent non-benign label (ties → alphabetical)."""
    attacks = Counter(l for l in labels if l != BENIGN_LABEL)
    if not attacks:
        return False, BENIGN_LABEL
    top = max(attacks.values())
    return True, sorted(l for l, n in attacks.items() if n == top)[0]


def _parse(column: str, text: str):
    typ = COLUMN_TYPES[column]
    if typ is bool:
        if text not in ("true", "false"):
            raise ValueError(f"{column}: expected true/false, got {text!r}")
        return text == "true"
    return typ(text)


def read_feature_csv(path: Union[str, Path]) -> List[dict]:
    """Read a golden/feature CSV (header = GOLDEN_COLUMNS) into typed dicts."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != GOLDEN_COLUMNS:
            raise ValueError(f"columns {reader.fieldnames} != {list(GOLDEN_COLUMNS)}")
        return [{c: _parse(c, row[c]) for c in GOLDEN_COLUMNS} for row in reader]


def validate_feature_row(row: Mapping) -> List[str]:
    errors = [f"missing '{c}'" for c in GOLDEN_COLUMNS if c not in row]
    if errors:
        return errors
    for c, typ in COLUMN_TYPES.items():
        v = row[c]
        ok = isinstance(v, bool) if typ is bool else (isinstance(v, typ) and not isinstance(v, bool)) or \
            (typ is float and isinstance(v, int) and not isinstance(v, bool))
        if not ok:
            errors.append(f"{c} has type {type(v).__name__}, expected {typ.__name__}")
    if errors:
        return errors
    if row["window_end"] - row["window_start"] != WINDOW_MS or row["window_start"] % SLIDE_MS:
        errors.append("window is not a 30 s window aligned to 10 s")
    if not row["window_start"] <= row["max_event_ts"] < row["window_end"]:
        errors.append("max_event_ts outside the window")
    if row["event_count"] < 1 or row["unique_ports"] < 1 or row["unique_ports"] > row["event_count"]:
        errors.append("event_count / unique_ports inconsistent")
    if not math.isclose(row["packet_rate"], packet_rate(row["event_count"]), abs_tol=FLOAT_TOLERANCE):
        errors.append("packet_rate != event_count / 30")
    if not math.isclose(row["bytes_per_flow"], bytes_per_flow(row["total_bytes"], row["event_count"]),
                        rel_tol=1e-12, abs_tol=FLOAT_TOLERANCE):
        errors.append("bytes_per_flow != total_bytes / event_count")
    if not math.isclose(row["port_ratio"], port_ratio(row["unique_ports"], row["event_count"]), abs_tol=FLOAT_TOLERANCE):
        errors.append("port_ratio != unique_ports / event_count")
    if row["syn_share"] < 0:
        errors.append("syn_share negative")
    if row["total_bytes"] < 0 or row["syn_ack_ratio"] < 0:
        errors.append("negative feature")
    return errors


def rows_equal(a: Mapping, b: Mapping) -> bool:
    """Equality for golden comparison: exact for ints/strings/bools, FLOAT_TOLERANCE for floats."""
    for c in GOLDEN_COLUMNS:
        if COLUMN_TYPES[c] is float:
            if not math.isclose(float(a[c]), float(b[c]), rel_tol=0, abs_tol=FLOAT_TOLERANCE):
                return False
        elif a[c] != b[c]:
            return False
    return True
