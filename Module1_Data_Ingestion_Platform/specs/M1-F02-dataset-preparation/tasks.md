# Tasks: M1-F02 — Dataset Preparation

| Field | Value |
|---|---|
| Feature ID | M1-F02 |
| Plan version | Approved 2026-10-21 (G3 passed) |
| Owner | Aswin S. |
| Target finish | 2026-10-23 |

Legend: `[P]` = can run in parallel. 📦 = needs the real raw files in `runtime/data/raw/TrafficLabelling/`.

## Phase 1 — Setup and contracts
- [x] **M1-T050** Add `pyarrow==17.0.0` to `requirements.txt` / `pyproject.toml`, then install · Refs: plan §2 · Done: 2026-10-21 (pyarrow 17.0.0 on host)
- [x] **M1-T051** C-01 → rc.3: formal manifest schema in §2.2 (+ `ids_contracts.events.MANIFEST_KEYS`, a validator and a test). C-06 → rc.4: `ids_ingest.prepare` in §5. SYNC_LOG · Refs: FR-014, FR-018 · Done: 2026-10-21 (C-01 rc.3 → rc.4 with reference hashes; C-06 rc.4)

## Phase 2 — Tests first
- [x] **M1-T060** [P] Synthetic-CSV builder helper (padded headers, duplicated column, latin-1 `\x96`, defect rows) · Files: `tests/unit/csv_factory.py` · Refs: AC-02 · Done: 2026-10-21 (`tests/csv_factory.py`, shared by unit + contract)
- [x] **M1-T061** [P] Unit tests: defect matrix, verification failures, noop/force, atomic failure, verify-only tamper, sample, CLI exit codes · Files: `tests/unit/test_prepare.py` · Refs: AC-02, 04..08, 10 · Done: 2026-10-21 (red → green)
- [x] **M1-T062** [P] Contract test: schema, `row_idx` contiguity, every row converts to a strict-valid C-01 event · Files: `tests/contract/test_c01_replay_contract.py` · Refs: AC-03 · Done: 2026-10-21
- [x] **M1-T063** [P] Real-data integration + perf tests (marker `data`, skipped without raw files) · Files: `tests/integration/test_prepare_real_data.py` · Refs: AC-01, 05, 07, 08, 09 · Done: 2026-10-21

## Phase 3 — Core implementation
- [x] **M1-T070** `RowCleaner` (positions, validation, normalisation, reasons) · Depends: T061 · Refs: FR-012 · Done: 2026-10-21
- [x] **M1-T071** `DayWriter` (schema, chunked ParquetWriter, content hash) · Refs: FR-013, NFR-012, NFR-013 · Done: 2026-10-21
- [x] **M1-T072** `prepare_all` (verification, canonical order, manifest, atomic swap, noop/force) · Depends: T070, T071 · Refs: FR-011, FR-014, FR-015 · Done: 2026-10-21
- [x] **M1-T073** `verify_replay` + `make_sample` + CLI `main` · Depends: T072 · Refs: FR-016..FR-018 · Done: 2026-10-21

## Phase 4 — Real data and measurement
- [x] **M1-T080** Run on the real files. Make the `-m data` tests green. Save the AC-09 measurement · 📦 · Depends: T073 · Refs: AC-01, AC-09 · Done: 2026-10-21 (5/5 real-data; 27.1 s, 139 MB, 34.3 MB)
- [x] **M1-T081** Generate and commit `mocks/replay_sample.parquet`. Wire `make mock` to it · 📦 · Refs: AC-08, Const. IV · Done: 2026-10-21 (8,046 rows, 72 KB; `make mock`)

## Phase 5 — Polish and verify
- [x] **M1-T090** README: raw-file placement, `prepare` usage, outputs · Done: 2026-10-21
- [x] **M1-T091** Spec AC table ✅ with references. Status → Verified. DEVELOPMENT_LOG entry · Done: 2026-10-21

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 Setup / contracts | 2 | 2 | — |
| 2 Tests | 4 | 4 | — |
| 3 Core | 4 | 4 | — |
| 4 Real data | 2 | 2 | — |
| 5 Polish | 2 | 2 | — |

## Blockers log
| Date | Task | Blocked on | Resolution |
|---|---|---|---|
| 2026-10-21 | All | Gates G1–G3 | Owner approved after review on 2026-10-21 |
