# Project Constitution

These are the non-negotiable rules for every module. Every `plan.md` must include a
**Constitution Check** confirming compliance. A deviation needs an ADR approved by the whole team.

| | |
|---|---|
| Version | 1.0.0-draft |
| Ratified | _pending: all 4 sign below_ |

---

### Article I — Spec before code
No production code is written without an **Approved** `spec.md`, a `plan.md` and a `tasks.md`.
Every commit and code change references a task ID (`MN-Txxx`). Every task traces to a requirement
(`MN-FR-xxx` / `MN-NFR-xxx`), and every requirement traces to a proposal goal or metric (G*, P*, F*).

### Article II — Contracts are the only coupling
Modules interact **only** through the contracts in `contracts/` (C-01..C-06). If an interaction
is not described in a contract, it is not allowed.

### Article III — Module isolation
1. Module code never imports another module's package (`ids_ingest`, `ids_model`, `ids_stream`, `ids_monitor`).
   The only shared import is `ids_contracts`.
2. A module folder is self-contained: its own dependencies (`requirements.txt` / `pyproject.toml`),
   its own Dockerfile or compose fragment if it needs one, and its own tests.
3. A module never reads or writes files inside another module's folder. Shared files travel
   through paths defined in C-06 (for example `DATA_DIR`, `MODEL_BUNDLE_PATH`).

### Article IV — Mock-first, standalone-runnable
Every module ships a mock of what it **provides** in `mocks/` (or a golden fixture in `contracts/fixtures/`)
before its real implementation. Every module can run and pass its tests with the other three replaced by mocks.

### Article V — Uniform module interface
Every module has a `README.md` (from `sdd/templates/module-readme-template.md`) and a `Makefile`
with exactly these targets:

| Target | Meaning |
|---|---|
| `make install` | Install module dependencies |
| `make test` | Unit tests |
| `make contract-test` | Contract tests against `contracts/` |
| `make run` | Run the module's real component using env from C-06 |
| `make mock` | Run/publish the module's mock for others |
| `make clean` | Remove generated artifacts |

### Article VI — Configuration through the environment
Hosts, ports, topic names, keyspaces, paths, rates and counts come from environment variables
named in **C-06**. They are never hardcoded. Each module documents the variables it reads.

### Article VII — Honest ML
1. The scoring path uses only the model and the rules from the C-03 bundle. There are **no hardcoded thresholds** in code.
2. Eval-only fields (`label`, `is_injected`) **must never** be used in feature computation or scoring.
   A contract test enforces this.
3. Offline and online features must reproduce the C-02 golden fixture.

### Article VIII — Tests derive from specs
Each acceptance criterion (`AC-xx`) maps to at least one automated test, or to a documented manual check
when it cannot be automated (for example a dashboard visual). Tests are written before or alongside the code, never "later".

### Article IX — Reproducibility and version pins
Python, Spark, scikit-learn, pandas, pyarrow, Kafka and Cassandra versions are pinned in
`contracts/versions.md` and used everywhere, including Colab. Random seeds are fixed and recorded.
Raw data and large artifacts are not committed (see `.gitignore`); the scripts that produce them are.

### Article X — Measured claims only
Every number in the report comes from a scripted run whose raw output is saved under
`Module4_Storage_Dashboard_Benchmarking/results/` along with its config. No hand-entered results.

### Article XI — Ownership and change control
1. The owner's version of a module is canonical. Others may build private versions for their own testing,
   but they never edit another owner's canonical module. Instead they raise an issue or a CR.
2. Contract changes follow the CR process: semantic versioning, impact analysis, and approval from every affected owner.
3. A breaking contract change (MAJOR) needs approval from all 4 members.

### Article XII — Simplicity
Use only the stack in the proposal (Kafka, PySpark, Cassandra, Docker Compose, scikit-learn, Streamlit)
plus small standard libraries. Adding any new infrastructure component requires an ADR.

---

## Amendments
Propose an amendment with an ADR in `docs/adr/`. It is adopted only with all 4 signatures and bumps this document's version.

## Signatures

| Member | Module | Signed (date) |
|---|---|---|
| Aswin S. | M1 | |
| Nitish Kumar Yadav | M2 | |
| Kumari Priyanka | M3 | |
| Vidhi Kant Gupta | M4 | |
