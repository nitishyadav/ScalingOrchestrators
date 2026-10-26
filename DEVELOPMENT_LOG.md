# Development Log — Aswin S. (M1 Data Ingestion and Platform)

An append-only record of every step taken, at every level of development, from the proposal to the final demo.
It is created from `sdd/templates/development-log-template.md` and maintained under procedure **PR-20**.
Never rewrite past entries. Add a correcting entry instead.

## Levels

| Level | Name | Typical steps | Procedures |
|---|---|---|---|
| L0 | Project | Proposal analysis, plan, decisions, environment readiness | PR-00, PR-03 |
| L1 | SDD framework | Workspace, constitution, workflow, templates, playbook | PR-01, PR-02 |
| L2 | Contracts | Contract docs, schemas, `ids_contracts`, golden fixtures, CRs, syncs | PR-04–06, PR-13, PR-14 |
| L3 | Module | Module README, Makefile, mocks, module ADRs | PR-12 |
| L4 | Feature | spec.md → plan.md → tasks.md, verification | PR-07–09, PR-11 |
| L5 | Task / code | TDD loop per task (`MN-Txxx`) | PR-10 |
| L6 | Integration | Module swaps, pairwise and E2E integration | PR-15, PR-16 |
| L7 | Experiments and report | E1–E3, recovery, FPR, figures, report, Git push | PR-17, PR-19 |

## Progress by level (as of 2026-10-22, end of session)

| Level | Status | Last step | Next step |
|---|---|---|---|
| L0 Project | ✅ Plan drafted. ✅ Environment + dataset ready (verified). 🟡 decisions proposed | S-020 toolchain + Docker engine | Team sync: accept the ADRs. Others draft D-01/02/04/05/08/10. **You:** dataset form |
| L1 SDD framework | ✅ Complete (constitution unsigned) | S-018 development log + PR-20 | PR-02: all 4 sign the constitution |
| L2 Contracts | 🟡 C-01 rc.5, C-06 rc.6, versions rc.3 In Review. 🔶 C-02..C-05 provisional replicas (S-045) | S-030 | **You:** send the bundle. Consumers review (PR-05) |
| L3 Module | ✅ M1 complete. 🔨 M4 replica (F01, F02) · 🔨 M2 replica (F02, F04) · ✅ M3 replica (F01–F04) | S-049 | M2-F03, M4-F03 |
| L4 Feature | ✅ **Module 1 complete**: F01 11/11 · F02 10/10 · F03 10/10 · F04 9/9 | S-044 | Replica M2–M4 features |
| L5 Task / code | ✅ M1: 20 + 14 + 12 + 8 = 54/54 tasks | S-044 | Replica tasks |
| L6 Integration | 🟡 Replica end-to-end pipeline runs (S-049). Canonical-module integration pending (team) | S-049 | I-01..I-04 with the owners' modules |
| L7 Experiments | ⬜ Not started | — | Phase P3 (5–10 Nov) |

---

## Step log

### S-001 · 2026-10-21 · L0 Project · PR-00
**What:** Analysed the project proposal (`../1_PHASE_1_IDEA_GEN/des_project_proposal 3.html`). Extracted the architecture
(producer → Kafka → Spark → Cassandra → Streamlit), design goals, success metrics and experiments, and gave them stable IDs:
goals G1–G6, performance metrics P1–P5, feature metrics F1–F5, and experiments E1–E3.
**Why:** SDD needs traceable requirements. Every later spec cites these IDs.
**Artifacts:** `PROJECT_PLAN.md` §1.1–1.3.
**Verification:** Cross-checked against proposal §1.3, §3.1–3.3 and §4.
**Decisions / issues:** none.

### S-002 · 2026-10-21 · L0 Project · PR-03 (identification)
**What:** Reviewed the proposal for gaps and inconsistencies that would break independently built modules. Found D-01..D-10:
the latency target conflicts with 30 s windows plus a watermark; the Cassandra `date_bucket` key creates a hotspot; MachineLearningCVE
lacks Source IP and Timestamp; PortScan is in the Friday file, not Thursday's; the 0.5 efficiency target contradicts the 1.5× milestone;
2017 timestamps would break watermarks; there is no ground truth in the stream; feature formulas are underspecified;
version pins are missing (sklearn pickles); there is no transport for metrics to the dashboard.
**Why:** Unresolved ambiguity is the main cause of integration failure.
**Artifacts:** `PROJECT_PLAN.md` §1.4.
**Verification:** n/a (analysis).
**Decisions / issues:** each D-xx becomes an ADR (PR-03).

### S-003 · 2026-10-21 · L0 Project · —
**What:** Split the system into 4 equal modules with one owner each, and 4 features per module: M1 Aswin (ingestion and platform),
M2 Nitish (ML model), M3 Priyanka (Spark streaming), M4 Vidhi (storage, dashboard, benchmarks). Fixed the folder names and Python packages.
**Why:** Equal workload, and each module owns one pipeline stage end to end.
**Artifacts:** `PROJECT_PLAN.md` §2, the four `ModuleN_*/README.md` files.
**Verification:** Effort-balance table (§2) and traceability matrix (§5).
**Decisions / issues:** none.

### S-004 · 2026-10-21 · L0 Project · —
**What:** Designed the plug-and-play integration architecture. Modules meet only through 4 seams (Kafka, files, Cassandra, CLI/env),
defined by 6 contracts (C-01..C-06). Mechanisms: mock-first, golden fixtures, contract tests, uniform Makefile targets,
"folder is the unit of exchange", and versioned contracts with change requests.
**Why:** The user requirement that each member builds all modules, and that any owner's module can be dropped in at integration.
**Artifacts:** `PROJECT_PLAN.md` §3, `contracts/README.md`, `integration/README.md`.
**Verification:** n/a (design).
**Decisions / issues:** none.

### S-005 · 2026-10-21 · L0 Project · —
**What:** Rebuilt the timeline on real dates (report 15 Nov, demo 29 Nov), using a compressed, parallel schedule with phases P0–P5.
Wrote the traceability matrix (goals and metrics → module features) and the risk register R1–R7.
**Why:** The proposal's 8-week plan no longer fits the remaining time.
**Artifacts:** `PROJECT_PLAN.md` §4–§7.
**Verification:** n/a.
**Decisions / issues:** R1 (16 GB RAM) and R7 (time) rated High.

### S-006 · 2026-10-21 · L1 SDD framework · PR-01
**What:** Created the workspace skeleton: four module folders, each with `specs/ src/<pkg>/ tests/{unit,contract,integration}/ mocks/ docs/adr/`,
plus `sdd/templates`, `contracts/{schemas,fixtures,python}`, `integration/checklists` and `docs/adr`, with `.gitkeep` files.
**Why:** Identical structure for all members, which the integration process depends on.
**Artifacts:** folder tree. `README.md` (folder map).
**Verification:** `find . -type d` listing matched the design.
**Decisions / issues:** none.

### S-007 · 2026-10-21 · L1 SDD framework · PR-02 (draft)
**What:** Wrote the project constitution with 12 articles (spec before code, contracts as the only coupling, module isolation, mock-first,
uniform Makefile, config through env, honest ML, tests from ACs, version pins, measured claims, ownership and CRs, simplicity).
**Why:** Non-negotiable rules that keep four independent builds compatible.
**Artifacts:** `CONSTITUTION.md` (signature table empty).
**Verification:** n/a.
**Decisions / issues:** needs all 4 signatures.

### S-008 · 2026-10-21 · L1 SDD framework · —
**What:** Wrote the SDD workflow (document hierarchy, gates G0–G5, ID scheme, review rules, change handling, AI usage) and 8 templates:
spec, plan, tasks, contract, contract change request, ADR, integration checklist, module README.
**Why:** The core of SDD: every feature follows the same artifacts and gates.
**Artifacts:** `sdd/WORKFLOW.md`, `sdd/templates/*.md`.
**Verification:** n/a.
**Decisions / issues:** none.

### S-009 · 2026-10-21 · L1 SDD framework · —
**What:** Wrote the module READMEs (scope, provides/consumes, mocks), the contracts registry, the integration guide and `.gitignore`
(data, models, checkpoints and `.env` excluded).
**Why:** Each module states its interfaces up front. The roughly 2 GB dataset must never be committed.
**Artifacts:** `Module{1..4}_*/README.md`, `contracts/README.md`, `integration/README.md`, `.gitignore`.
**Verification:** n/a.
**Decisions / issues:** none.

