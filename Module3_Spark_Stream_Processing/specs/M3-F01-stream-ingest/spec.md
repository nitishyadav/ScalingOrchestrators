# Spec: M3-F01 — Stream Ingest (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Shared plan and tasks: [M3-F01 plan](../M3-F01-stream-ingest/plan.md).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · 0.1.0-replica |
| Trace | §2.1 (Structured Streaming subscribes to the Kafka topic), Week 5–6 (1 min watermark), C-01, C-06 |

| ID | Requirement |
|---|---|
| M3-FR-001 | Read `KAFKA_TOPIC` from `kafka:29092` (C-06 in-network address) with a configurable `startingOffsets` (latest/earliest), `failOnDataLoss=false` |
| M3-FR-002 | Parse values with the C-01 schema (`from_json`). Drop records that are not JSON or that violate C-01 required fields or ranges, and count them (observed metrics). Never fail the query on bad data |
| M3-FR-003 | Event time = `timestamp_millis(timestamp)`, watermark 60 s (C-02) |
| M3-FR-004 | The job is launched only via `python -m ids_stream.job` (C-06 §5), which submits from `spark-client` (ADR-009) with `--executors`, `--trigger`, `--run-id`, `--await-seconds` |

| AC | Criterion | Type | Status |
|---|---|---|---|
| M3-F01-AC-01 | The Spark schema DDL equals the C-01 fields and types. The validity filter covers every C-01 range rule | unit/contract | ✅ `test_event_ddl_matches_c01`, `test_validity_filter_covers_c01_rules` |
| M3-F01-AC-02 | The job CLI builds the right `spark-submit` (cores.max = executors × cores, py-files, container paths). Bad flags → 2. Missing bundle or container → 1 | unit | ✅ `test_job_cli.py` (5 tests) |
| M3-F01-AC-03 | Live: malformed messages mixed into the topic are dropped and counted, and the query keeps running | integration | ✅ `test_end_to_end_with_injection_and_malformed_input` (5 malformed dropped and counted, query kept running) |
