"""Dashboard presentation (M4-F02 polish): theme CSS and HTML for the header, drift strip and KPI tiles.

Pure string builders, no Streamlit calls, so they are unit-tested. Rules (dataviz method):
- status colours (good / warning / critical) only on status elements, always with an icon and a text label;
- text wears text tokens, never a series colour; numbers use tabular figures;
- sparklines use series slot 1 (no axis, decoration of the number next to it, the chart below carries the detail).
Every builder returns one line of HTML: Streamlit's Markdown would turn blank or indented lines into code blocks.
"""
from __future__ import annotations

import datetime as dt
import html
from typing import Optional, Sequence

from ids_contracts import store as S

from ids_monitor.dashboard_model import (View, anomaly_status, fmt, latency_status)

# Dark theme tokens (match .streamlit/config.toml). Series colours: dark steps of the validated palette.
BG, PANEL, BORDER = "#0b0e14", "#121722", "#1f2633"
TEXT, TEXT_2, MUTED = "#e6e9ef", "#9aa3b2", "#6b7385"
SERIES_1 = "#3987e5"
STATUS = {"good": "#2fb344", "warning": "#f0b429", "critical": "#e5484d", "neutral": MUTED}
STATUS_LABEL = {"good": ("●", "On target"), "warning": ("▲", "Near limit"), "critical": ("✕", "Over limit"),
                "neutral": ("", "")}

CSS = f"""
<style>
:root {{ --bg:{BG}; --panel:{PANEL}; --border:{BORDER}; --text:{TEXT}; --text2:{TEXT_2}; --muted:{MUTED};
        --good:{STATUS['good']}; --warn:{STATUS['warning']}; --crit:{STATUS['critical']}; }}
html, body, [class*="css"] {{ font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }}
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ visibility: hidden; height: 0; }}
header[data-testid="stHeader"] {{ background: transparent; height: 0; }}
/* live refresh: no fade-out of the previous frame */
.stale-element, [data-stale="true"] {{ opacity: 1 !important; transition: none !important; }}
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"] .ids-card-title) {{
  background: var(--panel); border-color: var(--border) !important; border-radius: 12px; }}
[data-testid="stSidebar"] {{ background: #0e121b; border-right: 1px solid var(--border); }}
[data-testid="stTabs"] button p {{ font-size: 0.8rem; color: var(--text2); }}

.ids-header {{ display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap;
  padding: 14px 18px; background: var(--panel); border:1px solid var(--border); border-radius: 12px; margin-bottom: 12px; }}
.ids-brand {{ display:flex; align-items:center; gap:12px; }}
.ids-brand svg {{ flex: none; }}
.ids-title {{ font-size: 1.15rem; font-weight: 650; color: var(--text); letter-spacing: .2px; }}
.ids-sub {{ font-size: .8rem; color: var(--text2); }}
.ids-meta {{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; font-size:.8rem; color: var(--text2); }}
.ids-pill {{ border:1px solid var(--border); border-radius: 999px; padding: 3px 10px; background: var(--bg); }}
.ids-pill b {{ color: var(--text); font-weight: 600; font-family: ui-monospace, "SF Mono", Menlo, monospace; }}
.ids-badge {{ display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:3px 10px;
  font-weight:700; font-size:.72rem; letter-spacing:.8px; }}
.ids-badge.live {{ color: var(--good); background: rgba(47,179,68,.12); border:1px solid rgba(47,179,68,.35); }}
.ids-badge.ended {{ color: var(--text2); background: rgba(154,163,178,.10); border:1px solid var(--border); }}
.ids-dot {{ width:8px; height:8px; border-radius:50%; background: currentColor; }}
.ids-badge.live .ids-dot {{ animation: ids-pulse 1.6s ease-in-out infinite; }}
@keyframes ids-pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.25; }} }}
.ids-num {{ font-variant-numeric: tabular-nums; }}

.ids-drift {{ display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding: 12px 18px; border-radius: 12px;
  margin-bottom: 12px; border:1px solid var(--border); background: var(--panel); border-left: 4px solid var(--good); }}
.ids-drift.critical {{ border-left-color: var(--crit); background: linear-gradient(90deg, rgba(229,72,77,.14), var(--panel) 55%); }}
.ids-drift .d-icon {{ font-size: 1.3rem; }}
.ids-drift .d-text {{ flex: 1 1 320px; min-width: 0; }}
.ids-drift .d-title {{ font-weight: 650; color: var(--text); font-size: .95rem; }}
.ids-drift .d-sub {{ color: var(--text2); font-size: .8rem; margin-top: 2px; }}
.ids-gauge {{ flex: 0 1 300px; min-width: 200px; }}
.ids-gauge .g-track {{ position:relative; height: 8px; border-radius: 999px; background: var(--border); }}
.ids-gauge .g-fill {{ position:absolute; left:0; top:0; bottom:0; border-radius:999px; }}
.ids-gauge .g-mark {{ position:absolute; top:-4px; bottom:-4px; width:2px; background: var(--text); border-radius: 1px; }}
.ids-gauge .g-scale {{ display:flex; justify-content:space-between; font-size:.7rem; color: var(--muted); margin-top: 5px; }}
.ids-drift .d-rate {{ font-size: 1.5rem; font-weight: 700; color: var(--text); min-width: 90px; text-align:right; }}

.ids-tiles {{ display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }}
@media (max-width: 1100px) {{ .ids-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 560px) {{ .ids-tiles {{ grid-template-columns: 1fr; }} }}
.ids-tile {{ position:relative; overflow:hidden; background: var(--panel); border:1px solid var(--border);
  border-radius: 12px; padding: 14px 16px 10px; border-top: 3px solid var(--border); }}
.ids-tile.good {{ border-top-color: var(--good); }} .ids-tile.warning {{ border-top-color: var(--warn); }}
.ids-tile.critical {{ border-top-color: var(--crit); }}
.ids-tile .t-label {{ font-size:.78rem; color: var(--text2); text-transform: uppercase; letter-spacing: .7px; font-weight: 600; }}
.ids-tile .t-value {{ font-size: 2rem; font-weight: 700; color: var(--text); line-height: 1.15; margin-top: 6px; }}
.ids-tile .t-unit {{ font-size: .9rem; font-weight: 500; color: var(--text2); margin-left: 6px; }}
.ids-tile .t-foot {{ display:flex; gap: 10px; flex-wrap: wrap; align-items:center; font-size:.75rem; color: var(--text2);
  margin-top: 4px; min-height: 1.2em; }}
.ids-tile .t-status {{ font-weight: 650; }}
.ids-tile .t-spark {{ display:block; width:100%; height: 34px; margin-top: 6px; }}

.ids-card-title {{ font-size: .95rem; font-weight: 650; color: var(--text); }}
.ids-card-sub {{ font-size: .75rem; color: var(--text2); margin-top: 1px; }}
.ids-empty {{ color: var(--text2); font-size: .85rem; padding: 28px 0; text-align: center;
  border: 1px dashed var(--border); border-radius: 10px; margin: 8px 0; }}
</style>
"""

