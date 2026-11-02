# Spec: M4-F04 — Results and report figures

| Field | Value |
|---|---|
| Feature ID | M4-F04 |
| Module | Module4_Storage_Dashboard_Benchmarking |
| Owner | Vidhi Kant Gupta |
| Reviewers | Team (the report uses these numbers and figures) |
| Status | **Implemented** (2026-11-01): AC-01..05 ✅. AC-06 after the P3 runs |
| Version | 1.0.0 |
| Created / Updated | 2026-11-01 / 2026-11-01 |
| Proposal trace | §3.2–3.3 success metrics (P1–P5, F2–F5), Week 8–9 (results, figures for the report), PROJECT_PLAN M4-F04 (scaling plots, online rule-vs-hybrid table, F2 benign run, consolidated results) |
| Inputs | M4-F03 outputs only: `RESULTS_DIR/<EXP>-<YYYYMMDDHHMM>.json` and `RESULTS_DIR/raw/<run_id>/{samples,metrics}.csv` |
| Decisions applied | M4-ADR-002 (lower-bound / inconclusive efficiency), D-05, ADR-013 |

## 1. Summary
`python -m ids_monitor.analyze` reads the newest M4-F03 report per experiment and writes, to `RESULTS_DIR/analysis/`:
- a **scorecard** with every success metric, its value, its verdict and the run it came from;
- the **F3 table** (rule-only vs ML-only vs hybrid, per attack category, online);
- six **figures** for the report, as PNG and SVG;
- one Markdown file, `RESULTS.md`, that the report can quote directly.

A missing experiment shows as "not run", never as an error. Nothing is measured here: every number comes from M4-F03 files.

## 2. Context
The replica's analysis (`runtime/reference/m4-replica/`) had no F3 table, used capacity for scaling (see M4-ADR-002) and showed a P2 of 115 s
on a linear axis, which hid everything else. This version keeps verdicts identical to the M4-F03 report checks (single source of truth),
shows lower bounds and inconclusive results explicitly, and uses a log axis when values span more than 50×.

## 3. Scope
**In:** scorecard, F3 table, figures, `RESULTS.md`. **Out:** running experiments (M4-F03), the report text, F1 (offline, M2).

## 4. Functional requirements
| ID | Requirement | Priority | Trace |
|---|---|---|---|
| M4-FR-060 | `latest_reports(dir)`: for each experiment, the newest `<EXP>-<YYYYMMDDHHMM>.json` in `dir` itself (subfolders such as `smoke/` and `raw/` are ignored). Unparseable files are skipped with a warning | P0 | — |
| M4-FR-061 | Scorecard rows P1, P2, P3, P4, P5, F2, F3, F4, F5: metric, target, value, verdict (`PASS`, `FAIL`, `UNKNOWN`, `NOT RUN`), source run IDs and a note. Verdicts come from the M4-F03 report's `checks` (no re-computation): P1 ← P1; P2 ← LAT at 1000 ms (the C-06 default trigger; the best trigger is noted); P3 ← E1; P4 ← E2; P5 ← REC; F2 ← E3 0 %; F5 ← E3 (no banner at 0 % **and** a banner at 20 % and 100 %). `UNKNOWN` when the check passed is null (lower bound not met, inconclusive) | P0 | proposal §3.2–3.3 |
| M4-FR-062 | F3: the E3 per-category rows of all attack levels (5, 20, 100 %) are summed per category (flagged / windows), giving one table: category, windows, rule %, ML %, hybrid %. BENIGN comes from the 0 % level and is labelled as FPR. The F3 verdict is `PASS` (produced) when at least one attack category has windows | P0 | F3 |
| M4-FR-063 | F4 is measured by M4-F02 (AC-08), not by the harness. The row reads `RESULTS_DIR/evidence/F4.json` (`{"worst_case_s": …, "measured": "<date>", "source": …}`) when present (PASS when ≤ 5 s), otherwise `NOT RUN` with a pointer to M4-F02 AC-08 | P1 | F4 |
| M4-FR-064 | Figures (light, for print; dataviz reference palette: slot 1 `#2a78d6`, slot 2 `#eb6834`, slot 3 `#1baf7a`, validated all-pairs; targets as muted dashed rules with a direct label; one y-axis per panel; a legend whenever there are ≥ 2 series; value labels on bars): **scaling** (E1 and E2 panels: sustained ev/s vs N, ideal-linear reference from level 1, hollow markers for lower bounds), **latency** (LAT: median and tail p95 per trigger, 500 ms rule), **detection** (E3: anomalous share and banner max vs attack share, 15 % rule), **f3** (grouped bars per category × rule/ML/hybrid), **timeline** (P1: ev/s and p95 per 30 s sample, 2 stacked panels sharing x), **recovery** (REC: per-batch p95 over time, restart and recovery markers, threshold rule). A log y-axis is used when the plotted values span > 50× and the axis says so. A figure whose data is missing is skipped and listed in `RESULTS.md` | P0 | Week 8–9 |
| M4-FR-065 | Output: `RESULTS_DIR/analysis/{RESULTS.md, scorecard.json, f3.csv, figures/<name>.{png,svg}}`. `RESULTS.md` = scorecard table, F3 table, per-experiment links to the M4-F03 reports, the figures, and the list of skipped figures. Re-running on the same inputs gives byte-identical files | P0 | NFR-031 |
| M4-FR-066 | CLI `python -m ids_monitor.analyze` (C-06 conventions): exit 0 (also when nothing ran), 1 on a runtime error. Last stdout line = summary with `experiments`, `verdicts` (`{id: verdict}`), `figures`, `skipped`, `results_md`. `make analyze` | P0 | C-06 §5 conventions |

