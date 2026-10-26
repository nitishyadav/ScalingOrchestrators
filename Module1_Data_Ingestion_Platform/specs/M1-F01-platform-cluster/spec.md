# Spec: M1-F01 — Platform Cluster

| Field | Value |
|---|---|
| Feature ID | M1-F01 |
| Module | Module1_Data_Ingestion_Platform |
| Owner | Aswin S. |
| Reviewers | Kumari Priyanka (M3, runs jobs on it), Vidhi Kant Gupta (M4, benchmarks on it) |
| Status | **Verified** (2026-10-21, all 11 ACs ✅; consumer review by M3/M4 still requested) |
| Version | 0.1.0 |
| Created / Updated | 2026-10-21 / 2026-10-21 |
| Proposal trace | G1, G5, P1, P3, P4, P5; proposal §2.2 (Docker Compose pseudo-distributed cluster), Week 1–2 milestone |
| Contracts touched | C-06 1.0.0-rc.2 (provides: services, ports, `ids_ingest.platform`, `ids_ingest.topic_admin`); C-01 1.0.0-rc.1 (provides: topic configuration §2.1); `versions.md` (applies) |
| Decisions applied | ADR-009 (pins, Java 17, job submitted from the image) |

## 1. Summary
This feature delivers a one-command, pseudo-distributed platform on a single laptop. It provides a message broker,
a stream-processing cluster (one master and a configurable number of workers), a wide-column store, and a job-submission
point that matches the workers. It also delivers a command to create and resize the event topic. Every other module and
every experiment runs on this platform.

## 2. Context and motivation
The proposal (§2.2) runs Kafka, Spark and Cassandra under Docker Compose on one MacBook (16 GB). The experiments vary
Kafka partitions (E1, 1–16) and Spark executors (E2, 1–4), and test recovery after a worker restart (P5). A platform that is
unreliable, under-resourced or configured by hand would invalidate every measurement. See PROJECT_PLAN §2 (M1) and risk R1.

## 3. Scope
**In scope**
- Start, stop, check and clean the platform with stable commands (C-06).
- Health reporting for each service and an overall "ready" state.
- Executor capacity for up to 4 concurrent executors. Restarting one worker for recovery tests.
- Creating, increasing and recreating the event topic per C-01 §2.1.
- A stream-processing runtime with the pinned ML stack and the Kafka and Cassandra connectors available offline.
- A job-submission point whose Python matches the workers (ADR-009).
- A documented memory budget that fits the host.

