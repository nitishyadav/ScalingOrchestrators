# Real-Time Network Intrusion Detection — Team Scaling Orchestrators

Data Engineering at Scale (DES) · IISc Bangalore · 2026

A streaming pipeline that replays CIC-IDS2017 network flows through **Apache Kafka**, computes windowed traffic
features in **PySpark Structured Streaming**, scores them with an offline-trained **Isolation Forest** (broadcast and
applied through a `pandas_udf`) next to a rule check, stores results in **Apache Cassandra**, and shows them on a
**Streamlit** dashboard.

The project is built with **Spec-Driven Development (SDD)**. Each module is developed against versioned
**contracts**, not against other people's code. So any member's version of a module can replace any other's
as long as the contracts match. This README is for the four of us to clone the repo, understand the contracts,
and build our own version of a module, or of the whole pipeline.

Original proposal: [project_proposal.html](project_proposal.html).

---

## 1. Team and modules

| Module | Folder | Owner | Scope |
|---|---|---|---|
| M1 | [Module1_Data_Ingestion_Platform](Module1_Data_Ingestion_Platform/) | Aswin S. | Docker platform (Kafka, Spark, Cassandra), dataset preparation, replay producer, attack injector |
| M2 | [Module2_ML_Anomaly_Model](Module2_ML_Anomaly_Model/) | Nitish Kumar Yadav | Feature definition, Isolation Forest training and evaluation, detection bundle (model + rules) |
| M3 | [Module3_Spark_Stream_Processing](Module3_Spark_Stream_Processing/) | Kumari Priyanka | Spark job: windows, features, hybrid scoring, Cassandra sink, metrics, recovery |
| M4 | [Module4_Storage_Dashboard_Benchmarking](Module4_Storage_Dashboard_Benchmarking/) | Vidhi Kant Gupta | Cassandra schema, live dashboard, drift alert, benchmark harness (E1–E3, latency, recovery) |

**Ownership.** Each person owns one module. Everyone builds their own copy of all four, and that copy is a
**replica** until its owner replaces it with the real version. A replica folder says so in its README banner
("REPLICA built by …"). Replicas exist so that you can run the whole pipeline on your own machine without waiting for anyone.

---

## 2. Quick start: clone and run

### 2.1 Prerequisites

| Tool | Version | Why |
|---|---|---|
| Git | any recent | clone |
| Python | **3.11** (host) | tests, producer, model training, dashboard |
| Docker engine | Docker Desktop, or Colima 0.10.3 with Compose v2 (6 CPU, 10 GB) | Kafka, Spark, Cassandra |
| Java | **17** (Homebrew `openjdk@17` or Temurin) | host PySpark tests only |

Pinned versions are in [contracts/versions.md](contracts/versions.md). Use them exactly; the model is pickled, so
scikit-learn, numpy, pandas and pyarrow must match between training and scoring.

### 2.2 Clone and set up the workspace

```bash
git clone https://github.com/nitishyadav/ScalingOrchestrators.git
cd ScalingOrchestrators

python3.11 -m venv .venv                       # one shared host environment; the Makefiles use it automatically
source .venv/bin/activate
for m in Module1_Data_Ingestion_Platform Module2_ML_Anomaly_Model Module3_Spark_Stream_Processing Module4_Storage_Dashboard_Benchmarking; do
  (cd "$m" && make install)
done
```

Check that the contract layer and each module pass their tests:

```bash
for m in Module1_Data_Ingestion_Platform Module2_ML_Anomaly_Model Module3_Spark_Stream_Processing Module4_Storage_Dashboard_Benchmarking; do
  (cd "$m" && make test && make contract-test)
done
(cd contracts/python && python -m pytest -q)
```

### 2.3 Start the platform and run the pipeline

```bash
cp integration/.env.example integration/.env    # git-ignored; adjust locally if needed
cd Module1_Data_Ingestion_Platform && make run  # Kafka, Spark (1 master, 2 workers), Cassandra
cd ../Module4_Storage_Dashboard_Benchmarking && make run    # schema, then the dashboard on http://localhost:8501
```

