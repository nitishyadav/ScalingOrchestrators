"""A synthetic, complete M4-F03 result set (all 6 experiments + raw CSVs), written with M4-F03's own report code.

Used by the M4-F04 unit tests, the contract test and the visual check. Values are illustrative, not measurements.
"""
from pathlib import Path

from ids_monitor import bench_report as BR

T0 = 1_793_975_400_000
STAMP = "202611061430"


def _run(exp, level, rid, sustained=None, bound=False, p95=None, tail=None, rate=5000, **extra):
    s = {"status": "ok", "reason": "", "sustained_evs": sustained, "producer_bound": bound, "producer_rate": float(rate),
         "keeping_up": True, "p95_ms": p95, "p95_tail_ms": tail, "p50_ms": None if p95 is None else p95 * 0.6,
         "batch_ms_median": 800.0, "backlog_s": 0.0, "spark_processed_median": 9000.0, "steady_batches": 540,
         "steady_span_s": 540.0}
    return {"level": level, "run_id": rid, "status": "ok", "reason": "", "notes": [], "summary": s,
            "detection": None, "banner": None, "recovery": None, **extra}


def _cat(cat, n, rule, ml, hybrid):
    return {"category": cat, "windows": n, "rule": rule, "ml": ml, "hybrid": hybrid,
            "rule_flagged": round(rule * n), "ml_flagged": round(ml * n), "hybrid_flagged": round(hybrid * n)}


def write(results: Path, stamp: str = STAMP, only=None) -> Path:
    results = Path(results)
    runs = {
        "E1": [_run("E1", "1", f"E1-p1-e4-r15000-a0-{stamp}", 4200.0, rate=14900),
               _run("E1", "4", f"E1-p4-e4-r15000-a0-{stamp}", 9100.0, rate=14900),
               _run("E1", "8", f"E1-p8-e4-r15000-a0-{stamp}", 14300.0, bound=True, rate=14900),
               _run("E1", "16", f"E1-p16-e4-r15000-a0-{stamp}", 14500.0, bound=True, rate=14900)],
        "E2": [_run("E2", "1", f"E2-p8-e1-r15000-a0-{stamp}", 3900.0, rate=14900),
               _run("E2", "2", f"E2-p8-e2-r15000-a0-{stamp}", 6800.0, rate=14900),
               _run("E2", "4", f"E2-p8-e4-r15000-a0-{stamp}", 7200.0, rate=14900)],
        "P1": [_run("P1", "16x4", f"P1-p16-e4-r12000-a0-{stamp}", 10400.0, p95=2900.0, tail=4100.0, rate=12000)],
        "LAT": [_run("LAT", t, f"LAT-p8-e2-r5000-a0-t{t}-{stamp}", 5000.0, True, p95, tail)
                for t, p95, tail in (("1000", 1223.0, 1610.0), ("500", 640.0, 905.0), ("250", 410.0, 820.0))],
        "REC": [_run("REC", "8x2", f"REC-p8-e2-r5000-a0-{stamp}", 4950.0, True, 1150.0, 2400.0,
                     recovery={"restart_ms": T0 + 300_000, "pre_p95_ms": 1100.0, "threshold_ms": 2200.0,
                               "first_batch_s": 14.0, "max_gap_s": 15.0, "recovered_s": 21.0, "passed": True})],
    }
    e3 = []
    for a, share, banner_max, above in ((0, 0.021, 0.06, 0.0), (5, 0.07, 0.12, 0.0), (20, 0.22, 0.31, 0.85),
                                        (100, 0.93, 0.97, 1.0)):
        cats = [_cat("BENIGN", 4000, 0.004, 0.017, 0.021)]
        if a:
            cats = [_cat("INJ_DDOS", 40 * a, 0.35, 0.88, 0.94), _cat("INJ_PORTSCAN", 30 * a, 0.81, 0.42, 0.90),
                    _cat("INJ_SYNFLOOD", 30 * a, 0.62, 0.71, 0.86)] + cats
        e3.append(_run("E3", str(a), f"E3-p8-e2-r5000-a{a}-{stamp}", 5000.0, True, 1180.0, 1500.0,
                       detection={"windows": 4000 + 100 * a, "anomalous_share": share, "fpr_benign": 0.021,
                                  "recall_injected": 0.91 if a else None, "by_category": cats},
                       banner={"samples": 11, "max_share": banner_max, "share_above": above,
                               "first_alert_s": 330 if above else None}))
    runs["E3"] = e3
    for exp, rs in runs.items():
        if only and exp not in only:
            continue
        BR.write_json(results / f"{exp}-{stamp}.json", BR.experiment_report(exp, rs, 600, 60))
    # raw CSVs used by the timeline (P1) and recovery (REC) figures
    p1 = runs["P1"][0]["run_id"]
    BR.write_csv(results / "raw" / p1 / "samples.csv",
                 [{"t_s": t, "evs": 10_000 + (t % 90) * 10, "batches": 30, "p95_median_ms": 2800 + (t % 60) * 5,
                   "p95_max_ms": 4000} for t in range(0, 600, 30)], BR.SAMPLE_FIELDS)
    rec = runs["REC"][0]["run_id"]
    batches = [(T0 + i * 1000, 1100.0) for i in range(1, 300)] + [(T0 + 314_000, 9000.0), (T0 + 315_000, 4200.0)]
    batches += [(T0 + (316 + k) * 1000, 1150.0 if k > 4 else 2100.0) for k in range(284)]
    BR.write_csv(results / "raw" / rec / "metrics.csv",
                 [{"run_id": rec, "batch_ts": ts, "input_rows": 5000, "latency_p95_ms": p, "windows_written": 40}
                  for ts, p in batches], BR.METRICS_FIELDS)
    return results