**Out of scope** (and who handles it)
- Cassandra keyspace and tables: M4-F01 (C-04) and M3 (C-05). The platform only provides a running store.
- The producer, dataset and injector: M1-F02..F04.
- The stream job itself: M3. The dashboard service: M4-F02 (it only reuses the platform's network).

## 4. Actors and user stories
- **US-1:** As any team member, I want to start the full platform with one command and know when it is ready, so that I can develop against real services.
- **US-2:** As the M3 job (via its owner), I want to submit a PySpark job whose driver and executors have identical Python and libraries, so that `pandas_udf` scoring works.
- **US-3:** As the M4 benchmark harness, I want to set the partition count and executor capacity and restart a worker through commands, so that E1, E2 and P5 run unattended.
- **US-4:** As a member on a 16 GB laptop, I want the platform to stay within a known memory budget, so that the machine stays usable and the results are stable.

## 5. Functional requirements

| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M1-FR-001 | The platform MUST provide the services named in C-06 §4 (`kafka`, `spark-master`, `spark-worker`, `spark-client`, `cassandra`) on the C-06 host ports, started by `make run` in Module 1 (equivalently `python -m ids_ingest.platform up`). | P0 | US-1 | §2.2 |
| M1-FR-002 | Each service MUST expose a health status. `platform status` MUST report each service and an overall `ready` flag. `platform up` MUST return only when all services are healthy, or fail with exit 1 after a timeout. | P0 | US-1 | Wk 1–2 |
| M1-FR-003 | The broker MUST be reachable both from the host (`localhost:9092`) and from inside the platform network (`kafka:29092`). A message produced through one MUST be consumable through the other. | P0 | US-1, US-2 | C-06 |
| M1-FR-004 | The number of worker containers MUST be selectable from 1 to 4 at start (`--workers` / `SPARK_WORKERS`), and the default topology MUST offer capacity for at least 4 concurrent 1-core executors at `SPARK_EXECUTOR_MEMORY`. | P0 | US-3 | E2, P4 |
| M1-FR-005 | `topic_admin` MUST create the C-01 topic with N partitions (1–16), replication factor 1 and `retention.ms=1800000`. If the topic exists with N partitions it MUST succeed without change. If it has fewer than N it MUST increase them. If it has more than N it MUST fail with exit 2 unless `--recreate` is given, in which case it MUST delete and recreate the topic. | P0 | US-3 | E1, P3 |
| M1-FR-006 | The stream-processing runtime (master, workers, client) MUST contain the pinned Python ML stack (`versions.md`: scikit-learn, numpy, pandas, pyarrow, joblib, pyyaml) and the Kafka and Cassandra Spark connectors, available **without network access** at job time. | P0 | US-2 | G3, ADR-009 |
| M1-FR-007 | `spark-client` MUST mount the workspace at `/workspace` (read-only) and `runtime/` at `/workspace/runtime` (read-write), with `IDS_ROOT=/workspace` and the in-network C-06 addresses, so that module code and config resolve identically inside the platform. | P0 | US-2 | C-06 §2 |
| M1-FR-008 | `platform restart-worker [--index i]` MUST restart exactly one worker container, leaving the rest running. | P1 | US-3 | P5 |
| M1-FR-009 | `platform down` MUST stop all services and keep their data. `platform clean --yes` MUST also remove platform volumes. Without `--yes`, `clean` MUST refuse with exit 2. | P1 | US-1 | — |
| M1-FR-010 | Every platform command MUST follow C-06 §5: exit codes 0/1/2 and one JSON summary line on success. | P0 | US-3 | C-06 |

## 6. Non-functional requirements

| ID | Category | Requirement (measurable) | Trace |
|---|---|---|---|
| M1-NFR-001 | Startup | From a cold start with images already built or pulled, all services are healthy in **≤ 180 s** | US-1 |
| M1-NFR-002 | Resource | The sum of container memory limits is **≤ 10 GB** with the default topology. The documented per-service budget is enforced by limits | R1 |
| M1-NFR-003 | Throughput headroom | The broker accepts **≥ 15,000 msg/s** of 300-byte messages from one host producer at 16 partitions for 60 s | G1, P1 |
| M1-NFR-004 | Recovery support | After `restart-worker`, the worker re-registers with the master within **≤ 30 s** | P5 |
| M1-NFR-005 | Reproducibility | Every image is pinned to an exact version from `versions.md`. There are **no `latest` tags** | Art. IX |
| M1-NFR-006 | Portability | Runs natively on Apple Silicon (arm64) with a Docker-compatible engine and Compose v2 (Docker Desktop or Colima) | — |

## 7. Interfaces

### 7.1 Provided
| Contract | Version | What exactly is provided |
|---|---|---|
| C-06 | 1.0.0-rc.2 | §4 services and ports; §5 `ids_ingest.platform` and `ids_ingest.topic_admin` commands; `SPARK_WORKERS` |
| C-01 | 1.0.0-rc.1 | §2.1 topic configuration (partitions, RF, retention) |

### 7.2 Consumed
| Contract | Version | What is used | Mock used until the real one is available |
|---|---|---|---|
| C-06 | 1.0.0-rc.2 | `load_config`, env names, exit codes, summary line | n/a (shared package) |
| versions.md | 1.0.0-rc.2 | Image and library pins | n/a |

## 8. Data
No pipeline data is produced. Persistent state: broker log volume, store data volume, and `runtime/` on the host
(checkpoints and data mounted into the platform). The topic's retention bounds broker disk use (C-01 §2.1).

## 9. Acceptance criteria

| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M1-F01-AC-01 | **Given** a stopped platform **When** `make run` **Then** it exits 0 within 180 s, the summary shows all 5 services healthy, and the C-06 host ports accept connections | FR-001, FR-002, NFR-001 | integration | ✅ `test_ac01_up_from_stopped_within_180s` (59.1 s) |
| M1-F01-AC-02 | **Given** a running platform **When** `platform status` **Then** it prints per-service health and `"ready": true`. **When** one service is stopped **Then** `ready` is false and the exit code is 1 | FR-002, FR-010 | integration | ✅ `test_ac02_status_ready_then_detects_stopped_service`, unit `test_status_*` |
| M1-F01-AC-03 | **Given** a running platform **When** a message is produced on `localhost:9092` **Then** it is consumed from `spark-client` via `kafka:29092`, and vice versa | FR-003 | integration | ✅ `test_ac03_dual_listeners_host_and_in_network` |
| M1-F01-AC-04 | **Given** `--workers 2` (default) **When** the cluster is up **Then** the master reports 2 alive workers with ≥ 4 cores and enough memory for 4 executors of `SPARK_EXECUTOR_MEMORY` in total | FR-004 | integration | ✅ `test_ac04_workers_offer_four_executor_slots` |
| M1-F01-AC-05 | **Given** no topic **When** `topic_admin --partitions 4` **Then** the topic exists with 4 partitions, RF 1 and retention 1800000. **When** run again **Then** exit 0 with no change. **When** `--partitions 8` **Then** 8 partitions. **When** `--partitions 1` **Then** exit 2. **When** `--partitions 1 --recreate` **Then** 1 partition | FR-005 | unit (fake admin) + integration | ✅ `test_ac05_topic_admin_live`, unit `test_topic_admin_logic.py` |
| M1-F01-AC-06 | **Given** `spark-client` **When** a PySpark job imports the pinned libraries, reads the golden events from `/workspace/contracts/fixtures` and runs a `pandas_udf` on the workers with networking to the internet disabled **Then** it succeeds, and the reported versions equal `versions.md` | FR-006, FR-007 | integration | ✅ `test_ac06_pandas_udf_job_from_client_with_pinned_stack` |
| M1-F01-AC-07 | **Given** a running cluster **When** `platform restart-worker --index 1` **Then** only that container restarts and the master shows it alive again within 30 s | FR-008, NFR-004 | integration | ✅ `test_ac07_restart_worker_reregisters_within_30s` |
| M1-F01-AC-08 | **Given** a running platform with a topic **When** `platform down` then `up` **Then** the topic still exists. **When** `platform clean` without `--yes` **Then** exit 2 and nothing is removed | FR-009 | integration | ✅ `test_ac08_down_up_keeps_data_and_clean_needs_yes` |
| M1-F01-AC-09 | **Given** the compose definition **When** checked statically **Then** service names and ports equal C-06, no image uses `latest`, image versions equal `versions.md`, and the memory limits sum to ≤ 10 GB | FR-001, NFR-002, NFR-005 | unit (static) | ✅ `tests/unit/test_compose_static.py` |
| M1-F01-AC-10 | **Given** a running platform with 16 partitions **When** the broker perf tool sends 300-byte messages from the host for 60 s **Then** the sustained rate is ≥ 15,000 msg/s | NFR-003 | perf | ✅ `test_ac10_broker_accepts_15k_msgs_per_second`: 801,325 msg/s (`docs/measurements/AC-10-2026-10-21.json`) |
| M1-F01-AC-11 | **Given** any platform or topic_admin command **When** it succeeds **Then** its last stdout line parses as a C-06 summary. **When** given a bad flag **Then** exit 2 | FR-010 | contract | ✅ `tests/contract/test_c06_platform_contract.py`, unit summary-line tests |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| A host port is already in use | `up` fails with exit 1 naming the port. No partial cluster is left running |
| Not enough memory in the Docker VM | `up` checks the engine's memory before starting and fails with exit 1 if it is below the budget |
| The store is slow to start (often 60–90 s) | The health check waits until the store answers queries. The 180 s budget includes this |
| Decreasing the partition count | Refused without `--recreate` (Kafka cannot shrink a topic) |
| The Docker engine is not running | Every command fails fast with exit 1 and a hint ("start Docker Desktop or `colima start`") |
| `restart-worker` with an invalid index | Exit 2 |

## 11. Assumptions and dependencies
- A Docker-compatible engine with Compose v2 is installed (Docker Desktop or Colima) and allocated 6 CPUs and 10 GB RAM.
- Images can be pulled or built once while online. Job-time operation needs no internet.
- The Spark image tag pinned in `versions.md` exists for arm64 (verified in tasks).

## 12. Open questions
- None blocking. The broker metadata mode (KRaft or ZooKeeper) and the engine are plan-level choices (M1-ADR-001, M1-ADR-003).

## 13. Review checklist
- [x] No implementation details (frameworks, code structure) beyond the components the proposal mandates
- [x] Every FR is testable and has at least one AC
- [x] Every NFR has a number and a unit
- [x] Interfaces reference contracts by ID and version
- [x] Eval-only fields are not involved (no scoring in this feature)
- [x] No open `[NEEDS CLARIFICATION]`
- [ ] At least one consumer-module owner has reviewed (M3 or M4)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | 2026-10-21 | Aswin S. (with AI) | Initial draft. Approved by owner (KRaft chosen) |
| 0.1.0 | 2026-10-21 | Aswin S. (with AI) | Implemented and verified: all ACs pass (see table) |
