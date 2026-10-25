# Tasks: M1-F04 — Attack Injector

| Field | Value |
|---|---|
| Feature ID | M1-F04 |
| Plan version | Approved 2026-10-22 (G3) |
| Owner | Aswin S. |

## Phase 1 — Contracts
- [x] **M1-T150** C-06 rc.6: producer flags `--seed`, `--attack-start`, `--attack-duration`; attack summary fields. SYNC_LOG · Done: 2026-10-22 (C-06 rc.6)

## Phase 2 — Tests first
- [x] **M1-T160** Unit tests: `tests/unit/test_injector.py` (AC-01..06) and the attack CLI cases in `test_producer.py` (AC-09) · Done: 2026-10-22 (red → green)
- [x] **M1-T161** Contract: injected events in `test_c01_producer_contract.py`. C-06 CLI usage errors · Done: 2026-10-22
- [x] **M1-T162** Live + perf: `tests/integration/test_injector_live.py` (AC-07, AC-08) · Done: 2026-10-22

## Phase 3 — Core
- [x] **M1-T170** `injector.py`: `AttackGenerator`, `InjectingSource` · Done: 2026-10-22
- [x] **M1-T171** Producer wiring: flags, guards, summary fields; remove the "available from M1-F04" guard · Done: 2026-10-22 (also restructured `run()` to check the deadline before pulling the next item)

## Phase 4 — Live
- [x] **M1-T180** Live tests green. Perf measured and saved 🐳 · Done: 2026-10-22 (2/2 live + M1-F03 live regression 5/5)

## Phase 5 — Polish
- [x] **M1-T190** README injector section. Spec ACs ✅. Module 1 status. Log · Done: 2026-10-22
