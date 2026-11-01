# Tasks: M4-F01 — Store schema and access

| Field | Value |
|---|---|
| Feature ID | M4-F01 |
| Plan version | 1.0 |
| Owner | Vidhi Kant Gupta |
| Target finish | 2026-11-02 |

## Phase 1 — Setup
- [x] **M4-T001** Module skeleton, Makefile, pins · Files: module root · Refs: Const. V, IX · Done: S-002
- [x] **M4-T002** Unit-test fakes (`FakeSession`, row builders) · Files: `tests/unit/conftest.py` · Refs: NFR-004 · Done: 2026-11-01, conftest.py FakeSession

## Phase 2 — Tests first
- [x] **M4-T010** [P] Schema tests: parse, diff, old-key detection · Files: `tests/unit/test_schema.py` · Refs: AC-02, AC-03 · Done: 2026-11-01, 8 tests
- [x] **M4-T011** [P] Store tests: query shape, run filter, conversion, write validation, metrics/runs · Files: `tests/unit/test_store.py` · Refs: AC-04, AC-07, AC-08 · Done: 2026-11-01, 10 tests
- [x] **M4-T012** [P] View tests: drift, top-N, no label access · Files: `tests/unit/test_view.py` · Refs: AC-05, AC-06 · Done: 2026-11-01, 6 tests
- [x] **M4-T013** [P] Generator tests + contract test · Files: `tests/unit/test_synthetic.py`, `tests/contract/test_c04_c05_contract.py` · Refs: AC-09 · Done: 2026-11-01, 10 + 2 contract tests
- [x] **M4-T014** [P] CLI tests: exit codes, summary line · Files: `tests/unit/test_cli.py` · Refs: AC-11 · Done: 2026-11-01, 9 tests (CLI)

## Phase 3 — Core implementation
- [x] **M4-T020** `cli.py`, `db.py` · Depends: T014 · Refs: FR-012, NFR-003 · Done: 2026-11-01, cli.py, db.py
- [x] **M4-T021** `schema.py` (+ CLI `apply`/`check`/`--recreate`) · Depends: T010, T020 · Refs: FR-001..003 · Done: 2026-11-01, schema.py
- [x] **M4-T022** `store.py` · Depends: T011 · Refs: FR-004, FR-005, FR-008, FR-009 · Done: 2026-11-01, store.py
- [x] **M4-T023** `view.py` · Depends: T012 · Refs: FR-006, FR-007, FR-013 · Done: 2026-11-01, view.py
- [x] **M4-T024** `synthetic.py` (+ CLI, follow mode) · Depends: T013, T022 · Refs: FR-010, FR-011 · Done: 2026-11-01, synthetic.py

## Phase 4 — Mock and integration readiness
- [x] **M4-T030** `make run` / `make mock` targets · Refs: Const. IV, V · Done: 2026-11-01, Makefile run/mock
- [x] **M4-T031** Live tests: apply ×2 + check, recreate, round trip, follow, perf · Files: `tests/integration/test_store_live.py` · Refs: AC-01, 03, 04, 07, 10, 12 · Done: 2026-11-01, 6 live tests green

## Phase 5 — Polish and verify
- [x] **M4-T040** README (run steps, env vars) · Done: 2026-11-01, README M4-F01 section
- [x] **M4-T041** Spec AC table ✅ with test references, dev log · Done: 2026-11-01, S-007

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 2026-11-01 | M4-T031 | Docker not running; M1 compose needs `IDS_HOST_ROOT` | Standalone `cassandra:4.1.10` container `ids-m4-cassandra` (same image and heap) |
| 1 Setup | 2 | 2 | |
| 2 Tests | 5 | 5 | |
| 3 Core | 5 | 5 | |
| 4 Mock / Integration | 2 | 2 | |
| 5 Polish | 2 | 2 | |

## Blockers log
| Date | Task | Blocked on | Resolution |
|---|---|---|---|