### S-010 · 2026-10-21 · L1 SDD framework · —
**What:** Wrote the shareable, self-contained **SDD Playbook**: instructions for AI tools, canonical names, a provisional contract
baseline (v0.1 for C-01..C-06 and the pins), procedures PR-00..PR-19, the replica build order, owner versus replica mode, and phase
checkpoints. It is generated with an appendix of all workspace files. While writing it, identified **D-11** (replay time model,
a training/serving skew risk) and added it to the plan.
**Why:** Teammates give the playbook and the proposal to their AI tools to recreate the same workspace and build compatible replicas.
**Artifacts:** `sdd/playbook_core.md`, `sdd/build_playbook.sh`, `SDD_PLAYBOOK.md` (generated), `PROJECT_PLAN.md` (D-11), `runtime/` added to `.gitignore`.
**Verification:** Build script output 20 appendix sections with balanced fences.
**Decisions / issues:** D-11 added.

### S-011 · 2026-10-21 · L0 Project · —
**What:** Readiness check of the M1 owner's machine. Apple M3, 8 cores, 16 GB RAM, 197 GB free. **Docker not installed.** Python is only
the system 3.9.6. Java 21 and 8 are present (Spark 3.5 needs 8, 11 or 17). git and make are present.
**Why:** M1-F01 (platform) and local PySpark tests depend on these.
**Artifacts:** none (findings recorded here).
**Verification:** `docker`, `python3 --version`, `java -version`, `sysctl` and `df` checks.
**Decisions / issues:** Action items: install Docker Desktop (about 10 GB RAM and 6 CPUs allocated), Python 3.11 and Java 17 (Temurin).
Request the CIC-IDS2017 download.

### S-012 · 2026-10-21 · L2 Contracts · PR-04
**What:** Authored **C-01 Network Event 1.0.0-rc.1**: Kafka transport (topic, key, retention 30 min, compression), 11 fields with types, units
and constraints, the CIC TrafficLabelling column mapping and drop rules, a normalised label set, replay Parquet columns
(including `row_idx` and `source_file`), semantics (time, order, duplicates, eval-only), error handling and contract tests.
**Why:** M3 (stream) and M2 (training) both depend on this seam. It is the first contract needed.
**Artifacts:** `contracts/C-01_network_event.md`, `contracts/schemas/event.schema.json`.
**Verification:** see S-016.
**Decisions / issues:** applies ADR-003, -006, -007 and -011. CIC file names to be confirmed on download.

### S-013 · 2026-10-21 · L2 Contracts · PR-04
**What:** Authored **C-06 Runtime Config and Control 1.0.0-rc.1** (21 env vars with types and ranges, precedence rules, workspace-root
detection, compose service names and ports, the 4 control CLIs with flags, exit codes and a JSON summary line, the run-ID pattern,
the runtime directory layout) and **versions.md 1.0.0-rc.1** (pins plus hard rules, including a Colab pip cell).
**Why:** Every module and the M4 benchmark harness depend on stable config and commands.
**Artifacts:** `contracts/C-06_runtime_config_control.md`, `contracts/versions.md`, `integration/.env.example`.
**Verification:** see S-016.
**Decisions / issues:** applies ADR-009. Spark 3.5.5 with Java 17. The job is submitted from inside the Spark image.

### S-014 · 2026-10-21 · L2 Contracts · PR-06
**What:** Created the shared package **`ids_contracts`** (installable with `pip install -e contracts/python`, requires Python 3.9+,
no runtime dependencies). `events.py` provides field constants, the label set, the CIC mapping, `validate_event`/`check_event`,
`encode_event`/`decode_event`/`event_key`, `normalise_label` and `validate_replay_columns`. `config.py` provides `ENV_SPEC`,
`load_config` (with precedence and validation), `RuntimeConfig`, `validate_run_id`, `summary_line`, `read_env_file` and the exit codes.
**Why:** One validated implementation of each contract rule, shared by all modules, so contracts are enforced in code.
**Artifacts:** `contracts/python/pyproject.toml`, `contracts/python/ids_contracts/{__init__,events,config}.py`.
**Verification:** see S-016.
**Decisions / issues:** none.

### S-015 · 2026-10-21 · L2 Contracts · PR-06
**What:** Generated the golden fixture **`events_golden.jsonl`** deterministically: 126 events, 4 source IPs (benign, port scan,
injected SYN flood, DDoS), exact window-boundary times, and one late event within the 60 s watermark. Documented the scenario
for consumers.
**Why:** The shared input for M2/M3 feature parity and M3 parse tests. It is also the M1 mock (`producer --source fixture`).
**Artifacts:** `contracts/fixtures/_gen/gen_events_golden.py`, `contracts/fixtures/events_golden.jsonl`, `contracts/fixtures/README.md`.
**Verification:** The generator validates every event with `check_event(strict=True)`. The file has 126 lines.
**Decisions / issues:** none.

### S-016 · 2026-10-21 · L2 Contracts · PR-06
**What:** Wrote and ran the contract tests for C-01 (golden fixture shape, strict validity, late event, determinism,
invalid-value cases, encode/decode round trip, label normalisation, replay columns, JSON Schema versus Python agreement) and
C-06 (defaults, precedence, range errors, attack consistency, run IDs, summary line, `.env.example` versus `ENV_SPEC`).
**Why:** Constitution Art. VIII. A contract must have executable checks before it can be approved.
**Artifacts:** `contracts/python/tests/test_events.py`, `contracts/python/tests/test_config.py`.
**Verification:** `PYTHONPATH=. python3 -m pytest` in `contracts/python` gave **57 passed** (system Python 3.9.6, pytest, jsonschema).
**Decisions / issues:** re-run on Python 3.11 once it is installed.

### S-017 · 2026-10-21 · L0 Project · PR-03
**What:** Drafted ADRs for the decisions behind the M1 contracts: ADR-003 (TrafficLabelling dataset), ADR-006 (emission-time
timestamp), ADR-007 (eval-only ground-truth fields), ADR-009 (identical version pins, Java 17, job submitted from the image) and
ADR-011 (constant-rate replay with an offline time model at R_ref = 5000 ev/s).
**Why:** Each contract choice must be traceable to an accepted decision.
**Artifacts:** `docs/adr/ADR-003…`, `ADR-006…`, `ADR-007…`, `ADR-009…`, `ADR-011…`.
**Verification:** n/a (status Proposed).
**Decisions / issues:** need team acceptance. ADR-011 needs M2's explicit agreement.

### S-018 · 2026-10-21 · L1 SDD framework · PR-20
**What:** Started this development log. Added the development-log template and procedure PR-20 (keep a step log) to the playbook,
logged the contract publication in `contracts/SYNC_LOG.md`, and updated the contract registry statuses.
**Why:** User request: a step-by-step record of everything done at each level of development.
**Artifacts:** `DEVELOPMENT_LOG.md`, `sdd/templates/development-log-template.md`, `contracts/SYNC_LOG.md`, `contracts/README.md`,
`sdd/playbook_core.md`, `SDD_PLAYBOOK.md` (regenerated).
**Verification:** Playbook rebuilt.
**Decisions / issues:** none.

### S-019 · 2026-10-21 · L0 Project · —
**What:** Tried to obtain the CIC-IDS2017 dataset. The official page (unb.ca/cic/datasets/ids-2017.html) links to
cicresearch.ca/CICDataset/CIC-IDS-2017/, which is a **registration form** (name, email, organisation, job title, country).
**Why:** M1-F02 and M2 need `GeneratedLabelledFlows.zip` (ADR-003).
**Artifacts:** none.
**Verification:** Fetched both pages. The deep CSV links redirect back to the dataset index without registration.
**Decisions / issues:** The AI did not submit personal data on the user's behalf. **The user must fill in the form** and download `GeneratedLabelledFlows.zip` into `runtime/data/raw/`.

### S-020 · 2026-10-21 · L0 Project · —
**What:** Installed the toolchain with Homebrew: python@3.11 (3.11.17), openjdk@17 (17.0.21), colima (0.10.3), docker CLI (29.9.2)
and docker-compose (5.6.1). The first attempt failed on a transient ca-certificates link conflict, and the second on an outdated
Homebrew post-install step. Fixed with `brew update` + `brew postinstall python@3.11`. Registered the Compose plugin in
`~/.docker/config.json` (`cliPluginsExtraDirs`). Started Colima (`--cpu 6 --memory 10 --disk 60 --vm-type vz`).
Created a workspace venv `.venv` (Python 3.11) with `ids-contracts[test]` + pyyaml.
**Why:** S-011 action items. Docker is required for M1-F01. Python 3.11 is the pin.
**Artifacts:** `.venv/` (git-ignored), `~/.docker/config.json`.
**Verification:** `docker info` reports server 29.5.2, 6 CPUs, about 10 GB, aarch64. `docker run hello-world` OK. Contract tests on 3.11: 57 passed.
**Decisions / issues:** Colima chosen over Docker Desktop because Desktop needs an admin password and a GUI first run (M1-ADR-003 to record).
Java 17 is keg-only. Set `export JAVA_HOME=/opt/homebrew/opt/openjdk@17` for local PySpark (not added to the shell profile).
Colima holds up to 10 GB, so run `colima stop` when not working.

