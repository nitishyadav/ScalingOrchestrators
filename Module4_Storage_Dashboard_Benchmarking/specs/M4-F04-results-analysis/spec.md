# Spec: M4-F04 — Results Analysis and Figures (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Feature ID | M4-F04 |
| Status | **Implemented (replica)** 2026-10-25 |
| Version | 0.1.0-replica |
| Proposal trace | §3.2–3.3 metrics table (P1–P5, F2, F5), Week 8–9 (results, figures for the report) |
| Inputs | M4-F03 outputs only: `RESULTS_DIR/<EXP>-<stamp>.json` and `RESULTS_DIR/raw/<run_id>/{samples,metrics}.csv` |

## 1. Summary
`python -m ids_monitor.analyze` reads the newest report per experiment and writes a scorecard (each target with its
value, source run and PASS/FAIL) plus 5 figures for the final report: scaling (E1, E2), latency by trigger (LAT),
detection vs attack share (E3), a throughput/latency timeline (P1) and recovery (REC). A missing experiment is reported as "not run", never an error.

## 2. Functional requirements
| ID | Requirement |
|---|---|
| M4-FR-030 | `latest_reports(dir)`: newest `<EXP>-<YYYYMMDDHHMM>.json` per experiment (top level only, so `smoke/` is ignored) |
| M4-FR-031 | Scorecard rows: P1 (P1 run), P2 (LAT at the configured 1 s trigger, plus the best trigger), P3 (E1 efficiency at 4), P4 (E2 efficiency at 4), P5 (REC recovered_s), F2 (E3 0 % benign window FPR), F5 (E3 100 % banner alert fraction, and 20 % share for context) |
| M4-FR-032 | Figures (PNG, light; dataviz palette slot 1 `#2a78d6`, slot 2 `#eb6834`; muted dashed rules for targets; no dual axes; legends when ≥ 2 series): `scaling.png` (2 panels, capacity vs N with the ideal-linear reference), `latency.png` (median and worst per-batch p95 per trigger, 500 ms rule), `detection.png` (anomalous-window share and banner max share vs attack share, 15 % rule), `timeline.png` (P1: ev/s and p95 per 30 s sample, 2 stacked panels), `recovery.png` (REC per-batch p95 over time, restart marker) |
| M4-FR-033 | Output `RESULTS_DIR/analysis/RESULTS-<date>.md` (+ `.json`, `figures/`). Last stdout line = C-06 summary |

## 3. Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M4-F04-AC-01 | `latest_reports` picks the newest per experiment and ignores `smoke/` | unit | ✅ `test_latest_reports_ignores_older_and_smoke` |
| M4-F04-AC-02 | Scorecard from synthetic reports: values, PASS/FAIL, "not run" rows | unit | ✅ `test_scorecard` |
| M4-F04-AC-03 | Figures and markdown written from synthetic reports and raw CSVs; missing raw data skips a figure without failing | unit | ✅ `test_figures_and_markdown`; figures checked visually on the smoke results |
| M4-F04-AC-04 | Run on the full M4-F03 results; figures checked visually | measurement | ⬜ |