## 5. Non-functional requirements
| ID | Requirement |
|---|---|
| M4-NFR-030 | Analysis of a full result set (6 experiments) ≤ 30 s |
| M4-NFR-031 | Deterministic output (fixed SVG hash salt, no timestamps in image metadata) so result files diff cleanly in git |
| M4-NFR-032 | Pure functions for selection, scorecard and F3; figure functions take plain data, so all of it is unit-tested without the platform |

## 6. Acceptance criteria
| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M4-F04-AC-01 | **Given** several reports per experiment, a `smoke/` copy and a broken file **Then** the newest valid one per experiment is chosen | FR-060 | unit | ✅ `unit/test_analyze.py::test_latest_reports_newest_per_experiment` |
| M4-F04-AC-02 | **Given** synthetic M4-F03 reports **Then** each scorecard row has the value, verdict and source of §4 (incl. UNKNOWN for a lower bound, NOT RUN for missing experiments, F4 from evidence) | FR-061, 063 | unit | ✅ `unit/test_analyze.py::test_scorecard_values_verdicts_sources`, `::test_lower_bound_is_unknown_and_missing_is_not_run`, `::test_f4_from_evidence` |
| M4-F04-AC-03 | **Given** E3 reports **Then** the F3 table sums per category across attack levels and takes BENIGN from 0 % | FR-062 | unit | ✅ `unit/test_analyze.py::test_f3_table_sums_attack_levels_and_benign_from_0` |
| M4-F04-AC-04 | **Given** synthetic reports and raw CSVs **Then** the 6 figures are written (PNG + SVG), follow the palette, have one y-axis per panel, use a log axis only when values span > 50×; missing data skips a figure | FR-064 | unit | ✅ `unit/test_figures.py` (6 tests); visual check of all 6 figures on the synthetic set (2026-11-01, see dev log S-012) |
| M4-F04-AC-05 | **Given** the same inputs twice **Then** outputs are byte-identical. **Given** an empty results dir **Then** exit 0, every row NOT RUN | FR-065, 066, NFR-031 | unit + contract | ✅ `unit/test_analyze.py::test_outputs_and_determinism`, `::test_empty_results_dir`; `contract/test_analyze_cli.py` |
| M4-F04-AC-06 | **Given** the full M4-F03 results **Then** `RESULTS.md` and figures are produced and checked visually | all | measurement | ⬜ after M4-F03 AC-09 |

## 7. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Initial approved version |
