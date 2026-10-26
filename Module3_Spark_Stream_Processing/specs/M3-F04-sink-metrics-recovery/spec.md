# Spec: M3-F04 — Sink, Metrics, Recovery (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Shared plan and tasks: [M3-F01 plan](../M3-F01-stream-ingest/plan.md).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · 0.1.0-replica |
| Trace | §2.1 (results written to Cassandra), §3.1 (latency = event timestamp vs detected_at; throughput from the query listener), P2, P5, C-04, C-05 |

| ID | Requirement |
|---|---|
| M3-FR-031 | `foreachBatch`: upsert scored windows into `ids.window_scores` via the Spark-Cassandra connector, with `detected_at` = batch write time, `date_bucket`/`hour` from `window_end` UTC, `bundle_version`, `run_id` |
| M3-FR-032 | One `ids.pipeline_metrics` row per micro-batch (`StreamingQueryListener` progress + batch stats). Latency per D-01 with nearest-rank percentiles (null when nothing was written). One `ids.runs` row at start |
| M3-FR-033 | Checkpoint at `CHECKPOINT_DIR/<run_id>` (shared mount). Survive a worker restart and keep producing batches (P5) |
| M3-FR-034 | Graceful stop on SIGTERM or `--await-seconds`: stop the query, flush the metrics, print a C-06 summary (`batches`, `rows_written`) |

| AC | Criterion | Type | Status |
|---|---|---|---|
| M3-F04-AC-01 | Store and metrics row builders produce exactly the C-04/C-05 columns. Percentiles follow `ids_contracts.metrics.percentile` | unit/contract | ✅ `test_batch_stats_and_metrics_row`, `test_output_columns_equal_c04_c05` |
| M3-F04-AC-02 | **End-to-end live:** producer (with injection) → Kafka → this job → Cassandra. The rows validate as C-04, the injected SYN-flood and port-scan sources are flagged, metrics rows have latency, the run row exists | integration | ✅ `test_end_to_end_with_injection_and_malformed_input`: 5,223 windows, all injected SYN-flood + port-scan sources flagged, 21 metrics rows |
| M3-F04-AC-03 | **Recovery (P5):** `docker restart` of a worker mid-run, and new metrics batches still arrive within 30 s | integration | ✅ `test_recovery_after_worker_restart`: first batch 0.38 s after restart |
