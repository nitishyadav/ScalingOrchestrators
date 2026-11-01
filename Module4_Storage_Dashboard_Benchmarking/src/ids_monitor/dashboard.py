"""Live IDS dashboard (M4-T122, M4-F02). Launch: `make run` (http://localhost:8501, C-06 service `dashboard`).

Streamlit layer only: controls, layout and a 3 s auto-refreshing fragment. All numbers come from
`dashboard_model.build_view`; all charts from `charts`; all data from M4-F01 `Store` (C-04, C-05).
"""
from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from ids_contracts.config import load_runtime_config

from ids_monitor import charts, db, ui
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
def _html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def _card(title: str, sub: str, has_data: bool, chart_fn, rows, empty: str, table: pd.DataFrame) -> None:
    with st.container(border=True):
        _html(ui.card_title(title, sub))
        if not has_data:
            _html(ui.empty_html(empty))
            return
        chart_tab, data_tab = st.tabs(["Chart", "Data"])                     # FR-028: every chart has a table
        with chart_tab:
            st.altair_chart(chart_fn(rows), use_container_width=True, theme=None)
        with data_tab:
            st.dataframe(table, hide_index=True, use_container_width=True, height=240)


def _times(rows, key):
    df = pd.DataFrame(rows)
    if not df.empty:
        df[key] = df[key].map(utc)
    return df


def _top_table(v: View) -> None:
    with st.container(border=True):
        _html(ui.card_title("Top flagged source IPs",
                            f"Most anomalous windows in the last {v.span_s} s · rules that fired"))
        if not v.top:
            _html(ui.empty_html("no flagged IPs in this span."))
            return
        df = pd.DataFrame([{"src_ip": t.src_ip, "anomalous windows": t.windows, "max score": t.max_score,
                            "last seen": ui.hms(t.last_seen), "rules": ", ".join(t.rule_ids) or "—"} for t in v.top])
        st.dataframe(df, hide_index=True, use_container_width=True, column_config={
            "src_ip": st.column_config.TextColumn("Source IP", width="small"),
            "anomalous windows": st.column_config.ProgressColumn(
                "Windows", format="%d", min_value=0, max_value=int(df["anomalous windows"].max()), width="small",
                help="Anomalous windows in the span"),
            "max score": st.column_config.NumberColumn("Max score", format="%.2f", width="small"),
            "last seen": st.column_config.TextColumn("Last seen", width="small", help="UTC"),
            "rules": st.column_config.TextColumn("Rules fired", width="large"),
        })


def render(v: View) -> None:
    _html(ui.header_html(v))
    _html(ui.drift_html(v))                                                    # FR-021: icon + text + gauge
    if not v.has_windows and not v.has_metrics:
        _html(ui.empty_html("nothing written in this span yet. Start the stream job, or run `make mock`."))
    _html(ui.tiles_html(v))                                                    # FR-020

    left, right = st.columns(2, gap="medium")
    with left:
        _card("Throughput", "Rows/s per micro-batch · arrival rate vs processing rate (gap = headroom)", v.has_metrics,
              charts.throughput_chart, v.throughput, "no pipeline metrics in this span.",
              _times(v.throughput, "batch_ts"))
    with right:
        _card("End-to-end latency", "p50 / p95 per micro-batch · P2 target 500 ms", bool(v.latency),
              charts.latency_chart, v.latency, "no batch has written rows in this span.",
              _times(v.latency, "batch_ts"))
    _card("Anomaly rate per 10 s window", "Share of (source IP, 30 s window) scores flagged · drift line 15 %",
          v.has_windows, charts.anomaly_rate_chart, v.anomaly_rate, "no windows in this span.",
          _times(v.anomaly_rate, "window_end"))
    _top_table(v)                                                              # full width: rule lists need room


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
    st.set_page_config(page_title="IDS Live Monitor", page_icon="🛡️", layout="wide",
                       initial_sidebar_state="collapsed")
    _html("\n".join(line for line in ui.CSS.splitlines() if line.strip()))  # blank lines would end the HTML block
    try:
        options = [AUTO] + run_ids(open_store())
    except Exception:                                         # noqa: BLE001 - the live area reports the error
        options = [AUTO]
    with st.sidebar:
        st.markdown("### View settings")
        run_choice = st.selectbox("Run", options, key="run",
                                  help="Newest first. 'Latest' follows new runs automatically")
        span_s = st.slider("Span (s)", SPAN_MIN, SPAN_MAX, SPAN_DEFAULT, step=30, key="span")
        force_now = st.toggle("Anchor at now", value=False, key="force_now",
                              help="A finished run is shown as of its last batch unless this is on")
        st.divider()
        st.caption(f"Refreshes every {REFRESH_S} s. Data: Cassandra `window_scores` (C-04) and "
                   f"`pipeline_metrics` (C-05) via M4-F01.")
    live(run_choice, span_s, force_now)
