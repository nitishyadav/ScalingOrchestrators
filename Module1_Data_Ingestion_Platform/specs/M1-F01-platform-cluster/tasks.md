# Tasks: M1-F01 — Platform Cluster

| Field | Value |
|---|---|
| Feature ID | M1-F01 |
| Plan version | Approved 2026-10-21 (G3 passed) |
| Owner | Aswin S. |
| Target finish | 2026-10-27 |

Legend: `[P]` = can run in parallel. 🐳 = needs a running Docker engine.

## Phase 1 — Setup
- [x] **M1-T001** Package skeleton `src/ids_ingest/__init__.py`, `pyproject.toml` (depends on `ids-contracts`), `requirements.txt` with pins, `Makefile` with the 6 standard targets · Refs: Const. V · Done: 2026-10-21
- [x] **M1-T002** [P] ADRs: `docs/adr/M1-ADR-001-kraft.md`, `M1-ADR-002-kafka-client.md`, `M1-ADR-003-container-engine.md` · Refs: plan §8 · Done: 2026-10-21
- [x] **M1-T003** [P] Verify the image tags exist for arm64 (`docker manifest inspect` for apache/spark 3.5.5 java17 python3, apache/kafka 3.8.x, cassandra 4.1.x). Update `versions.md` with exact tags · 🐳 · Refs: NFR-005, NFR-006 · Done: 2026-10-21 (manifests, S-023)

## Phase 2 — Tests first
- [x] **M1-T010** [P] Static compose test: service names and ports equal C-06 §4, no `latest`, tags equal `versions.md`, memory limits sum ≤ 10 GB · Files: `tests/unit/test_compose_static.py` · Refs: AC-09 · Done: 2026-10-21 (red → green)
- [x] **M1-T011** [P] topic_admin decision-table tests with `FakeAdmin` (create / no-op / increase / refuse-shrink → 2 / recreate) · Files: `tests/unit/test_topic_admin_logic.py` · Refs: AC-05 · Done: 2026-10-21 (red → green)
- [x] **M1-T012** [P] Platform CLI tests with a fake compose runner: exit codes, summary line, `clean` without `--yes` → 2, bad `--index` → 2, engine-down message · Files: `tests/unit/test_platform_cli.py` · Refs: AC-02, AC-08, AC-11 · Done: 2026-10-21 (red → green; caught engine-check gap)
- [x] **M1-T013** [P] C-06 contract tests: `--help` exits 0, bad flag exits 2, last line is a JSON summary, compose service and port table equals C-06 · Files: `tests/contract/test_c06_platform_contract.py` · Refs: AC-11 · Done: 2026-10-21 (red → green)
- [x] **M1-T014** Live integration tests (marker `docker`), skipped when no engine · Files: `tests/integration/test_platform_live.py` · Refs: AC-01..04, AC-06..08 · Done: 2026-10-21

## Phase 3 — Core implementation
- [x] **M1-T020** `platform/spark/requirements-spark.txt` + `Dockerfile` (pinned stack, connector jars baked in at build) · Depends: T003 · Refs: FR-006 · Done: 2026-10-21 (stack + 5 jars SHA-1 verified)
- [x] **M1-T021** `platform/docker-compose.yml`: kafka (KRaft, dual listeners), spark-master, spark-worker (2 cores), spark-client (mounts, env), cassandra (heap caps), health checks, limits, network, volumes · Depends: T010, T020 · Refs: FR-001, FR-003, FR-004, FR-007, NFR-002 · Done: 2026-10-21
- [x] **M1-T022** `src/ids_ingest/_compose.py`: injectable runner, `ps --format json` parsing, health aggregation · Depends: T012 · Refs: FR-002 · Done: 2026-10-21
- [x] **M1-T023** `src/ids_ingest/platform.py`: `up` (engine and memory pre-check, port check, readiness wait ≤ 180 s), `down`, `status`, `restart-worker`, `clean --yes` · Depends: T022 · Refs: FR-001, FR-002, FR-008, FR-009, FR-010 · Done: 2026-10-21
- [x] **M1-T024** `src/ids_ingest/topic_admin.py`: decision logic + confluent-kafka admin adapter · Depends: T011 · Refs: FR-005, FR-010 · Done: 2026-10-21
- [x] **M1-T025** Build the image and bring the platform up. Make T010–T013 green · 🐳 · Depends: T020–T024 · Refs: AC-09, AC-11 · Done: 2026-10-21 (up in 59.1 s; spark-client trimmed to 1.25 G)

## Phase 4 — Integration readiness and measurement
- [x] **M1-T030** Run the live tests: dual listeners, worker cores, restart-worker timing, down/up persistence · 🐳 · Depends: T014, T025 · Refs: AC-01..04, AC-07, AC-08 · Done: 2026-10-21 (8/8 live)
- [x] **M1-T031** pandas_udf smoke job from `spark-client` with the network disabled for the job (`--network none` is not possible in-cluster, so verify that no `--packages` and no pip are used at runtime and that the jars are local) · 🐳 · Refs: AC-06 · Done: 2026-10-21 (AC-06)
- [x] **M1-T032** Broker perf test at 16 partitions, 300 B, 60 s. Save output to `docs/measurements/AC-10-<date>.txt` · 🐳 · Refs: AC-10, NFR-003 · Done: 2026-10-21 (801k msg/s, no compression)
- [x] **M1-T033** Tick "Verified" for the image pins in `versions.md`. Log a SYNC_LOG entry if pins changed · Refs: NFR-005 · Done: 2026-10-21 (versions.md rc.3)

## Phase 5 — Polish and verify
- [x] **M1-T040** Module README quick start (engine setup, `make install/run`, platform commands, memory budget) · Done: 2026-10-21
- [x] **M1-T041** Spec AC table → ✅ with test references. Status → Verified. DEVELOPMENT_LOG entry · Done: 2026-10-21

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 Setup | 3 | 3 | — |
| 2 Tests | 5 | 5 | — |
| 3 Core | 6 | 6 | — |
| 4 Integration / Measure | 4 | 4 | — |
| 5 Polish | 2 | 2 | — |

## Blockers log
| Date | Task | Blocked on | Resolution |
|---|---|---|---|
| 2026-10-21 | All | Gates G1 (spec review by M3/M4), G2, G3 | Owner approved G1–G3 on 2026-10-21. Consumer review of the spec still requested |
| 2026-10-21 | follow-up | Host clients first try `localhost` → ::1 (IPv6), which Colima does not forward. librdkafka falls back to IPv4 (harmless warning). Consider advertising `127.0.0.1:9092` via a C-06 CR | Open (minor) |
