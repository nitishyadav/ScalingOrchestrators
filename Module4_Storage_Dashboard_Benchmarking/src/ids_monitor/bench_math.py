"""Benchmark maths (M4-T221, FR-043..048, M4-ADR-002). Pure functions over C-05 / C-04 dict rows, epoch ms.

A C-05 batch at `batch_ts` covers the interval (previous batch, batch_ts], so every time range here is half-open (start, end].
"""
from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ids_contracts import store as S
from ids_contracts.metrics import percentile

BOUND_RATIO = 0.95                # sustained ≥ 95 % of the offered rate → kept up (producer-bound / keeping up)
SAMPLE_S = 30                     # proposal: sample every 30 s
DRIFT_SAMPLE_S = 30
RECOVERY_BATCHES = 3


def _sorted(metrics: Iterable[Mapping]) -> List[Mapping]:
    return sorted(metrics, key=lambda m: m["batch_ts"])


def _median(values: List[float]) -> Optional[float]:
    return float(statistics.median(values)) if values else None


def _lat(batches: Iterable[Mapping], col: str = "latency_p95_ms") -> List[float]:
    return [float(b[col]) for b in batches if b["windows_written"] > 0 and b[col] is not None]


def steady(metrics: Iterable[Mapping], start_ms: int, end_ms: int) -> List[Mapping]:
    """Batches in (start, end], oldest first."""
    return [m for m in _sorted(metrics) if start_ms < m["batch_ts"] <= end_ms]


def summarize(metrics: Sequence[Mapping], producer_start_ms: int, producer_end_ms: int, warmup_s: int,
              target_rate: int, producer_rate: Optional[float] = None) -> Dict[str, Any]:
    """FR-043/044: sustained throughput, producer-bound flag, backlog, latency (median of per-batch p95 = the P2 figure)."""
    start = producer_start_ms + warmup_s * 1000
    st = steady(metrics, start, producer_end_ms)
    span_s = (producer_end_ms - start) / 1000
    inputs = [m for m in _sorted(metrics) if m["input_rows"] > 0]
    out: Dict[str, Any] = {
        "batches": len(metrics), "steady_batches": len(st), "steady_span_s": span_s, "target_rate": target_rate,
        "producer_rate": producer_rate,
        "backlog_s": max(0.0, (inputs[-1]["batch_ts"] - producer_end_ms) / 1000) if inputs else None,
    }
    if not st or span_s <= 0:
        return {**out, "status": "failed", "reason": "no batches in steady state", "sustained_evs": None,
                "producer_bound": None, "keeping_up": None, "p95_ms": None, "p95_tail_ms": None, "p50_ms": None,
                "spark_processed_median": None, "batch_ms_median": None}
    sustained = round(sum(m["input_rows"] for m in st) / span_s, 1)
    p95s = _lat(st)
    return {**out, "status": "ok", "reason": "",
            "sustained_evs": sustained,
            "producer_bound": None if producer_rate is None else sustained >= BOUND_RATIO * producer_rate,
            "keeping_up": sustained >= BOUND_RATIO * target_rate,
            "p95_ms": _median(p95s),
            "p95_tail_ms": percentile(p95s, 95),
            "p50_ms": _median(_lat(st, "latency_p50_ms")),
            "spark_processed_median": _median([float(m["processed_rows_per_sec"]) for m in st if m["input_rows"] > 0]),
            "batch_ms_median": _median([float(m["batch_duration_ms"]) for m in st])}


def samples(metrics: Sequence[Mapping], start_ms: int, end_ms: int, bin_s: int = SAMPLE_S) -> List[Dict[str, Any]]:
    """FR-045: per (t, t + 30 s] bin from the producer start: ev/s, median and max per-batch p95, batches."""
    rows, t = [], 0
    ordered = _sorted(metrics)
    while start_ms + t * 1000 < end_ms:
        lo, hi = start_ms + t * 1000, min(start_ms + (t + bin_s) * 1000, end_ms)
        b = [m for m in ordered if lo < m["batch_ts"] <= hi]
        p95s = _lat(b)
        rows.append({"t_s": t, "evs": round(sum(m["input_rows"] for m in b) / ((hi - lo) / 1000), 1), "batches": len(b),
                     "p95_median_ms": _median(p95s), "p95_max_ms": max(p95s) if p95s else None})
        t += bin_s
    return rows


def efficiency(levels: Sequence[Tuple[int, Optional[float], Optional[bool]]]) -> List[Dict[str, Any]]:
    """FR-046: (N, sustained throughput, producer_bound) per level; level 1 (the first) is the baseline."""
    n1, t1, bound1 = levels[0]
    out = []
    for n, t, bound in levels:
        if t is None or not t1:
            out.append({"n": n, "throughput": t, "speedup": None, "efficiency": None, "qualifier": "missing"})
            continue
        speedup = round(t / t1, 4)
        qualifier = "inconclusive" if bound1 else ("lower_bound" if bound and n != n1 else "exact")
        out.append({"n": n, "throughput": t, "speedup": speedup, "efficiency": round(speedup / (n / n1), 4),
                    "qualifier": qualifier})
    return out


