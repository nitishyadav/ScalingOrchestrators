# Spec: M4-F03 — Benchmark Harness (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Feature ID | M4-F03 |
| Status | **Draft → Implemented (replica)** 2026-10-25 |
| Version | 0.1.0-replica |
| Proposal trace | §3.2 P1–P5, §3.3 F2/F5, Week 8 (scripted E1/E2/E3, 10 min runs, 30 s samples, p95 latency, efficiency, raw results), PROJECT_PLAN D-05, D-12/ADR-013, D-13 |
| Contracts | C-06 rc.7 (drives M1 `topic_admin`, `producer`, `platform restart-worker` and M3 `job` only through their CLIs; run IDs §6), C-05 (reads `pipeline_metrics`, `runs`), C-04 (reads `window_scores` for detection) |

## 1. Summary
`python -m ids_monitor.bench --experiment E1|E2|E3|P1|LAT|REC` runs each level of an experiment end to end on the live platform:
recreate the topic with N partitions → start the stream job (executors, trigger) → wait for it to register → replay at the rate
(with attack injection for E3) for `--duration` s → drain → stop the job gracefully → collect C-05 metrics (and C-04 windows for E3) →
write raw results and a per-experiment summary. `--dry-run` prints the plan and commands without running anything.

## 2. Experiments (levels)
| Experiment | Varies | Fixed | Answers |
|---|---|---|---|
| E1 | partitions {1, 4, 8, 16} | 2 executors, 5,000 ev/s, no attacks | P3 (efficiency 1 → 4 partitions ≥ 0.5) |
| E2 | executors {1, 2, 4} | 8 partitions, 5,000 ev/s | P4 (efficiency 1 → 4 executors ≥ 0.5) |
| E3 | attack share {0, 5, 20, **100**} % (mixed) | 8 partitions, 2 executors, 5,000 ev/s | F2 (0 % = benign-only run, window FPR < 5 %), F5 (banner; 100 % = all-attack load, ADR-013), detection per level |
| P1 | — | 16 partitions × 4 executors, **12,000 ev/s** | P1 (sustained ≥ 10,000 ev/s) |
| LAT | trigger {1 s, 500 ms, 250 ms} | 8 partitions, 2 executors, 5,000 ev/s | P2 (p95 < 500 ms), D-13 |
| REC | — | 8 × 2, 5,000 ev/s; worker 1 restarted at 50 % of the run | P5 (recovery < 30 s) |

All replay uses `--days Monday` (looped). The background is then benign, so E3's attack share is exactly the injected share and E3-0 % is the F2 benign-only run.

## 3. Functional requirements
| ID | Requirement | Trace |
|---|---|---|
| M4-FR-020 | Run IDs follow C-06 §6: `<EXP>-p<P>-e<E>-r<R>-a<A>[-t<ms>]-<YYYYMMDDHHMM>` (UTC). `-t` only for LAT | C-06 |
| M4-FR-021 | Each run invokes only C-06 CLIs (subprocesses), never module internals. Each CLI's last stdout line (JSON summary) is kept | Art. III (plug and play) |
| M4-FR-022 | Steady state = batches from producer start + `--warmup` (default 60 s) to producer end. Per run: **sustained input rate** (Σ input rows / steady span), **capacity** (median `processed_rows_per_sec` over steady batches with input), **p95 latency** (median of per-batch `latency_p95_ms`, D-01) and the worst per-batch p95 (95th percentile of them), median batch duration, `keeping_up` (sustained ≥ 95 % of target) | P1, P2 |
| M4-FR-023 | 30 s samples (proposal): per 30 s bin, ev/s (Σ input/30), median capacity, median and max per-batch p95 | Week 8 |
| M4-FR-024 | Efficiency for E1/E2 = (C_N / C_1) / (N / 1), with C = capacity. Sustained input is fixed at 5,000 ev/s in E1/E2, so it cannot show scaling; the summary states this | P3, P4, D-05 |
| M4-FR-025 | E3 detection from C-04 rows of the run: windows, anomalous share, injected-window recall (`label_type` `INJ_*`), benign-window FPR (`label_attack` false), CIC-attack windows, and the banner: the 300 s rolling anomalous share sampled every 30 s (max, and the fraction of samples above 15 %) | F2, F5, ADR-013 |
| M4-FR-026 | REC: restart `--index 1` at 50 % of the run. Report: first input batch after the restart (s), the largest gap between input batches, and **recovered_s** = time until 3 consecutive batches have p95 ≤ max(2 × pre-restart median, pre + 1 s) | P5 |
| M4-FR-027 | Raw results in `RESULTS_DIR/raw/<run_id>/`: `config.json`, `producer.json`, `job.json`, `metrics.csv`, `samples.csv`, `summary.json`, (`detection.json`, `recovery.json`), `*.log`. Experiment summary `RESULTS_DIR/<EXP>-<stamp>.{json,md}` | Week 8 |
| M4-FR-028 | Ctrl-C stops the producer and the job gracefully, keeps what was collected, marks the run `interrupted`, and stops the experiment. A failed run (CLI exit ≠ 0) is recorded and the experiment continues | Art. VIII |
| M4-FR-029 | `--levels a,b` restricts the levels (smoke tests). `--duration`, `--warmup`. `--dry-run` prints run IDs and commands, and touches nothing | C-06 |

## 4. Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M4-F03-AC-01 | Plans: levels, run-ID format (valid per C-06), `--levels` filter, dry-run prints commands and runs nothing | unit | ✅ `test_plans_levels_and_run_ids`, `test_commands_use_only_c06_clis`, `test_dry_run_prints_plan_and_runs_nothing`, `test_bad_level_is_usage_error` |
| M4-F03-AC-02 | Metric maths on synthetic C-05 rows: steady-state selection, sustained rate, capacity, p95, 30 s samples, efficiency | unit | ✅ `test_summary_steady_state_capacity_and_latency`, `test_summary_detects_backlog`, `test_30s_samples`, `test_efficiency` |
| M4-F03-AC-03 | Detection and banner maths on synthetic C-04 rows; recovery maths on synthetic metrics with a gap | unit | ✅ `test_detection_rates_and_banner`, `test_recovery_after_restart` |
| M4-F03-AC-04 | Orchestration with fake CLIs: call order (topic → job → registered → producer → drain → stop job → collect), raw files written, failed CLI recorded, interrupt handling | unit | ✅ `test_orchestration_order_and_raw_files`, `test_failed_cli_is_recorded_and_experiment_continues`, `test_interrupt_stops_children_and_experiment`, `test_recovery_run_restarts_worker` |
| M4-F03-AC-05 | Live smoke: E1 with `--levels 1 --duration 60` on the platform completes and writes valid raw results | integration | ✅ `test_ac05_smoke_run_writes_valid_raw_results` (76 s); manual smokes E1-1, E3-100, REC (2026-10-25, `results/smoke/`) |
| M4-F03-AC-06 | Full runs E1, E2, E3, P1, LAT, REC at 600 s, with results in `results/` | measurement | ⬜ |

## 5. Out of scope
Figures and the results analysis (M4-F04). Changing defaults (for example `TRIGGER_INTERVAL`) from the results is a C-06 CR.

## 6. Change log
| Version | Date | Change |
|---|---|---|
| 0.1.0-replica | 2026-10-25 | Initial replica spec |
