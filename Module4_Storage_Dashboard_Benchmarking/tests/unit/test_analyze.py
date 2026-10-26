"""M4-F04 results analysis (AC-01..AC-03), on synthetic M4-F03 outputs."""
import csv
import json
from dataclasses import asdict

import pytest

from conftest import BASE
from ids_monitor import analyze as an
from ids_monitor import bench as bn


def run(spec, stamp="202610251400", **summary):
    base = {"sustained_evs": 5000.0, "capacity_rows_per_s": 10_000.0, "latency_p95_ms": 900.0, "latency_p95_worst_ms": 1100.0,
            "batch_duration_ms": 500.0, "backlog_s": 0.0, "keeping_up": True}
    return {"run_id": spec.run_id(stamp), "spec": asdict(spec), "status": "ok", "summary": {**base, **summary},
            "times_ms": {"producer_start": BASE, "producer_end": BASE + 600_000}}


def write(results, exp, runs, stamp="202610251400", sub=None):
    rep = bn.experiment_report(exp, runs, 600, 60)
    rep.update(interrupted=False, report_stem=f"{exp}-{stamp}")
    d = results / sub if sub else results
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{exp}-{stamp}.json").write_text(json.dumps(rep, default=str))
    return rep


def det(share, alert, fpr=0.01):
    return {"windows": 1000, "anomalous": int(share * 1000), "anomalous_share": share,
            "injected": {"windows": 10, "flagged": 10, "recall": 1.0}, "cic_attack": {"windows": 0, "flagged": 0, "recall": None},
            "benign": {"windows": 990, "flagged": int(fpr * 990), "fpr": fpr},
            "banner": {"samples": 10, "max_share": share + 0.02, "alert_fraction": alert, "threshold": 0.15, "span_s": 300}}


@pytest.fixture
def results(tmp_path):
    e1 = bn.plan("E1")
    write(tmp_path, "E1", [run(e1[0], capacity_rows_per_s=10_000.0), run(e1[1], capacity_rows_per_s=24_000.0)])
    write(tmp_path, "E1", [run(e1[0], stamp="202610251300", capacity_rows_per_s=1.0)], stamp="202610251300")   # older
    write(tmp_path, "E1", [run(e1[0], stamp="202610251500", capacity_rows_per_s=2.0)], stamp="202610251500", sub="smoke")
    e2 = bn.plan("E2")
    write(tmp_path, "E2", [run(e2[0], capacity_rows_per_s=6000.0), run(e2[2], capacity_rows_per_s=9000.0)])
    lat = bn.plan("LAT")
    write(tmp_path, "LAT", [run(lat[0], latency_p95_ms=1040.0), run(lat[1], latency_p95_ms=620.0), run(lat[2], latency_p95_ms=410.0)])
    e3 = bn.plan("E3")
    write(tmp_path, "E3", [dict(run(s), detection=det(sh, al)) for s, sh, al in zip(e3, (0.01, 0.03, 0.06, 1.0), (0.0, 0.0, 0.0, 1.0))])
    p1 = run(bn.plan("P1")[0], sustained_evs=11_000.0)
    write(tmp_path, "P1", [p1])
    raw = tmp_path / "raw" / p1["run_id"]
    raw.mkdir(parents=True)
    with open(raw / "samples.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["t_s", "batches", "input_evs", "capacity_median", "p95_median_ms", "p95_max_ms"])
        w.writeheader()
        w.writerows({"t_s": t, "batches": 30, "input_evs": 11_000 + t, "capacity_median": 15_000, "p95_median_ms": 800,
                     "p95_max_ms": 1200} for t in range(0, 600, 30))
    return tmp_path


def test_latest_reports_ignores_older_and_smoke(results):
    reps = an.latest_reports(results)
    assert set(reps) == {"E1", "E2", "LAT", "E3", "P1"}
    assert reps["E1"]["report_stem"] == "E1-202610251400"


def test_scorecard(results):
    card = {r["id"]: r for r in an.scorecard(an.latest_reports(results))}
    assert card["P1"]["value"] == 11_000.0 and card["P1"]["pass"] is True
    assert card["P2"]["value"] == 1040.0 and card["P2"]["pass"] is False
    assert card["P2-best"]["value"] == 410.0 and card["P2-best"]["pass"] is True and "250" in card["P2-best"]["metric"]
    assert card["P3"]["value"] == pytest.approx(0.6) and card["P3"]["pass"] is True
    assert card["P4"]["value"] == pytest.approx(0.375) and card["P4"]["pass"] is False
    assert card["F2"]["value"] == 0.01 and card["F2"]["pass"] is True
    assert card["F5"]["value"] == 1.0 and card["F5"]["pass"] is True
    assert card["P5"]["pass"] is None and card["P5"]["value"] is None and card["P5"]["note"] == "not run"


def test_figures_and_markdown(results):
    out = an.run(results, date="2026-10-25")
    figs = sorted(p.name for p in (results / "analysis" / "figures").glob("*.png"))
    assert figs == ["detection.png", "latency.png", "scaling.png", "timeline.png"]        # no REC: recovery skipped
    md = (results / "analysis" / "RESULTS-2026-10-25.md").read_text()
    assert "| P3 |" in md and "not run" in md and "figures/scaling.png" in md and "recovery.png" not in md
    assert out["figures"] == 4 and out["passed"] == 5 and out["failed"] == 2
