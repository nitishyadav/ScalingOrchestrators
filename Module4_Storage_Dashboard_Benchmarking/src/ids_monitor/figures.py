"""Report figures (M4-T321, M4-FR-064). Light theme for print, matplotlib Agg, deterministic output.

Dataviz rules applied:
- categorical slots in fixed order: blue, orange, aqua (validated all-pairs, light; aqua < 3:1 on white → value labels, table in RESULTS.md);
- one y-axis per panel, never twin axes; targets as muted dashed rules with a direct label;
- legend whenever a panel has ≥ 2 series; text in text ink, never in a series colour;
- lower bounds (a level that kept up with the producer, M4-ADR-002) drawn hollow.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

from ids_contracts import store as S  # noqa: E402

SERIES = ("#2a78d6", "#eb6834", "#1baf7a")     # slots 1–3, light
MUTED, GRID, SURFACE = "#898781", "#e4e3df", "#fcfcfb"
TEXT, TEXT_2 = "#0b0b0b", "#52514e"
P1_TARGET, P2_TARGET_MS = 10_000, 500
LOG_SPAN = 50
GAP_S = 3                                       # recovery plot: break the line where batches stopped
NAMES = ("scaling", "latency", "detection", "f3", "timeline", "recovery")


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "font.family": "DejaVu Sans", "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.labelsize": 10, "axes.labelcolor": TEXT_2, "text.color": TEXT,
        "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": TEXT_2, "ytick.labelcolor": TEXT_2,
        "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
        "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2, "lines.markersize": 7,
        "svg.hashsalt": "ids-m4", "svg.fonttype": "none",
    })


def needs_log(values: Sequence[Optional[float]]) -> bool:
    v = [x for x in values if x is not None and x > 0]
    return bool(v) and max(v) / min(v) > LOG_SPAN


def _ref(ax, y: float, label: str, below: bool = False) -> None:
    ax.axhline(y, color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
    ax.annotate(label, xy=(1, y), xycoords=("axes fraction", "data"), xytext=(-2, -4 if below else 3),
                textcoords="offset points", ha="right", va="top" if below else "bottom", fontsize=9, color=TEXT_2)


def _log_if_needed(ax, values, label: str) -> None:
    if needs_log(values):
        ax.set_yscale("log")
        ax.set_ylabel(f"{label} — log scale")
    else:
        ax.set_ylabel(label)
        top = max((v for v in values if v is not None), default=1)
        ax.set_ylim(0, top * 1.15)


def _thousands(ax) -> None:
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _fig(n: int = 1, w: float = 7.0, h: float = 3.6, **kw) -> Tuple[Figure, List[Any]]:
    style()
    fig, axes = plt.subplots(n if kw.get("sharex") else 1, 1 if kw.get("sharex") else n, figsize=(w, h),
                             constrained_layout=True, **kw)
    return fig, list(axes) if n > 1 else [axes]


# ---- figures -------------------------------------------------------------------------------------
def scaling(panels: Sequence[Tuple[str, str, Sequence[Mapping]]]) -> Figure:
    """panels: (title, x label, M4-F03 efficiency rows). Sustained ev/s vs N with the ideal-linear reference."""
    fig, axes = _fig(len(panels), w=3.9 * len(panels) + 0.4, h=4.0)
    handles = {}
    for ax, (title, xlabel, rows) in zip(axes, panels):
        rows = [r for r in rows if r["throughput"] is not None]
        n = [r["n"] for r in rows]
        t = [r["throughput"] for r in rows]
        base_n, base_t = n[0], t[0]
        top = max(t) * 1.5                                    # the ideal line runs off the top instead of squashing the data
        h_ideal, = ax.plot(n, [base_t * x / base_n for x in n], color=MUTED, linestyle=(0, (4, 3)), linewidth=1.2, zorder=1)
        handles["ideal (linear from the first level)"] = h_ideal
        ax.plot(n, t, color=SERIES[0], zorder=2)
        lower = [r["qualifier"] in ("lower_bound", "inconclusive") for r in rows]
        exact = [(x, y) for x, y, lo in zip(n, t, lower) if not lo]
        bound = [(x, y) for x, y, lo in zip(n, t, lower) if lo]
        if exact:
            h, = ax.plot([e[0] for e in exact], [e[1] for e in exact], linestyle="none", marker="o", markersize=8,
                         color=SERIES[0], zorder=3)
            handles["measured (saturated)"] = h
        if bound:
            h, = ax.plot([b[0] for b in bound], [b[1] for b in bound], linestyle="none", marker="o", markersize=8,
                         color=SERIES[0], markerfacecolor="white", markeredgecolor=SERIES[0], markeredgewidth=2, zorder=4)
            handles["kept up with the producer (lower bound)"] = h
        at4 = next((r for r in rows if r["n"] == 4), None)
        if at4 is not None and at4["efficiency"] is not None:
            ge = "≥ " if at4["qualifier"] == "lower_bound" else ""
            ax.annotate(f"efficiency at 4: {ge}{at4['efficiency']:.2f}\n(speedup {ge}{at4['speedup']:.2f}×)",
                        xy=(4, at4["throughput"]), xytext=(10, -8), textcoords="offset points", ha="left", va="top",
                        fontsize=9, color=TEXT)
        ax.set_xticks(n, [str(x) for x in n])
        ax.set_xlim(0, max(n) * 1.08)
        ax.set_ylim(0, top)
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("sustained throughput (ev/s)")
        _thousands(ax)
    fig.legend(list(handles.values()), list(handles), loc="outside lower center", ncols=len(handles))
    return fig


def latency(runs: Sequence[Mapping]) -> Figure:
    """LAT: median and tail of per-batch p95 per trigger (dot plot), P2 rule."""
    runs = sorted(runs, key=lambda r: -int(r["level"]))
    labels = [f"{int(r['level']) // 1000} s" if int(r["level"]) % 1000 == 0 else f"{r['level']} ms" for r in runs]
    med = [(r.get("summary") or {}).get("p95_ms") for r in runs]
    tail = [(r.get("summary") or {}).get("p95_tail_ms") for r in runs]
    fig, (ax,) = _fig(1, w=6.0, h=3.6)
    x = list(range(len(runs)))
    ax.plot(x, med, color=SERIES[0], marker="o", label="p95 (median of batches)")
    ax.plot(x, tail, color=SERIES[1], marker="D", markersize=6, label="tail (95th pct of batch p95)")
    for xi, v in zip(x, med):
        if v is not None:
            ax.annotate(f"{v:,.0f}", (xi, v), xytext=(6, -3), textcoords="offset points", fontsize=9, color=TEXT)
    _ref(ax, P2_TARGET_MS, f"P2 target {P2_TARGET_MS} ms")
    _log_if_needed(ax, med + tail + [P2_TARGET_MS], "end-to-end latency (ms)")
    if ax.get_yscale() != "log":
        _thousands(ax)
    ax.set_xticks(x, labels)
    ax.set_xlabel("trigger interval")
    ax.set_title("LAT — latency by trigger interval\n8 partitions × 2 executors, 5,000 ev/s", linespacing=1.4)
    ax.margins(x=0.12)
    ax.legend(loc="upper right")
    return fig


def detection(runs: Sequence[Mapping]) -> Figure:
    """E3: anomalous-window share and the drift banner's max 300 s share per attack level, 15 % rule."""
    runs = sorted(runs, key=lambda r: int(r["level"]))
    x = list(range(len(runs)))
    share = [(r.get("detection") or {}).get("anomalous_share") for r in runs]
    banner = [(r.get("banner") or {}).get("max_share") for r in runs]
    fig, (ax,) = _fig(1, w=6.0, h=3.6)
    ax.plot(x, share, color=SERIES[0], marker="o", label="anomalous windows (run)")
    ax.plot(x, banner, color=SERIES[1], marker="D", markersize=6, label="drift banner input (max over 300 s)")
    _ref(ax, S.DRIFT_THRESHOLD, f"drift threshold {S.DRIFT_THRESHOLD:.0%}")
    ax.set_xticks(x, [f"{r['level']} %" for r in runs])
    ax.set_xlabel("injected attack share (mixed)")
    ax.set_ylabel("share of windows")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_title("E3 — detection and drift banner by attack share")
    ax.legend(loc="upper left")
    return fig


