"""Benchmark raw files and experiment reports (M4-T222, FR-049). Every number is recomputable from `metrics.csv`."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from ids_contracts.metrics import METRICS_COLUMNS

from ids_monitor import bench_math as BM
from ids_monitor.bench_plan import EXPERIMENTS

P1_TARGET_EVS = 10_000
P2_TARGET_MS = 500
P3_P4_EFFICIENCY = 0.5
D05_MIN_SPEEDUP = 1.5
F2_MAX_FPR = 0.05
P5_MAX_S = 30


# ---- files ---------------------------------------------------------------------------------------
def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


METRICS_FIELDS = [c for c, _ in METRICS_COLUMNS]
SAMPLE_FIELDS = ["t_s", "evs", "batches", "p95_median_ms", "p95_max_ms"]


# ---- checks --------------------------------------------------------------------------------------
def _check(name: str, value: Any, target: str, passed: Optional[bool], note: str = "") -> Dict[str, Any]:
    return {"check": name, "value": value, "target": target, "passed": passed, "note": note}


def _by_level(runs: Sequence[Mapping]) -> Dict[str, Mapping]:
    return {r["level"]: r for r in runs}


def scaling(runs: Sequence[Mapping]) -> List[Dict[str, Any]]:
    """E1/E2 efficiency rows over the levels that ran, baseline = the lowest level."""
    ok = sorted((r for r in runs if r.get("summary")), key=lambda r: int(r["level"]))
    if not ok:
        return []
    return BM.efficiency([(int(r["level"]), r["summary"].get("sustained_evs"), r["summary"].get("producer_bound"))
                          for r in ok])


def _judge(met: bool, qualifier: str) -> Optional[bool]:
    """Exact: pass/fail. Lower bound: a met target passes, a missed one is unknown. Inconclusive: unknown."""
    if qualifier == "exact":
        return met
    return True if (qualifier == "lower_bound" and met) else None


def checks(experiment: str, runs: Sequence[Mapping], eff: Sequence[Mapping]) -> List[Dict[str, Any]]:
    lv = _by_level(runs)
    out: List[Dict[str, Any]] = []
    if experiment in ("E1", "E2"):
        at4 = next((e for e in eff if e["n"] == 4), None)
        target = "P3" if experiment == "E1" else "P4"
        if at4 is None or at4["efficiency"] is None:
            out.append(_check(f"{target} efficiency at 4", None, f"≥ {P3_P4_EFFICIENCY}", None, "level 1 or 4 missing"))
        else:
            q = at4["qualifier"]
            note = {"exact": "", "lower_bound": "lower bound: level 4 kept up with the producer",
                    "inconclusive": "inconclusive: level 1 kept up with the producer (M4-ADR-002)"}[q]
            out.append(_check(f"{target} efficiency at 4", at4["efficiency"], f"≥ {P3_P4_EFFICIENCY}",
                              _judge(at4["efficiency"] >= P3_P4_EFFICIENCY, q), note))
            out.append(_check("D-05 minimum speedup at 4", at4["speedup"], f"≥ {D05_MIN_SPEEDUP}×",
                              _judge(at4["speedup"] >= D05_MIN_SPEEDUP, q), note))
    elif experiment == "P1":
        s = (lv.get("16x4") or {}).get("summary") or {}
        v = s.get("sustained_evs")
        out.append(_check("P1 sustained ev/s", v, f"≥ {P1_TARGET_EVS:,}", None if v is None else v >= P1_TARGET_EVS))
    elif experiment == "LAT":
        for level, r in lv.items():
            v = (r.get("summary") or {}).get("p95_ms")
            out.append(_check(f"P2 p95 at trigger {level} ms", v, f"< {P2_TARGET_MS} ms", None if v is None else v < P2_TARGET_MS))
    elif experiment == "E3":
        zero = lv.get("0") or {}
        fpr = (zero.get("detection") or {}).get("fpr_benign")
        out.append(_check("F2 benign-only window FPR (0 %)", fpr, f"< {F2_MAX_FPR:.0%}", None if fpr is None else fpr < F2_MAX_FPR))
        above = (zero.get("banner") or {}).get("share_above")
        out.append(_check("F5 no drift banner at 0 %", above, "0 samples above 15 %", None if above is None else above == 0))
        for level in ("20", "100"):
            m = ((lv.get(level) or {}).get("banner") or {}).get("max_share")
            out.append(_check(f"F5 drift banner fires at {level} %", m, "> 15 %", None if m is None else m > 0.15))
    elif experiment == "REC":
        rec = (lv.get("8x2") or {}).get("recovery") or {}
        v = rec.get("recovered_s")
        out.append(_check("P5 recovery", v, f"< {P5_MAX_S} s", bool(rec.get("passed")) if rec else None,
                          "" if v is not None or not rec else "latency never returned under the threshold"))
    return out


def experiment_report(experiment: str, runs: Sequence[Mapping], duration_s: int, warmup_s: int,
                      interrupted: bool = False) -> Dict[str, Any]:
    eff = scaling(runs) if experiment in ("E1", "E2") else []
    return {"experiment": experiment, "target": EXPERIMENTS[experiment].target, "duration_s": duration_s,
            "warmup_s": warmup_s, "interrupted": interrupted,
            "runs": [{k: r.get(k) for k in ("level", "run_id", "status", "reason", "summary", "detection", "banner",
                                            "recovery", "notes")} for r in runs],
            "efficiency": eff, "checks": checks(experiment, runs, eff)}


# ---- markdown ------------------------------------------------------------------------------------
def _f(v: Any, spec: str = ",.0f") -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return format(v, spec) if isinstance(v, (int, float)) else str(v)


def _mark(passed: Optional[bool]) -> str:
    return {True: "✅", False: "❌", None: "➖"}[passed]


def report_markdown(rep: Mapping[str, Any]) -> str:
    e = rep["experiment"]
    lines = [f"# {e} — benchmark results", "",
             f"Target: {rep['target']}. Each run: {rep['duration_s']} s replay, steady state after a {rep['warmup_s']} s warm-up.",
             "Throughput = Σ input rows / steady span (M4-ADR-002). p95 = median of per-batch p95 (D-01); tail = 95th percentile of them.",
             "*Kept up* = sustained ≥ 95 % of the producer's achieved rate: the system was not saturated, so the throughput is a lower bound.", ""]
    if rep.get("interrupted"):
        lines += ["> **Interrupted:** the experiment was stopped with Ctrl-C; later levels did not run.", ""]
    lines += ["| Level | Run ID | Status | Sustained ev/s | Producer ev/s | Kept up | p95 ms (median / tail) | Batch ms | Backlog s |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["runs"]:
        s = r.get("summary") or {}
        status = r["status"] + (f" ({r['reason']})" if r.get("reason") else "")
        lines.append(f"| {r['level']} | `{r['run_id']}` | {status} | {_f(s.get('sustained_evs'))} | {_f(s.get('producer_rate'))} | "
                     f"{_f(s.get('producer_bound'))} | {_f(s.get('p95_ms'))} / {_f(s.get('p95_tail_ms'))} | "
                     f"{_f(s.get('batch_ms_median'))} | {_f(s.get('backlog_s'), '.1f')} |")
    if rep.get("efficiency"):
        lines += ["", "| N | Throughput ev/s | Speedup | Efficiency | Basis |", "|---|---|---|---|---|"]
        for x in rep["efficiency"]:
            ge = "≥ " if x["qualifier"] == "lower_bound" else ""
            lines.append(f"| {x['n']} | {_f(x['throughput'])} | {ge}{_f(x['speedup'], '.2f')} | {ge}{_f(x['efficiency'], '.2f')} | "
                         f"{x['qualifier'].replace('_', ' ')} |")
    if any(r.get("detection") for r in rep["runs"]):
        lines += ["", "| Level | Windows | Anomalous | Recall (injected) | FPR (benign) | Banner max | Samples > 15 % |",
                  "|---|---|---|---|---|---|---|"]
        for r in rep["runs"]:
            d, b = r.get("detection") or {}, r.get("banner") or {}
            lines.append(f"| {r['level']} % | {_f(d.get('windows'))} | {_f(d.get('anomalous_share'), '.1%')} | "
                         f"{_f(d.get('recall_injected'), '.1%')} | {_f(d.get('fpr_benign'), '.2%')} | {_f(b.get('max_share'), '.1%')} | "
                         f"{_f(b.get('share_above'), '.0%')} |")
    for r in rep["runs"]:
        rec = r.get("recovery")
        if rec:
            lines += ["", "| Restart → first batch s | Largest gap s | Pre-restart p95 ms | Threshold ms | Recovered s |",
                      "|---|---|---|---|---|",
                      f"| {_f(rec.get('first_batch_s'), '.1f')} | {_f(rec.get('max_gap_s'), '.1f')} | {_f(rec.get('pre_p95_ms'))} | "
                      f"{_f(rec.get('threshold_ms'))} | {_f(rec.get('recovered_s'), '.1f')} |"]
    lines += ["", "| Check | Value | Target | Pass | Note |", "|---|---|---|---|---|"]
    for c in rep["checks"]:
        v = c["value"]
        lines.append(f"| {c['check']} | {_f(v, '.3f') if isinstance(v, float) else _f(v)} | {c['target']} | {_mark(c['passed'])} | {c['note']} |")
    return "\n".join(lines) + "\n"
