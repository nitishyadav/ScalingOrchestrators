"""Live IDS dashboard (M4-T122, M4-F02). Launch: `make run` (http://localhost:8501, C-06 service `dashboard`).

Streamlit layer only: controls, layout and a 3 s auto-refreshing fragment. All numbers come from
`dashboard_model.build_view`; all charts from `charts`; all data from M4-F01 `Store` (C-04, C-05).
"""
from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from ids_contracts.config import load_runtime_config

from ids_monitor import charts, db
from ids_monitor.dashboard_model import View, build_view, choose_anchor, fmt, utc
from ids_monitor.store import Store, current_ms

REFRESH_S = 3                         # FR-024 / F4: visible ≤ 5 s after the write
AUTO = "Latest run (auto)"
SPAN_MIN, SPAN_MAX, SPAN_DEFAULT = 60, 900, 300


@st.cache_resource(show_spinner=False)
def _cached_store() -> Store:
    cfg = load_runtime_config()
    _, session = db.connect(cfg)                              # failures are not cached: the next refresh retries
    return Store(session, cfg.cassandra_keyspace)


def open_store() -> Store:
    return _cached_store()


def run_ids(store: Store) -> List[str]:
    seen: List[str] = []
    for r in store.latest_runs(50):                           # newest first; a restarted run appears once
        if r["run_id"] not in seen:
            seen.append(r["run_id"])
    return seen


def load_view(store: Store, run_choice: str, span_s: int, force_now: bool) -> View:
    ids = run_ids(store)
    run_id = (ids[0] if ids else None) if run_choice == AUTO else run_choice
    metrics = store.latest_metrics(run_id, limit=min(2_000, span_s * 2 + 20)) if run_id else []
    anchor, mode = choose_anchor(metrics, current_ms(), force_now)
    res = store.read_windows(anchor - span_s * 1000, anchor, run_id=run_id)
    return build_view(res.rows, metrics, anchor, mode, span_s, run_id, res.invalid)


# ---- rendering -----------------------------------------------------------------------------------
def _chart(title: str, has_data: bool, chart_fn, rows, empty: str, table: pd.DataFrame) -> None:
    st.subheader(title)
    if not has_data:
        st.info(f"Waiting for data: {empty}")
        return
    st.altair_chart(chart_fn(rows), use_container_width=True, theme="streamlit")
    with st.expander("Data table"):
        st.dataframe(table, hide_index=True, use_container_width=True)


def _times(rows, key):
    df = pd.DataFrame(rows)
    if not df.empty:
        df[key] = df[key].map(utc)
    return df


def render(v: View) -> None:
    st.caption(v.caption)
    if v.banner.level == "critical":
        st.error(v.banner.text, icon=v.banner.icon)
    else:
        st.success(v.banner.text, icon=v.banner.icon)
    if not v.has_windows and not v.has_metrics:
        st.info("Waiting for data: nothing written in this span yet. Start the stream job, or `make mock` for synthetic data.")

    k = v.kpis
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Input throughput (ev/s)", fmt(k.throughput_evs),
              help="Median input rows/s over the last 10 batches with input (C-05)")
    c2.metric("p95 latency (ms, target < 500)", fmt(k.latency_p95_ms),
              help="Median per-batch p95 of detected_at − max_event_ts over the last 10 batches that wrote rows (D-01)")
    c3.metric("Anomaly rate (span)", "—" if k.anomaly_rate is None else f"{k.anomaly_rate * 100:.1f} %",
              help="Anomalous windows / all windows in the span. The banner uses the last 300 s (ADR-013)")
    c4.metric("Windows (span)", f"{k.windows:,}")

    left, right = st.columns(2)
    with left:
        _chart("Throughput", v.has_metrics, charts.throughput_chart, v.throughput, "no pipeline metrics in this span.",
               _times(v.throughput, "batch_ts"))
    with right:
        _chart("Latency", bool(v.latency), charts.latency_chart, v.latency, "no batch has written rows in this span.",
               _times(v.latency, "batch_ts"))
    _chart("Anomaly rate per 10 s window", v.has_windows, charts.anomaly_rate_chart, v.anomaly_rate,
           "no windows in this span.", _times(v.anomaly_rate, "window_end"))

    st.subheader("Top flagged source IPs")
    if v.top:
        st.dataframe(pd.DataFrame([{"src_ip": t.src_ip, "anomalous windows": t.windows, "max score": t.max_score,
                                    "last seen (UTC)": utc(t.last_seen), "rules": ", ".join(t.rule_ids) or "—"}
                                   for t in v.top]), hide_index=True, use_container_width=True)
    else:
        st.info("Waiting for data: no flagged IPs in this span.")


@st.fragment(run_every=REFRESH_S)
def live(run_choice: str, span_s: int, force_now: bool) -> None:
    try:
        view = load_view(open_store(), run_choice, span_s, force_now)
    except db.StoreUnavailable as exc:
        st.error(f"{exc}. Retrying every {REFRESH_S} s.", icon="⚠️")
        return
    except Exception as exc:                                  # noqa: BLE001 - keep the page alive and retrying
        st.error(f"Cassandra read failed ({type(exc).__name__}: {exc}). Retrying every {REFRESH_S} s.", icon="⚠️")
        return
    render(view)


def main() -> None:
    st.set_page_config(page_title="IDS live monitor", page_icon="🛡️", layout="wide")
    st.title("IDS live monitor")
    try:
        options = [AUTO] + run_ids(open_store())
    except Exception:                                         # noqa: BLE001 - the live area reports the error
        options = [AUTO]
    with st.sidebar:
        st.header("View")
        run_choice = st.selectbox("Run", options, key="run",
                                  help="Newest first. 'Latest' follows new runs automatically")
        span_s = st.slider("Span (s)", SPAN_MIN, SPAN_MAX, SPAN_DEFAULT, step=30, key="span")
        force_now = st.toggle("Anchor at now", value=False, key="force_now",
                              help="A finished run is shown as of its last batch unless this is on")
        st.caption(f"Refreshes every {REFRESH_S} s · C-04 / C-05 via M4-F01")
    live(run_choice, span_s, force_now)
