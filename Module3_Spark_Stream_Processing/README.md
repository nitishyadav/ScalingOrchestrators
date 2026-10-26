> **REPLICA built by Aswin S. (M1). Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 3 — Spark Stream Processing

| | |
|---|---|
| Owner | **Kumari Priyanka** |
| Python package | `ids_stream` |
| Status | Replica: M3-F01 ✅ · F02 ✅ · F03 ✅ · F04 ✅ (end-to-end verified) |
| Contracts owned | C-05 Pipeline Metrics |
| Contracts consumed | C-01 (events), C-02 (features), C-03 (bundle), C-04 (store), C-06 (config) |

## Purpose
This module is the PySpark Structured Streaming job at the centre of the pipeline. It consumes events
from Kafka, computes 30 s / 10 s sliding-window features per source IP, scores them with the broadcast
Isolation Forest via `pandas_udf` alongside rule checks, and writes results and runtime metrics to Cassandra.
Checkpointing gives fast recovery.

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M3-F01 Stream ingest (Kafka source, parse, watermark, bad records) | [specs/M3-F01-stream-ingest/](specs/M3-F01-stream-ingest/spec.md) | ✅ Verified (replica) |
| M3-F02 Windowed features (C-02 parity with golden fixture) | [specs/M3-F02-windowed-features/](specs/M3-F02-windowed-features/spec.md) | ✅ Verified (replica, golden 23/23) |
| M3-F03 Hybrid scoring (broadcast bundle, `pandas_udf`, rules) | [specs/M3-F03-hybrid-scoring/](specs/M3-F03-hybrid-scoring/spec.md) | ✅ Verified (replica, golden scores) |
| M3-F04 Sink, metrics, checkpointing and recovery | [specs/M3-F04-sink-metrics-recovery/](specs/M3-F04-sink-metrics-recovery/spec.md) | ✅ Verified (replica, e2e + recovery) |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Anomaly rows | C-04 (as writer) | M4 | `mocks/fake_stream_writer.py` |
| Pipeline metrics | C-05 | M4 | `mocks/fake_stream_writer.py` |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Events | C-01 | M1 | `events_golden.jsonl` pushed by `producer --source fixture` |
| Feature spec + fixture | C-02 | M2 | `contracts/fixtures/features_golden.csv` |
| Detection bundle | C-03 | M2 | `Module2_ML_Anomaly_Model/mocks/dummy_bundle/` (copied to `MODEL_BUNDLE_PATH`) |
| Store schema | C-04 | M4 | `contracts/schemas/ids_schema.cql` |

## Quick start
```bash
make install && make test && make contract-test     # host side (no PySpark needed)
# Platform up (Module 1), topic created, bundle installed (Module 2 `make mock` → runtime/bundle/current):
python -m ids_stream.job --run-id DEV-x --starting-offsets earliest          # runs until Ctrl-C (graceful)
python -m ids_stream.job --executors 2 --trigger "1 second" --await-seconds 120 --run-id E2-...
make integration-test      # golden parity in Spark + end-to-end + worker-restart recovery (about 4 min)
```
- **Submission:** `job.py` submits `app.py` from `spark-client` (same Python as the workers), with `--py-files runtime/build/ids_stream.zip`.
- **Pipeline:** Kafka → C-01 parse/validate (malformed dropped and counted) → watermark 60 s → `window(30 s, 10 s)` per `src_ip` → `foreachBatch`:
  features → broadcast IsolationForest via `pandas_udf` + rules compiled from `rules.yaml` → upsert `ids.window_scores`.
- **Metrics:** listener progress → `ids.pipeline_metrics` (written from the main thread). One `ids.runs` row per start.
- **Checkpoint:** `runtime/checkpoints/<run_id>`.
