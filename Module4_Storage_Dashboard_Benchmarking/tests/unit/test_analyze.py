"""M4-T310: report selection, scorecard, F3 table, evidence, outputs (AC-01, 02, 03, 05)."""
import json

import pytest

from ids_monitor import analyze as A
from ids_monitor import bench_report as BR

import results_fixture as RF


# ---- AC-01 ----
def test_latest_reports_newest_per_experiment(tmp_path):
    RF.write(tmp_path, "202611061430", only={"E1"})
    RF.write(tmp_path, "202611071000", only={"E1", "E2"})
    (tmp_path / "smoke").mkdir()
    BR.write_json(tmp_path / "smoke" / "E1-202612010000.json", {"experiment": "E1"})   # ignored: subfolder
    (tmp_path / "E2-202612010000.json").write_text("{not json")                       # broken: skipped
    (tmp_path / "notes.json").write_text("{}")                                          # not a report name
    got = A.latest_reports(tmp_path)
    assert {k: p.name for k, (p, _) in got.items()} == {"E1": "E1-202611071000.json", "E2": "E2-202611071000.json"}


# ---- AC-02 ----
def rows(tmp_path, evidence=None):
    RF.write(tmp_path)
    if evidence:
        BR.write_json(tmp_path / "evidence" / "F4.json", evidence)
    return {r["id"]: r for r in A.scorecard(A.latest_reports(tmp_path), A.load_evidence(tmp_path))}


def test_scorecard_values_verdicts_sources(tmp_path):
    card = rows(tmp_path)
    assert list(card) == ["P1", "P2", "P3", "P4", "P5", "F2", "F3", "F4", "F5"]
    assert (card["P1"]["value"], card["P1"]["verdict"]) == (10400.0, "PASS")
    assert card["P1"]["source"] == ["P1-p16-e4-r12000-a0-202611061430"]
    assert (card["P2"]["value"], card["P2"]["verdict"]) == (1223.0, "FAIL")
    assert "best: 250 ms trigger, 410 ms" in card["P2"]["note"]
    assert card["P3"]["value"] == pytest.approx(9100 / 4200 / 4, abs=1e-3) and card["P3"]["verdict"] == "PASS"  # 0.54
    assert card["P4"]["value"] == pytest.approx(7200 / 3900 / 4, abs=1e-3) and card["P4"]["verdict"] == "FAIL"  # 0.46
    assert (card["P5"]["value"], card["P5"]["verdict"]) == (21.0, "PASS")
    assert (card["F2"]["value"], card["F2"]["verdict"]) == (0.021, "PASS")
    assert card["F3"]["verdict"] == "PASS" and card["F3"]["value"] == "3 attack categories"
    assert card["F4"]["verdict"] == "NOT RUN" and "M4-F02 AC-08" in card["F4"]["note"]
    assert card["F5"]["verdict"] == "PASS" and len(card["F5"]["source"]) == 3


def test_lower_bound_is_unknown_and_missing_is_not_run(tmp_path):
    RF.write(tmp_path, only={"E1"})
    rep = json.loads((tmp_path / f"E1-{RF.STAMP}.json").read_text())
    for r in rep["runs"]:
        if r["level"] == "4":
            r["summary"]["sustained_evs"], r["summary"]["producer_bound"] = 7000.0, True      # 0.42, lower bound
    rep2 = BR.experiment_report("E1", rep["runs"], 600, 60)
    BR.write_json(tmp_path / f"E1-{RF.STAMP}.json", rep2)
    card = {r["id"]: r for r in A.scorecard(A.latest_reports(tmp_path), {})}
    assert card["P3"]["verdict"] == "UNKNOWN" and "lower bound" in card["P3"]["note"]
    assert {card[k]["verdict"] for k in ("P1", "P2", "P4", "P5", "F2", "F3", "F5")} == {"NOT RUN"}


def test_f4_from_evidence(tmp_path):
    card = rows(tmp_path, {"worst_case_s": 3.44, "measured": "2026-11-01", "source": "M4-F02 AC-08"})
    assert (card["F4"]["value"], card["F4"]["verdict"]) == (3.44, "PASS")
    card = rows(tmp_path, {"worst_case_s": 6.1, "measured": "2026-11-02", "source": "M4-F02 AC-08"})
    assert card["F4"]["verdict"] == "FAIL"


# ---- AC-03 ----
def test_f3_table_sums_attack_levels_and_benign_from_0(tmp_path):
    RF.write(tmp_path, only={"E3"})
    (_, rep), = A.latest_reports(tmp_path).values()
    t = {r["category"]: r for r in A.f3_table(rep)}
    assert list(t) == ["INJ_DDOS", "INJ_PORTSCAN", "INJ_SYNFLOOD", "BENIGN"]
    ddos = t["INJ_DDOS"]                                      # 40 × (5 + 20 + 100) = 5,000 windows
    assert ddos["windows"] == 5000 and ddos["rule"] == round((70 + 280 + 1400) / 5000, 4)
    assert t["BENIGN"]["windows"] == 4000 and t["BENIGN"]["hybrid"] == 0.021 and t["BENIGN"]["levels"] == "0 %"
    assert A.f3_table(None) == []


# ---- AC-05 ----
def test_outputs_and_determinism(tmp_path):
    RF.write(tmp_path)
    first = A.analyze(tmp_path)
    out = tmp_path / "analysis"
    files = sorted(p.relative_to(out) for p in out.rglob("*") if p.is_file())
    blobs = {p: (out / p).read_bytes() for p in files}
    assert first["skipped"] == [] and len(first["figures"]) == 6
    assert {"RESULTS.md", "scorecard.json", "f3.csv"} <= {str(p) for p in files}
    A.analyze(tmp_path)
    assert {p: (out / p).read_bytes() for p in files} == blobs                       # byte-identical rerun
    md = (out / "RESULTS.md").read_text()
    assert md.startswith("# Results") and "| P3 |" in md and "![scaling](figures/scaling.png)" in md
    assert "| INJ_DDOS |" in md and "E1-202611061430.md" in md


def test_empty_results_dir(tmp_path):
    res = A.analyze(tmp_path)
    assert set(res["verdicts"].values()) == {"NOT RUN"} and res["figures"] == []
    assert len(res["skipped"]) == 6 and (tmp_path / "analysis" / "RESULTS.md").exists()
