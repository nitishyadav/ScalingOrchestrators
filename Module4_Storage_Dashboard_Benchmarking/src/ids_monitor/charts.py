"""Altair chart specs for the dashboard (M4-T121, FR-022).

Visual rules (dataviz method, reference palette; validated light + dark):
- categorical slots in fixed order: blue then orange; the same series always gets the same colour;
- one y-axis per chart (no dual axes); reference lines in muted ink, dashed, directly labelled;
- 2 px lines, bars with rounded data ends and a gap between neighbours; hover tooltips everywhere;
- status colours are reserved for the drift banner, never used in charts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import altair as alt
import pandas as pd

from ids_contracts import store as S

SERIES_LIGHT = ["#2a78d6", "#eb6834"]                        # categorical slots 1, 2 (light surface)
SERIES = ["#3987e5", "#d95926"]                              # same slots, dark steps (the page theme is dark)
MUTED = "#898781"                                            # axis/labels/reference ink (both modes)
GRID, TEXT_2 = "#1f2633", "#9aa3b2"                          # match ui.py tokens
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
P2_TARGET_MS = 500                                           # P2: p95 end-to-end latency < 500 ms
HEIGHT = 240
TIME_AXIS = alt.Axis(format="%H:%M:%S", labelColor=MUTED, title=None, grid=False, tickCount=6,
                     domainColor=GRID, tickColor=GRID)
UTC = alt.Scale(type="utc")                                  # the page states times in UTC; never the viewer's zone


def styled(chart):
    """Dark, recessive chrome: transparent background, faint grid, no view border (rendered with theme=None)."""
    return (chart.configure(background="transparent", font="-apple-system, Inter, Segoe UI, sans-serif")
            .configure_view(stroke=None)
            .configure_axis(gridColor=GRID, gridOpacity=1, domain=False, ticks=False, labelColor=MUTED,
                            titleColor=TEXT_2, titleFontWeight=500, titleFontSize=11, labelFontSize=11, labelPadding=6)
            .configure_legend(labelColor=TEXT_2, labelFontSize=11, symbolStrokeWidth=3, symbolSize=120)
            .configure_text(color=MUTED))


def _time(rows: Sequence[Dict[str, Any]], key: str) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if not df.empty:
        df["time"] = pd.to_datetime(df[key], unit="ms", utc=True)
    return df


def _reference(value: float, label: str) -> alt.LayerChart:
    """Dashed rule + label at the right end, drawn above the data (a halo keeps the label legible over marks)."""
    d = pd.DataFrame([{"ref": value, "label": label}])
    rule = alt.Chart(d).mark_rule(color=MUTED, strokeDash=[5, 4], strokeWidth=1.5).encode(y="ref:Q")
    text = alt.Chart(d).mark_text(color=TEXT_2, align="right", baseline="bottom", dx=-2, dy=-4, fontWeight=600,
                                  stroke="#121722", strokeWidth=4, strokeOpacity=0.9, strokeJoin="round").encode(
        y="ref:Q", x=alt.value("width"), text="label:N")
    text_fill = alt.Chart(d).mark_text(color=TEXT_2, align="right", baseline="bottom", dx=-2, dy=-4,
                                       fontWeight=600).encode(y="ref:Q", x=alt.value("width"), text="label:N")
    return rule + text + text_fill
    return rule + text


def _lines(df: pd.DataFrame, value: str, y_title: str, domain: List[str], y_format: str, tip_format: str):
    color = alt.Color("series:N", title=None, legend=alt.Legend(orient="top", labelColor=MUTED),
                      scale=alt.Scale(domain=domain, range=SERIES[:len(domain)]))
    base = alt.Chart(df).encode(x=alt.X("time:T", axis=TIME_AXIS, scale=UTC),
                                y=alt.Y(f"{value}:Q", title=y_title, axis=alt.Axis(format=y_format, labelColor=MUTED, tickCount=5)),
                                color=color)
    hover = alt.selection_point(fields=["time"], nearest=True, on="pointerover", empty=False, clear="pointerout")
    lines = base.mark_line(strokeWidth=2)
    points = base.mark_point(size=80, filled=True).encode(
        opacity=alt.condition(hover, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("time:T", title="batch (UTC)", format="%H:%M:%S", formatType="utc"), alt.Tooltip("series:N"),
                 alt.Tooltip(f"{value}:Q", title=y_title, format=tip_format)]).add_params(hover)
    crosshair = alt.Chart(df).mark_rule(color=MUTED, strokeWidth=1).encode(x=alt.X("time:T", scale=UTC)).transform_filter(hover)
    return lines + points + crosshair


def throughput_chart(rows: Sequence[Dict[str, Any]]):
    return styled(_lines(_time(rows, "batch_ts"), "rows_per_s", "rows / s", ["input", "processed"], ",.0f",
                         ",.0f").properties(height=HEIGHT))


def latency_chart(rows: Sequence[Dict[str, Any]]):
    lines = _lines(_time(rows, "batch_ts"), "ms", "latency (ms)", ["p50", "p95"], ",.0f", ",.0f")
    return styled((lines + _reference(P2_TARGET_MS, f"P2 target {P2_TARGET_MS} ms")).properties(height=HEIGHT))


def anomaly_rate_chart(rows: Sequence[Dict[str, Any]]):
    df = _time(rows, "window_end")
    if not df.empty:                                         # one bar per 10 s slide ending at window_end, 1 s gap
        df["t0"] = pd.to_datetime(df["window_end"] - S.SLIDE_MS + 1_000, unit="ms", utc=True)
    top = min(1.0, max(2 * S.DRIFT_THRESHOLD, float(df["rate"].max()) if not df.empty else 0.0))  # threshold mid-chart
    bars = alt.Chart(df).mark_bar(color=SERIES[0], opacity=0.75, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("t0:T", axis=TIME_AXIS, scale=UTC), x2="time:T",
        y=alt.Y("rate:Q", title="anomalous windows", axis=alt.Axis(format=".0%", labelColor=MUTED, tickCount=5),
                scale=alt.Scale(domain=[0, top])),
        y2=alt.datum(0),                                     # bars grow from 0 (x/x2 alone leave no baseline)
        tooltip=[alt.Tooltip("time:T", title="window end (UTC)", format="%H:%M:%S", formatType="utc"),
                 alt.Tooltip("rate:Q", title="anomaly rate", format=".1%"),
                 alt.Tooltip("anomalous:Q"), alt.Tooltip("total:Q", title="windows")])
    ref = _reference(S.DRIFT_THRESHOLD, f"drift threshold {S.DRIFT_THRESHOLD:.0%}")
    return styled((bars + ref).properties(height=HEIGHT))
