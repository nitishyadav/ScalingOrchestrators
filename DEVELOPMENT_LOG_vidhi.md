# Development Log — Vidhi Kant Gupta (M4 Storage, Dashboard and Benchmarking)

An append-only record of every step taken, at every level of development (PR-20).
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

## Progress by level

| Level | Status | Last step | Next step |
|---|---|---|---|
| L0 Project | ✅ Oriented, owner-build plan agreed | S-001 | — |
| L1 SDD framework | 🟡 Constitution not yet signed by M4 | — | PR-02: sign the M4 row |
| L2 Contracts | 🟡 C-04 1.0.0-rc.1 In Review | S-005 | PR-05: M3 review of C-04; review C-05 |
| L3 Module | 🟡 Owner skeleton created, M4-ADR-001 Accepted | S-004 | — |
| L4 Feature | 🟡 M4-F01 Verified | S-007 | M4-F02 dashboard |
| L5 Task / code | 🟡 M4-T001..T041 done (M4-F01) | S-007 | M4-F02 tasks |
| L6 Integration | ⬜ | — | I-03 with M3 (2–4 Nov) |
| L7 Experiments | ⬜ | — | P3 (5–10 Nov) |

## Step log

### S-001 · 2026-11-01 · L0 Project · PR-00
**What:** Oriented on the repo as M4 owner. Module 4 held a complete replica by Aswin S. (F01–F04), and C-04 was 0.1.0-replica.
Agreed on a **fresh owner build**: own specs, plans, tasks and code, with the replica used only as a reference (playbook §8).
Priority order from the calendar: C-04 → F01 → F02 (before I-03, 2–4 Nov) → F03 (before P3, 5 Nov) → F04 (report, 15 Nov).
**Why:** Playbook §8: the replica is discarded at integration and replaced by the owner's folder.
**Artifacts:** none in the repo.
**Verification:** n/a.
**Decisions / issues:** none.

### S-002 · 2026-11-01 · L3 Module · PR-01
**What:** Created branch `m4-owner`. Copied the replica to `runtime/reference/m4-replica/` (git-ignored) for reading, removed it from the
module folder on this branch, and created the owner skeleton: `specs/ src/ids_monitor/ tests/{unit,contract,integration}/ mocks/ docs/adr/ results/`,
`Makefile` (the Art. V targets; `run` and `mock` are stubs until M4-F01/F02), `pyproject.toml`, `requirements.txt` (pins from versions.md), and the README.
**Why:** Owner mode needs a clean module folder that is built feature by feature under the SDD gates.
**Artifacts:** `Module4_Storage_Dashboard_Benchmarking/*`, `DEVELOPMENT_LOG_vidhi.md`.
**Verification:** `make install && make test && make contract-test` (see the session output).
**Decisions / issues:** none.

### S-003 · 2026-11-01 · L0 Project · —
**What:** Environment readiness. Installed Python 3.11 and OpenJDK 17 (Homebrew), and created the shared `.venv` (Python 3.11).
Ran `make install` in M4 (pinned dependencies installed).
**Why:** Python 3.11 and Java 17 are required by contracts/versions.md. Before this, only Python 3.14 was present and Java was missing.
**Artifacts:** `.venv/` (git-ignored).
**Verification:** `make install` OK. `make test` and `make contract-test` collect no tests yet (the skeleton has none). `pytest contracts/python`: 103 passed.
Java 17 is keg-only and not on PATH yet. Docker daemon not running.
**Decisions / issues:** Add openjdk@17 to PATH. Start Docker before live tests.

### S-004 · 2026-11-01 · L3 Module · PR-03
**What:** Wrote and accepted **M4-ADR-001**, the partition key for `ids.window_scores`.
The decision is `((date_bucket, bucket), window_end DESC, src_ip ASC)` with `bucket = (60·hour + minute) // 5` UTC (0..287).
Options considered: keep `(date_bucket, hour)`, use hour + crc32 shard (D-02), or use a 5-minute bucket.
**Why:** D-02 left the key to M4.
C-02 windows slide every 10 s (360 `window_end` per hour), with ≈ 1.7–3k `src_ip` per `window_end` (from the M2-F03 window counts).
So an hour partition holds ≈ 0.6–1.1M rows (≈ 100–300 MB), above Cassandra's ≈ 100k-row / 100 MB guidance.
A 5-minute bucket gives ≈ 50–90k rows (12–25 MB), a drift read touches ≤ 2 partitions, and the key needs no hash parity between Spark and Python.
Cross-check: replica E1 p8 wrote 748k upserts in 600 s, which fits ≈ 140k distinct rows each upserted ≈ 5× in update mode.
**Artifacts:** `Module4_Storage_Dashboard_Benchmarking/docs/adr/M4-ADR-001-store-partition-key.md`.
**Verification:** sizing is an estimate. The live measurement (`nodetool tablehistograms`) is a follow-up in M4-F01.
**Decisions / issues:** breaking for the 0.1.0 writer (`hour` → `bucket`). The live table needs a one-time `DROP`.