SHIELD = (f'<svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-hidden="true">'
          f'<path d="M12 2.5 4 5.5v6c0 4.6 3.3 8.7 8 10 4.7-1.3 8-5.4 8-10v-6l-8-3Z" fill="{SERIES_1}" fill-opacity=".18" '
          f'stroke="{SERIES_1}" stroke-width="1.6" stroke-linejoin="round"/>'
          f'<path d="m8.5 12 2.4 2.4 4.6-4.8" stroke="{TEXT}" stroke-width="1.8" stroke-linecap="round" '
          f'stroke-linejoin="round"/></svg>')


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def hms(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000).astimezone().strftime("%H:%M:%S")


def header_html(v: View) -> str:
    live = v.anchor_mode == "now"
    badge = (f'<span class="ids-badge live" role="status"><span class="ids-dot"></span>LIVE</span>' if live else
             f'<span class="ids-badge ended" role="status"><span class="ids-dot"></span>ENDED</span>')
    tz_name = dt.datetime.now().astimezone().tzname() or "local"
    when = f"Updated {hms(v.anchor_ms)} {tz_name}" if live else f"As of run end · {hms(v.anchor_ms)} {tz_name}"
    invalid = f'<span class="ids-pill">{v.invalid:,} invalid rows skipped</span>' if v.invalid else ""
    return ('<div class="ids-header"><div class="ids-brand">' + SHIELD +
            '<div><div class="ids-title">IDS Live Monitor</div>'
            '<div class="ids-sub">Streaming intrusion detection · anomaly scores per source IP and 30 s window</div>'
            '</div></div><div class="ids-meta">'
            f'<span class="ids-pill">Run <b>{_e(v.run_id or "—")}</b></span>{badge}'
            f'<span class="ids-pill">Span <b>{v.span_s} s</b></span>{invalid}'
            f'<span class="ids-num">{_e(when)}</span></div></div>')


