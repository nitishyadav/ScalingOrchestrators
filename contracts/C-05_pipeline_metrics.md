# Contract C-05: Pipeline Metrics

> **PROVISIONAL REPLICA.** Authored by Aswin S. (M1) in replica mode from the playbook §5.6 (D-01, D-10). The canonical owner,
> **Kumari Priyanka (M3)**, authors and approves v1.0, and this file is then replaced.

| Field | Value |
|---|---|
| Contract ID | C-05 |
| Version | 0.1.0-replica |
| Status | **Provisional (replica)** |
| Provider (owner) | M3: Kumari Priyanka (this draft by M1) |
| Consumers | M4 (dashboard throughput, benchmark harness) |
| Medium | Cassandra tables `ids.pipeline_metrics`, `ids.runs` |
| DDL | `schemas/metrics_schema.cql` (idempotent. Applied live on 2026-10-22) |
| Code | `ids_contracts.metrics` (`METRICS_COLUMNS`, `RUNS_COLUMNS`, `percentile`, validators) |
| Decisions applied | D-01 (latency definition), D-10 (metrics transport) |

## 1. Purpose
This contract makes the stream job's throughput and latency visible to the dashboard and the benchmark harness without either
reading Spark internals.

## 2. Tables
- `pipeline_metrics`: **one row per micro-batch**, `PRIMARY KEY ((run_id), batch_ts)`, newest first.
- `runs`: **one row per stream-job start**, `PRIMARY KEY ((bucket), started_at)` with `bucket = 'all'`, newest first. `config_json` holds partitions,
  executors, rate, attack mode and share, bundle_version and trigger.

## 3. Semantics
| Field | Definition |
|---|---|
| `batch_ts` | Micro-batch end time (UTC) |
| `input_rows`, `input_rows_per_sec`, `processed_rows_per_sec`, `batch_duration_ms` | From Spark `StreamingQueryProgress` (`numInputRows`, `inputRowsPerSecond`, `processedRowsPerSecond`, `durationMs.triggerExecution`) |
| `windows_written`, `anomalies_written` | C-04 rows upserted in this batch, and how many have `is_anomaly` |
| `latency_*_ms` | **D-01:** for every C-04 row written in the batch, `detected_at − max_event_ts`. p50/p95/max over those rows with **nearest-rank** percentiles (`ids_contracts.metrics.percentile`). **Null** when no rows were written |
| `kafka_partitions`, `executors` | Run configuration tags (for E1/E2) |

The P2 target (p95 < 500 ms at 5,000 ev/s) is evaluated on `latency_p95_ms` across the run's batches. The aggregation (for example the median of batch p95s,
or a recomputation from C-04 rows) is defined by M4-F03.

## 4. Approvals
| Role | Member | Version | Date |
|---|---|---|---|
| Provider | Kumari Priyanka (M3) | — | |
| Consumer | Vidhi Kant Gupta (M4) | — | |
| Replica author | Aswin S. (M1) | 0.1.0-replica | 2026-10-22 |

## 5. Change log
| Version | Date | Change |
|---|---|---|
| 0.1.0-replica | 2026-10-22 | Provisional replica from the playbook §5.6. DDL applied live |