### S-005 · 2026-11-01 · L2 Contracts · PR-04, PR-06
**What:** Authored **C-04 1.0.0-rc.1** (owner version, template format, status In Review).
- DDL `contracts/schemas/ids_schema.cql` uses the new key.
- `ids_contracts.store`: `BUCKET_S`, `partition_key` (5-minute), new `partition_keys(start, end)` for readers, `NULLABLE` (eval-only pair only),
  and a slide-alignment check in `validate_row`.
- C-04 tests moved out of `test_replica_contracts.py` into the owner-owned `contracts/python/tests/test_store.py`. They cover the DDL ↔ constants check,
  bucket and day boundaries, 30 `window_end`s per bucket, `partition_keys` coverage, valid and invalid rows, and the drift rule.
- Updated the contracts README registry, `SYNC_LOG.md`, and the PROJECT_PLAN D-02 row (resolved).

**Why:** PR-04, to replace the M1 replica with the owner contract before I-03 (2–4 Nov).
**Artifacts:** `contracts/C-04_anomaly_store.md`, `contracts/schemas/ids_schema.cql`, `contracts/python/ids_contracts/store.py`,
`contracts/python/tests/test_store.py`, `contracts/python/tests/test_replica_contracts.py`, `contracts/README.md`, `contracts/SYNC_LOG.md`, `PROJECT_PLAN.md`.
**Verification:** `pytest contracts/python`: **130 passed**. Before this step it was 103 passed; the new store tests replace the 2 replica store tests.
M3 tests were not run (M3 deps are not in the shared venv). By reading the code: the M3 contract test still passes because its columns are derived,
but the M3 sink `app.py:119` (`to_store` builds `hour`) and `tests/integration/test_e2e_live.py:78-79` (queries by `hour`) must change to `bucket`.
These are M3's changes, not mine (Art. III).
**Decisions / issues:** C-04 depends on ADR-013 (drift = anomalous-window share), which is still *Proposed (replica)* and is mine to accept.

### S-006 · 2026-11-01 · L2 Contracts · PR-03
**What:** Accepted ADR-013 (the drift banner keeps the anomalous-window share, > 15 % over 300 s; F5 is validated with a 100 % injection phase in E3).
**Why:** C-04 §5 depends on it, and it was a replica draft waiting for the M4 owner.
**Artifacts:** `docs/adr/ADR-013-drift-metric.md` (status).
**Verification:** n/a.
**Decisions / issues:** none.

### S-007 · 2026-11-01 · L4/L5 Feature · PR-07..PR-11
**What:** Built **M4-F01 Store schema and access** end to end: spec 1.0.0, plan, tasks M4-T001..T041, then the code.
- `schema.py`: apply/check, plus `--recreate` for the 0.1.0 key.
- `store.py`: partition-key reads per 5-minute bucket, validated writes.
- `view.py`: drift summary and top flagged IPs. It never reads labels.
- `synthetic.py`: the seeded mock of M3, including follow mode.
- `cli.py` / `db.py`: C-06 exit codes and summary line.
- `make run` = schema apply. `make mock` = synthetic data.
**Why:** M3 ↔ M4 integration (I-03, 2–4 Nov) needs the schema and a verified read path. M4-F02/F03 build on `Store` + `view`.
**Artifacts:** `Module4_…/specs/M4-F01-store-schema-access/*`, `src/ids_monitor/{cli,db,schema,store,view,synthetic}.py`, `tests/{unit,contract,integration}/*`, `Makefile`, `README.md`.
**Verification:** `make test` 43 passed. `make contract-test` 2 passed. `make integration-test` 6 passed, run on a local `cassandra:4.1.10` container `ids-m4-cassandra`.
AC-12 perf: 75,000 rows from 2 partitions in **1.48 s** (target ≤ 3 s), drift and top-N in 0.012 s.
All 12 ACs ✅. Spec status: Verified.
**Decisions / issues:** The first live run failed in the round-trip test. Two synthetic runs shared IPs and window_ends, so run b upserted over run a. That is the correct C-04 key semantics, so the fix was in the test (distinct IPs).
Note: concurrent runs that share (window, `src_ip`) overwrite each other, because `run_id` is not in the key. Experiments run one at a time.

## Open items

| # | Item | Level | Owner | Due | Status |
|---|---|---|---|---|---|
| 1 | Sign the constitution (M4 row) | L1 | Vidhi | 2 Nov | Open |
| 2 | C-04 1.0.0-rc.1 + M4-ADR-001 key sizing, then send to Priyanka (M3) | L2 | Vidhi | 2 Nov | Authored (S-004, S-005). **Send to Priyanka** |
| 3 | Review C-05 as a consumer | L2 | Vidhi | 2 Nov | Open |
| 4 | M3 review and approval of C-04 1.0.0-rc.1. M3 sink and e2e test move `hour` → `bucket`. Drop the live table once | L2 | Priyanka / Vidhi | 2 Nov | Open |
| 5 | Accept or replace ADR-013 (drift metric, replica draft) | L2 | Vidhi | 2 Nov | Done (S-006) |
| 6 | M4-F01: init detects the 0.1.0 key (`--recreate`) — done (S-007). Still to do: measure partition sizes at the real rate during I-03 | L4 | Vidhi | 3 Nov | Partly done |
