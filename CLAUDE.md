# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Team project (DES, IISc) for a real-time network intrusion detection pipeline: CIC-IDS2017 flows are replayed through Kafka, windowed and scored in PySpark Structured Streaming (Isolation Forest + rules), stored in Cassandra, and shown on a Streamlit dashboard. It is built with **Spec-Driven Development (SDD)**. The root docs (`README.md`, `CONSTITUTION.md`, `PROJECT_PLAN.md`, `SDD_PLAYBOOK.md`, `sdd/WORKFLOW.md`) define the method; read `README.md` first.

The repo is a monorepo of four modules, each owned by a different person and each present here as a full copy (a "replica" unless the README banner says otherwise):

| Module | Package | Scope |
|---|---|---|
| `Module1_Data_Ingestion_Platform` | `ids_ingest` | Docker platform (Kafka/Spark/Cassandra), dataset prep, replay producer, attack injector |
| `Module2_ML_Anomaly_Model` | `ids_model` | Features, Isolation Forest training, detection bundle (model + rules) |
| `Module3_Spark_Stream_Processing` | `ids_stream` | Spark job: windows, features, hybrid scoring, Cassandra sink, metrics |
| `Module4_Storage_Dashboard_Benchmarking` | `ids_monitor` | Cassandra schema, dashboard, drift alert, benchmark harness |

## Architecture rules that shape every change

- **Contracts are the only coupling.** `contracts/C-01…C-06` (event format, feature definition, detection bundle, anomaly store, pipeline metrics, runtime config/CLI) are the sole shared surface. A module must never import another module's package or touch files in another module's folder; the only shared import is `ids_contracts` (`contracts/python/ids_contracts/`). Paths/hosts/topics/rates come from environment variables named in C-06 (template: `integration/.env.example`), never hardcoded.
- **Golden fixtures define parity.** `contracts/fixtures/` (`events_golden.jsonl` → `features_golden.csv` → `scores_golden.csv`) must be reproduced exactly by every implementation; `make contract-test` checks this.
- **Do not edit `contracts/` directly** to suit your module. Contract changes go through a change request (`sdd/templates/contract-change-request-template.md`) and are logged in `contracts/SYNC_LOG.md`. Version pins are in `contracts/versions.md` (the model is pickled, so scikit-learn/numpy/pandas/pyarrow versions must match between training and scoring).
- **Honest ML:** eval-only fields (`label`, `is_injected`) are never read by feature computation or scoring; no hardcoded thresholds in the scoring path (they come from the C-03 bundle); test sets are never used for choosing thresholds, features, or rules.
- **Spec before code:** work lives in `ModuleN/specs/MN-Fxx-<slug>/{spec.md,plan.md,tasks.md}`; commits reference task IDs (`MN-Txxx`) and each acceptance criterion maps to a test. Steps are recorded append-only in `DEVELOPMENT_LOG.md`. Non-trivial decisions get ADRs in `docs/adr/` (project-wide) or `ModuleN/docs/adr/`.
- Measured numbers in reports must come from scripted runs saved under `docs/measurements/` (M1–M3) or `Module4…/results/`, not hand-entered.

## Commands

Python 3.11, one shared venv at the repo root (the Makefiles use `../.venv/bin/python` automatically if present). Java 17 is needed only for host PySpark tests; Docker (Colima/Docker Desktop) for the platform.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
(cd Module1_Data_Ingestion_Platform && make install)   # repeat per module; also installs contracts/python
(cd contracts/python && python -m pytest -q)           # contract layer tests
```

Every module has the same Makefile targets (Constitution Art. V), run from inside the module folder:

```bash
make test             # pytest tests/unit
make contract-test    # pytest tests/contract (against contracts/ + golden fixtures)
make integration-test # pytest tests/integration -m docker  (needs the platform up; slow)
make run | mock | clean
```

Single test: `../.venv/bin/python -m pytest tests/unit/test_producer.py::test_name -q -p no:cacheprovider` (or `source .venv/bin/activate` and drop the interpreter path). Markers: `docker`, `perf` (M1 `integration-test` runs `docker and not perf`), `data` (needs real CIC CSVs; M1 `make data-test`).

Module-specific:
- **M1:** `make run` starts the platform (`python -m ids_ingest.platform up`; `clean --yes` wipes volumes). `python -m ids_ingest.prepare [--sample]`, `ids_ingest.producer`, `ids_ingest.injector` have `--help`.
- **M2:** `make mock` installs a dummy bundle and regenerates golden scores; `make eda`; `python -m ids_model.train --install` builds the real bundle; `make run` validates the bundle at `MODEL_BUNDLE_PATH`.
- **M3:** `make run` / `python -m ids_stream.job --run-id DEV-you --await-seconds 120` (needs platform, topic, bundle). Ctrl-C once = graceful stop, twice = force.
- **M4:** `make run` (applies/checks schema, serves Streamlit on :8501), `make demo` (in-memory data, no platform), `make bench EXP=E1 ARGS="--levels 1 --duration 60"`, `make bench-all`, `make analyze`.
- **Whole pipeline:** `python integration/demo.py up|status|down` (copy `integration/.env.example` to `integration/.env` first).

The raw dataset (CIC-IDS2017 `TrafficLabelling` CSVs, ~2 GB), `runtime/` (bundles, checkpoints, replay data), venvs and trained models (except `Module2…/mocks/dummy_bundle`) are git-ignored. Run IDs: `DEV-<anything>` for development, C-06 pattern (`E1-p4-e2-r5000-a0-<YYYYMMDDHHMM>`) for experiments.

## Branching

Work on a module branch (e.g. `m2-nitish`) and merge to `main` via reviewed PR; PRs touch `contracts/` only with a change request.