### S-021 · 2026-10-21 · L4 Feature · PR-07, PR-08, PR-09
**What:** Wrote the **M1-F01 platform-cluster** spec (10 FRs, 6 NFRs, 11 ACs, edge cases), plan (KRaft Kafka with dual listeners,
Spark master + 2×2-core workers + `spark-client`, Cassandra with capped heap, custom Spark image with pinned stack and baked
connector jars, `ids_ingest.platform` / `topic_admin` CLIs, a 9.75 GB memory budget, a Constitution Check, a test strategy) and 22 tasks in
5 phases.
**Why:** Phase 0 checklist: each owner writes their F01 spec. The platform blocks every module's integration.
**Artifacts:** `Module1_Data_Ingestion_Platform/specs/M1-F01-platform-cluster/{spec,plan,tasks}.md`.
**Verification:** Spec review checklist ticked except the consumer review.
**Decisions / issues:** The plan proposes M1-ADR-001 (KRaft instead of ZooKeeper, which deviates from the proposal wording),
M1-ADR-002 (confluent-kafka) and M1-ADR-003 (Colima). **Gates G1–G3 are pending. No code written.**

### S-022 · 2026-10-21 · L2 Contracts · PR-04 (revision)
**What:** Revised **C-06 to 1.0.0-rc.2** with changes found while writing the M1-F01 spec: a `spark-client` service, the `ids_ingest.platform`
command, a new `SPARK_WORKERS` env var (1–4), and `SPARK_EXECUTOR_MEMORY` default changed from 1g to 768m (4 executors fit the 10 GB budget).
Updated `ids_contracts/config.py`, `.env.example`, the tests, playbook §5 and the SYNC_LOG. Revised **versions.md to rc.2** (confluent-kafka, container engine;
host Python and Java marked verified).
**Why:** The contract had to cover what the platform provides. It was still in review, so no CR was needed.
**Artifacts:** `contracts/C-06_runtime_config_control.md`, `contracts/versions.md`, `contracts/python/ids_contracts/config.py`,
`contracts/python/tests/test_config.py`, `integration/.env.example`, `contracts/SYNC_LOG.md`, `contracts/README.md`, `sdd/playbook_core.md`.
**Verification:** `.venv/bin/python -m pytest` gave **58 passed** on Python 3.11.17.
**Decisions / issues:** none.

### S-023 · 2026-10-21 · L2 Contracts · —
**What:** Checked that the pinned images exist for arm64 with `docker manifest inspect`: `apache/spark:3.5.5-scala2.12-java17-python3-ubuntu` ✅,
`apache/kafka:3.8.1` ✅, `cassandra:4.1.10` ✅. Recorded the exact tags in `versions.md` and the M1-F01 plan.
**Why:** De-risk the pins before the team reviews them. This is information gathering only (task M1-T003 stays formally open until the gates pass).
**Artifacts:** `contracts/versions.md`, `Module1_…/specs/M1-F01-platform-cluster/plan.md`.
**Verification:** All three manifests list arm64.
**Decisions / issues:** Runtime verification (the image actually runs with the pinned Python stack) remains in M1-F01.

### S-024 · 2026-10-21 · L2 Contracts · PR-14 (publish)
**What:** Rebuilt the playbook (3,644 lines, 39 appendix files). Assembled the team bundle in `../TEAM_SHARE/2026-10-21/`: the playbook,
the proposal, `contracts_2026-10-21.zip` (28 files) and a ready-to-send message with review requests and owner deadlines.
**Why:** Teammates need the playbook and contracts to set up, review and start their own contracts.
**Artifacts:** `../TEAM_SHARE/2026-10-21/{MESSAGE_TO_TEAM.md, SDD_PLAYBOOK.md, contracts_2026-10-21.zip, des_project_proposal 3.html}`.
**Verification:** Zip listing shows 28 files. `*.egg-info` and caches excluded and git-ignored.
**Decisions / issues:** **Sending is left to the user** (outward-facing).

### S-025 · 2026-10-21 · L2 Contracts · PR-14 (correction of S-024)
**What:** The project-tree review found a stray, dangling symlink `contracts/python/{{pkgetc}}/cert.pem`. The failed Homebrew
post-install step (S-020) created it, with unfilled path placeholders, because the shell's working directory was `contracts/python`.
It had been included in the S-024 zip. Removed it and rebuilt `contracts_2026-10-21.zip`, which now has **27 files** (not 28).
**Why:** Shared bundles must contain only contract content.
**Artifacts:** `../TEAM_SHARE/2026-10-21/contracts_2026-10-21.zip` (rebuilt).
**Verification:** No `{{` entries in the zip listing. Contract tests still 58 passed. Colima running.
**Decisions / issues:** Lesson: run package-manager commands from a neutral directory, never from inside the workspace.

### S-026 · 2026-10-21 · L4 Feature · gates G1–G3
**What:** The user filed the CIC dataset form (the download itself is still pending) and **approved M1-F01 spec, plan and tasks**, choosing
KRaft over ZooKeeper. Statuses set to Approved. The consumer review of the spec by M3/M4 is still requested.
**Why:** SDD: no implementation before G1–G3.
**Artifacts:** `Module1_…/specs/M1-F01-platform-cluster/{spec,plan,tasks}.md`.
**Verification:** n/a.
**Decisions / issues:** M1-ADR-001 (KRaft) accepted.

### S-027 · 2026-10-21 · L3 Module / L5 Task · PR-10 (M1-T001, T002)
**What:** Module 1 skeleton: `pyproject.toml` (ids-ingest, confluent-kafka 2.6.1, pyyaml), `requirements.txt`, a `Makefile` with the 6 standard
targets plus `integration-test`, `src/ids_ingest/__init__.py`. Wrote M1-ADR-001 (KRaft), M1-ADR-002 (confluent-kafka) and M1-ADR-003 (Colima or Docker Desktop).
Added `load_runtime_config` to `ids_contracts.config` (`integration/.env` < process env < overrides, per C-06 §2) with 2 tests.
**Why:** Constitution Art. V. Every module CLI must load config the same way.
**Artifacts:** `Module1_…/{pyproject.toml,requirements.txt,Makefile,src/ids_ingest/__init__.py,docs/adr/M1-ADR-00{1,2,3}-*.md}`, `contracts/python/ids_contracts/config.py`, `contracts/python/tests/test_config.py`.
**Verification:** Contract package 60 passed.
**Decisions / issues:** confluent-kafka 2.6.1 arm64 cp311 wheel confirmed on PyPI.

### S-028 · 2026-10-21 · L5 Task · PR-10 (M1-T010..T014, tests first)
**What:** Wrote the tests before the code: static compose checks (AC-09), the topic_admin decision table with a fake admin (AC-05), platform CLI behaviour with a
fake engine and clock (AC-02/08/11), C-06 contract tests (doc ↔ compose ↔ CLI), live integration tests (AC-01..08) with a Spark
smoke job, and a broker perf test (AC-10). The first run was **red** as expected (collection errors and 8 contract failures).
**Why:** Constitution Art. VIII. Every AC has a test before any implementation.
**Artifacts:** `Module1_…/tests/{conftest.py, unit/*, contract/*, integration/*}`.
**Verification:** Red state confirmed.
**Decisions / issues:** none.

### S-029 · 2026-10-21 · L5 Task · PR-10 (M1-T020..T024)
**What:** Implemented the Spark image (FROM `apache/spark:3.5.5-scala2.12-java17-python3-ubuntu`, pinned stack, 5 connector jars fetched at
build with SHA-1 verification: spark-sql-kafka 3.5.5, token-provider 3.5.5, kafka-clients 3.4.1 (from the spark-parent POM), commons-pool2 2.11.1,
SCC assembly 3.5.1), `docker-compose.yml` (KRaft dual listeners, master, 2×2-core workers, spark-client, Cassandra, health checks, limits,
mounts), `_compose.py`, `platform.py` (up/status/down/clean/restart-worker with engine, memory and port pre-checks and readiness polling) and
`topic_admin.py` (create/noop/increase/refuse/recreate, retention 30 min).
**Why:** M1-F01 FR-001..FR-010.
**Artifacts:** `Module1_…/platform/{docker-compose.yml, spark/Dockerfile, spark/requirements-spark.txt, spark/fetch_jars.py, spark/spark-defaults.client.conf}`, `src/ids_ingest/{_compose,platform,topic_admin}.py`.
**Verification:** Unit 48 passed, contract 8 passed. Two failures fixed along the way: (1) a test bug, where the volume parser split `${VAR:?msg}`;
(2) a **real gap**, where `status` did not check the engine first, so it now fails fast with the "start Colima" hint, as the spec requires.
**Decisions / issues:** C-06 → **rc.3**: zookeeper not used, workers mount workspace and runtime (checkpoints shared with executors), `load_runtime_config`.