CATEGORY_LABELS = {"INJ_DDOS": "DDoS\n(injected)", "INJ_SYNFLOOD": "SYN flood\n(injected)",
                   "INJ_PORTSCAN": "Port scan\n(injected)", "BENIGN": "Benign\n(false positives)"}


def f3(rows: Sequence[Mapping]) -> Figure:
    """F3: per category, the share each detector flags (recall for attacks, FPR for benign). Grouped bars, value labels."""
    cats = [r["category"] for r in rows]
    fig, (ax,) = _fig(1, w=max(6.0, 1.6 * len(cats) + 1), h=3.8)
    width = 0.26
    for i, (name, label) in enumerate((("rule", "rule-only"), ("ml", "ML-only"), ("hybrid", "hybrid (ML or rule)"))):
        xs = [k + (i - 1) * width for k in range(len(cats))]
        vals = [r[name] for r in rows]
        ax.bar(xs, vals, width=width, color=SERIES[i], edgecolor="white", linewidth=1.5, label=label, zorder=2)
        for xv, v in zip(xs, vals):
            ax.annotate(f"{v:.0%}", (xv, v), xytext=(0, 2), textcoords="offset points", ha="center", va="bottom",
                        fontsize=8, color=TEXT)
    ax.set_xticks(range(len(cats)), [CATEGORY_LABELS.get(c, c) for c in cats])
    ax.set_ylim(0, 1.12)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
    ax.set_ylabel("windows flagged")
    ax.set_title("F3 — rule-only vs ML-only vs hybrid, per attack category (E3, online)")
    ax.legend(loc="upper center", ncols=3, bbox_to_anchor=(0.5, -0.22))
    return fig


