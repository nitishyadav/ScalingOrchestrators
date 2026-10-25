-- C-05 Pipeline Metrics (owner M3) — PROVISIONAL REPLICA 0.1.0-replica, authored by M1 (Aswin). Replace at v1.0.
-- Idempotent; safe to apply before or after ids_schema.cql.
CREATE KEYSPACE IF NOT EXISTS ids
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS ids.pipeline_metrics (
  run_id                 text,
  batch_ts               timestamp,
  batch_id               bigint,
  input_rows             bigint,
  input_rows_per_sec     double,
  processed_rows_per_sec double,
  batch_duration_ms      bigint,
  latency_p50_ms         double,
  latency_p95_ms         double,
  latency_max_ms         double,
  windows_written        int,
  anomalies_written      int,
  kafka_partitions       int,
  executors              int,
  PRIMARY KEY ((run_id), batch_ts)
) WITH CLUSTERING ORDER BY (batch_ts DESC);

CREATE TABLE IF NOT EXISTS ids.runs (
  bucket      text,
  started_at  timestamp,
  run_id      text,
  config_json text,
  PRIMARY KEY ((bucket), started_at)
) WITH CLUSTERING ORDER BY (started_at DESC);