### S-030 · 2026-10-21 · L5 Task / L6 · PR-10, PR-11 (M1-T025, T030..T033)
**What:** Built the image (2.69 GB, stack printed 1.5.2 / 1.26.4 / 2.2.3 / 17.0.0), started the platform: **all 5 services healthy and 2 workers in 59.1 s**.
`spark-client` was trimmed from 1.5 to 1.25 GiB because Colima `--memory 10` reports 9.69 GiB (budget is now 9.5 GiB). Live tests **8/8 passed**
(1 min 51 s), covering dual listeners, a pandas_udf + sklearn job on the workers with identical Python 3.10.12 and pins on driver and executors, connectors local,
worker restart re-registered, and data kept across down/up. Broker perf: the first run (lz4, identical payloads) gave 1.17M msg/s, which is **inflated by compression and was discarded**.
Re-run without compression: **801,325 msg/s** for 300-byte messages over 60 s at 16 partitions (target ≥ 15,000).
**Why:** M1-F01 AC-01..AC-10, Constitution Art. X (measured, saved, honest).
**Artifacts:** `Module1_…/docs/measurements/AC-10-2026-10-21.json`, `contracts/versions.md` (**rc.3**: image pins verified at runtime).
**Verification:** As above. The runtime versions were read from the running containers (Python 3.10.12, Java 17.0.14, Kafka 3.8.1, Cassandra 4.1.10).
**Decisions / issues:** Minor open item: host clients first try IPv6 `::1` for `localhost`, which Colima does not forward. A harmless warning, logged in tasks.md.

### S-031 · 2026-10-21 · L4 Feature · PR-11 (M1-T040, T041)
**What:** Module 1 README quick start (engine setup, make targets, platform commands, job submission from spark-client, memory budget).
Spec AC table all ✅ with test references. Spec status **Verified**. 20/20 tasks ticked (the earlier "22 tasks" in S-021 was a miscount; it is 20).
Rebuilt the playbook and refreshed the team bundle (contracts zip with C-06 rc.3 and versions rc.3, message updated to 60 tests).
**Why:** Gate G4. The team bundle had not been sent yet, so it is refreshed rather than versioned.
**Artifacts:** `Module1_…/README.md`, `…/spec.md`, `…/tasks.md`, `SDD_PLAYBOOK.md`, `../TEAM_SHARE/2026-10-21/*`.
**Verification:** See S-032.
**Decisions / issues:** none.

### S-032 · 2026-10-21 · L4 Feature · PR-11 (gate G4 check)
**What:** Final clean run of all suites after the playbook rebuild (3,722 lines) and the team-zip refresh (27 files).
**Why:** Gate G4: tests green and every AC verified.
**Artifacts:** `SDD_PLAYBOOK.md`, `../TEAM_SHARE/2026-10-21/{SDD_PLAYBOOK.md, contracts_2026-10-21.zip}`.
**Verification:** contracts package **60 passed** · M1 unit **48 passed** · M1 contract **8 passed** · platform `status` ready (5 services healthy, 2/2 workers alive).
Live suites from S-030: integration **8 passed**, perf **1 passed** (801,325 msg/s).
**Decisions / issues:** The platform is left **running** (Colima holds up to 10 GB). Stop with `python -m ids_ingest.platform down` and `colima stop`.

### S-033 · 2026-10-21 · L0 Project / L2 Contracts · PR-04 (revision)
**What:** The user downloaded the dataset. The `.zip` in `~/Downloads` was a **stalled partial download** (68 MB, not a valid zip), but the extracted
`~/Downloads/TrafficLabelling /` folder held all 8 CSVs (1.1 GB). Copied them (originals untouched) to `runtime/data/raw/TrafficLabelling/` and
recorded SHA-256 checksums. Profiled every row against the C-01 rules with a read-only script (scratchpad, `python -I`): **3,119,345 data rows to
2,830,743 valid**, the only drops being 288,602 empty rows (Thursday WebAttacks). All 8 mapped columns present. Headers padded with spaces. `Fwd Header Length`
is duplicated. Web-attack labels carry `\x96`. **Timestamp formats are inconsistent** (`dd/mm/yyyy hh:mm:ss` on Monday, `d/m/yyyy h:mm` 12-hour without AM/PM elsewhere).
No IPv6. No fractional bytes. All 15 labels map into the C-01 label set.
**Why:** Open item #11. Check that the contract (written partly from memory) matches the real data before review.
**Artifacts:** `runtime/data/raw/TrafficLabelling/*.csv` (git-ignored). C-01 **rc.2** (reference table with checksums and valid-row counts per file, raw-file quirks,
`orig_ts` declared opaque). `ids_contracts.events` (`CIC_REFERENCE`, `CIC_TOTAL_VALID_ROWS`, `verify_cic_file`) + 2 tests. Fixture `orig_ts` strings corrected to the
real day-first format and regenerated. ADR-003 marked verified. PROJECT_PLAN D-04 confirmed from data.
**Verification:** `verify_cic_file` passes for all 8 raw files. Contracts package **62 passed**. M1 unit 48, contract 8 passed.
**Decisions / issues:** **D-04 confirmed:** PortScan only in Fri-Afternoon-PortScan (158,930), Infiltration 36 on Thursday afternoon, Monday 100 % benign.
For M2: the F1 test files are attack-heavy (PortScan 55 %, DDoS 57 %), so the report must state the base rate when quoting precision.
At R_ref = 5000 ev/s the full replay takes 566 s (9.4 min), so M1-F03 must support looping for 10 k ev/s runs.

### S-034 · 2026-10-21 · L1 SDD framework / L2 Contracts · PR-14 (deferred)
**What:** **User decision:** the team bundle will be shared only once development is complete. Replaced the dated `TEAM_SHARE/2026-10-21/` folder
with `sdd/make_team_share.sh`, which regenerates `../TEAM_SHARE/` from the current playbook, proposal, contracts zip and message
(the message source moved to `sdd/team_message.md`).
**Why:** A bundle sent later must reflect the latest contracts, not a stale snapshot.
**Artifacts:** `sdd/make_team_share.sh`, `sdd/team_message.md`, `../TEAM_SHARE/` (regenerated).
**Verification:** The script ran and produced 4 files.
**Decisions / issues:** **Trade-off accepted by the user:** C-01, C-06 and versions.md stay "In Review" (owner-approved only) until teammates see them.
Replicas of M2–M4 are built against the playbook §5 baseline, and any mismatch with their real C-02..C-05 will surface at integration (risk R5).

### S-035 · 2026-10-21 · L4 Feature · PR-07, PR-08, PR-09
**What:** Drafted **M1-F02 Dataset Preparation**: spec (8 FRs, 4 NFRs, 10 ACs), plan (streaming stdlib-csv + pyarrow ParquetWriter, positional
column selection for the duplicated header, row-content SHA-256 for determinism, atomic swap, stratified mock sample) and 14 tasks.
The plan relies on the S-033 profiling run (about 23 s for a full pass).
**Why:** Next M1 feature. M1-F03 and all of M2 depend on the replay dataset.
**Artifacts:** `Module1_…/specs/M1-F02-dataset-preparation/{spec,plan,tasks}.md`.
**Verification:** Spec review checklist ticked except the consumer review (M2).
**Decisions / issues:** Needs C-01 rc.3 (manifest schema) and C-06 rc.4 (`prepare` CLI) in task M1-T051. **Gates G1–G3 pending.**

### S-036 · 2026-10-21 · L4 Feature / L2 Contracts · gates G1–G3, PR-10 (M1-T050, T051)
**What:** The user reviewed the M1-F02 docs (no comments) and **approved G1–G3**. Added `pyarrow==17.0.0` to M1 (package 0.2.0). C-01 → **rc.3**:
formal replay-manifest schema (§2.2) + `validate_manifest`, `DROP_REASONS`, `MANIFEST_*` in `ids_contracts` with 8 tests. C-06 → **rc.4**: the `ids_ingest.prepare`
command. `.gitignore` exception for `mocks/replay_sample.parquet`.
**Why:** FR-014 and FR-018 need contract support before code (Art. II).
**Artifacts:** `contracts/C-01_network_event.md`, `contracts/C-06_runtime_config_control.md`, `contracts/python/ids_contracts/events.py`, tests, `contracts/versions.md`, SYNC_LOG.
**Verification:** Contracts package 70 passed.
**Decisions / issues:** none.