def timeline(samples: Sequence[Mapping]) -> Figure:
    """P1: throughput and p95 per 30 s sample, 2 stacked panels sharing the time axis."""
    t = [float(r["t_s"]) for r in samples]
    evs = [float(r["evs"]) for r in samples]
    p95 = [float(r["p95_median_ms"]) if r["p95_median_ms"] not in ("", None) else None for r in samples]
    fig, (a1, a2) = _fig(2, w=7.0, h=5.0, sharex=True)
    a1.plot(t, evs, color=SERIES[0], marker="o", markersize=4)
    _ref(a1, P1_TARGET, f"P1 target {P1_TARGET:,} ev/s", below=min(evs) >= P1_TARGET * 0.9)
    a1.set_ylabel("throughput (ev/s)")
    a1.set_ylim(0, max(evs + [P1_TARGET]) * 1.2)
    _thousands(a1)
    a1.set_title("P1 — 16 partitions × 4 executors, 12,000 ev/s offered (30 s samples)")
    a2.plot(t, p95, color=SERIES[0], marker="o", markersize=4)
    _log_if_needed(a2, p95, "p95 latency (ms)")
    if a2.get_yscale() != "log":
        _thousands(a2)
    a2.set_xlabel("time since replay start (s)")
    return fig


def recovery(batches: Sequence[Tuple[float, float]], rec: Mapping[str, Any]) -> Figure:
    """REC: per-batch p95 around the worker restart (t = 0), the recovery threshold and the recovery point."""
    x, y = [], []
    for i, (bx, by) in enumerate(batches):
        if i and bx - batches[i - 1][0] > GAP_S:              # no batches ran in the gap: do not draw a line across it
            x.append(float("nan"))
            y.append(float("nan"))
        x.append(bx)
        y.append(by)
    fig, (ax,) = _fig(1, w=7.0, h=3.6)
    ax.plot(x, y, color=SERIES[0], linewidth=1.2, marker="o", markersize=2.5)
    _log_if_needed(ax, [b[1] for b in batches] + [rec.get("threshold_ms")], "per-batch p95 latency (ms)")
    if ax.get_yscale() != "log":
        _thousands(ax)
    if rec.get("threshold_ms"):
        _ref(ax, rec["threshold_ms"], f"recovery threshold {rec['threshold_ms']:,.0f} ms")
    ax.axvline(0, color=MUTED, linewidth=1.2, zorder=1)
    ax.annotate("worker 1 restarted", xy=(0, 1), xycoords=("data", "axes fraction"), xytext=(-4, -12),
                textcoords="offset points", ha="right", fontsize=9, color=TEXT_2)
    if rec.get("recovered_s") is not None:
        ax.axvline(rec["recovered_s"], color=MUTED, linestyle=(0, (1, 2)), linewidth=1.2, zorder=1)
        ax.annotate(f"recovered after {rec['recovered_s']:.0f} s (P5 < 30 s)", xy=(rec["recovered_s"], 1),
                    xycoords=("data", "axes fraction"), xytext=(4, -26), textcoords="offset points", fontsize=9, color=TEXT_2)
    ax.set_xlabel("seconds from restart")
    ax.set_title("REC — recovery after a Spark worker restart (8 × 2, 5,000 ev/s)")
    return fig


