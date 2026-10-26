"""C-02 reference feature builder in pandas (M2-F02, REPLICA). Must reproduce contracts/fixtures/features_golden.csv.

Reads only C-01 SCORING_FIELDS for features; `label` (eval-only) feeds only label_attack / label_type.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd

from ids_contracts import features as F
from ids_contracts.events import BENIGN_LABEL, REPLAY_DAYS, SCORING_FIELDS

R_REF = 5000
DEFAULT_T0_MS = 1_767_225_600_000          # a multiple of 10 s (2026-01-01T00:00:00Z)
_INT = ("window_start", "window_end", "total_bytes", "unique_ports", "event_count", "max_event_ts")
_FLOAT = ("syn_ack_ratio", "packet_rate") + F.RATIO_FEATURES


def _empty() -> pd.DataFrame:
    dtypes = {c: "int64" for c in _INT} | {c: "float64" for c in _FLOAT} | {"src_ip": "object", "label_type": "object",
                                                                         "label_attack": "bool"}
    return pd.DataFrame({c: pd.Series(dtype=dtypes[c]) for c in F.GOLDEN_COLUMNS})


EXTENDED_COLUMNS = ("syn_sum", "ack_sum", "attack_events")      # experiment/eval only (D-14); never in C-02 output


def build_features(events: pd.DataFrame, extended: bool = False) -> pd.DataFrame:
    """Events (C-01 fields) → one row per (window, src_ip) in GOLDEN_COLUMNS order, sorted by (window_start, src_ip).
    extended=True appends EXTENDED_COLUMNS (raw SYN/ACK sums; eval-only count of non-benign events)."""
    if len(events) == 0:
        return _empty()
    base = events[list(SCORING_FIELDS)].copy()
    base["timestamp"] = base["timestamp"].astype("int64")
    has_labels = "label" in events.columns
    if has_labels:
        base["label"] = events["label"].to_numpy()
        base["_attack"] = (base["label"] != BENIGN_LABEL).astype("int64")
    first = (base["timestamp"] // F.SLIDE_MS) * F.SLIDE_MS
    exploded = pd.concat([base.assign(window_start=first - k * F.SLIDE_MS) for k in range(F.WINDOWS_PER_EVENT)],
                         ignore_index=True)
    keys = ["window_start", "src_ip"]
    out = exploded.groupby(keys, sort=True).agg(
        total_bytes=("bytes_sent", "sum"), unique_ports=("dst_port", "nunique"), syn=("syn_flag", "sum"),
        ack=("ack_flag", "sum"), event_count=("timestamp", "size"), max_event_ts=("timestamp", "max"),
        **({"attack_events": ("_attack", "sum")} if has_labels else {})).reset_index()
    out["window_end"] = out["window_start"] + F.WINDOW_MS
    out["syn_ack_ratio"] = out["syn"] / (out["ack"] + 1)
    out["packet_rate"] = out["event_count"] / F.WINDOW_S
    n = out["event_count"].astype("float64")                       # C-02 0.2.0 ratio features (D-14)
    out["bytes_per_flow"] = out["total_bytes"] / n
    out["port_ratio"] = out["unique_ports"] / n
    out["syn_share"] = out["syn"] / n
    out["label_type"] = np.nan
    if has_labels:
        attacks = exploded[exploded["label"] != BENIGN_LABEL]
        if len(attacks):
            counts = attacks.groupby(keys + ["label"]).size().reset_index(name="n")
            top = (counts.sort_values(keys + ["n", "label"], ascending=[True, True, False, True])
                   .drop_duplicates(keys)[keys + ["label"]].rename(columns={"label": "label_type"}))
            out = out.drop(columns=["label_type"]).merge(top, on=keys, how="left")
    out["label_attack"] = out["label_type"].notna()
    out["label_type"] = out["label_type"].fillna(BENIGN_LABEL)
    out = out.sort_values(keys).reset_index(drop=True)
    for c in _INT:
        out[c] = out[c].astype("int64")
    for c in _FLOAT:
        out[c] = out[c].astype("float64")
    if extended:
        out = out.rename(columns={"syn": "syn_sum", "ack": "ack_sum"})
        if "attack_events" not in out:
            out["attack_events"] = 0
        return out[list(F.GOLDEN_COLUMNS) + list(EXTENDED_COLUMNS)].astype({c: "int64" for c in EXTENDED_COLUMNS})
    return out[list(F.GOLDEN_COLUMNS)]


def to_records(df: pd.DataFrame) -> List[dict]:
    """DataFrame → list of dicts with plain Python types (for `ids_contracts.features` validators / rows_equal)."""
    out = []
    for row in df.itertuples(index=False):
        r = row._asdict()
        out.append({c: (int(r[c]) if c in _INT else float(r[c]) if c in _FLOAT else bool(r[c]) if c == "label_attack"
                        else str(r[c])) for c in F.GOLDEN_COLUMNS})
    return out


def replay_timestamps(n: int, t0_ms: int, rate: int) -> np.ndarray:
    """ADR-011 / C-02 §4: t0 + floor(i·1000/R) ms for i = 0..n-1."""
    return t0_ms + (np.arange(n, dtype="int64") * 1000) // rate


def features_from_replay(replay: pd.DataFrame, rate: int = R_REF, t0_ms: Optional[int] = None,
                         extended: bool = False) -> pd.DataFrame:
    """Stamp C-01 replay rows (in day order, then row_idx order) at the constant replay rate, then build C-02 features."""
    df = replay
    if {"day", "row_idx"} <= set(df.columns):
        order = df["day"].astype(str).map({d: i for i, d in enumerate(REPLAY_DAYS)})
        df = df.assign(_o=order).sort_values(["_o", "row_idx"]).drop(columns="_o")
    df = df.reset_index(drop=True).assign(timestamp=replay_timestamps(len(df), DEFAULT_T0_MS if t0_ms is None else t0_ms, rate))
    return build_features(df, extended=extended)