### S-037 · 2026-10-21 · L5 Task · PR-10 (M1-T060..T073)
**What:** Tests first: `tests/csv_factory.py` (synthetic CSVs reproducing the real quirks: padded and duplicated headers, latin-1 `\x96`, empty rows),
22 unit tests (defect matrix, verification, noop/force determinism, atomic failure, verify-only tamper, sample, CLI), 5 C-01 contract tests, and 5 real-data
tests (red as expected). Then `src/ids_ingest/prepare.py`: `RowCleaner` (positional mapping, 9 drop reasons), `DayWriter` (100k-row chunked ParquetWriter
+ content hash), `prepare_all` (verify, noop/force, atomic swap via `replay.tmp-*`), `verify_replay`, `make_sample` (per-label quota), CLI.
**Why:** M1-F02 FR-011..FR-018.
**Artifacts:** `Module1_…/src/ids_ingest/prepare.py`, `tests/csv_factory.py`, `tests/unit/test_prepare.py`, `tests/contract/test_c01_replay_contract.py`,
`tests/integration/test_prepare_real_data.py`, Makefile (`mock` → sample, `data-test`).
**Verification:** One failure on the first green attempt: `pq.read_table` on a file inside `day=X/` silently adds a hive `day` column. Both the test and `verify_replay`
were switched to `pq.ParquetFile(...).read()`, so only the file's own schema is checked. Also simplified a convoluted create/rebuild expression. Unit 71, contract 12 (+1 skipped) passed.
**Decisions / issues:** none.

### S-038 · 2026-10-21 · L5 Task / L4 Feature · PR-10, PR-11 (M1-T080..T091)
**What:** Ran on the **real dataset**: 2,830,743 rows (Mon 529,918 · Tue 445,909 · Wed 692,703 · Thu 458,968 · Fri 703,245), the only drops being 288,602 empty rows,
all 15 label totals as profiled, verify-only OK, rerun noop, forced rebuild with identical content hashes. **Measured (AC-09): 27.1 s, peak 139 MB, 34.3 MB on disk**
(targets 300 s / 2 GB / 300 MB). Committed the mock `mocks/replay_sample.parquet` (8,046 rows, all 15 labels, 72 KB, byte-identical on regeneration).
Published the per-day reference `content_sha256` in **C-01 rc.4** + `ids_contracts.events.REPLAY_CONTENT_SHA256`, enforced by the real-data test, so any replica can
prove it replays identical data. README dataset section. Spec AC table all ✅, status **Verified**. 14/14 tasks.
**Why:** Gate G4. Plug-and-play: identical replay data across replicas is now checkable.
**Artifacts:** `runtime/data/replay/` (git-ignored), `Module1_…/mocks/replay_sample.parquet`, `Module1_…/docs/measurements/AC-09-M1-F02-2026-10-21.json`,
`contracts/C-01_network_event.md` (rc.4), `ids_contracts/events.py`, `Module1_…/README.md`, spec/tasks.
**Verification:** Contracts **71** · M1 unit **71** · M1 contract **13** · real data **5** passed. The rebuild under rc.4 reproduced the reference hashes.
**Decisions / issues:** The output is far smaller than estimated (34 MB rather than 100–200 MB) thanks to dictionary encoding. Next: M1-F03 replay producer (must loop the 9.4-min replay for 10 k ev/s runs).

### S-039 · 2026-10-21 · L4 Feature / L2 Contracts · PR-07..09 (gates pre-approved), PR-04 (M1-T100)
**What:** The user instructed "proceed and also go ahead and develop", which pre-approves G1–G3 for **M1-F03 Replay Producer**. Wrote the spec (10 FRs, 5 NFRs, 10 ACs),
plan (source / pacer / sink split, injectable clock, `murmur2_random` partitioner) and 12 tasks. Contracts: **C-01 rc.5** (librdkafka producers must set
`partitioner=murmur2_random`, because the librdkafka default hashes keys differently from Java/Spark) + `LIBRDKAFKA_PARTITIONER`. **C-06 rc.5** (producer
flags `--no-loop`, `--allow-unverified`, full summary fields).
**Why:** The next M1 feature. Every throughput and latency number depends on this stream.
**Artifacts:** `Module1_…/specs/M1-F03-replay-producer/{spec,plan,tasks}.md`, `contracts/C-01_*.md`, `contracts/C-06_*.md`, `ids_contracts/{events,config}.py`, SYNC_LOG.
**Verification:** Contracts package 71 passed.
**Decisions / issues:** Fixture mode carries the fixture's own `is_injected` (25 injected SYN-flood events), so `injected` = 25 there.

### S-040 · 2026-10-21 · L5 Task · PR-10 (M1-T110..T123)
**What:** Tests first: 19 unit tests (FakeClock/FakeSink: event build, order/days/loop/exhaust, reference-hash guard, pacing distribution, fixture gaps,
invalid-record guard, stop flag, CLI codes), 3 C-01 producer contract tests, extended C-06 CLI contract tests (prepare + producer), 5 live + 1 perf test.
Then `src/ids_ingest/producer.py`: `ReplaySource`, `FixtureSource`, `KafkaSink` (pre-flight, acknowledgement accounting, BufferError retry), `run()` (due = start + i/R,
≤ 2 ms early bursts, validation sampling, per-second histogram), CLI with SIGINT/SIGTERM handling. `topic_admin` now IPv4-only (`broker.address.family=v4`).
**Why:** M1-F03 FR-021..FR-030.
**Artifacts:** `Module1_…/src/ids_ingest/producer.py`, `topic_admin.py`, `tests/unit/test_producer.py`, `tests/contract/test_c01_producer_contract.py`,
`tests/contract/test_c06_platform_contract.py`, `tests/integration/test_producer_{live,perf}.py`.
**Verification:** One real bug found by the pacing test: a run ending on its duration stopped at the last event (4.999 s), dropping the final second from the
statistics and overstating the rate slightly. It now waits out the full duration. Also tidied a placeholder left in a contract test. Unit 91, contract 23 passed.
**Decisions / issues:** Open item #12 (IPv6 warning) is resolved for M1 clients without a contract change.

### S-041 · 2026-10-22 · L5 Task / L4 Feature · PR-10, PR-11 (M1-T130..T141)
**What:** Live on the platform: **5/5** (5,000 ev/s × 20 s on 4 partitions within ±2 % with all messages consumed and strict-valid, replay order on 1 partition,
fixture gaps exact live, SIGTERM graceful with exact counts, missing topic and broker-down errors). Perf (AC-05): **11,999.6 ev/s** at `--rate 12000` × 60 s,
16 partitions (p05 11,973, 720,000 sent, 0 failed). Ceiling run at the C-06 maximum `--rate 100000` × 20 s delivered **99,987 ev/s** (0 failed), so the true
ceiling is ≥ 100k (not pushed beyond the contract limit). README producer section. Spec Verified (AC-06 tolerance clarified to ±1 %, spec 0.1.1). 12/12 tasks.
**Why:** Gate G4.
**Artifacts:** `Module1_…/docs/measurements/AC-05-M1-F03-2026-10-22.json`, README, spec, tasks.
**Verification:** As above.
**Decisions / issues:** The producer has more than 8× headroom over the 12k target, so it will not bottleneck E1/E2. Next: **M1-F04 attack injector**, the last M1 feature.

### S-042 · 2026-10-22 · L4 Feature / L2 Contracts · PR-07..09, PR-04 (M1-T150)
**What:** The user approved building **M1-F04 Attack Injector** the same way ("yes"). Checked the replay data first: 19,129 distinct IPs, **none** in the RFC 5737
documentation ranges, so those ranges are used for attackers (unambiguous ground truth). The busiest real source, 172.16.0.1 (CIC attack NAT), carries 559,247 flows (about 20 %),
which is relevant for M2: rate alone is not an attack signature. Wrote the spec (8 FRs, 2 NFRs, 9 ACs), plan and 8 tasks. **C-06 rc.6**: producer flags `--seed`,
`--attack-start`, `--attack-duration` and attack summary fields.
**Why:** The last M1 feature. Needed for E3 (0/5/20 %), F5 (drift banner) and the demo.
**Artifacts:** `Module1_…/specs/M1-F04-attack-injector/{spec,plan,tasks}.md`, `contracts/C-06_*.md`, `ids_contracts/config.py`, SYNC_LOG.
**Verification:** n/a (docs).
**Decisions / issues:** Signatures: ddos 2 sources (packet_rate ≥ 100 per source at 5 %), synflood 4 sources, portscan 1 source sweeping ports, mixed cycles types.

### S-043 · 2026-10-22 · L5 Task · PR-10 (M1-T160..T171)
**What:** Tests first: 19 injector unit tests (exact share and spread, signatures, 30 s window signature strength using the C-02 provisional formulas,
time window, seed determinism, replay order/content untouched, blindness to replay labels), producer CLI attack cases, an injected-event contract test,
updated C-06 CLI contract cases. Then `src/ids_ingest/injector.py` (`AttackGenerator`, `InjectingSource` with error diffusion) and producer wiring (flags, guards,
summary). **Design fix found while wiring:** `run()` pulled the next item from the source *before* checking the deadline, so with injection an unsent
item could be counted in the per-type tallies. `run()` now decides before pulling.
**Why:** M1-F04 FR-041..FR-048.
**Artifacts:** `Module1_…/src/ids_ingest/{injector,producer}.py`, `tests/unit/test_injector.py`, `tests/unit/test_producer.py`, `tests/contract/test_c01_producer_contract.py`,
`tests/contract/test_c06_platform_contract.py`, `tests/integration/test_injector_live.py`.
**Verification:** Unit **117**, contract **25** passed on the first green run.
**Decisions / issues:** none.