# ---- building and saving -------------------------------------------------------------------------
def _csv(path: Path) -> Optional[List[Dict[str, str]]]:
    if not path.exists():
        return None
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def build_all(reports: Mapping[str, Tuple[Path, Mapping]], results_dir: Path) -> Tuple[Dict[str, Figure], List[Dict[str, str]]]:
    """All figures that the available results support; the rest are listed with the reason they were skipped."""
    rep = {k: v[1] for k, v in reports.items()}
    figs: Dict[str, Figure] = {}
    skipped: List[Dict[str, str]] = []

    def skip(name, reason):
        skipped.append({"figure": name, "reason": reason})

    panels = [(t, xl, rep[e]["efficiency"]) for e, t, xl in (
        ("E1", "E1 — Kafka partitions (4 executors)", "partitions"),
        ("E2", "E2 — Spark executors (8 partitions)", "executors"))
        if e in rep and [r for r in rep[e].get("efficiency", []) if r["throughput"] is not None]]
    figs["scaling"] = scaling(panels) if panels else None
    if not panels:
        skip("scaling", "E1 and E2 not run")
    lat = [r for r in rep.get("LAT", {}).get("runs", []) if (r.get("summary") or {}).get("p95_ms") is not None]
    figs["latency"] = latency(lat) if lat else None
    if not lat:
        skip("latency", "LAT not run")
    e3 = [r for r in rep.get("E3", {}).get("runs", []) if r.get("detection")]
    figs["detection"] = detection(e3) if e3 else None
    if not e3:
        skip("detection", "E3 not run")
    from ids_monitor.analyze import f3_table          # local import: analyze imports this module
    rows = f3_table(rep.get("E3"))
    figs["f3"] = f3(rows) if rows else None
    if not rows:
        skip("f3", "E3 not run (no per-category rows)")
    p1 = next(iter(rep.get("P1", {}).get("runs", [])), None)
    samples = _csv(Path(results_dir) / "raw" / p1["run_id"] / "samples.csv") if p1 else None
    figs["timeline"] = timeline(samples) if samples else None
    if not samples:
        skip("timeline", "P1 not run" if not p1 else f"raw/{p1['run_id']}/samples.csv missing")
    rec_run = next(iter(rep.get("REC", {}).get("runs", [])), None)
    rec = (rec_run or {}).get("recovery")
    metrics = _csv(Path(results_dir) / "raw" / rec_run["run_id"] / "metrics.csv") if rec_run else None
    if rec and metrics:
        r0 = rec["restart_ms"]
        pts = sorted(((int(m["batch_ts"]) - r0) / 1000, float(m["latency_p95_ms"])) for m in metrics
                     if m.get("latency_p95_ms") not in ("", None) and abs(int(m["batch_ts"]) - r0) <= 120_000)
        figs["recovery"] = recovery(pts, rec)
    else:
        figs["recovery"] = None
        skip("recovery", "REC not run" if not rec_run else ("no recovery result" if not rec else
                                                             f"raw/{rec_run['run_id']}/metrics.csv missing"))
    return {k: v for k, v in figs.items() if v is not None}, skipped


def save(fig: Figure, out_dir: Path, name: str) -> List[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", dpi=200, metadata={"Software": None})
    fig.savefig(out_dir / f"{name}.svg", metadata={"Date": None, "Creator": None})
    plt.close(fig)
    return [f"{name}.png", f"{name}.svg"]
