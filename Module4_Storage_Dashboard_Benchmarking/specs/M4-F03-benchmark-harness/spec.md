# Spec: M4-F03 — Benchmark harness

| Field | Value |
|---|---|
| Feature ID | M4-F03 |
| Module | Module4_Storage_Dashboard_Benchmarking |
| Owner | Vidhi Kant Gupta |
| Reviewers | Aswin S. (M1, producer/platform CLIs), Kumari Priyanka (M3, stream job CLI, C-05) |
| Status | **Implemented** (2026-11-01): AC-01..07 ✅. AC-08 (live smoke) and AC-09 (full runs) need the platform (I-03 / P3) |
| Version | 1.0.0 |
| Created / Updated | 2026-11-01 / 2026-11-01 |
| Proposal trace | §3.2 P1–P5, §3.3 F2/F5, Week 8 (scripted E1/E2/E3, 10 min runs, 30 s samples, p95 latency, efficiency, raw results) |
| Contracts touched | C-06 1.0.0-rc.7 (drives M1 `topic_admin`, `producer`, `platform restart-worker` and M3 `job` through their CLIs; run IDs §6; `ids_monitor.bench` §5), C-05 0.1.0-replica (reads), C-04 1.0.0-rc.1 (reads, E3) |
| Decisions applied | D-01 (latency), D-05 (≥ 0.5 target, ≥ 1.5× minimum), D-13 (P2 at 1 s trigger), ADR-013 (drift), **M4-ADR-002** (throughput and latency method) |

## 1. Summary
`python -m ids_monitor.bench --experiment E1|E2|E3|P1|LAT|REC` runs every level of an experiment end to end on the live platform and saves raw
results plus a per-experiment report. One level: recreate the topic → start the stream job → wait until it registers → replay for `--duration`
seconds → drain → stop the job gracefully → read C-05 (and C-04 for E3) → compute → write. `--dry-run` prints the plan and the exact commands
and touches nothing. Figures and the cross-experiment scorecard are M4-F04.

## 2. Context and motivation
Every number in the report comes from this harness (G5, P1–P5). Two lessons from the replica runs of 25 Oct (`runtime/reference/m4-replica/results/`)
shape this spec:
- **At a fixed 5,000 ev/s, scaling cannot be seen.** The replica took efficiency from Spark's per-batch `processed_rows_per_sec`.
  With small batches that mostly measures per-batch overhead, so more partitions looked *slower* (E1 efficiency 0.22). E1/E2 here
  run at a **saturating** rate and measure **sustained throughput**; a level that keeps up with the producer is flagged
  (its throughput is only a lower bound). See M4-ADR-002.
- **E1 with 2 executors caps the speedup at 2×** (2 task slots), so efficiency at 4 partitions could never exceed 0.5. E1 here uses 4 executors.

## 3. Scope
**In scope:** plans and run IDs, orchestration through C-06 CLIs only, metric maths, raw results, per-experiment JSON + Markdown report,
dry run, graceful interrupt. **Out of scope:** figures and the scorecard (M4-F04); changing C-06 defaults from the results (a CR); tuning M3.

## 4. User stories
- **US-1:** As the M4 owner, I run one command per experiment and get raw data and a report I can put in the report.
- **US-2:** As a reviewer, I can trace every number back to a run ID, its configuration and its raw per-batch metrics.
- **US-3:** As the owner, I can preview exactly what a run will do (`--dry-run`) and smoke-test one short level before a 3 h session.

## 5. Experiments
| Exp | Varies (levels) | Fixed | Rate (ev/s) | Answers |
|---|---|---|---|---|
| E1 | partitions 1, 4, 8, 16 | 4 executors, trigger 1 s | 15,000 (saturating) | P3: efficiency 1 → 4 partitions ≥ 0.5 (min 1.5×, D-05) |
| E2 | executors 1, 2, 4 | 8 partitions, trigger 1 s | 15,000 (saturating) | P4: efficiency 1 → 4 executors ≥ 0.5 |
| E3 | attack share 0, 5, 20, 100 % (`mixed`) | 8 × 2, trigger 1 s | 5,000 | F2 (0 % = benign-only window FPR), F5 (drift banner), detection per level |
| P1 | — | 16 partitions × 4 executors | 12,000 | P1: sustained ≥ 10,000 ev/s |
| LAT | trigger 1000, 500, 250 ms | 8 × 2 | 5,000 | P2: p95 < 500 ms (D-01), D-13 |
| REC | — | 8 × 2, worker 1 restarted at 50 % of the run | 5,000 | P5: recovery < 30 s |

Replay uses `--days Monday` (benign, looped), so E3's attack share is exactly the injected share. Defaults: `--duration` 600 s, `--warmup` min(60 s, duration / 4) (60 s at 600 s; 15 s for a 60 s smoke).