### S-044 · 2026-10-22 · L5 / L4 · PR-10, PR-11 (M1-T180, T190) · **Module 1 complete**
**What:** Live: mixed 20 % at 5,000 ev/s × 20 s, with every message consumed, injected count = summary, labels consistent, strict-valid, and attacker IPs disjoint from
the replay data. Perf: **11,999.6 ev/s** at `--rate 12000` with mixed 20 % (720,000 sent, **144,000 injected = 20.0 %**, 0 failed). Re-ran the M1-F03 live suite
after the `run()` change: 5/5 (no regression). README injector section. Spec Verified (9/9). 8/8 tasks.
**Why:** Gate G4. **All four Module 1 features are verified** (F01 11/11, F02 10/10, F03 10/10, F04 9/9).
**Artifacts:** `Module1_…/docs/measurements/AC-08-M1-F04-2026-10-22.json`, README, spec, tasks.
**Verification:** As above.
**Decisions / issues:** Module 1 is owner-verified. Its contracts (C-01 rc.5, C-06 rc.6, versions rc.3) stay In Review until the team sees them (user decision S-034).
Next: the replica builds of M2–M4 (playbook §7) against the §5 baseline, starting with the shared contracts the other modules own (C-02..C-05 provisional).

### S-045 · 2026-10-22 · L2 Contracts · PR-04/PR-06 (replica mode), playbook §7 step 2
**What:** The user approved starting the replica builds ("Yes go ahead!"). Authored **provisional replica** contracts for the teammates' seams, all 0.1.0-replica and
marked "owner to replace": **C-02** Feature Definition (windows, formulas, eval-only labels, offline timing), **C-03** Detection Bundle (layout, manifest, rules.yaml,
decision semantics), **C-04** Anomaly Store (`ids.window_scores`, hour-bucketed key, upsert, drift rule), **C-05** Pipeline Metrics (`pipeline_metrics`, `runs`,
D-01 latency with nearest-rank percentiles). Added `ids_contracts.{features,bundle,store,metrics}`, `schemas/{ids_schema,metrics_schema}.cql`,
`schemas/{manifest,rules}.schema.json`, and the C-02 golden fixture **`features_golden.csv` (23 rows)** produced by an independent reference generator
(`fixtures/_gen/gen_features_golden.py`), so neither M2 nor M3 "owns" correctness.
**Why:** Playbook §7. The replica pipeline (M2–M4) needs these seams. The golden features are the parity target for M2 (pandas) and M3 (Spark).
**Artifacts:** `contracts/C-0{2,3,4,5}_*.md`, `contracts/python/ids_contracts/{features,bundle,store,metrics}.py`, `contracts/python/tests/test_replica_contracts.py`,
`contracts/schemas/*`, `contracts/fixtures/{features_golden.csv,_gen/gen_features_golden.py,README.md}`, `contracts/README.md`, SYNC_LOG, `sdd/team_message.md`.
**Verification:** Contracts package **96 passed** (71 + 25). The golden file regenerates byte-identically. Python column constants equal the CQL. Both CQL files **applied to the
live Cassandra** (twice, so idempotent): keyspace `ids` with 3 tables. Two writes to the same (window, IP) leave **one** row with the newer values (upsert, D-02). TTL 604800 active.
Test rows deleted.
**Decisions / issues:** Placeholder rule thresholds: the golden port scan (40 ports in 30 s) does not reach `R-PORT-SCAN` (≥ 50), which is fine for placeholders, but M2 should tune them.
C-03 `scores_golden.csv` waits for the dummy bundle (M2-F04 replica).