def detection(windows: Sequence[Mapping]) -> Dict[str, Any]:
    """FR-047 (evaluation only: reads the eval-only labels, ADR-007)."""
    def injected(w):
        return str(w["label_type"] or "").startswith("INJ_")
    inj = [w for w in windows if injected(w)]
    benign = [w for w in windows if not w["label_attack"]]
    cic = [w for w in windows if w["label_attack"] and not injected(w)]
    flagged = sum(bool(w["is_anomaly"]) for w in windows)

    def rate(xs):
        return round(sum(bool(w["is_anomaly"]) for w in xs) / len(xs), 4) if xs else None
    return {"windows": len(windows), "anomalous_share": round(flagged / len(windows), 4) if windows else None,
            "injected_windows": len(inj), "recall_injected": rate(inj),
            "benign_windows": len(benign), "fpr_benign": rate(benign), "cic_attack_windows": len(cic),
            "by_category": by_category(windows)}


DETECTORS = (("rule", "rule_flag"), ("ml", "ml_flag"), ("hybrid", "is_anomaly"))


def category(w: Mapping) -> str:
    """Attack category of a window from its eval-only labels: injected type, a CIC attack type, or 'BENIGN'."""
    if not w["label_attack"]:
        return "BENIGN"
    return str(w["label_type"] or "ATTACK")


def by_category(windows: Sequence[Mapping]) -> List[Dict[str, Any]]:
    """F3 (online): per category, the share of windows each detector flags (= recall for attacks, FPR for BENIGN).
    rule = rule_flag, ml = ml_flag, hybrid = is_anomaly (= ml OR rule, C-04)."""
    groups: Dict[str, List[Mapping]] = {}
    for w in windows:
        groups.setdefault(category(w), []).append(w)
    rows = []
    for cat in sorted(groups, key=lambda c: (c == "BENIGN", c)):
        ws = groups[cat]
        row: Dict[str, Any] = {"category": cat, "windows": len(ws)}
        for name, col in DETECTORS:
            row[f"{name}_flagged"] = sum(bool(w[col]) for w in ws)
            row[name] = round(row[f"{name}_flagged"] / len(ws), 4)
        rows.append(row)
    return rows


def banner(windows: Sequence[Mapping], start_ms: int, end_ms: int, step_s: int = DRIFT_SAMPLE_S,
           window_s: int = S.DRIFT_WINDOW_S) -> Dict[str, Any]:
    """FR-047 / F5: the dashboard's drift rule (ADR-013) evaluated every 30 s over (t − 300 s, t]."""
    shares, first = [], None
    t = start_ms + window_s * 1000
    while t <= end_ms:
        ws = [w for w in windows if t - window_s * 1000 < w["window_end"] <= t]
        a = sum(bool(w["is_anomaly"]) for w in ws)
        share = a / len(ws) if ws else 0.0
        shares.append(share)
        if first is None and S.drift_alert(a, len(ws)):
            first = (t - start_ms) // 1000
        t += step_s * 1000
    above = sum(s > S.DRIFT_THRESHOLD for s in shares)
    return {"samples": len(shares), "max_share": round(max(shares), 4) if shares else None,
            "share_above": round(above / len(shares), 4) if shares else None, "first_alert_s": first}


def recovery(metrics: Sequence[Mapping], restart_ms: int, pre_s: int = 120) -> Dict[str, Any]:
    """FR-048 / P5. recovered_s = restart → the first of 3 consecutive batches with p95 ≤ max(2 × pre, pre + 1 s)."""
    ordered = _sorted(metrics)
    pre = _median(_lat(m for m in ordered if restart_ms - pre_s * 1000 <= m["batch_ts"] < restart_ms))
    inputs = [m["batch_ts"] for m in ordered if m["input_rows"] > 0]
    gaps = [b - a for a, b in zip(inputs, inputs[1:])]
    after = [m for m in ordered if m["batch_ts"] > restart_ms]
    first = next((m["batch_ts"] for m in after if m["input_rows"] > 0), None)
    threshold = None if pre is None else max(2 * pre, pre + 1000)
    recovered = None
    lat_after = [m for m in after if m["windows_written"] > 0 and m["latency_p95_ms"] is not None]
    if threshold is not None:
        for i in range(len(lat_after) - RECOVERY_BATCHES + 1):
            if all(m["latency_p95_ms"] <= threshold for m in lat_after[i:i + RECOVERY_BATCHES]):
                recovered = (lat_after[i]["batch_ts"] - restart_ms) / 1000
                break
    return {"restart_ms": restart_ms, "pre_p95_ms": pre, "threshold_ms": threshold,
            "first_batch_s": None if first is None else (first - restart_ms) / 1000,
            "max_gap_s": max(gaps) / 1000 if gaps else None,
            "recovered_s": recovered, "passed": recovered is not None and recovered < 30}