def drift_html(v: View) -> str:
    d, b = v.drift, v.banner
    level = "critical" if b.level == "critical" else "good"
    scale_max = max(2 * S.DRIFT_THRESHOLD, d.rate)
    fill = 100 * d.rate / scale_max if d.total else 0
    mark = 100 * S.DRIFT_THRESHOLD / scale_max
    sub = (f"{d.anomalous:,} of {d.total:,} windows anomalous in the last {S.DRIFT_WINDOW_S} s · "
           f"threshold {S.DRIFT_THRESHOLD:.0%} (ADR-013)" if d.total else
           f"No windows in the last {S.DRIFT_WINDOW_S} s · threshold {S.DRIFT_THRESHOLD:.0%} (ADR-013)")
    rate = f"{d.rate * 100:.1f} %" if d.total else "—"
    role = "alert" if level == "critical" else "status"
    return (f'<div class="ids-drift {level}" role="{role}"><span class="d-icon" aria-hidden="true">{_e(b.icon)}</span>'
            f'<div class="d-text"><div class="d-title">{_e(b.text)}</div><div class="d-sub">{_e(sub)}</div></div>'
            f'<div class="ids-gauge" aria-hidden="true"><div class="g-track">'
            f'<div class="g-fill" style="width:{fill:.1f}%;background:{STATUS[level]}"></div>'
            f'<div class="g-mark" style="left:calc({mark:.1f}% - 1px)" title="drift threshold"></div></div>'
            f'<div class="g-scale"><span>0 %</span><span>threshold {S.DRIFT_THRESHOLD:.0%}</span>'
            f'<span>{scale_max:.0%}</span></div></div>'
            f'<div class="d-rate ids-num">{rate}</div></div>')


def sparkline_svg(values: Sequence[float], color: str = SERIES_1) -> str:
    """Line + soft area for the last values (oldest first). Empty string for fewer than 2 points."""
    vals = [float(x) for x in values if x is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(0.0, min(vals)), max(vals)                     # zero baseline: no exaggerated wiggles
    span = (hi - lo) or 1.0
    n = len(vals) - 1
    pts = [(100 * i / n, 30 - 26 * (x - lo) / span) for i, x in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,32 {line} 100,32"
    return (f'<svg class="t-spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">'
            f'<polygon points="{area}" fill="{color}" fill-opacity=".12"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2" '
            f'vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>')


def delta_text(now: Optional[float], prev: Optional[float], what: str) -> str:
    """'▲ 2.1 % vs previous 10 batches'. Text ink only; the direction is stated, not colour-coded."""
    if now is None or prev is None or prev == 0:
        return ""
    pct = 100 * (now - prev) / prev
    arrow = "▲" if pct > 0.05 else "▼" if pct < -0.05 else "■"
    return f"{arrow} {abs(pct):.1f} % vs {what}"


def tile_html(label: str, value: str, unit: str = "", status: str = "neutral", foot: str = "",
              spark: str = "") -> str:
    icon, text = STATUS_LABEL[status]
    badge = (f'<span class="t-status" style="color:{STATUS[status]}">{icon} {text}</span>' if text else "")
    unit_html = f'<span class="t-unit">{_e(unit)}</span>' if unit and value != "—" else ""
    foot_html = f"<span>{_e(foot)}</span>" if foot else ""
    return (f'<div class="ids-tile {status}"><div class="t-label">{_e(label)}</div>'
            f'<div class="t-value ids-num">{_e(value)}{unit_html}</div>'
            f'<div class="t-foot">{badge}{foot_html}</div>{spark}</div>')


def tiles_html(v: View) -> str:
    k = v.kpis
    inp = [r["rows_per_s"] for r in v.throughput if r["series"] == "input"][-40:]
    p95 = [r["ms"] for r in v.latency if r["series"] == "p95"][-40:]
    rate = [r["rate"] for r in v.anomaly_rate][-40:]
    lat_s, an_s = latency_status(k.latency_p95_ms), anomaly_status(k.anomaly_rate)
    lat_delta = delta_text(k.latency_p95_ms, k.latency_prev_ms, "prev 10")
    tiles = [
        tile_html("Input throughput", fmt(k.throughput_evs), "ev/s", "neutral",
                  delta_text(k.throughput_evs, k.throughput_prev, "previous 10 batches") or "median of last 10 batches",
                  sparkline_svg(inp)),
        tile_html("p95 latency", fmt(k.latency_p95_ms), "ms", lat_s,
                  "target < 500 ms" + (f" · {lat_delta}" if lat_delta else ""),
                  sparkline_svg(p95)),
        tile_html("Anomaly rate", "—" if k.anomaly_rate is None else f"{k.anomaly_rate * 100:.1f}", "%", an_s,
                  f"over {v.span_s} s · drift above {S.DRIFT_THRESHOLD:.0%}", sparkline_svg(rate)),
        tile_html("Windows scored", f"{k.windows:,}", "", "neutral",
                  f"{k.ips:,} source IPs · {k.flagged_ips:,} flagged"),
    ]
    return '<div class="ids-tiles">' + "".join(tiles) + "</div>"


def card_title(title: str, sub: str = "") -> str:
    return (f'<div class="ids-card-title">{_e(title)}</div>' +
            (f'<div class="ids-card-sub">{_e(sub)}</div>' if sub else ""))


def empty_html(text: str) -> str:
    return f'<div class="ids-empty">Waiting for data: {_e(text)}</div>'
