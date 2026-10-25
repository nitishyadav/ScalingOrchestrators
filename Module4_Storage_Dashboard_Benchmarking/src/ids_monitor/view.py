"""Dashboard view model (M4-F02, REPLICA): everything the page shows, as plain data — no Streamlit, no Cassandra.

`build_view` works with `store.StoreReader` (live) or `DemoReader` (in-memory synthetic, for `--demo`).
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, List, Optional

from ids_contracts import store as S

from . import synthetic as syn
from .store import aggregate_top, drift_summary

DEMO_RUN = "DEMO-synthetic"
TOP_N = 10
STALE_S = 30            # a run whose newest batch is older than this is "finished" (M4-FR-018)
KPI_BATCHES = 10        # headline tiles = median of the last N batches that had data


def _empty(run_id: Optional[str], runs: List[str], now_ms: int, seconds: int) -> dict:
    return {"run_id": run_id, "runs": runs, "now_ms": now_ms, "as_of_ms": now_ms, "live": True, "seconds": seconds,
            "has_data": False,
            "kpis": {"throughput": None, "latency_p95_ms": None, "anomaly_rate": None, "windows": 0, "anomalous": 0},
            "drift": drift_summary([]), "throughput": [], "latency": [], "rate_series": [], "top": []}


def _median(values):
    if not values:
        return None
    v = sorted(values)
    return v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2


def build_view(reader, now_ms: int, run_id: Optional[str] = None, seconds: int = S.DRIFT_WINDOW_S,
               history: int = 60, anchor: str = "auto") -> dict:
    """anchor: "auto" (now for a live run, the last batch for a finished one), "now", or "run_end"."""
    runs = [r["run_id"] for r in reader.runs(limit=20)]
    run_id = run_id or (runs[0] if runs else None)
    if run_id is None:
        return _empty(None, runs, now_ms, seconds)
    metrics = sorted(reader.metrics(run_id, limit=history), key=lambda m: m["batch_ts"])     # oldest → newest
    last_batch = metrics[-1]["batch_ts"] if metrics else None
    live = last_batch is None or now_ms - last_batch <= STALE_S * 1000
    as_of = last_batch if last_batch is not None and (anchor == "run_end" or (anchor == "auto" and not live)) else now_ms
    windows = reader.recent_windows(as_of, seconds, run_id)
    view = _empty(run_id, runs, now_ms, seconds)
    view.update(as_of_ms=as_of, live=live)
    drift = drift_summary(windows)
    with_input = [m for m in metrics if m["input_rows"] > 0]                 # idle batches carry no throughput
    with_latency = [m for m in metrics if m["latency_p95_ms"] is not None]
    per_window = defaultdict(lambda: [0, 0])
    for w in windows:
        per_window[w["window_end"]][0] += w["is_anomaly"]
        per_window[w["window_end"]][1] += 1
    view.update(
        has_data=bool(windows or metrics),
        drift=drift,
        kpis={"throughput": _median([m["input_rows_per_sec"] for m in with_input[-KPI_BATCHES:]]),
              "latency_p95_ms": _median([m["latency_p95_ms"] for m in with_latency[-KPI_BATCHES:]]),
              "anomaly_rate": drift["rate"] if drift["total"] else None,
              "windows": drift["total"], "anomalous": drift["anomalous"]},
        throughput=[{"batch_ts": m["batch_ts"], "rows_per_sec": m["input_rows_per_sec"]} for m in metrics],
        latency=[{"batch_ts": m["batch_ts"], "p50": m["latency_p50_ms"], "p95": m["latency_p95_ms"]}
                 for m in metrics if m["latency_p95_ms"] is not None],
        rate_series=[{"window_end": end, "anomalous": a, "total": t, "rate": a / t}
                     for end, (a, t) in sorted(per_window.items())],
        top=aggregate_top(windows, TOP_N),
    )
    return view


class DemoReader:
    """StoreReader lookalike over synthetic data regenerated relative to 'now' (no Cassandra)."""

    def __init__(self, share: float = 0.2, n_ips: int = 30, seed: int = 42, span_s: int = 900,
                 clock: Callable[[], int] = lambda: int(time.time() * 1000)):
        self.share, self.n_ips, self.seed, self.span_s, self.clock = share, n_ips, seed, span_s, clock

    def _data(self):
        """Synthetic run ending at the demo clock (the "run end"); queries only filter it."""
        return syn.generate(self.clock(), self.span_s, self.n_ips, self.share, DEMO_RUN, self.seed)

    def runs(self, limit: int = 20) -> List[dict]:
        return [self._data()["run"]]

    def recent_windows(self, now_ms: int, seconds: int = S.DRIFT_WINDOW_S, run_id: Optional[str] = None) -> List[dict]:
        if run_id not in (None, DEMO_RUN):
            return []
        start = now_ms - seconds * 1000
        rows = [r for r in self._data()["windows"] if start <= r["window_end"] <= now_ms]
        return sorted(rows, key=lambda r: (-r["window_end"], r["src_ip"]))

    def metrics(self, run_id: str, limit: int = 60) -> List[dict]:
        if run_id != DEMO_RUN:
            return []
        rows = sorted(self._data()["metrics"], key=lambda m: -m["batch_ts"])
        return rows[:limit]
