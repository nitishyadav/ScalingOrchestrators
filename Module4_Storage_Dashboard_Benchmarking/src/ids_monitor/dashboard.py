"""IDS Live Monitor — Streamlit dashboard (M4-F02, REPLICA built by M1; canonical owner Vidhi Kant Gupta).

Run:   streamlit run src/ids_monitor/dashboard.py                    (reads Cassandra, C-04/C-05)
       streamlit run src/ids_monitor/dashboard.py -- --demo          (in-memory synthetic data, no Cassandra)
       streamlit run src/ids_monitor/dashboard.py -- --run-id ID     (pin a run)
Charts follow the dataviz method: stat tiles for headline numbers, thin single-axis lines, reference-palette slots 1–2
(validated light + dark), status banners with icon + label, hover tooltips, the top-10 table as the table view.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

import altair as alt
import pandas as pd
import streamlit as st

from ids_contracts import store as C04
from ids_monitor.view import DemoReader, build_view

# reference palette (dataviz references/palette.md) — categorical slots 1–2, validated light + dark
SERIES = {"light": ("#2a78d6", "#eb6834"), "dark": ("#3987e5", "#d95926")}
MUTED = "#8a8984"
REFRESH_S = 3
P95_TARGET_MS = 500


def parse_args(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--demo-share", type=float, default=0.2)
    p.add_argument("--run-id")
    args, _ = p.parse_known_args(argv)
    return args


ARGS = parse_args(sys.argv[1:])
st.set_page_config(page_title="IDS Live Monitor", page_icon="🛡️", layout="wide")
MODE = "dark" if st.get_option("theme.base") == "dark" else "light"
BLUE, ORANGE = SERIES[MODE]


@st.cache_resource
def get_reader(demo: bool, share: float):
    if demo:
        return DemoReader(share=share)
    from ids_contracts.config import load_runtime_config
    from ids_monitor.store import StoreReader, connect
    return StoreReader(connect(load_runtime_config()))


def _ts(ms_list):
    return pd.to_datetime(pd.Series(ms_list, dtype="int64"), unit="ms", utc=True)


def line_chart(df: pd.DataFrame, y: str, y_title: str, color: str, y_format: str = ",.0f",
               rule_value=None, rule_label: str = "") -> alt.LayerChart:
    """Single-series line with a hover crosshair + tooltip and an optional dashed reference rule."""
    hover = alt.selection_point(nearest=True, on="mouseover", fields=["t"], empty=False)
    base = alt.Chart(df).encode(x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M:%S", grid=False)))
    line = base.mark_line(strokeWidth=2, color=color).encode(
        y=alt.Y(f"{y}:Q", title=y_title, axis=alt.Axis(format=y_format, gridOpacity=0.3)))
    points = base.mark_point(size=80, filled=True, color=color).encode(
        y=f"{y}:Q", opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("t:T", title="Time (UTC)", format="%H:%M:%S"), alt.Tooltip(f"{y}:Q", title=y_title, format=y_format)],
    ).add_params(hover)
    crosshair = base.mark_rule(color=MUTED, strokeWidth=1).encode(
        opacity=alt.condition(hover, alt.value(0.6), alt.value(0)))
    layers = [line, crosshair, points]
    if rule_value is not None:
        ref = pd.DataFrame({"v": [rule_value], "label": [rule_label]})
        layers.append(alt.Chart(ref).mark_rule(color=MUTED, strokeDash=[4, 4], strokeWidth=1).encode(y="v:Q"))
        layers.append(alt.Chart(ref).mark_text(align="left", dx=4, dy=-6, color=MUTED, fontSize=11).encode(
            y="v:Q", x=alt.value(0), text="label:N"))
    return alt.layer(*layers).properties(height=220)


def latency_chart(points) -> alt.LayerChart:
    """p50 and p95 on one ms axis (no dual axis); legend + direct end labels; dashed 500 ms target."""
    df = pd.DataFrame(points)
    df["t"] = _ts(df["batch_ts"])
    long = df.melt(id_vars=["t"], value_vars=["p50", "p95"], var_name="series", value_name="ms")
    scale = alt.Scale(domain=["p50", "p95"], range=[BLUE, ORANGE])
    hover = alt.selection_point(nearest=True, on="mouseover", fields=["t"], empty=False)
    base = alt.Chart(long).encode(x=alt.X("t:T", title=None, axis=alt.Axis(format="%H:%M:%S", grid=False)))
    lines = base.mark_line(strokeWidth=2).encode(
        y=alt.Y("ms:Q", title="Latency (ms)", axis=alt.Axis(gridOpacity=0.3)),
        color=alt.Color("series:N", scale=scale, legend=alt.Legend(orient="top", title=None)))
    points = base.mark_point(size=80, filled=True).encode(
        y="ms:Q", color=alt.Color("series:N", scale=scale, legend=None),
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("t:T", title="Batch (UTC)", format="%H:%M:%S"), alt.Tooltip("series:N", title="Series"),
                 alt.Tooltip("ms:Q", title="Latency (ms)", format=",.0f")]).add_params(hover)
    last = long[long["t"] == long["t"].max()]
    labels = alt.Chart(last).mark_text(align="left", dx=6, fontSize=11).encode(
        x="t:T", y="ms:Q", text="series:N", color=alt.value(MUTED))
    target = pd.DataFrame({"v": [P95_TARGET_MS], "label": [f"{P95_TARGET_MS} ms p95 target"]})
    rule = alt.Chart(target).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(y="v:Q")
    rule_text = alt.Chart(target).mark_text(align="left", dx=4, dy=-6, color=MUTED, fontSize=11).encode(
        y="v:Q", x=alt.value(0), text="label:N")
    return alt.layer(lines, points, labels, rule, rule_text).properties(height=220)


def render(view: dict, source: str) -> None:
    k, d = view["kpis"], view["drift"]
    if not view["has_data"]:
        st.info("Waiting for data: no windows or metrics for this run in the selected span yet.", icon="⏳")
    elif d["alert"]:
        st.error(f"Drift alert: anomaly rate {d['rate']:.1%} > {C04.DRIFT_THRESHOLD:.0%} over the last "
                 f"{view['seconds']} s ({d['anomalous']} of {d['total']} windows). Retraining recommended.", icon="🚨")
    else:
        st.success(f"No drift: anomaly rate {d['rate']:.1%} ≤ {C04.DRIFT_THRESHOLD:.0%} over the last {view['seconds']} s.",
                   icon="✅")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Throughput", "—" if k["throughput"] is None else f"{k['throughput']:,.0f} ev/s", help="Median input rows/s over the last 10 micro-batches that had input (C-05)")
    c2.metric("p95 latency", "—" if k["latency_p95_ms"] is None else f"{k['latency_p95_ms']:,.0f} ms",
              help=f"Median of the per-batch p95 (detected_at − max_event_ts, D-01) over the last 10 batches with rows. Target < {P95_TARGET_MS} ms")
    c3.metric("Anomaly rate", "—" if k["anomaly_rate"] is None else f"{k['anomaly_rate']:.1%}",
              help=f"Anomalous / all windows, last {view['seconds']} s. Drift threshold {C04.DRIFT_THRESHOLD:.0%}")
    c4.metric("Windows scored", f"{k['windows']:,}", help=f"Window rows (C-04) in the last {view['seconds']} s")

    left, right = st.columns(2)
    with left:
        st.markdown("**Throughput** · input events per second, per micro-batch")
        if view["throughput"]:
            df = pd.DataFrame(view["throughput"])
            df["t"] = _ts(df["batch_ts"])
            st.altair_chart(line_chart(df, "rows_per_sec", "Events/s", BLUE), use_container_width=True, theme="streamlit")
        else:
            st.caption("No metrics yet.")
    with right:
        st.markdown("**Anomaly rate** · share of anomalous windows, per 10 s window")
        if view["rate_series"]:
            df = pd.DataFrame(view["rate_series"])
            df["t"] = _ts(df["window_end"])
            st.altair_chart(line_chart(df, "rate", "Anomaly rate", BLUE, y_format=".0%", rule_value=C04.DRIFT_THRESHOLD,
                                       rule_label="15 % drift threshold"), use_container_width=True, theme="streamlit")
        else:
            st.caption("No windows in the selected span.")

    st.markdown("**Latency** · p50 and p95 per micro-batch")
    if view["latency"]:
        st.altair_chart(latency_chart(view["latency"]), use_container_width=True, theme="streamlit")
    else:
        st.caption("No latency samples yet.")

    st.markdown(f"**Top {len(view['top']) or 10} flagged source IPs** · last {view['seconds']} s")
    top = pd.DataFrame([{"Source IP": t["src_ip"], "Anomalous windows": t["anomalous_windows"],
                         "Max score": round(t["max_score"], 3),
                         "Last seen (UTC)": dt.datetime.fromtimestamp(t["last_seen"] / 1000, dt.timezone.utc).strftime("%H:%M:%S"),
                         "Rules fired": t["rule_ids"] or "—"} for t in view["top"]],
                       columns=["Source IP", "Anomalous windows", "Max score", "Last seen (UTC)", "Rules fired"])
    st.dataframe(top, hide_index=True, use_container_width=True)
    as_of = dt.datetime.fromtimestamp(view["as_of_ms"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    mode = "live" if view["live"] else f"finished run, shown as of its last batch ({as_of} UTC)"
    st.caption(f"Run {view['run_id'] or '—'} · {mode} · source: {source} · refreshed every {REFRESH_S} s · "
               f"updated {dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%S')} UTC")


# ---- page ------------------------------------------------------------------------------------
st.title("IDS Live Monitor")
source = "DEMO (synthetic, in-memory)" if ARGS.demo else "Cassandra (C-04 / C-05)"
try:
    reader = get_reader(ARGS.demo, ARGS.demo_share)
except Exception as exc:                      # StoreUnavailable and driver errors
    st.error(f"Cannot reach Cassandra: {exc}. Start the platform (`python -m ids_ingest.platform up`) "
             f"or run with `-- --demo`.", icon="⚠️")
    st.stop()

with st.sidebar:
    st.caption("REPLICA dashboard (M4-F02) built by Aswin S. · canonical owner Vidhi Kant Gupta")
    runs = [r["run_id"] for r in reader.runs(limit=20)]
    options = ([ARGS.run_id] if ARGS.run_id and ARGS.run_id not in runs else []) + runs
    run_id = st.selectbox("Run", options, index=options.index(ARGS.run_id) if ARGS.run_id in options else 0) if options else None
    seconds = st.slider("Time span (s)", 60, 900, C04.DRIFT_WINDOW_S, step=30)
    anchor = {"Auto (live, or the run's end)": "auto", "Now": "now"}[
        st.radio("Time reference", ["Auto (live, or the run's end)", "Now"], index=0,
                 help="A finished run (no batch for 30 s) is shown as of its last batch, so past runs stay viewable.")]


@st.fragment(run_every=REFRESH_S)
def live():
    render(build_view(reader, int(time.time() * 1000), run_id=run_id, seconds=seconds, anchor=anchor), source)


live()
