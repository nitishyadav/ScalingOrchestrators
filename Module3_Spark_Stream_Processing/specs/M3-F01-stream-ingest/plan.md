# Plan: M3-F01..F04 — Stream Job (REPLICA, shared plan)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Runtime | The platform Spark image (Spark 3.5.5, Python 3.10, pinned stack, Kafka + Cassandra connectors baked in), submitted from `spark-client` |

## Components
| File | Runs where | Responsibility |
|---|---|---|
| `src/ids_stream/spec.py` | host + container (pure Python) | C-01 Spark DDL, validity SQL, label-count columns, rules → SQL, C-04/C-05 column lists, metrics row builder, bundle metadata reader |
| `src/ids_stream/app.py` | container (PySpark driver) | Kafka/file source → parse → watermark → windowed aggregates → `foreachBatch`: pandas_udf scoring (broadcast model) + rules → Cassandra upsert → batch stats. Listener → metrics queue → main thread writes C-05 rows |
| `src/ids_stream/job.py` | host | C-06 CLI: validates config and bundle, zips `ids_stream` into `runtime/build/`, `docker exec spark-client spark-submit …`, SIGTERM → `pkill -TERM` the driver, re-emits the summary |
| `tests/spark/parity_app.py` | container | Golden parity driver (file stream of `events_golden.jsonl`, `availableNow`), prints JSON for host-side asserts |

## Key choices
| Choice | Why |
|---|---|
| Scoring inside `foreachBatch` on the static micro-batch frame | Python UDFs on static frames are fully supported. Exact `detected_at` per batch |
| Metrics written from the **main thread** (the listener only enqueues) | No Spark jobs launched from listener callbacks |
| `--py-files runtime/build/ids_stream.zip` | Executors import `ids_stream`. `ids_contracts` comes from the image `PYTHONPATH` |
| `spark.sql.shuffle.partitions = executors × cores × 2` (default 8) | The default 200 is far too many for 4 cores |
| Label type from 17 per-label count columns | Bounded state (no `collect_list` of labels) |

## Constitution check
All ✅. Only `ids_contracts` is imported across modules (no `ids_model`: M3 loads the C-03 bundle itself). Config via C-06. Thresholds only from the bundle.
Eval-only columns are never model inputs.