### S-046 · 2026-10-22 · L3–L5 Module 4 (REPLICA) · M4-F01 (PR-07..PR-11)
**What:** The user approved continuing ("Ofc"). Started the **Module 4 replica** (README banner: "REPLICA built by Aswin S., canonical owner Vidhi"). M4-F01 store schema and access:
lite spec (7 FRs, 5 ACs), plan and tasks. Package `ids_monitor` (cassandra-driver 3.29.2, arm64 wheel verified), Makefile with the 6 standard targets.
`store.py` (connect with a single-node address translator, apply/check schema against `system_schema`, partition-key-only reads over UTC hour buckets, drift, top-N,
metrics, runs, writers with LOCAL_ONE), `schema.py` CLI (`apply`, `check`), `synthetic.py` + `mocks/synthetic_rows.py` (M4's mock: seeded, contract-valid C-04/C-05 rows, `--follow` live mode).
Tests first (red → green).
**Why:** Playbook §7 step 3. The dashboard (M4-F02) and benchmarks (M4-F03) build on this access layer. The mock lets them start before M3 exists.
**Artifacts:** `Module4_Storage_Dashboard_Benchmarking/{README.md,pyproject.toml,requirements.txt,Makefile,src/ids_monitor/*,mocks/synthetic_rows.py,tests/*,specs/M4-F01-store-schema-access/*}`.
**Verification:** Unit **21**, contract **7**, live **3** passed (schema idempotent, every column round-trips including ms timestamps, drift rate exactly 0.2, ordered top-10, cleanup,
unreachable store reported). `make run` → schema apply + check OK. `make mock` wrote 1,800 windows + 120 metrics rows (DEV-synthetic, 7-day TTL), read back with drift 0.2 and the alert on.
**Decisions / issues:** Cassandra advertises its in-container IP, so host clients need the address translator (documented in the README). M3's Spark connector runs in-network and is unaffected.

### S-047 · 2026-10-22 · L4–L5 Module 4 (REPLICA) · M4-F02 Live Dashboard (PR-07..PR-11)
**What:** The user asked whether results can be shown in a dashboard yet. Answer: there was no dashboard, and only synthetic data. Real results need M2 + M3.
So M4-F02 was built ahead of M2 on the M4 mock. Loaded the **dataviz skill**: stat tiles for headline numbers, single-axis thin lines (no dual axis, latency p50/p95 share
one ms axis), reference-palette slots 1–2, status banners with icon + label, hover crosshair + tooltips, the top-10 table as the table view.
**Palette validated** with the skill's validator after installing Node (`brew install node`, v26.12.0, run from a neutral directory): light worst CVD ΔE 24.7,
normal 33.6. Dark 26.8 / 31.8. Contrast ≥ 3:1. ALL PASS. Installed the pinned stack into `.venv`: numpy 1.26.4, pandas 2.2.3, pyarrow 17.0.0, scikit-learn 1.5.2,
joblib 1.4.2, streamlit 1.39.0 (Altair 5.5.0). `view.py` (pure `build_view` + `DemoReader` with an injectable clock) and `dashboard.py` (Streamlit page,
`@st.fragment(run_every=3)`, `--demo`, `--run-id`). Makefile `run` → schema + dashboard, `demo` (extra).
**Why:** User request. G6, F4 (≤ 5 s visibility via the 3 s refresh), F5 (drift banner).
**Artifacts:** `Module4_…/src/ids_monitor/{view,dashboard}.py`, `tests/unit/{test_view,test_dashboard_app}.py`, `tests/integration/test_dashboard_live.py`,
`specs/M4-F02-dashboard/*`, Makefile, README, requirements/pyproject.
**Verification:** Unit **28** (including 2 Streamlit AppTest renders), live **5** (fresh Cassandra run renders with the alert; the server answers `/_stcore/health` = ok).
One design gap fixed: the demo reader used the wall clock for metrics while windows used the caller's time, so it now takes an injected clock.
One harmless warning is Streamlit 1.39 calling an Altair API that Altair 5.5 deprecated (inside Streamlit, not our code).
**Live now:** `http://localhost:8501` serving run `DEV-live-demo` (synthetic feed `--follow 7200`): about 4,900 ev/s, p95 about 390 ms, anomaly rate 20.0 %, drift alert on, 900 windows.
**Decisions / issues:** I could not visually inspect the rendered page (no browser tool in this session), so the owner should eyeball it (dataviz step 7). Charts use the light
palette unless Streamlit's theme base is configured as dark.

### S-048 · 2026-10-22 · L2–L5 Module 2 (REPLICA) · M2-F02 + M2-F04 (PR-07..PR-11)
**What:** Started the **Module 2 replica** (README banner, canonical owner Nitish). Package `ids_model` with the ADR-009 pins. Contract replicas bumped: **C-02 0.1.1**
(offline timestamps floored, `replay_timestamp`) and **C-03 0.1.1** (`scores_golden.csv` format, `SCORE_COLUMNS`, `read_scores_csv`, tolerance 1e-9).
**M2-F02:** `features.py`, a vectorised pandas C-02 builder (explode into 3 windows, groupby, exact `nunique`, eval-only labels via the most frequent non-benign label),
`replay_timestamps` / `features_from_replay` (ADR-011 timing). **M2-F04:** `bundle.py`, a dummy Pipeline(StandardScaler, IsolationForest n=100, seed 42) on seeded
synthetic features, threshold = 99th percentile of training scores (0.654), C-03 manifest and rules, `Bundle.load` with the ADR-009 version guard, vectorised `score`,
`scores_golden.csv`, CLI (`make-dummy [--install]`, `golden-scores`, `check`). `make mock` → `mocks/dummy_bundle/`, `runtime/bundle/current`, `contracts/fixtures/scores_golden.csv`.
**Why:** Playbook §7 steps 7–8. M3 needs a valid bundle plus the golden features and scores as parity targets.
**Artifacts:** `Module2_ML_Anomaly_Model/{README.md,pyproject.toml,requirements.txt,Makefile,src/ids_model/*,mocks/dummy_bundle/*,tests/*,specs/M2-F0{2,4}-*/*}`,
`contracts/{C-02,C-03}_*.md`, `contracts/python/ids_contracts/{features,bundle}.py`, `contracts/fixtures/scores_golden.csv`, `runtime/bundle/current/`.
**Verification:** Contracts **97**. M2 unit **10**, contract **3** (pandas output = all **23 golden rows**), integration **1**: **the host-trained bundle (Python 3.11) loads
in the Spark image (Python 3.10, sklearn 1.5.2, numpy 1.26.4) and reproduces every golden score within 1e-9. Risk R3 is retired for the replica path.**
One test-design flaw fixed: it demanded non-anomalous rows in a random frame where random SYN/ACK ratios trip the rule almost everywhere.
**Decisions / issues:** The dummy flags 8 of 23 golden windows, all via `R-SYN-FLOOD` (port scan + SYN flood). ML flags none and the DDoS windows go uncaught. Expected for a dummy.
Real training (M2-F03) and rule tuning are the owner's work (Nitish), or a later replica step.

### S-049 · 2026-10-22 · L2–L6 Module 3 (REPLICA) · M3-F01..F04 · **first end-to-end pipeline run**
**What:** The user approved the M3 replica ("Yes"). Four lite specs plus a shared plan and tasks. Package `ids_stream`: `spec.py` (pure: C-01 DDL + validity SQL,
C-02 aggregate SQL, 17 bounded per-label count columns + label-type SQL, rules → SQL with id/feature/operator validation, C-04/C-05 columns, metrics row builder,
bundle metadata reader, container paths), `job.py` (host C-06 CLI: finds `spark-client` by compose labels, zips `ids_stream`, `docker exec spark-client spark-submit …`,
SIGTERM → `pkill -TERM` the driver, re-emits the summary), `app.py` (PySpark driver: Kafka → `from_json` + observed malformed counts → watermark 60 s →
`window(30 s,10 s)` per `src_ip` → `foreachBatch`: finalize features → **broadcast IsolationForest via vectorised `pandas_udf`** + compiled rules →
Spark-Cassandra-connector upsert → batch stats; a `StreamingQueryListener` enqueues progress and the main thread writes `ids.pipeline_metrics`; an `ids.runs` row at start;
checkpoint `runtime/checkpoints/<run_id>`; graceful stop). `tests/spark/parity_app.py` runs inside the container.
**Why:** Playbook §7 steps 9–11. Closes the loop: producer → Kafka → Spark → Cassandra → dashboard.
**Artifacts:** `Module3_Spark_Stream_Processing/{README.md,pyproject.toml,requirements.txt,Makefile,src/ids_stream/*,tests/*,specs/M3-F0{1,2,3,4}-*/*}`.
**Verification:** Host unit **13**, contract **6**. **Golden parity in the real Spark runtime: features 23/23 exact, scores within 1e-9** (Spark = pandas M2 = independent reference).
**End-to-end** (`DEV-m3-e2e-f7de77`): producer 60,000 events (12,000 injected, mixed 20 %) + 5 malformed → Spark counted 60,005 inputs, dropped and counted the 5 malformed →
**5,223 windows** written (all valid C-04), 113 anomalous, **every injected SYN-flood and port-scan source flagged**, 21 C-05 metrics rows, `runs` row present.
Per-batch p95 latency: median **1,223 ms**, max 7,133 ms (first batch with the start-up backlog). **Recovery (P5):** `docker restart` of worker 1 mid-run, first batch **0.38 s** later,
46 batches after (target ≤ 30 s). Two bugs fixed during the build: (1) `job.py` stripped all spaces before matching the summary line, so "stream app" never matched; now it parses JSON.
(2) Two sloppy test assertions tightened.
**Decisions / issues:** **New D-12** (drift metric vs attack share: 20 % injected events gives only about 2 % anomalous windows, so the banner wouldn't fire; recommend an event-weighted rate) and
**D-13** (P2 latency: about 1.2 s median p95 at 2k ev/s with a 1 s trigger vs the 500 ms target). Both added to PROJECT_PLAN §1.4 for the owners.
**Live now:** real pipeline `DEV-live-real` (topic `live-demo`, 2,000 ev/s with mixed 20 % injection, 30 min), visible on the dashboard at http://localhost:8501. The synthetic feed is stopped.

### S-050 · 2026-10-22 · L4–L6 Module 2 (REPLICA) · M2-F03 real training + evaluation
**What:** The user asked how long training takes (answer: minutes of compute, about an hour of build), then approved ("Okay go ahead"). Spec with a **no-leakage protocol**:
train = Monday first 80 % (benign), benign hold-out = Monday last 20 % (F2), validation = Tue–Thu (threshold choice only), test = Fri DDoS + PortScan files
(reported only). All splits replayed at R_ref (ADR-011). `bundle.py` refactored (`write_bundle`, `rule_flags`). New `train.py`: Pipeline(log1p → StandardScaler →
IsolationForest n=200, seed 42), threshold = the percentile of train scores maximising validation hybrid F1 subject to hold-out FPR < 5 %, metrics for rule/ML/hybrid,
recall per category, JSON + Markdown report, C-03 bundle `runtime/bundle/1.0.0-replica`.
**Why:** Proposal F1/F2/F3 and G3. Replace the dummy model.
**Artifacts:** `Module2_…/src/ids_model/{train,bundle}.py`, `tests/unit/test_train.py`, `tests/integration/test_train_real_data.py`, `specs/M2-F03-if-training-eval/*`,
`docs/measurements/F03-training-2026-10-22.{md,json}`, `runtime/bundle/1.0.0-replica` (installed as `current`), PROJECT_PLAN (D-14).
**Verification:** M2 unit **18**, contract **3**, Spark-image + real data **2**, contracts **97**. Training: **4.9 s, 1.2 GB peak**. Windows: train 37,939, hold-out 17,845, validation 119,536, test 21,279.
Chosen threshold: p99.5 = 0.7488. **Results (window level, hybrid): F1 recall 0.941 ✅ (DDoS 1.000, PortScan 0.875), F2 hold-out FPR 1.21 % ✅, F1 precision 0.058 ❌.**
**Root-cause analysis:** only 17 of 21,279 test windows are attacks (all CIC attacks come from **one source IP, 172.16.0.1**; the DDoS file replays in about 45 s, so about 9 attacker
windows). Flow-level view: precision about 0.60, recall 1.0, but about 87 % of benign flows sit in flagged windows: the 4 volume-dominated features at 270× time compression make busy
benign hosts look like floods. IsolationForest also cannot extrapolate (a unit test exposed it: out-of-range points score like the training extremes).
→ **D-14** recorded with options (recommend: report honestly now + rate-invariant features via a C-02 change).
One test fixed: its premise (an IF flags far-out points at strict thresholds) was false. It now forces rule hits instead.
**Live (AC-05):** stopped `DEV-live-real` (graceful driver stop. Note: my `pkill -f "run-id DEV-live-real"` also matched the host job wrapper; the driver still shut down cleanly,
no stray apps), installed `1.0.0-replica`, started **`DEV-live-trained`** (topic `live-trained`, 2,000 ev/s, mixed 20 % injection, 30 min). Preliminary vs the dummy:
benign windows flagged 1.00 % vs 1.27 %, share of flags that are injected 39.3 % vs 22.6 %, injected DDoS caught 80 % vs 100 % (PortScan/SYN 100 % both).
**Correction:** in S-049 / chat I described the dummy as raising "many false positives". Over 12.3 min its benign flag *rate* was 1.27 % (ML 0.67 %). The issue is *precision*
(most flags fall on benign hosts because they vastly outnumber attackers), which is the same structural effect as D-14.
**Decisions / issues:** D-14 open (team). F1 precision cannot be fixed by tuning alone.

### S-051 · 2026-10-22 · L0 Project · session end (graceful shutdown)
**What:** The user ended the session ("continue tomorrow") and asked for a graceful stop of all services. In dependency order: (1) the stream job `DEV-live-trained`, via SIGTERM to
the driver only. It finished the batch, flushed metrics and exited 0 with summary: **3,600,000 input rows processed, 715,431 window rows written, 82,602 anomalous row writes,
1,796 metrics rows, 0 malformed**. (2) The producer had already finished: 3,600,000 sent, 0 failed, 720,000 injected (20.0 %), 2,000.0 ev/s. (3) Dashboard SIGTERM.
(4) `ids_ingest.platform down` (volumes kept: Kafka topics and Cassandra data persist). (5) `colima stop`.
**Why:** Free the machine (Colima holds up to 10 GB) without losing data or leaving half-written runs.
**Verification:** 0 containers, Colima not running, no project processes on the host.
**Resume tomorrow:** `colima start` → `cd Module1_Data_Ingestion_Platform && make run` (about 60 s) → `cd ../Module4_Storage_Dashboard_Benchmarking && make run` (dashboard;
earlier runs remain selectable for 7 days, the TTL). The trained bundle `1.0.0-replica` is still installed at `runtime/bundle/current`. Open choices: M4-F03 benchmark harness
(E1–E3), team decisions D-12/D-13/D-14, or the D-14 feature experiment.

### S-052 · 2026-10-25 · L4–L5 Module 4 (REPLICA) · M4-F02 0.2.0: finished runs in the dashboard (pending item 3)
**What:** The user asked why the app "stopped". The job had ended on its `--await-seconds 420`, and the dashboard then showed empty tiles,
because its 5-minute window followed the wall clock. Changes to `ids_monitor.view.build_view`: a time anchor (`auto` = the run's last
window if the run is idle for more than `STALE_S` = 30 s, else now; `now`), the fields `as_of_ms` and `live`, and KPI tiles from the **median of the last
`KPI_BATCHES` = 10 batches with input or latency** (trailing idle batches showed 0, and a partial tail batch showed 149 ev/s). The dashboard has a "Time reference" radio
and a live/finished caption. `DemoReader` takes an injectable clock (it had mixed wall-clock metrics with caller-time windows).
**Spec:** M4-F02 → 0.2.0-replica (FR-018, AC-06).
**Verification:** M4 unit + contract 38 passed; live suite 5 passed; a finished run is shown with its real KPIs.

### S-053 · 2026-10-25 · L5 Module 3 (REPLICA) · Ctrl-C in the job wrapper (pending item 8)
**What:** Ctrl-C in `python -m ids_stream.job` killed the `docker exec` client (SIGINT went to the whole process group). The driver's final
summary was lost, and the wrapper reported "failed". Fix: `exec_stream` starts `docker exec` with `start_new_session=True`. The wrapper's handler sends
**SIGTERM to the driver** (via `pkill` in the container) on the first Ctrl-C, so the driver finishes the batch, flushes metrics and prints its summary. It sends **SIGKILL** on the second Ctrl-C.
**Verification:** unit tests with a fake docker (handler TERM then KILL), plus live `test_ctrl_c.py` (exit 0 with summary after Ctrl-C).

### S-054 · 2026-10-25 · L2–L6 Contracts + M2 + M3 (REPLICA) · D-14 resolved: C-02/C-03 0.2.0, bundle 1.1.0 (pending item 6)
**What:** (1) Offline experiment `ids_model.experiment_d14` (4 feature variants, same M2-F03 protocol, flow-level metrics):
V3 = `bytes_per_flow, port_ratio, syn_ack_ratio, syn_share` gives flow P/R **0.846 / 1.000**, against V0's 0.595 / 1.000. Benign flows inside flagged windows drop from 86.7 % to 23.2 %,
and ML-only flags 0 % benign. The rest comes from the placeholder `R-PORT-SCAN` rule. A tuned rule missed the CIC PortScan, so the rules stay placeholders (owner M2).
(2) Contract cascade: **C-02 0.2.0-replica** (3 ratio columns; `FEATURE_ORDER` = V3; `BASE_FEATURES`, `RATIO_FEATURES`, `RULE_FEATURES`), **C-03 0.2.0-replica**
(manifest `feature_order` const = V3; rules may reference any `RULE_FEATURES`). C-04 unchanged (stores the base features). Golden features regenerated (23 rows, +3 columns).
(3) M2: builder computes the ratios; the dummy's synthetic benign data re-centred on the golden benign host (about 1 kB per flow, SYN on every flow), so that `scores_golden.csv` now
covers benign, ML-only, rule-only and both. Retrained **`1.1.0-replica`** (4 s), installed at `runtime/bundle/current`: threshold p99.9 = 0.7688, window P/R
**0.112 / 0.941** (was 0.058 / 0.941), hold-out FPR 1.00 %. F1 is still not met at window level (one attacker IP; see ADR-012).
(4) M3: `finalize` adds the ratio columns; the pandas UDF takes `FEATURE_ORDER`; rule SQL accepts `RULE_FEATURES`.
**Why:** D-14. ADR-012 (proposed, owner M2).
**Verification:** contracts 98 · M1 142 · M2 unit+contract 24 + bundle-in-image 1 · M3 unit+contract 20 + **Spark golden parity 2** + **e2e live + Ctrl-C 3** (4 min) · M4 38, all passed.
The old bundle 1.0.0 is now correctly refused by the C-03 validator (feature order).
**Decisions / issues:** D-14 → ADR-012. **D-12 → ADR-013** (pending item 4): keep the anomalous-window share. Event-weighting measured at 87–94 % at 20 % injection, so it overstates;
F5 is validated with a 100 % injection phase in E3.

---

## Open items

| # | Item | Level | Owner | Due | Status |
|---|---|---|---|---|---|
| 1 | Install Docker engine, Python 3.11, Java 17 | L0 | Aswin | 22 Oct | ✅ S-020 |
| 2 | Fill in the CIC download form | L0 | Aswin | 22 Oct | ✅ (S-026) |
| 3 | Send the team bundle: `bash sdd/make_team_share.sh`, then share `../TEAM_SHARE/` | L2 | Aswin | after development (user decision, S-034) | ⏸ deferred |
| 4 | Sign the constitution (PR-02) | L1 | All | 22 Oct | ⬜ |
| 5 | Review C-01 (M2, M3), C-06 rc.2 (all) and versions.md rc.2 (all) | L2 | Nitish, Priyanka, Vidhi | 23 Oct | ⬜ |
| 6 | Accept ADR-003/006/007/009/011. Draft ADR-001/002/004/005/008/010 | L0 | All | 23 Oct | ⬜ |
| 7 | Author C-02 and C-03 (Nitish), C-04 (Vidhi), C-05 (Priyanka) | L2 | Owners | 24 Oct | ⬜ |
| 8 | M1-F01 spec, plan and tasks | L4 | Aswin | 24 Oct | ✅ drafted (S-021) |
| 9 | Approve M1-F01 gates G1–G3 (you, plus a review by Priyanka or Vidhi) | L4 | Aswin + reviewer | 23 Oct | ✅ owner (S-026); consumer review pending |
| 10 | Implement M1-F01 (M1-T001..T041) | L5 | Aswin | 27 Oct | ✅ Verified (S-030, S-031) |
| 11 | Download the dataset and check it against C-01 | L0 | Aswin | 22 Oct | ✅ (S-033). Optional: delete the partial `~/Downloads/GeneratedLabelledFlows.zip.download` |
| 13 | M1-F02 dataset preparation | L4/L5 | Aswin | 24 Oct | ✅ Verified (S-038) |
| 14 | M1-F03 replay producer | L4/L5 | Aswin | 25 Oct | ✅ Verified (S-041) |
| 15 | M1-F04 attack injector | L4/L5 | Aswin | 26 Oct | ✅ Verified (S-044). **Module 1 complete** |
| 16 | Replica builds of M2–M4 (playbook §7) | L2–L5 | Aswin | 1 Nov | 🟡 C-02..C-05 provisional (S-045), M4-F01 ✅ (S-046), M4-F02 dashboard ✅ (S-047), M2-F02/F04 ✅ (S-048), **M3-F01..F04 ✅, end to end (S-049)**, M2-F03 ✅ trained bundle (S-050). Next: M4-F03 benchmarks (E1–E3) |
| 18 | Resolve D-12 (drift metric), D-13 (P2 latency), **D-14 (F1 precision / feature design)** with the owners | L0 | Aswin + team | — | 🟡 D-14 → ADR-012, D-12 → ADR-013 (S-054, replica, proposed); D-13 open |
| 17 | Eyeball the dashboard at http://localhost:8501 (layout, labels, dark mode) | L4 | Aswin | — | ⬜ |
| 12 | Minor: IPv6 `localhost` warning | L2 | Aswin | — | ✅ resolved for M1 clients (`broker.address.family=v4`, S-040). Other modules' host clients should do the same |
