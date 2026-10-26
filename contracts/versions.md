# Version Pins (ADR-009)

| Field | Value |
|---|---|
| Version | 1.0.0-rc.4 |
| Status | **In Review** (all 4 approve) |
| Owner | M1 — Aswin S. |

These pins apply **everywhere**: host machines, Docker images and Google Colab. Change them only through a CR.

## Hard rules
1. **scikit-learn, numpy, pandas and pyarrow must be identical** wherever the model is trained (Colab) and wherever it is scored
   (Spark executors). A joblib pickle is not guaranteed to load across scikit-learn versions.
2. **The Spark driver and executors must have the same Python minor version.** `pandas_udf` fails otherwise.
   Therefore the stream job is submitted from a container built from the same image as the workers, not from the host.
3. Spark runs on **Java 17**. Spark 3.5 does not officially support Java 21.

## Pins

| Component | Pin | Where | Verified |
|---|---|---|---|
| Python (host tools, tests, producer, dashboard) | 3.11.x | host | ✅ 3.11.17 on M1 host (2026-10-21) |
| Python (Spark image) | the image's Python, identical on driver and workers | Docker | ✅ 3.10.12 on driver and executors (M1-F01-AC-06) |
| Java | 17 (Temurin or Homebrew `openjdk@17`) | Docker + host for local PySpark tests | ✅ 17.0.21 on M1 host (Homebrew), 17.0.14 in the Spark image |
| Apache Spark / PySpark | 3.5.5 (Scala 2.12). Image `apache/spark:3.5.5-scala2.12-java17-python3-ubuntu` | Docker + host | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Spark Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5` (+ kafka-clients 3.4.1, commons-pool2 2.11.1, token-provider 3.5.5), baked into the image | Spark | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Spark Cassandra connector | `com.datastax.spark:spark-cassandra-connector-assembly_2.12:3.5.1`, baked into the image | Spark | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Kafka | `apache/kafka:3.8.1` (KRaft) | Docker | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Cassandra | `cassandra:4.1.10` | Docker | ✅ runs in the platform (M1-F01, 2026-10-21) |
| scikit-learn | 1.5.2 | Colab, Spark image, host | ✅ Spark image (driver + executors) |
| numpy | 1.26.4 | Colab, Spark image, host | ✅ Spark image |
| pandas | 2.2.3 | Colab, Spark image, host | ✅ Spark image |
| pyarrow | 17.0.0 | Colab, Spark image, host | ✅ Spark image (pandas_udf ran), ✅ host (M1-F02 writer) |
| joblib | 1.4.2 | Colab, Spark image | ✅ Spark image |
| Kafka Python client | `confluent-kafka==2.6.1` (M1-ADR-002) | M1 | ✅ host (topic_admin, perf test) |
| Container engine | Docker Desktop **or** Colima, with Compose v2. VM ≥ 6 CPU / 10 GB | host | ✅ Colima 0.10.3 + Docker CLI 29.9 + Compose 5.6 on M1 host |
| cassandra-driver | 3.29.2 | M3 (if needed), M4 | ⬜ |
| streamlit | 1.39.0 | M4 | ⬜ |
| pyyaml | 6.0.2 | M2, M3 | ✅ Spark image + host |
| pytest / jsonschema | 8.3.x / 4.23.x | all (tests only) | ⬜ |
| matplotlib (+ pyparsing) | 3.9.2 (+ 3.1.4, newer pyparsing raises deprecation warnings in 3.9.2) | M2 (EDA figures), M4 (results figures); host only, never in the Spark image | ✅ host (2026-10-25) |

The "Verified" column is ticked when an image or environment actually runs with the pin (for example during M1-F01).
If a pin cannot be satisfied (an image tag does not exist, or a wheel is unavailable on arm64), raise a CR that names the replacement.

## Colab cell (training must start with this)
```python
!pip install -q scikit-learn==1.5.2 numpy==1.26.4 pandas==2.2.3 pyarrow==17.0.0 joblib==1.4.2 pyyaml==6.0.2
import sklearn, numpy, pandas, pyarrow; print(sklearn.__version__, numpy.__version__, pandas.__version__, pyarrow.__version__)
# Restart the runtime after installing, then record the printed versions in the bundle manifest (C-03).
```
