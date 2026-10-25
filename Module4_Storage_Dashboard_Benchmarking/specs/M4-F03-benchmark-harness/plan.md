# Plan: M4-F03 — Benchmark Harness (REPLICA)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Stack | Standard library (`subprocess`, `signal`, `statistics`), cassandra-driver via M4-F01 `StoreReader`. No new dependencies |

## Design
| Component | File | Notes |
|---|---|---|
| Plans | `bench.EXPERIMENTS`, `RunSpec`, `plan(experiment, levels, stamp)` | Pure. Run IDs per C-06 §6 |
| Metric maths | `summarize_metrics`, `samples`, `efficiency`, `detection`, `recovery` | Pure functions over C-05 / C-04 dict rows (epoch ms) |
| Orchestration | `Runner(cli, store, clock, results_dir)` | `cli` = subprocess adapter (fake in tests). `store` = `StoreReader`-like |
| Output | `write_raw`, `experiment_report` | JSON + CSV + Markdown |
| CLI | `main()` → `python -m ids_monitor.bench` | Last stdout line = C-06 summary (`runs`, `results_dir`) |

## Run sequence (one level)
1. `ids_ingest.topic_admin --partitions P --recreate` (M1)
2. `ids_stream.job --executors E --trigger T --run-id RID --await-seconds <budget> --starting-offsets earliest` (M3, background)
3. Wait for the `ids.runs` row of RID (≤ 180 s), plus 10 s for the query to start
4. `ids_ingest.producer --days Monday --rate R --duration D --run-id RID [--attack-mode mixed --attack-share S]` (M1, background). REC: at D/2,
   `ids_ingest.platform restart-worker --index 1`
5. Drain: poll C-05 until the newest input batch is ≥ 8 s old (≤ 120 s)
6. SIGINT to the job wrapper (it SIGTERMs the driver, S-053). Wait ≤ 120 s, then a second SIGINT
7. Collect C-05 (+ C-04 for E3) → maths → raw files

## Budget
16 runs × (D + about 90 s overhead): at D = 600 s, about 3 h. Run it in the background with no other heavy work, since the host CPU is shared with the Colima VM.