## 6. Functional requirements
| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M4-FR-040 | Run IDs follow C-06 §6: `<EXP>-p<P>-e<E>-r<R>-a<A>[-t<ms>]-<YYYYMMDDHHMM>` UTC (`-t` only for LAT) and are valid per `RUN_ID_PATTERN`. Two runs never share an ID | P0 | US-2 | C-06 §6 |
| M4-FR-041 | Each level drives only C-06 CLIs as subprocesses (`ids_ingest.topic_admin`, `ids_stream.job`, `ids_ingest.producer`, `ids_ingest.platform restart-worker`) with C-06 flags only, never module internals. Each CLI's JSON summary (last stdout line) and its logs are kept. A preflight checks that every needed CLI answers `--help` | P0 | US-1 | C-06 §5, Art. III |
| M4-FR-042 | Sequence per level: topic recreate with P partitions → start the job (executors, trigger, run ID) → wait until its C-05 `runs` row appears (≤ 180 s) + 10 s → start the producer (rate, duration, run ID, attack flags) → REC only: restart worker 1 at 50 % → wait for the producer → drain (until no input batch for 10 s, ≤ 120 s) → SIGINT the job (second SIGINT after 120 s, kill after 30 s more) → collect | P0 | US-1 | — |
| M4-FR-043 | Steady state = batches with `batch_ts` in [producer start + warm-up, producer end]. Per run: **sustained throughput** = Σ `input_rows` / steady span (ev/s); producer achieved rate (its summary); `producer_bound` = sustained ≥ 95 % of the producer's achieved rate; `backlog_s` = last input batch − producer end; median Spark `processed_rows_per_sec` (reported, not used for efficiency); median batch duration | P0 | US-1 | P1, M4-ADR-002 |
| M4-FR-044 | Latency per run (D-01, C-05 §3): **p95** = median of per-batch `latency_p95_ms` over steady batches that wrote rows (the P2 figure); also the 95th percentile of the per-batch p95s (tail) and the median p50 | P0 | US-1 | P2, M4-ADR-002 |
| M4-FR-045 | 30 s samples per run (proposal): per bin, ev/s (Σ input / 30), median per-batch p95, max per-batch p95, batches | P1 | US-2 | Week 8 |
| M4-FR-046 | Efficiency for E1/E2: speedup S(N) = T_N / T_1 and efficiency S(N) / N with T = sustained throughput. If level 1 is `producer_bound` the result is **inconclusive**; if level N is, the efficiency is a **lower bound** (shown as "≥") | P0 | US-1 | P3, P4, D-05 |
| M4-FR-047 | E3 detection from the run's C-04 rows: windows, anomalous share, recall on injected windows (`label_type` `INJ_*`), FPR on benign windows (`label_attack` false), and the drift banner as the 300 s rolling anomalous share sampled every 30 s (max, share of samples > 15 %). Eval-only columns are read only here | P0 | US-1 | F2, F5, ADR-013, ADR-007 |
| M4-FR-048 | REC: from the restart time, the first input batch after it, the largest gap between input batches, and **recovered_s** = time until 3 consecutive batches have p95 ≤ max(2 × pre-restart median, pre-restart median + 1,000 ms). P5 passes if recovered_s < 30 | P0 | US-1 | P5 |
| M4-FR-049 | Raw results in `RESULTS_DIR/raw/<run_id>/`: `config.json`, `commands.json`, `<cli>.json` summaries, `<cli>.log`, `metrics.csv`, `samples.csv`, `summary.json`, plus `detection.json` (E3) / `recovery.json` (REC). Experiment report `RESULTS_DIR/<EXP>-<stamp>.{json,md}` with a per-level table and pass/fail checks against P1–P5 / F2 | P0 | US-2 | Week 8 |
| M4-FR-050 | A failed level (a CLI exits ≠ 0, the job never registers, or no batches) is recorded with its reason and the experiment continues. Ctrl-C stops the producer and the job gracefully, keeps what was collected, marks the run `interrupted` and ends the experiment | P0 | US-1 | Art. VIII |
| M4-FR-051 | CLI: `--experiment` (required), `--levels a,b` (subset; unknown level = usage error, exit 2), `--duration` (→ `RUN_DURATION_S`), `--warmup` (default min(60, duration / 4), < duration), `--dry-run`. Exit 0 when every run is ok, 1 if any run failed, 0 with status `stopped` on Ctrl-C. Summary fields: `experiment`, `runs`, `failed`, `results_dir`, `report` | P0 | US-3 | C-06 §5 |

## 7. Non-functional requirements
| ID | Category | Requirement | Trace |
|---|---|---|---|
| M4-NFR-020 | Overhead | Harness overhead per level (excluding `--duration`) ≤ 120 s in the normal case | budget |
| M4-NFR-021 | Testability | Plans, maths and reports are pure; orchestration takes injected CLI, store and clock adapters, so every AC except AC-08/09 runs without the platform | Const. VIII |
| M4-NFR-022 | Reproducibility | Same plan + seed → same commands; every number in a report is recomputable from `metrics.csv` | US-2 |

