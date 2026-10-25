# Tasks: M1-F03 — Replay Producer

| Field | Value |
|---|---|
| Feature ID | M1-F03 |
| Plan version | Approved 2026-10-21 (G3 pre-approved by owner) |
| Owner | Aswin S. |

Legend: 🐳 = needs the running platform.

## Phase 1 — Contracts
- [x] **M1-T100** C-01 rc.5 (murmur2_random). C-06 rc.5 (producer flags and summary). SYNC_LOG · Done: 2026-10-21 (C-01 rc.5, C-06 rc.5)

## Phase 2 — Tests first
- [x] **M1-T110** Unit tests with `FakeClock` / `FakeSink` · Files: `tests/unit/test_producer.py` · Refs: AC-03, 04, 06..09 · Done: 2026-10-21 (red → green; found the end-of-run timing gap)
- [x] **M1-T111** Contract tests · Files: `tests/contract/test_c01_producer_contract.py`, extend `test_c06_platform_contract.py` · Refs: AC-10 · Done: 2026-10-21
- [x] **M1-T112** Live integration + perf tests · Files: `tests/integration/test_producer_live.py`, `tests/integration/test_producer_perf.py` · Refs: AC-01, 02, 04, 05, 07, 08 · Done: 2026-10-21

## Phase 3 — Core
- [x] **M1-T120** Sources (`ReplaySource`, `FixtureSource`), `make_event`, `Clock` · Refs: FR-021, 022, 025 · Done: 2026-10-21
- [x] **M1-T121** `KafkaSink` (pre-flight, delivery accounting, BufferError retry) · Refs: FR-022, 026, 027 · Done: 2026-10-21
- [x] **M1-T122** `run()` pacing loop + `RunStats` + CLI `main` (signals, guards, exit codes) · Refs: FR-023, 024, 027..030 · Done: 2026-10-21
- [x] **M1-T123** `broker.address.family=v4` in topic_admin too (closes open item #12 for M1 clients) · Done: 2026-10-21

## Phase 4 — Live
- [x] **M1-T130** Live integration tests green 🐳 · Done: 2026-10-22 (5/5 live)
- [x] **M1-T131** Perf: 12k × 60 s + max rate, saved 🐳 · Done: 2026-10-22 (11,999.6 ev/s; ceiling ≥ 100k)

## Phase 5 — Polish
- [x] **M1-T140** README producer section · Done: 2026-10-22
- [x] **M1-T141** Spec ACs ✅, status Verified, log · Done: 2026-10-22