The dataset (CIC-IDS2017 "TrafficLabelling" CSVs, about 2 GB) is **not in git**. Download it from the
[CIC site](https://www.unb.ca/cic/datasets/ids-2017.html), put the CSVs in `runtime/data/raw/TrafficLabelling/`, then
run `python -m ids_ingest.prepare` in Module 1. It checks SHA-256 hashes against C-01 and writes the replay dataset.

Until the dataset is ready you can work from the mocks: every module ships stand-ins (`mocks/`), and
`make mock` in Modules 2–4 produces synthetic data that matches the contracts.

---

## 3. How the modules talk: the contracts

Modules never import each other's code. They interact only through the **contracts** in [contracts/](contracts/),
which are the only shared surface:

| ID | Contract | Provider | Consumers | What it fixes |
|---|---|---|---|---|
| C-01 | [Network Event](contracts/C-01_network_event.md) | M1 | M2, M3 | Event JSON fields, replay Parquet layout, dataset hashes |
| C-02 | [Feature Definition](contracts/C-02_feature_definition.md) | M2 | M3 | Window size and slide, watermark, feature formulas, model input order |
| C-03 | [Detection Bundle](contracts/C-03_detection_bundle.md) | M2 | M3 | `model.joblib`, `manifest.json`, `rules.yaml`, decision semantics |
| C-04 | [Anomaly Store](contracts/C-04_anomaly_store.md) | M4 | M3, M4 | Cassandra window table, key design |
| C-05 | [Pipeline Metrics](contracts/C-05_pipeline_metrics.md) | M3 | M4 | Per-batch metrics, latency definition, run table |
| C-06 | [Runtime Config and Control](contracts/C-06_runtime_config_control.md) | M1 | all | Environment variables, CLI commands, run-ID format, service names |

Supporting files:

- [contracts/versions.md](contracts/versions.md): pinned versions (ADR-009). Changing a pin is a change request.
- [contracts/schemas/](contracts/schemas/): CQL DDL and JSON schemas.
- [contracts/fixtures/](contracts/fixtures/): golden files. `events_golden.jsonl` goes in, `features_golden.csv` and
  `scores_golden.csv` come out. **Every implementation must reproduce these files**, and this is how parity is checked.
- [contracts/python/ids_contracts/](contracts/python/ids_contracts/): the shared validators and constants (the `ids_contracts` package).
- [contracts/SYNC_LOG.md](contracts/SYNC_LOG.md): every contract revision, with its date and reason.

**Status of the contracts.** C-01 and C-06 are *In Review* (rc versions). C-02 to C-05 are *provisional replicas*
written by M1 so the pipeline could be built end to end. Their owners replace them with v1.0 once they have reviewed them.

---

## 4. How to build your own version of a module

This is the workflow the SDD method asks for. It is also how you get your own working version.

1. **Read the contracts for your module** (section 3) and the module's own `README.md`.
2. **Start from the golden fixtures.** Your module's output must match them. Run `make contract-test` and it tells you where you differ.
3. **Write the spec first.** Copy the templates from [sdd/templates/](sdd/templates/) into `specs/<ID>-<slug>/`:
   `spec.md` (requirements and acceptance criteria), `plan.md` (design) and `tasks.md`. IDs follow the scheme in
   [sdd/WORKFLOW.md](sdd/WORKFLOW.md) (`M2-F03`, `M2-FR-021`, `M2-F03-AC-02`, and so on).
4. **Write the tests before the code.** Acceptance criteria become unit, contract or integration tests.
5. **Implement, then run** `make test`, `make contract-test`, and the integration tests if the platform is up.
6. **Record the step** in `DEVELOPMENT_LOG.md` (one entry per step, newest at the end).
7. **If a contract is wrong, raise a change request** (CR, template in `sdd/templates/`). Do not change the contract
   on your own side and hope the others follow. Contract changes go through [contracts/SYNC_LOG.md](contracts/SYNC_LOG.md).

**Plug-and-play check.** Your module is interchangeable with a teammate's when:
- `contracts/` is identical on both sides (same versions),
- `make contract-test` passes in every module,
- the integration checklist in [integration/checklists/](integration/checklists/) passes for the seam you touch.

**Rules that matter most** (full text in [CONSTITUTION.md](CONSTITUTION.md)):
- No code before its spec is approved.
- Modules depend on contracts, never on each other's code.
- Eval-only fields (`label`, `is_injected`) are never read by the scoring path. This keeps evaluation honest.
- Test sets are never used for any choice (thresholds, features, rules).

---

## 5. Step-by-step: run each module on its own

| Module | Install | Test | Run | Notes |
|---|---|---|---|---|
| M1 | `make install` | `make test`, `make contract-test`, `make integration-test` | `make run` (platform) | `python -m ids_ingest.prepare`, `producer`, `injector` (see `--help`) |
| M2 | `make install` | `make test`, `make contract-test`, `make integration-test` | `make mock` (dummy bundle, golden scores); `python -m ids_model.train --install` (real bundle) | `python -m ids_model.eda` profiles the dataset |
| M3 | `make install` | `make test`, `make contract-test`, `make integration-test` | `python -m ids_stream.job --run-id DEV-you --await-seconds 120` | Ctrl-C stops gracefully (first) or forces (second) |
| M4 | `make install` | `make test`, `make contract-test`, `make integration-test` | `make run` (dashboard), `make demo` (no platform), `make bench EXP=E1 ARGS="--levels 1 --duration 60"` | `make analyze` builds the scorecard and figures |

**Whole pipeline in one command** (after `make install` everywhere):

```bash
python integration/demo.py up      # platform → schema → bundle check → topic → stream job → producer → dashboard
python integration/demo.py status
python integration/demo.py down    # graceful, in order: producer → stream job → dashboard
```

**Run IDs.** Development runs use `DEV-<anything>`. Experiment runs use the C-06 pattern
(`E1-p4-e2-r5000-a0-<YYYYMMDDHHMM>`), so every stored row traces back to its configuration.

---

## 6. Repository layout

```
ScalingOrchestrators/
├── README.md                  ← you are here
├── CONSTITUTION.md            ← non-negotiable engineering rules (all modules)
├── PROJECT_PLAN.md            ← scope, module split, timeline, decisions (D-01…D-14), risks
├── SDD_PLAYBOOK.md            ← self-contained guide to this method, for you and your AI tools
├── DEVELOPMENT_LOG.md         ← step-by-step record of everything done
├── sdd/                       ← workflow, templates, playbook sources, team-share script
├── contracts/                 ← the only shared surface: C-01…C-06, versions, schemas, fixtures, ids_contracts
├── integration/               ← env template, cross-module checklists, demo script
├── docs/adr/                  ← project-wide architecture decision records
├── Module1_Data_Ingestion_Platform/
├── Module2_ML_Anomaly_Model/
├── Module3_Spark_Stream_Processing/
└── Module4_Storage_Dashboard_Benchmarking/
```

Every module has the same layout:

```
ModuleN_<name>/
├── README.md        ← owner, scope, provides and consumes, how to run
├── specs/           ← <ID>-<slug>/{spec.md, plan.md, tasks.md}
├── src/<package>/   ← module code
├── tests/{unit,contract,integration}/
├── mocks/           ← stand-ins this module provides, so others can work without it
└── docs/            ← ADRs and measurement reports
```

Large and generated artifacts are **not** in git (see `.gitignore`): the raw dataset, `runtime/` (bundles, checkpoints,
replay data), virtualenvs, trained model files (except the dummy bundle), benchmark raw output.

---

## 7. Reading order

1. This README
2. [SDD_PLAYBOOK.md](SDD_PLAYBOOK.md): the method, step by step (give it, with the proposal, to your AI assistant)
3. [PROJECT_PLAN.md](PROJECT_PLAN.md): what we build, who builds what, the open decisions (D-01…D-14)
4. [CONSTITUTION.md](CONSTITUTION.md)
5. [sdd/WORKFLOW.md](sdd/WORKFLOW.md)
6. [contracts/README.md](contracts/README.md)
7. Your module's README

---

## 8. Status

| Module | State |
|---|---|
| M1 Data ingestion and platform | Complete (F01–F04 verified) |
| M2 ML anomaly model | Replica: features, training, bundle, EDA. Bundle 1.1.0-replica (feature set from D-14, ADR-012) |
| M3 Spark stream processing | Replica: F01–F04 verified, end to end, parity with golden files |
| M4 Storage, dashboard, benchmarking | Replica: store, dashboard, benchmark harness, analysis. Full benchmark run in progress |

Open team decisions (see [PROJECT_PLAN.md](PROJECT_PLAN.md) §4):
- **D-12** drift metric: decided in [ADR-013](docs/adr/ADR-013-drift-metric.md) (replica, proposed).
- **D-13** p95 latency target (about 1 s measured against 500 ms): under study with the latency sweep.
- **D-14** F1 precision: the feature set is adopted in [ADR-012](docs/adr/ADR-012-rate-invariant-features.md) (replica, proposed). Window precision stays structurally low because every CIC attack comes from one source IP.

This repository is the shared place to work from. Keep your own module changes on a branch named after
your module (for example `m2-nitish`), and merge into `main` only through a reviewed pull request that touches the contracts only with a change request.

---

## Team

- Aswin S. (M1, replica author of contracts C-02…C-05 provisional baseline)
- Nitish Kumar Yadav (M2)
- Kumari Priyanka (M3)
- Vidhi Kant Gupta (M4)

Course: Data Engineering at Scale (DES), IISc Bangalore, 2026.
