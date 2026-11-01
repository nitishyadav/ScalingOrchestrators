"""M4-T222: report checks against P1–P5 / F2 / F5 and the Markdown report (AC-04, AC-06)."""
from ids_monitor import bench_report as BR


def run(level, sustained=None, bound=False, p95=None, det=None, ban=None, rec=None, status="ok"):
    return {"level": level, "run_id": f"X-{level}", "status": status, "reason": "", "notes": [],
            "summary": {"sustained_evs": sustained, "producer_bound": bound, "p95_ms": p95, "producer_rate": 15000.0},
            "detection": det, "banner": ban, "recovery": rec}


def by_name(rep):
    return {c["check"]: c for c in rep["checks"]}


def test_scaling_exact_pass_and_fail():
    ok = by_name(BR.experiment_report("E1", [run("1", 4000.0), run("4", 9000.0)], 600, 60))
    assert ok["P3 efficiency at 4"]["passed"] is True and ok["D-05 minimum speedup at 4"]["passed"] is True
    bad = by_name(BR.experiment_report("E2", [run("1", 4000.0), run("2", 5000.0), run("4", 5200.0)], 600, 60))
    assert bad["P4 efficiency at 4"]["passed"] is False and bad["D-05 minimum speedup at 4"]["value"] == 1.3


def test_scaling_lower_bound_and_inconclusive():
    lb = BR.experiment_report("E1", [run("1", 4000.0), run("4", 5000.0, bound=True)], 600, 60)
    c = by_name(lb)["P3 efficiency at 4"]
    assert c["passed"] is None and "lower bound" in c["note"]              # a missed lower bound is unknown, not a fail
    assert "≥ 1.25" in BR.report_markdown(lb)
    inc = by_name(BR.experiment_report("E1", [run("1", 4000.0, bound=True), run("4", 9000.0)], 600, 60))
    assert inc["P3 efficiency at 4"]["passed"] is None and "inconclusive" in inc["P3 efficiency at 4"]["note"]
    assert by_name(BR.experiment_report("E1", [run("1", 4000.0)], 600, 60))["P3 efficiency at 4"]["passed"] is None


def test_p1_lat_e3_rec_checks():
    assert by_name(BR.experiment_report("P1", [run("16x4", 10_400.0)], 600, 60))["P1 sustained ev/s"]["passed"] is True
    lat = by_name(BR.experiment_report("LAT", [run("1000", p95=1223.0), run("250", p95=410.0)], 600, 60))
    assert lat["P2 p95 at trigger 1000 ms"]["passed"] is False and lat["P2 p95 at trigger 250 ms"]["passed"] is True
    e3 = by_name(BR.experiment_report("E3", [
        run("0", det={"fpr_benign": 0.012}, ban={"share_above": 0.0, "max_share": 0.05}),
        run("20", det={"fpr_benign": 0.01}, ban={"share_above": 0.8, "max_share": 0.31}),
        run("100", det={"fpr_benign": None}, ban={"share_above": 1.0, "max_share": 0.97})], 600, 60))
    assert e3["F2 benign-only window FPR (0 %)"]["passed"] is True and e3["F5 no drift banner at 0 %"]["passed"] is True
    assert e3["F5 drift banner fires at 20 %"]["passed"] is True and e3["F5 drift banner fires at 100 %"]["passed"] is True
    rec = by_name(BR.experiment_report("REC", [run("8x2", rec={"recovered_s": None, "passed": False})], 600, 60))
    assert rec["P5 recovery"]["passed"] is False and "never returned" in rec["P5 recovery"]["note"]


def test_markdown_has_tables_and_interrupt_note():
    rep = BR.experiment_report("E1", [run("1", 4000.0), run("4", None, status="failed")], 600, 60, interrupted=True)
    md = BR.report_markdown(rep)
    assert md.startswith("# E1 — benchmark results") and "**Interrupted:**" in md
    assert "| 4 | `X-4` | failed |" in md and "| Check | Value | Target | Pass | Note |" in md and "➖" in md
