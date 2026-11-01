"""Dashboard view model (M4-T120): everything the page shows, computed without Streamlit or Cassandra.

FR-020 headline numbers, FR-021 banner, FR-022 chart rows, FR-023 top IPs, FR-026 anchor, FR-027 empty states,
FR-030 eval-only columns are never read.
"""
from __future__ import annotations

import datetime as dt
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ids_contracts import store as S

from ids_monitor.view import Drift, FlaggedIp, drift_summary, top_flagged

KPI_BATCHES = 10                      # medians over the last 10 qualifying batches (partial/idle batches mislead)
FINISHED_AFTER_MS = 30_000            # newest batch older than this → the run is over; anchor at its end
TOP_N = 10


@dataclass(frozen=True)
class Kpis:
    throughput_evs: Optional[float]
    latency_p95_ms: Optional[float]
    anomaly_rate: Optional[float]     # over the whole span
    windows: int


@dataclass(frozen=True)
class Banner:
    level: str                        # "critical" | "ok"
    icon: str
    text: str


@dataclass(frozen=True)
class View:
    run_id: Optional[str]
    anchor_ms: int
    anchor_mode: str                  # "now" | "run_end"
    span_s: int
    kpis: Kpis
    drift: Drift                      # last DRIFT_WINDOW_S before the anchor (ADR-013)
    banner: Banner
    throughput: List[Dict[str, Any]]  # long form: batch_ts, series (input|processed), rows_per_s
    anomaly_rate: List[Dict[str, Any]]  # window_end, rate, anomalous, total
    latency: List[Dict[str, Any]]     # long form: batch_ts, series (p50|p95), ms
    top: List[FlaggedIp]
    invalid: int = 0
    caption: str = ""
    has_windows: bool = field(init=False)
    has_metrics: bool = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "has_windows", bool(self.anomaly_rate))
        object.__setattr__(self, "has_metrics", bool(self.throughput))


def fmt(value: Optional[float], spec: str = ",.0f") -> str:
    return "—" if value is None else format(value, spec)


def utc(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def choose_anchor(metrics: Sequence[Mapping], now_ms: int, force_now: bool = False) -> Tuple[int, str]:
    """(anchor_ms, mode). A run whose newest batch is > 30 s old is shown as of that batch (FR-026)."""
    if force_now or not metrics:
        return now_ms, "now"
    latest = max(m["batch_ts"] for m in metrics)
    return (latest, "run_end") if now_ms - latest > FINISHED_AFTER_MS else (now_ms, "now")


def _median(values: List[float]) -> Optional[float]:
    return float(statistics.median(values)) if values else None


def build_view(windows: Sequence[Mapping], metrics: Sequence[Mapping], anchor_ms: int, anchor_mode: str,
               span_s: int, run_id: Optional[str], invalid: int = 0) -> View:
    start = anchor_ms - span_s * 1000
    ws = [w for w in windows if start <= w["window_end"] <= anchor_ms]
    ms = sorted((m for m in metrics if start <= m["batch_ts"] <= anchor_ms), key=lambda m: m["batch_ts"])

    newest = ms[::-1]
    thr = [m["input_rows_per_sec"] for m in newest if m["input_rows"] > 0][:KPI_BATCHES]
    lat = [m["latency_p95_ms"] for m in newest if m["windows_written"] > 0 and m["latency_p95_ms"] is not None]
    span_drift = drift_summary(ws)
    kpis = Kpis(_median(thr), _median(lat[:KPI_BATCHES]), span_drift.rate if span_drift.total else None, len(ws))

    drift_start = anchor_ms - S.DRIFT_WINDOW_S * 1000
    drift = drift_summary(w for w in ws if w["window_end"] >= drift_start)
    if drift.alert:
        banner = Banner("critical", "🚨", f"Drift alert: anomaly rate {drift.rate * 100:.1f} % > "
                                         f"{S.DRIFT_THRESHOLD * 100:.0f} % — retraining recommended")
    elif drift.total:
        banner = Banner("ok", "✅", f"No drift: anomaly rate {drift.rate * 100:.1f} % ≤ "
                                   f"{S.DRIFT_THRESHOLD * 100:.0f} % over the last {S.DRIFT_WINDOW_S} s")
    else:
        banner = Banner("ok", "✅", f"No drift: no windows in the last {S.DRIFT_WINDOW_S} s")

    per_end: Dict[int, List[int]] = {}
    for w in ws:
        a = per_end.setdefault(w["window_end"], [0, 0])
        a[0] += bool(w["is_anomaly"])
        a[1] += 1
    rate_rows = [{"window_end": e, "rate": a / t, "anomalous": a, "total": t} for e, (a, t) in sorted(per_end.items())]

    throughput = [{"batch_ts": m["batch_ts"], "series": s, "rows_per_s": float(m[col])}
                  for m in ms for s, col in (("input", "input_rows_per_sec"), ("processed", "processed_rows_per_sec"))]
    latency = [{"batch_ts": m["batch_ts"], "series": s, "ms": float(m[col])}
               for m in ms if m["latency_p95_ms"] is not None
               for s, col in (("p50", "latency_p50_ms"), ("p95", "latency_p95_ms"))]

    where = "live" if anchor_mode == "now" else "as of run end"
    caption = (f"Run {run_id or '—'} · {where} · {utc(anchor_ms)} · span {span_s} s"
               + (f" · {invalid} invalid rows skipped" if invalid else ""))
    return View(run_id, anchor_ms, anchor_mode, span_s, kpis, drift, banner, throughput, rate_rows, latency,
                top_flagged(ws, TOP_N), invalid, caption)
