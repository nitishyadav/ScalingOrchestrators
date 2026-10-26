# Plan: M1-F01 — Platform Cluster

| Field | Value |
|---|---|
| Feature ID | M1-F01 |
| Spec version implemented | 0.1.0 |
| Owner | Aswin S. |
| Status | **Approved** (G2, 2026-10-21, KRaft) |
| Updated | 2026-10-21 |

## 1. Approach summary
A single Compose file in `Module1_Data_Ingestion_Platform/platform/` defines five services. They are a KRaft-mode Kafka broker
with two listeners (host and in-network), a Spark standalone master, a scalable Spark worker service, a long-running
`spark-client` container for job submission, and Cassandra with a capped heap. Spark master, workers and client share one custom
image built from the official Spark image. That image adds the pinned Python ML stack and pre-fetched connector jars, so it needs
no network at job time and has identical Python everywhere. Two thin Python CLIs (`ids_ingest.platform`, `ids_ingest.topic_admin`)
wrap `docker compose` and the Kafka admin API. They take their configuration from `ids_contracts.config` and print C-06 summary lines.

## 2. Technical context
| Item | Choice | Pinned version (`contracts/versions.md`) |
|---|---|---|
| Language (CLIs, tests) | Python | 3.11.x (host) |
| Container engine | Docker Desktop **or** Colima (CLI-only, used on the M1 owner's Mac), Compose v2 | — |
| Broker | Official `apache/kafka`, KRaft single node | `apache/kafka:3.8.1` |
| Processing | Custom image `ids/spark:3.5.5` FROM `apache/spark:3.5.5-scala2.12-java17-python3-ubuntu` | Spark 3.5.5, Java 17 |
| Store | Official `cassandra` | `cassandra:4.1.10` |
| Kafka client (CLIs) | `confluent-kafka` (librdkafka, arm64 wheels, fast enough for M1-F03) | 2.6.x |
| Static tests | `pyyaml`, `pytest` | 6.0.2, 8.3.x |

## 3. Constitution check
| Article | Compliant? | Notes |
|---|---|---|
| I Spec before code | ✅ | Spec 0.1.0. No code until G1–G3 |
| II Contracts only coupling | ✅ | Exposes only C-06 services and commands and the C-01 topic config |
| III Module isolation | ✅ | Only `ids_contracts` is imported. The client mounts the workspace read-only and never writes into other modules |
| IV Mock-first | ✅ | The platform is infrastructure, so no mock is needed. Consumers can use `local[*]` Spark (C-06 allows it) until it is ready |
| V Uniform Makefile | ✅ | `install/test/contract-test/run/mock/clean`. Extra operations go through the `ids_ingest.platform` CLI, not extra targets |
| VI Config via env | ✅ | Ports, partitions, workers and memory all come from C-06 |
| VII Honest ML | ✅ | n/a (no scoring) |
| VIII Tests from AC | ✅ | Each AC is mapped in §7 |
| IX Pins, seeds | ✅ | Exact image tags. A static test cross-checks them against `versions.md` |
| X Measured claims | ✅ | NFR-003 is measured with the broker perf tool. Output is saved under `Module1_…/docs/measurements/` |
| XI Ownership / CR | ✅ | C-06 rc.2 changes (`spark-client`, platform CLI, `SPARK_WORKERS`, executor memory) were made while still in review and logged |
| XII Simplicity | ✅ | Only the proposal stack. KRaft *removes* ZooKeeper (M1-ADR-001) |

## 4. Design

### 4.1 Components
```
                         host (macOS)                                     │  Docker engine VM (6 CPU, 10 GB)
  python -m ids_ingest.platform ──► docker compose -f platform/docker-compose.yml ──────────────────────────────┐
  python -m ids_ingest.topic_admin ─► localhost:9092 ──────────────────────────────────────►┌───────────┐     │
                                                                                            │  kafka    │     │
  ┌──────────────┐  spark://spark-master:7077  ┌──────────────┐                            │ 9092 ext  │     │
  │ spark-client │ ──────────────────────────► │ spark-master │◄── spark-worker × N        │ 29092 int │     │
  │ /workspace ro│ ── kafka:29092 ───────────────────────────────────────────────────────► └───────────┘     │
  │ runtime  rw  │ ── cassandra:9042 ──────────────────────────────────────────────────────► cassandra       │
  └──────────────┘                                                                                           │
```

| Component | Responsibility |
|---|---|
| `platform/docker-compose.yml` | Service definitions, listeners, health checks, memory/CPU limits, volumes, network `ids-net` |
| `platform/spark/Dockerfile` | Pinned Python stack plus connector jars baked into `/opt/spark/jars`. Same image for master, workers and client |
| `platform/spark/requirements-spark.txt` | Exactly the `versions.md` pins for the Spark runtime |
| `src/ids_ingest/platform.py` | `up/down/status/restart-worker/clean`. Engine and memory pre-checks. Readiness wait. Summary line |
| `src/ids_ingest/topic_admin.py` | Create, increase or recreate the topic per FR-005, using an admin-client interface that tests can fake |
| `src/ids_ingest/_compose.py` | Builds and runs `docker compose` commands (subprocess), parses `ps --format json` |

### 4.2 Requirement → component mapping
| Requirement | Component / file | Notes |
|---|---|---|
| FR-001, FR-002 | `docker-compose.yml` health checks; `platform.py up/status` | `up` waits on `docker compose ps` health until timeout |
| FR-003 | Kafka listeners `EXTERNAL://localhost:9092`, `INTERNAL://kafka:29092`, `CONTROLLER://:9093` | The classic advertised-listener pitfall is covered by AC-03 |
| FR-004 | `spark-worker` with `SPARK_WORKER_CORES=2`; `--scale spark-worker=$SPARK_WORKERS` | 2 workers × 2 cores = 4 executor slots |
| FR-005 | `topic_admin.py` | Decision logic is pure and unit-tested with a fake admin |
| FR-006 | `Dockerfile` + `requirements-spark.txt` | Jars fetched at **build** time (Maven Central) |
| FR-007 | `spark-client` volumes + env | `IDS_ROOT=/workspace` |
| FR-008 | `platform.py restart-worker` → `docker restart <project>-spark-worker-<i>` | |
| FR-009 | `down` vs `clean --yes` (`down -v`) | |
| FR-010 | All CLIs use `ids_contracts.config.summary_line` and the exit-code constants | |

### 4.3 File layout
```
Module1_Data_Ingestion_Platform/
├── Makefile  pyproject.toml  requirements.txt
├── platform/
│   ├── docker-compose.yml
│   └── spark/{Dockerfile, requirements-spark.txt}
├── src/ids_ingest/{__init__,_compose,platform,topic_admin}.py
├── tests/unit/{test_compose_static.py, test_topic_admin_logic.py, test_platform_cli.py}
├── tests/contract/test_c06_platform_contract.py
├── tests/integration/test_platform_live.py        (marker: docker)
└── docs/{adr/M1-ADR-001-kraft.md, adr/M1-ADR-002-kafka-client.md, adr/M1-ADR-003-container-engine.md, measurements/}
```

### 4.4 Memory budget (NFR-002, limits enforced in compose)
| Service | Limit | Inside |
|---|---|---|
| kafka | 1.25 GB | JVM heap 768 MB |
| cassandra | 2.0 GB | `MAX_HEAP_SIZE=1G`, `HEAP_NEWSIZE=256M` |
| spark-master | 0.5 GB | daemon heap 256 MB |
| spark-worker × 2 | 2 × 2.25 GB | 2 cores each. Two executors of 768 MB + overhead plus Python workers |
| spark-client | 1.25 GB | driver 768 MB + Python (trimmed from 1.5 GB in T025: Colima 10 GB reports 9.69 GiB) |
| **Total (default)** | **9.5 GiB** | ≤ engine memory (9.69 GiB on Colima `--memory 10`), leaving about 6 GB for macOS |

`SPARK_EXECUTOR_MEMORY` therefore defaults to **768m** (C-06 rc.2). With 4 workers the total would exceed the budget,
so `up --workers 4` warns, and E2 uses the default 2 workers with 4 slots.

## 5. Configuration
| Env var (C-06) | Default | Used for |
|---|---|---|
| `KAFKA_BOOTSTRAP` | `localhost:9092` | topic_admin (host) |
| `KAFKA_TOPIC`, `KAFKA_PARTITIONS` | `network-events`, 8 | topic_admin |
| `SPARK_WORKERS` | 2 | `up --workers` |
| `SPARK_EXECUTOR_MEMORY` | 768m | Informational check of worker capacity (AC-04) |
| `IDS_ROOT` | auto | Compose bind-mount source for `/workspace` |

## 6. Mock and stub strategy
| Dependency | During development | Swapped at |
|---|---|---|
| Docker engine | Unit and static tests need no engine. `_compose` is faked via an injected runner | Integration tests (`-m docker`) |
| Kafka admin | `FakeAdmin` implementing `list_topics/create/increase/delete` | AC-05 integration |

## 7. Test strategy
| Level | What | Tooling | Maps to AC |
|---|---|---|---|
| Unit (static) | Compose names, ports, no `latest`, versions equal `versions.md`, memory sum ≤ 10 GB | pytest + pyyaml | AC-09 |
| Unit | topic_admin decision table. Platform CLI argument handling, exit codes, summary line | pytest, fakes | AC-05, AC-11 |
| Contract | C-06 service and port table equals compose. Every CLI `--help` exits 0, a bad flag exits 2 | pytest | AC-11 |
| Integration | up/status/ready, dual listeners, workers and cores, pandas_udf in the client offline, restart-worker, down/up persistence | pytest `-m docker` | AC-01..04, 06..08 |
| Performance | `kafka-producer-perf-test.sh --record-size 300 --throughput -1` for 60 s | script, results saved | AC-10 |

## 8. Risks and alternatives considered
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| KRaft broker (no ZooKeeper) | About 0.5 GB less RAM, one fewer service, the default since Kafka 3.3+ | Deviates from the proposal text "Zookeeper" | ✅ M1-ADR-001 (report notes it) |
| ZooKeeper + broker | Matches the proposal wording | More memory (R1), deprecated in Kafka 4 | |
| `confluent-kafka` | Fast (C library), full admin API | Native wheel | ✅ M1-ADR-002 |
| `kafka-python` | Pure Python | Too slow for ≥ 12k ev/s in M1-F03 | |
| Colima engine | CLI-only, scriptable, free | Not the GUI Docker Desktop | ✅ M1-ADR-003 (either works, same compose) |
| Bitnami images | Convenient env vars | Catalogue changed in 2025. Pinned tags unreliable | ✗ (use official images) |

## 9. Done means
- [ ] All tasks in `tasks.md` complete
- [ ] `make test` and `make contract-test` green. `pytest -m docker` green on a running engine
- [ ] Every AC in the spec ✅ with test reference. The AC-10 measurement is saved
- [ ] Pins in `versions.md` ticked "Verified" for Spark, Kafka and Cassandra images
- [ ] README quick start updated
