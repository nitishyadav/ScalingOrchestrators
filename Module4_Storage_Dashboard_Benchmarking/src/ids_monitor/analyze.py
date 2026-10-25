"""`python -m ids_monitor.analyze` — M4-F04 results analysis and figures (REPLICA).

Reads the newest M4-F03 report per experiment (RESULTS_DIR/<EXP>-<stamp>.json, raw/<run_id>/*.csv) and writes
RESULTS_DIR/analysis/RESULTS-<date>.{md,json} with a target scorecard and figures/ (scaling, latency, detection, timeline, recovery).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from ids_contracts import store as S
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR, ConfigError, load_runtime_config, summary_line

REPORT_RE = re.compile(r"^(E1|E2|E3|P1|LAT|REC)-(\d{12})\.json$")
SLOT1, SLOT2 = "#2a78d6", "#eb6834"                      # dataviz reference palette, light (validated 2026-10-22)
INK, MUTED, RULE, GRID = "#1f2328", "#59636e", "#d0d7de", "#eef1f4"


# ---- discovery and scorecard (AC-01, AC-02) ------------------------------------------------------
def latest_reports(results_dir: Path) -> Dict[str, dict]:
    newest: Dict[str, Path] = {}
    for p in Path(results_dir).glob("*.json"):
        m = REPORT_RE.match(p.name)
        if m and (m.group(1) not in newest or p.name > newest[m.group(1)].name):
            newest[m.group(1)] = p
    return {k: json.loads(p.read_text()) for k, p in newest.items()}


def _ok(rep: Optional[Mapping]) -> List[dict]:
    return [r for r in (rep or {}).get("runs", []) if r.get("status") == "ok" and r.get("summary")]


def _row(id_, metric, target, value=None, unit="", passed=None, source=None, note=""):
    return {"id": id_, "metric": metric, "target": target, "value": value, "unit": unit, "pass": passed, "source": source,
            "note": note or ("not run" if value is None and passed is None else "")}


def scorecard(reports: Mapping[str, dict]) -> List[dict]:
    rows = []
    p1 = _ok(reports.get("P1"))
    if p1:
        s = p1[0]["summary"]
        rows.append(_row("P1", "Sustained throughput, 16 partitions × 4 executors", "≥ 10,000 ev/s", s["sustained_evs"], "ev/s",
                         bool(s["sustained_evs"] and s["sustained_evs"] >= 10_000 and s["keeping_up"]), p1[0]["run_id"],
                         f"capacity {s['capacity_rows_per_s']:,.0f} rows/s, keeping up: {s['keeping_up']}"))
    else:
        rows.append(_row("P1", "Sustained throughput, 16 partitions × 4 executors", "≥ 10,000 ev/s"))
    lat = {r["spec"]["level"]: r for r in _ok(reports.get("LAT"))}
    if lat:
        conf = lat.get("1000")
        if conf:
            v = conf["summary"]["latency_p95_ms"]
            rows.append(_row("P2", "p95 latency at 5,000 ev/s, trigger 1 s (configured)", "< 500 ms", v, "ms",
                             v is not None and v < 500, conf["run_id"]))
        best = min((r for r in lat.values() if r["summary"]["latency_p95_ms"] is not None),
                   key=lambda r: r["summary"]["latency_p95_ms"], default=None)
        if best:
            v = best["summary"]["latency_p95_ms"]
            rows.append(_row("P2-best", f"p95 latency at 5,000 ev/s, best trigger ({best['spec']['level']} ms)", "< 500 ms", v, "ms",
                             v < 500, best["run_id"], f"keeping up: {best['summary']['keeping_up']}"))
    else:
        rows.append(_row("P2", "p95 latency at 5,000 ev/s", "< 500 ms"))
    for id_, exp, what in (("P3", "E1", "partitions"), ("P4", "E2", "executors")):
        chk = (reports.get(exp) or {}).get("checks", {}).get("efficiency_at_4")
        if chk:
            rows.append(_row(id_, f"{exp} scaling efficiency, 1 → 4 {what}", "≥ 0.5", chk["value"], "", chk["pass"], exp,
                             f"speedup {chk['speedup']:.2f}× (minimum acceptable 1.5×: {'met' if chk['minimum_speedup_pass'] else 'not met'})"))
        else:
            rows.append(_row(id_, f"{exp} scaling efficiency, 1 → 4 {what}", "≥ 0.5"))
    rec = [r for r in _ok(reports.get("REC")) if r.get("recovery")]
    if rec:
        v = rec[0]["recovery"]
        rows.append(_row("P5", "Recovery after a Spark worker restart", "< 30 s", v["recovered_s"], "s", v["p5_pass"], rec[0]["run_id"],
                         f"first batch after {v['first_batch_after_s']} s, largest gap {v['max_gap_s']} s"))
    else:
        rows.append(_row("P5", "Recovery after a Spark worker restart", "< 30 s"))
    e3 = {r["spec"]["level"]: r for r in _ok(reports.get("E3")) if r.get("detection")}
    if "0" in e3:
        v = e3["0"]["detection"]["benign"]["fpr"]
        rows.append(_row("F2", "False-positive rate, benign-only run (windows)", "< 5 %", v, "share", v is not None and v < 0.05,
                         e3["0"]["run_id"]))
    else:
        rows.append(_row("F2", "False-positive rate, benign-only run (windows)", "< 5 %"))
    if "100" in e3:
        v = e3["100"]["detection"]["banner"]["alert_fraction"]
        ctx = e3.get("20", {}).get("detection", {}).get("banner", {}).get("max_share")
        rows.append(_row("F5", "Drift banner on the all-attack load (share of 30 s samples alerting)", "fires", v, "share",
                         bool(v and v > 0.5), e3["100"]["run_id"],
                         "" if ctx is None else f"at 20 % injection the 300 s share peaks at {ctx:.1%} (ADR-013)"))
    else:
        rows.append(_row("F5", "Drift banner on the all-attack load", "fires"))
    return rows


# ---- figures (AC-03) -----------------------------------------------------------------------------
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"axes.edgecolor": RULE, "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True, "font.size": 9,
                         "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
                         "lines.linewidth": 2, "lines.markersize": 6, "legend.frameon": False, "figure.dpi": 150,
                         "savefig.bbox": "tight", "figure.facecolor": "white", "axes.facecolor": "white"})
    return plt


def _target(ax, y, label, horizontal=True):
    (ax.axhline if horizontal else ax.axvline)(y, color=MUTED, linestyle="--", linewidth=1)
    if horizontal:
        ax.annotate(label, (1, y), xycoords=("axes fraction", "data"), xytext=(-2, 3), textcoords="offset points",
                    ha="right", va="bottom", color=MUTED, fontsize=8)


def _read_csv(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    with open(path) as fh:
        return [{k: (float(v) if v not in ("", None) and k != "run_id" else v) for k, v in r.items()} for r in csv.DictReader(fh)]


def fig_scaling(plt, reports, path) -> bool:
    panels = [(e, reports[e]) for e in ("E1", "E2") if reports.get(e, {}).get("efficiency")]
    if not panels:
        return False
    fig, axes = plt.subplots(1, len(panels), figsize=(3.8 * len(panels), 3.0), squeeze=False)
    for ax, (exp, rep) in zip(axes[0], panels):
        eff = [e for e in rep["efficiency"] if e["capacity"] is not None]
        n = [e["n"] for e in eff]
        cap = [e["capacity"] for e in eff]
        base = cap[0] / n[0]
        ax.plot(n, [base * k for k in n], color=MUTED, linestyle="--", linewidth=1, label="Ideal (linear)")
        ax.plot(n, cap, color=SLOT1, marker="o", label="Measured capacity")
        for e in eff[1:]:
            ax.annotate(f"eff {e['efficiency']:.2f}", (e["n"], e["capacity"]), xytext=(4, -12), textcoords="offset points",
                        fontsize=8, color=MUTED)
        ax.set_xscale("log", base=2)
        ax.set_xticks(n, [str(k) for k in n])
        ax.minorticks_off()
        ax.set_ylim(0, max(max(cap), base * n[-1]) * 1.1)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:,.0f}k"))
        ax.set_xlabel("Kafka partitions" if exp == "E1" else "Spark executors")
        ax.set_ylabel("Capacity (rows/s)")
        ax.set_title(f"{exp}: capacity vs {'partitions' if exp == 'E1' else 'executors'}")
    axes[0][0].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def fig_latency(plt, reports, path) -> bool:
    runs = sorted(_ok(reports.get("LAT")), key=lambda r: -int(r["spec"]["level"]))
    if not runs:
        return False
    labels = [f"{r['spec']['level']} ms" for r in runs]
    x = range(len(runs))
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.plot(x, [r["summary"]["latency_p95_ms"] for r in runs], color=SLOT1, marker="o", label="Median per-batch p95")
    ax.plot(x, [r["summary"]["latency_p95_worst_ms"] for r in runs], color=SLOT2, marker="o", label="Worst per-batch p95 (95th pct)")
    ax.plot(x, [r["summary"]["batch_duration_ms"] for r in runs], color=MUTED, marker="o", linewidth=1, label="Median batch duration")
    _target(ax, 500, "P2 target 500 ms")
    ax.set_xticks(list(x), labels)
    ax.set_xlabel("Trigger interval")
    ax.set_ylabel("Milliseconds")
    ax.set_ylim(0, None)
    ax.set_title("LAT: latency by trigger interval (5,000 ev/s)")
    ax.legend(loc="upper right", fontsize=8)
    fig.savefig(path)
    plt.close(fig)
    return True


def fig_detection(plt, reports, path) -> bool:
    runs = sorted((r for r in _ok(reports.get("E3")) if r.get("detection")), key=lambda r: r["spec"]["share"])
    if not runs:
        return False
    x = range(len(runs))
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    ax.plot(x, [r["detection"]["anomalous_share"] * 100 for r in runs], color=SLOT1, marker="o", label="Anomalous windows, whole run")
    ax.plot(x, [(r["detection"]["banner"]["max_share"] or 0) * 100 for r in runs], color=SLOT2, marker="o",
            label="Banner metric, max over 300 s windows")
    _target(ax, S.DRIFT_THRESHOLD * 100, "banner threshold 15 %")
    ax.set_xticks(list(x), [f"{r['spec']['level']} %" for r in runs])
    ax.set_xlabel("Injected attack share")
    ax.set_ylabel("Share of windows (%)")
    ax.set_ylim(0, 105)
    ax.set_title("E3: anomalous-window share vs attack share")
    ax.legend(loc="upper left", fontsize=8)
    fig.savefig(path)
    plt.close(fig)
    return True


def fig_timeline(plt, results_dir, reports, path) -> bool:
    runs = _ok(reports.get("P1"))
    rows = _read_csv(Path(results_dir) / "raw" / runs[0]["run_id"] / "samples.csv") if runs else []
    if not rows:
        return False
    t = [r["t_s"] for r in rows]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.4, 4.4), sharex=True)
    a1.plot(t, [r["input_evs"] for r in rows], color=SLOT1)
    _target(a1, 10_000, "P1 target 10,000 ev/s")
    a1.set_ylim(0, None)
    a1.set_ylabel("Input (ev/s)")
    a1.set_title(f"P1: 30 s samples, {runs[0]['spec']['rate']:,} ev/s offered, 16 partitions × 4 executors")
    a2.plot(t, [r["p95_median_ms"] for r in rows], color=SLOT1, label="Median per-batch p95")
    a2.plot(t, [r["p95_max_ms"] for r in rows], color=SLOT2, label="Max per-batch p95")
    _target(a2, 500, "P2 target 500 ms")
    a2.set_ylim(0, None)
    a2.set_ylabel("Latency (ms)")
    a2.set_xlabel("Seconds since producer start")
    a2.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return True


def fig_recovery(plt, results_dir, reports, path) -> bool:
    runs = [r for r in _ok(reports.get("REC")) if r.get("recovery")]
    rows = _read_csv(Path(results_dir) / "raw" / runs[0]["run_id"] / "metrics.csv") if runs else []
    if not rows:
        return False
    start, rec = runs[0]["times_ms"]["producer_start"], runs[0]["recovery"]
    pts = [((r["batch_ts"] - start) / 1000, r["latency_p95_ms"]) for r in rows if r["latency_p95_ms"] not in ("", None)]
    xs, ys = [], []
    for i, (x, y) in enumerate(pts):                  # break the line where no batch ran (no fake interpolation)
        if i and x - pts[i - 1][0] > 3:
            xs.append(float("nan"))
            ys.append(float("nan"))
        xs.append(x)
        ys.append(y)
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    ax.plot(xs, ys, color=SLOT1, linewidth=1.5, marker="o", markersize=2.5)
    rs = (rec["restart_ms"] - start) / 1000
    ax.axvline(rs, color=MUTED, linestyle="--", linewidth=1)
    ax.annotate("worker restart", (rs, 1), xycoords=("data", "axes fraction"), xytext=(4, -12), textcoords="offset points",
                color=MUTED, fontsize=8)
    if rec["recovered_s"] is not None:
        ax.axvspan(rs, rs + rec["recovered_s"], color=SLOT2, alpha=0.12, linewidth=0)
        ax.annotate(f"recovered after {rec['recovered_s']:.1f} s", (rs + rec["recovered_s"], 1), xycoords=("data", "axes fraction"),
                    xytext=(4, -26), textcoords="offset points", color=INK, fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("Seconds since producer start")
    ax.set_ylabel("Per-batch p95 latency (ms, log)")
    ax.set_title("REC: latency through a Spark worker restart (5,000 ev/s)")
    fig.savefig(path)
    plt.close(fig)
    return True


def figures(results_dir: Path, reports: Mapping[str, dict], fig_dir: Path) -> List[str]:
    plt = _plt()
    fig_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for name, fn in (("scaling", lambda p: fig_scaling(plt, reports, p)), ("latency", lambda p: fig_latency(plt, reports, p)),
                     ("detection", lambda p: fig_detection(plt, reports, p)),
                     ("timeline", lambda p: fig_timeline(plt, results_dir, reports, p)),
                     ("recovery", lambda p: fig_recovery(plt, results_dir, reports, p))):
        if fn(fig_dir / f"{name}.png"):
            made.append(name)
    return made


# ---- report --------------------------------------------------------------------------------------
def _fmt(r: Mapping) -> str:
    v = r["value"]
    if v is None:
        return "—"
    if r["unit"] == "share":
        return f"{v:.2%}"
    if r["unit"] in ("ev/s", "ms"):
        return f"{v:,.0f} {r['unit']}"
    if r["unit"] == "s":
        return f"{v:.1f} s"
    return f"{v:.2f}"


def report_markdown(card: Sequence[Mapping], reports: Mapping[str, dict], figs: Sequence[str], date: str) -> str:
    mark = {True: "✅ PASS", False: "❌ FAIL", None: "⬜"}
    lines = [f"# Benchmark results ({date})", "",
             "Generated by `python -m ids_monitor.analyze` from the newest M4-F03 report per experiment. Latency follows D-01 "
             "(`detected_at − max_event_ts` per written window, p95 per micro-batch, median over steady-state batches).", "",
             "## Scorecard", "", "| ID | Metric | Target | Value | Result | Source | Note |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['metric']} | {r['target']} | {_fmt(r)} | {mark[r['pass']]} | {('`' + r['source'] + '`') if r['source'] else '—'} | {r['note']} |"
              for r in card]
    lines += ["", "## Reports used", ""]
    lines += [f"- {k}: `{v['report_stem']}.md` ({len(v['runs'])} runs, {v['duration_s']} s each)" for k, v in sorted(reports.items())]
    titles = {"scaling": "Scaling (E1, E2)", "latency": "Latency by trigger (LAT)", "detection": "Detection vs attack share (E3)",
              "timeline": "Throughput and latency over time (P1)", "recovery": "Recovery (REC)"}
    for f in figs:
        lines += ["", f"## {titles[f]}", "", f"![{titles[f]}](figures/{f}.png)"]
    return "\n".join(lines) + "\n"


def run(results_dir: Path, date: Optional[str] = None) -> dict:
    date = date or dt.date.today().isoformat()
    results_dir = Path(results_dir)
    reports = latest_reports(results_dir)
    card = scorecard(reports)
    out = results_dir / "analysis"
    figs = figures(results_dir, reports, out / "figures")
    (out / f"RESULTS-{date}.json").write_text(json.dumps({"date": date, "scorecard": card,
                                                           "reports": {k: v["report_stem"] for k, v in reports.items()}}, indent=2) + "\n")
    (out / f"RESULTS-{date}.md").write_text(report_markdown(card, reports, figs, date))
    return {"report": str(out / f"RESULTS-{date}.md"), "experiments": sorted(reports), "figures": len(figs),
            "passed": sum(1 for r in card if r["pass"] is True), "failed": sum(1 for r in card if r["pass"] is False),
            "not_run": sum(1 for r in card if r["pass"] is None)}


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_monitor.analyze", description="M4-F04 results analysis (replica).")
    p.add_argument("--results-dir", type=Path, help="default RESULTS_DIR")
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    out = run(args.results_dir or cfg.results_dir)
    print(summary_line("analyze", cfg.run_id, **out))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
