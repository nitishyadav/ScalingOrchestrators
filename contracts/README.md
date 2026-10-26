# Contracts — the only shared surface between modules

Modules depend on **contracts**, never on each other's code (Constitution Art. II–III).
Each contract is written from [../sdd/templates/contract-template.md](../sdd/templates/contract-template.md)
and must be **Approved v1.0** before code is written on either side of its seam.

## Registry

| ID | File | Provider | Consumers | Medium | Status |
|---|---|---|---|---|---|
| C-01 | [`C-01_network_event.md`](C-01_network_event.md) | M1 Aswin | M3, M2 | Kafka JSON + replay Parquet | **In Review 1.0.0-rc.5** |
| C-02 | [`C-02_feature_definition.md`](C-02_feature_definition.md) | M2 Nitish | M3 | Spec + golden CSV | 🔶 **Provisional replica 0.2.0** (by M1, owner to replace) |
| C-03 | [`C-03_detection_bundle.md`](C-03_detection_bundle.md) | M2 Nitish | M3 | File bundle | 🔶 **Provisional replica 0.2.0** (by M1, owner to replace) |
| C-04 | [`C-04_anomaly_store.md`](C-04_anomaly_store.md) | M4 Vidhi | M3 (writer) | Cassandra CQL | 🔶 **Provisional replica 0.1.0** (by M1, owner to replace) |
| C-05 | [`C-05_pipeline_metrics.md`](C-05_pipeline_metrics.md) | M3 Priyanka | M4 | Cassandra CQL | 🔶 **Provisional replica 0.1.0** (by M1, owner to replace) |
| C-06 | [`C-06_runtime_config_control.md`](C-06_runtime_config_control.md) | M1 Aswin | All | Env vars, CLI, service names | **In Review 1.0.0-rc.7** |
| — | [`versions.md`](versions.md) | M1 (all approve) | All | Version pins | **In Review 1.0.0-rc.4** |

**Provisional baseline:** concrete v0.1 values for every contract (fields, formulas, DDL, env vars, pins)
are in [../SDD_PLAYBOOK.md §5](../SDD_PLAYBOOK.md). Owners start from them, and replicas build against them until v1.0 is approved.

## What each contract must settle

**C-01 Network Event**: topic name; message key = `src_ip`; fields `timestamp` (emission time,
epoch ms, D-06), `src_ip`, `dst_ip`, `dst_port`, `bytes_sent`, `syn_flag`, `ack_flag`; types and units;
the mapping from CIC-IDS2017 TrafficLabelling columns (D-03); optional `orig_ts`, `event_id`;
**eval-only** `label` and `is_injected` (D-07); the replay Parquet layout for M2.

**C-02 Feature Definition**: window 30 s, slide 10 s, watermark 1 min; grouping (`src_ip`, window);
exact formulas and zero-handling for `total_bytes`, `unique_ports`, `syn_ack_ratio`, `packet_rate` (D-08);
column order; window ground-truth rule (D-07); golden input and output fixtures.

**C-03 Detection Bundle**: directory layout (`model.joblib`, `scaler.joblib` or a single pipeline,
`manifest.json`, `rules.yaml`); the manifest fields (bundle version, feature order, sklearn version,
score semantics and sign, decision threshold, training metrics, seed); the `rules.yaml` schema;
the loading procedure; the dummy bundle.

**C-04 Anomaly Store**: keyspace, replication, table DDL, primary key (D-02); columns
`window_start`, `window_end`, `src_ip`, the 4 features, `anomaly_score`, `ml_flag`, `rule_flag`,
`is_anomaly`, `detected_at`, `max_event_ts`, eval-only `label`; upsert semantics; TTL; write consistency.

**C-05 Pipeline Metrics**: table DDL; per-micro-batch fields (`batch_id`, input rows/s,
processed rows/s, batch duration, latency p50/p95 per D-01, run_id, config tags such as partitions and executors).

**C-06 Runtime Config and Control**: env var names (for example `KAFKA_BOOTSTRAP`, `KAFKA_TOPIC`,
`CASSANDRA_HOSTS`, `CASSANDRA_KEYSPACE`, `MODEL_BUNDLE_PATH`, `DATA_DIR`, `RUN_ID`); compose service names
and ports; CLI flags for the producer (`--rate`, `--duration`, `--attack-mode`, `--attack-share`), topic admin
(`--partitions`) and stream job (`--executors`, `--trigger`); `.env.example`.

## Planned layout

```
contracts/
├── README.md                 ← this registry
├── C-01_… .. C-06_….md       ← human-readable contracts
├── versions.md               ← pinned versions (D-09)
├── changes/                  ← CR-xxx change requests
├── schemas/                  ← event.schema.json, ids_schema.cql, manifest.schema.json, rules.schema.json
├── fixtures/                 ← events_golden.jsonl, features_golden.csv, scores_golden.csv
└── python/ids_contracts/     ← constants, models, validators (no business logic)
```
