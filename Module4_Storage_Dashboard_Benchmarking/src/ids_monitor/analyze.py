"""Results analysis (M4-T320, M4-F04): scorecard, F3 table, figures and RESULTS.md from M4-F03 outputs.

    python -m ids_monitor.analyze            # reads RESULTS_DIR, writes RESULTS_DIR/analysis/

Nothing is measured here. Verdicts are taken from the M4-F03 report `checks` (single source of truth).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ids_contracts.config import RuntimeConfig

from ids_monitor import bench_report as BR
from ids_monitor import cli

COMMAND = "ids_monitor.analyze"
REPORT_NAME = re.compile(r"^(E1|E2|E3|P1|LAT|REC)-(\d{12})\.json$")
VERDICT = {True: "PASS", False: "FAIL", None: "UNKNOWN"}
P2_DEFAULT_TRIGGER = "1000"          # C-06 TRIGGER_INTERVAL default "1 second"
F4_TARGET_S = 5.0
F3_FIELDS = ["category", "levels", "windows", "rule", "ml", "hybrid"]


# ---- selection (FR-060) --------------------------------------------------------------------------
def latest_reports(results_dir: Path) -> Dict[str, Tuple[Path, Dict[str, Any]]]:
    """Newest valid `<EXP>-<stamp>.json` per experiment, in `results_dir` itself only (not smoke/ or raw/)."""
    best: Dict[str, Tuple[str, Path, Dict[str, Any]]] = {}
    d = Path(results_dir)
    if not d.is_dir():
        return {}
    for p in sorted(d.iterdir()):
        m = REPORT_NAME.match(p.name)
        if not m or not p.is_file():
            continue
        try:
            rep = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            print(f"{COMMAND}: skipping unreadable report {p.name}", file=sys.stderr)
            continue
        exp, stamp = m.groups()
        if exp not in best or stamp > best[exp][0]:
            best[exp] = (stamp, p, rep)
    return {exp: (p, rep) for exp, (_, p, rep) in sorted(best.items())}


def load_evidence(results_dir: Path) -> Dict[str, Any]:
    """Measurements made outside the harness (FR-063): `evidence/F4.json` from M4-F02 AC-08."""
    p = Path(results_dir) / "evidence" / "F4.json"
    try:
        return {"F4": json.loads(p.read_text())} if p.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


# ---- scorecard (FR-061, FR-063) ------------------------------------------------------------------
def _check(rep: Optional[Mapping], name: str) -> Optional[Mapping]:
    return next((c for c in (rep or {}).get("checks", []) if c["check"] == name), None)


def _runs(rep: Optional[Mapping], levels: Optional[Sequence[str]] = None) -> List[str]:
    return [r["run_id"] for r in (rep or {}).get("runs", []) if levels is None or r["level"] in levels]


def _row(rid: str, metric: str, target: str, value: Any, verdict: str, source: List[str], note: str = "") -> Dict[str, Any]:
    return {"id": rid, "metric": metric, "target": target, "value": value, "verdict": verdict, "source": source, "note": note}


def _from_check(rid, metric, target, rep, check_name, levels=None, note="") -> Dict[str, Any]:
    if rep is None:
        return _row(rid, metric, target, None, "NOT RUN", [], note)
    c = _check(rep, check_name)
    if c is None:
        return _row(rid, metric, target, None, "NOT RUN", _runs(rep, levels), "level not run")
    return _row(rid, metric, target, c["value"], VERDICT[c["passed"]], _runs(rep, levels),
                "; ".join(x for x in (c.get("note"), note) if x))


def scorecard(reports: Mapping[str, Tuple[Path, Mapping]], evidence: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rep = {k: v[1] for k, v in reports.items()}
    rows = [_from_check("P1", "Sustained throughput, 16 partitions × 4 executors", "≥ 10,000 ev/s", rep.get("P1"),
                        "P1 sustained ev/s")]
    lat = rep.get("LAT")
    best = None
    if lat:
        p95s = [(r["summary"]["p95_ms"], r["level"]) for r in lat["runs"] if (r.get("summary") or {}).get("p95_ms") is not None]
        best = min(p95s) if p95s else None
    rows.append(_from_check("P2", "p95 end-to-end latency at 5,000 ev/s (1 s trigger, D-01)", "< 500 ms", lat,
                            f"P2 p95 at trigger {P2_DEFAULT_TRIGGER} ms", [P2_DEFAULT_TRIGGER],
                            f"best: {best[1]} ms trigger, {best[0]:,.0f} ms" if best else ""))
    rows.append(_from_check("P3", "Scaling efficiency, 1 → 4 partitions (E1)", "≥ 0.5 (min 1.5×)", rep.get("E1"),
                            "P3 efficiency at 4", ["1", "4"]))
    rows.append(_from_check("P4", "Scaling efficiency, 1 → 4 executors (E2)", "≥ 0.5 (min 1.5×)", rep.get("E2"),
                            "P4 efficiency at 4", ["1", "4"]))
    rows.append(_from_check("P5", "Recovery after a Spark worker restart", "< 30 s", rep.get("REC"), "P5 recovery"))
    e3 = rep.get("E3")
    rows.append(_from_check("F2", "False-positive rate, benign-only run (windows)", "< 5 %", e3,
                            "F2 benign-only window FPR (0 %)", ["0"]))
    table = f3_table(e3)
    attacks = [r for r in table if r["category"] != "BENIGN" and r["windows"]]
    rows.append(_row("F3", "Rule-only vs hybrid per attack category (online)", "Produced",
                     f"{len(attacks)} attack categories" if e3 else None,
                     ("PASS" if attacks else "FAIL") if e3 else "NOT RUN",
                     _runs(e3, ["5", "20", "100"]) if e3 else [], "table in RESULTS.md and f3.csv" if attacks else ""))
    f4 = evidence.get("F4")
    if f4 and f4.get("worst_case_s") is not None:
        rows.append(_row("F4", "Alert visible on the dashboard after the Cassandra write", "≤ 5 s", f4["worst_case_s"],
                         "PASS" if f4["worst_case_s"] <= F4_TARGET_S else "FAIL", [str(f4.get("source", "M4-F02 AC-08"))],
                         f"measured {f4.get('measured', '?')}"))
    else:
        rows.append(_row("F4", "Alert visible on the dashboard after the Cassandra write", "≤ 5 s", None, "NOT RUN", [],
                         "measured by M4-F02 AC-08 (live test), not the harness; put it in evidence/F4.json"))
    if e3 is None:
        rows.append(_row("F5", "Drift banner fires when the anomaly rate > 15 %", "Correct", None, "NOT RUN", []))
    else:
        cs = [_check(e3, n) for n in ("F5 no drift banner at 0 %", "F5 drift banner fires at 20 %",
                                      "F5 drift banner fires at 100 %")]
        passed = [c["passed"] if c else None for c in cs]
        verdict = "FAIL" if False in passed else ("PASS" if all(p is True for p in passed) else "UNKNOWN")
        parts = []
        if cs[0] is not None and cs[0]["value"] is not None:
            parts.append(f"0 %: {cs[0]['value']:.0%} of samples above 15 %")
        parts += [f"{lv} %: max {c['value']:.0%}" for lv, c in zip(("20", "100"), cs[1:]) if c and c["value"] is not None]
        value = "; ".join(parts) or None
        rows.append(_row("F5", "Drift banner fires when the anomaly rate > 15 %", "Correct", value, verdict,
                         _runs(e3, ["0", "20", "100"]), "no banner at 0 %, banner at 20 % and 100 % (ADR-013)"))
    return rows


# ---- F3 (FR-062) ---------------------------------------------------------------------------------
def f3_table(e3: Optional[Mapping]) -> List[Dict[str, Any]]:
    """Per category, flagged / windows summed over the attack levels (5, 20, 100 %); BENIGN from the 0 % level (FPR)."""
    if not e3:
        return []
    acc: Dict[str, Dict[str, Any]] = {}
    for r in e3.get("runs", []):
        for c in ((r.get("detection") or {}).get("by_category") or []):
            if (c["category"] == "BENIGN") != (r["level"] == "0"):
                continue
            a = acc.setdefault(c["category"], {"windows": 0, "rule": 0, "ml": 0, "hybrid": 0, "levels": []})
            a["windows"] += c["windows"]
            for d in ("rule", "ml", "hybrid"):
                a[d] += c[f"{d}_flagged"]
            a["levels"].append(r["level"])
    out = []
    for cat in sorted(acc, key=lambda c: (c == "BENIGN", c)):
        a = acc[cat]
        out.append({"category": cat, "levels": ", ".join(f"{lv} %" for lv in sorted(set(a["levels"]), key=int)),
                    "windows": a["windows"],
                    **{d: round(a[d] / a["windows"], 4) if a["windows"] else None for d in ("rule", "ml", "hybrid")}})
    return out


# ---- RESULTS.md (FR-065) -------------------------------------------------------------------------
def _v(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.3g}"
    return str(v)


ICON = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "UNKNOWN": "➖ UNKNOWN", "NOT RUN": "⬜ NOT RUN"}


def results_markdown(card, f3, reports, figures, skipped) -> str:
    lines = ["# Results — success metrics", "",
             "Generated by `python -m ids_monitor.analyze` (M4-F04) from the newest M4-F03 report per experiment. "
             "Method: M4-ADR-002. Verdicts are the M4-F03 report checks.", "",
             "| ID | Metric | Target | Value | Verdict | Source runs | Note |", "|---|---|---|---|---|---|---|"]
    for r in card:
        src = "<br>".join(f"`{s}`" for s in r["source"]) or "—"
        lines.append(f"| {r['id']} | {r['metric']} | {r['target']} | {_v(r['value'])} | {ICON[r['verdict']]} | {src} | {r['note']} |")
    lines += ["", "F1 (IF precision/recall on held-out days) is an offline M2 result and is reported by M2-F03.", ""]
    lines += ["## F3 — rule-only vs ML-only vs hybrid (online, E3)", ""]
    if f3:
        lines += ["Share of windows each detector flags: recall for attack categories (5, 20, 100 % levels together), "
                  "false-positive rate for benign windows (0 % level).", "",
                  "| Category | Levels | Windows | Rule-only | ML-only | Hybrid |", "|---|---|---|---|---|---|"]
        for r in f3:
            lines.append(f"| {r['category']} | {r['levels']} | {r['windows']:,} | {r['rule']:.1%} | {r['ml']:.1%} | {r['hybrid']:.1%} |")
    else:
        lines.append("E3 not run.")
    lines += ["", "## Figures", ""]
    for name in figures:
        lines += [f"![{name}](figures/{name}.png)", ""]
    if skipped:
        lines += ["Skipped figures:", ""] + [f"- **{s['figure']}**: {s['reason']}" for s in skipped] + [""]
    lines += ["## Experiment reports", ""]
    if reports:
        lines += [f"- {exp}: [`{p.name.replace('.json', '.md')}`](../{p.name.replace('.json', '.md')})" for exp, (p, _) in reports.items()]
    else:
        lines.append("No M4-F03 reports found.")
    return "\n".join(lines) + "\n"


def analyze(results_dir: Path) -> Dict[str, Any]:
    from ids_monitor import figures as F
    results_dir = Path(results_dir)
    out = results_dir / "analysis"
    reports = latest_reports(results_dir)
    card = scorecard(reports, load_evidence(results_dir))
    f3 = f3_table(reports.get("E3", (None, None))[1])
    figs, skipped = F.build_all(reports, results_dir)
    names = [n for n in F.NAMES if n in figs]
    for n in names:
        F.save(figs[n], out / "figures", n)
    BR.write_json(out / "scorecard.json", card)
    BR.write_csv(out / "f3.csv", f3, F3_FIELDS)
    (out / "RESULTS.md").write_text(results_markdown(card, f3, reports, names, skipped))
    return {"experiments": list(reports), "verdicts": {r["id"]: r["verdict"] for r in card}, "figures": names,
            "skipped": [s["figure"] for s in skipped], "results_md": str(out / "RESULTS.md")}


# ---- CLI (FR-066) --------------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    argparse.ArgumentParser(prog=f"python -m {COMMAND}",
                            description="M4-F04: scorecard, F3 table and report figures from M4-F03 results "
                                        "(RESULTS_DIR → RESULTS_DIR/analysis/).").parse_args(argv)

    def handler(cfg: RuntimeConfig) -> Dict[str, Any]:
        return analyze(Path(cfg.results_dir))

    return cli.run(COMMAND, handler)


if __name__ == "__main__":
    sys.exit(main())
