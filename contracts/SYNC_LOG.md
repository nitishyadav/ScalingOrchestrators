# Contract Sync Log (PR-14)

Every time contract files are published (by the owner) or received (by everyone else), add one line.
Before integrating, compare this log between two members' trees. The contract versions must match.

| Date | Contract / file | Version | Action | By | Notes |
|---|---|---|---|---|---|
| 2026-10-21 | C-01 Network Event (+ event.schema.json, events_golden.jsonl, ids_contracts/events.py) | 1.0.0-rc.1 | Authored | Aswin (M1) | Sent for review to M2, M3 |
| 2026-10-21 | C-06 Runtime Config (+ .env.example, ids_contracts/config.py) | 1.0.0-rc.1 | Authored | Aswin (M1) | Sent for review to all |
| 2026-10-21 | versions.md | 1.0.0-rc.1 | Authored | Aswin (M1) | Needs all 4 approvals |
| 2026-10-22 | C-02, C-03, C-04, C-05 (+ ids_contracts features/bundle/store/metrics, schemas, features_golden.csv) | 0.1.0-replica | **Provisional replica** authored | Aswin (M1, replica mode) | Owners Nitish/Vidhi/Priyanka author v1.0 and replace. CQL applied live to Cassandra 4.1.10 (idempotent, upsert verified) |
| 2026-10-22 | C-06 | 1.0.0-rc.6 | Revised before review | Aswin (M1) | Attack injection flags and summary fields (M1-F04) |
| 2026-10-21 | C-01 (+ ids_contracts/events.py LIBRDKAFKA_PARTITIONER) | 1.0.0-rc.5 | Revised before review | Aswin (M1) | murmur2_random partitioner for librdkafka producers (M1-F03) |
| 2026-10-21 | C-06 | 1.0.0-rc.5 | Revised before review | Aswin (M1) | Producer flags and summary fields (M1-F03) |
| 2026-10-21 | C-01 (+ ids_contracts/events.py REPLAY_CONTENT_SHA256) | 1.0.0-rc.4 | Revised before review | Aswin (M1) | Reference replay hashes: replicas can prove identical data |
| 2026-10-21 | C-01 (+ ids_contracts/events.py validate_manifest, DROP_REASONS) | 1.0.0-rc.3 | Revised before review | Aswin (M1) | Replay manifest schema (M1-F02) |
| 2026-10-21 | C-06 | 1.0.0-rc.4 | Revised before review | Aswin (M1) | `ids_ingest.prepare` command (M1-F02) |
| 2026-10-21 | C-01 (+ ids_contracts/events.py CIC_REFERENCE, events_golden.jsonl regenerated) | 1.0.0-rc.2 | Revised before review | Aswin (M1) | Verified against the downloaded dataset: SHA-256 + 2,830,743 valid rows; orig_ts opaque |
| 2026-10-21 | C-06 (+ .env.example, ids_contracts/config.py) | 1.0.0-rc.2 | Revised before review | Aswin (M1) | spark-client, platform CLI, SPARK_WORKERS, executor memory 768m |
| 2026-10-21 | C-06 (+ ids_contracts/config.py: `load_runtime_config`) | 1.0.0-rc.3 | Revised before review | Aswin (M1) | KRaft (no zookeeper), workers mount workspace and runtime, .env loading |
| 2026-10-21 | versions.md | 1.0.0-rc.3 | Revised before review | Aswin (M1) | Image pins verified at runtime in M1-F01. Exact connector artifacts |
| 2026-10-21 | versions.md | 1.0.0-rc.2 | Revised before review | Aswin (M1) | confluent-kafka, container engine; host Python/Java verified |
| 2026-10-25 | C-02 (+ features.py, features_golden.csv), C-03 (+ bundle.py, manifest/rules schemas, scores_golden.csv) | 0.2.0-replica | **Provisional replica** revised | Aswin (M1, replica mode) | D-14/ADR-012: ratio features, V3 model inputs. M2 bundle 1.1.0-replica; M3 parity + e2e re-proved |
| 2026-10-25 | C-06 (+ ids_contracts/config.py RUN_ID_PATTERN) | 1.0.0-rc.7 | Revised before review | Aswin (M1) | Run IDs for P1/LAT/REC measurement runs; bench flags (M4-F03) |
| 2026-10-25 | versions.md | 1.0.0-rc.4 | Revised before review | Aswin (M1) | matplotlib 3.9.2 + pyparsing 3.1.4 (host only: M2 EDA and M4 results figures) |