## 8. Interfaces
**Provided:** `python -m ids_monitor.bench` (C-06 §5), `make bench EXP=…`, raw results and reports in `RESULTS_DIR`.
**Consumed:** C-06 CLIs of M1/M3 (subprocess), C-05 `pipeline_metrics` + `runs`, C-04 `window_scores` (E3) via M4-F01 `Store`.
Mocks until the platform is up: fake CLI/store/clock adapters in tests; `--dry-run`.

## 9. Acceptance criteria
| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M4-F03-AC-01 | **Given** each experiment **Then** the plan has the levels of §5, valid unique run IDs, and `--levels` filters them; an unknown level is a usage error | FR-040, 051 | unit | ✅ `unit/test_bench_plan.py::test_levels_*`, `::test_fixed_settings_*`, `::test_run_ids_*`, `::test_levels_filter_and_errors`; `contract/test_bench_cli.py` |
| M4-F03-AC-02 | **Given** a level **Then** its commands use only C-06 CLIs and flags, with the right values per experiment; `--dry-run` prints them and calls nothing | FR-041, 051 | unit | ✅ `unit/test_bench_plan.py::test_commands_*`, `::test_command_values`; `unit/test_bench_runner.py::test_dry_run_*` |
| M4-F03-AC-03 | **Given** synthetic C-05 rows with warm-up, idle and drain batches **Then** steady state, sustained throughput, producer_bound, backlog, p95 (median and tail) and 30 s samples are exact | FR-043, 044, 045 | unit | ✅ `unit/test_bench_math.py::test_steady_*`, `::test_summary_*`, `::test_saturated_*`, `::test_no_steady_*`, `::test_30s_samples` |
| M4-F03-AC-04 | **Given** throughputs per level **Then** speedup and efficiency are exact, with "≥" when level N is producer-bound and "inconclusive" when level 1 is | FR-046 | unit | ✅ `unit/test_bench_math.py::test_efficiency_*`; `unit/test_bench_report.py::test_scaling_*` |
| M4-F03-AC-05 | **Given** synthetic C-04 rows **Then** recall, FPR, anomalous share and banner samples are exact. **Given** metrics with a restart gap **Then** first batch, max gap and recovered_s are exact | FR-047, 048 | unit | ✅ `unit/test_bench_math.py::test_detection_rates`, `::test_banner_*`, `::test_recovery_*`; `unit/test_bench_report.py::test_p1_lat_e3_rec_checks` |
| M4-F03-AC-06 | **Given** fake CLIs **Then** the call order is topic → job → registered → producer → (restart) → drain → stop → collect; raw files and the report are written and parse | FR-042, 049 | unit | ✅ `unit/test_bench_runner.py::test_call_order_*`, `::test_e3_*_rec_*`; `unit/test_bench_report.py::test_markdown_*` |
| M4-F03-AC-07 | **Given** a CLI failing, a job that never registers, or Ctrl-C **Then** the run is recorded failed/interrupted with a reason, children are stopped, and the experiment continues (failure) or ends (Ctrl-C) with the documented exit code | FR-050, 051 | unit | ✅ `unit/test_bench_runner.py::test_failed_cli_*`, `::test_job_never_registers`, `::test_job_ignoring_sigint_is_killed`, `::test_interrupt_*`, `::test_preflight_*` |
| M4-F03-AC-08 | **Given** the platform is up **When** `bench --experiment E1 --levels 1 --duration 60` runs **Then** it completes and writes valid raw results | all | integration | 🟡 `integration/test_bench_live.py` written; skips: no platform, replay data, bundle, M1/M3 install (2026-11-01). Run at I-03 |
| M4-F03-AC-09 | **Given** the platform **When** E1, E2, E3, P1, LAT and REC run at 600 s **Then** the reports are in `results/` (feeds M4-F04) | all | measurement | ⬜ P3 phase (5–10 Nov) |

## 10. Edge cases
| Case | Expected |
|---|---|
| Producer ends before the job processes everything | Drain waits ≤ 120 s; `backlog_s` reports it |
| No steady batches (job died) | Run failed: "no batches in steady state" |
| A batch without written rows (latency null) | Excluded from latency, included in throughput |
| Same minute as the previous run | Wait for the next minute before starting (unique run IDs) |
| Topic shrink (16 → 1) | `--recreate` always (C-06 note) |

## 11. Assumptions
- The platform (`ids_ingest.platform up --workers 2`) is up and idle, and M1/M3 are installed in the same Python (`make install` in each).
- The producer can reach the saturating rate or close to it. If it cannot, `producer_bound` makes that visible.

## 12. Open questions
None. (M3's job also offers `--starting-offsets` and `--shuffle-partitions`, which are not in C-06. The harness does not use them.)

## 13. Review checklist
- [x] Every FR has at least one AC · [x] NFRs have numbers · [x] Contracts by ID and version · [x] Eval-only fields only for evaluation (FR-047)
- [ ] M1/M3 owners review the commands (at I-03)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Initial approved version |
