-- C-04 Anomaly Store (owner M4) — PROVISIONAL REPLICA 0.1.0-replica, authored by M1 (Aswin). Replace at v1.0.
-- Applied by M4-F01's init step; idempotent.
CREATE KEYSPACE IF NOT EXISTS ids
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS ids.window_scores (
  date_bucket    text,
  hour           int,
  window_end     timestamp,
  src_ip         text,
  window_start   timestamp,
  total_bytes    bigint,
  unique_ports   int,
  syn_ack_ratio  double,
  packet_rate    double,
  event_count    int,
  anomaly_score  double,
  ml_flag        boolean,
  rule_flag      boolean,
  rule_ids       text,
  is_anomaly     boolean,
  max_event_ts   timestamp,
  detected_at    timestamp,
  bundle_version text,
  run_id         text,
  label_attack   boolean,
  label_type     text,
  PRIMARY KEY ((date_bucket, hour), window_end, src_ip)
) WITH CLUSTERING ORDER BY (window_end DESC, src_ip ASC)
  AND default_time_to_live = 604800;
