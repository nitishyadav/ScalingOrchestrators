# Plan: M4-F03 — Benchmark harness

| Field | Value |
|---|---|
| Spec | 1.0.0 (Approved 2026-11-01) |
| Status | **Approved** |
| Stack | Standard library only (`subprocess`, `signal`, `statistics`, `csv`, `json`). C-05/C-04 via M4-F01 `Store`. No new dependency |

## 1. Components
| File | Contents | Pure? |
|---|---|---|
| `src/ids_monitor/bench_plan.py` | `EXPERIMENTS` (§5 table), `RunSpec`, `plan(exp, levels)`, `run_id(spec, stamp)`, `commands(spec, run_id, duration, budget_s)` | yes |
| `src/ids_monitor/bench_math.py` | `steady`, `summarize` (FR-043/044), `samples` (FR-045), `efficiency` (FR-046), `detection` + `banner` (FR-047), `recovery` (FR-048) | yes |
| `src/ids_monitor/bench_report.py` | `write_raw(dir, …)` (FR-049), `experiment_report(…)` → dict, `report_markdown(dict)`, `checks(exp, runs)` | file I/O only |
| `src/ids_monitor/bench.py` | adapters (`SubprocessCli`, `SystemClock`), `Runner` (FR-042, 050), `main()` (FR-051) | no |

## 2. Adapters (NFR-021)
- **cli:** `run(argv, log) → (exit_code, summary_dict | None)` for short commands; `start(argv, log) → handle` with `poll()`, `wait(timeout)`,
  `interrupt()` (SIGINT), `kill()`, `summary()` for the job and the producer. Commands are `[sys.executable, "-m", module, *flags]`,
  run from the workspace root with the parent environment (C-06 config is read by each CLI itself).
- **store:** `latest_runs`, `latest_metrics(run_id, limit)`, `read_windows(start, end, run_id)` (M4-F01 `Store`).
- **clock:** `now_ms()`, `sleep(s)`. Tests use a fake clock that advances on `sleep`, and a fake CLI that writes C-05 rows into a fake store.

## 3. Level sequence (FR-042)
| Step | Action | Timeout |
|---|---|---|
| 1 | `ids_ingest.topic_admin --partitions P --recreate` | 120 s |
| 2 | start `ids_stream.job --executors E --trigger T --run-id RID --await-seconds <D + 600>` | — |
| 3 | poll `runs` for RID every 2 s, then sleep 10 s | 180 s |
| 4 | start `ids_ingest.producer --source replay --days Monday --rate R --duration D --run-id RID --seed 42 [--attack-mode mixed --attack-share S]` | — |
| 5 | REC: at D/2, `ids_ingest.platform restart-worker --index 1` | 180 s |
| 6 | wait for the producer | D + 120 s |
| 7 | drain: poll metrics every 2 s until the newest input batch is ≥ 10 s old | 120 s |
| 8 | SIGINT job; second SIGINT after 120 s; kill after 30 s more | 150 s |
| 9 | collect metrics (limit 100,000), windows (E3), compute, write raw | — |

Ctrl-C at any step: interrupt producer and job (step 8 logic), collect, mark `interrupted`, stop.

## 4. Raw layout (FR-049)
`results/raw/<RID>/{config.json, commands.json, topic_admin.json, job.json, producer.json, restart.json, *.log, metrics.csv, samples.csv, summary.json, detection.json, recovery.json}`
and `results/<EXP>-<YYYYMMDDHHMM>.{json,md}`.

## 5. Risks
| Risk | Mitigation |
|---|---|
| Producer cannot reach 15,000 ev/s | `producer_bound` flag, ADR-002 interpretation rules |
| Full run ≈ 3.5 h | `--levels` smoke first; run in the background, platform otherwise idle |
| M3 replica job replaced at integration | Only C-06 flags used; preflight `--help` check |
