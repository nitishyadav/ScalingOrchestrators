# Tasks: M4-F03 — Benchmark harness

| Field | Value |
|---|---|
| Feature ID | M4-F03 |
| Plan version | 1.0 |
| Owner | Vidhi Kant Gupta |
| Target finish | 2026-11-04 (code), runs in P3 (5–10 Nov) |

## Phase 1 — Setup
- [x] **M4-T201** M4-ADR-002 (throughput / latency method) · Refs: FR-043, 044, 046 · Done: 2026-11-01, `docs/adr/M4-ADR-002-benchmark-method.md` Accepted

## Phase 2 — Tests first
- [x] **M4-T210** [P] Plan tests · Files: `tests/unit/test_bench_plan.py` · Refs: AC-01, AC-02 · Done: 2026-11-01, 17 tests
- [x] **M4-T211** [P] Maths tests · Files: `tests/unit/test_bench_math.py` · Refs: AC-03, AC-04, AC-05 · Done: 2026-11-01, 9 tests
- [x] **M4-T212** [P] Runner tests with fake CLI/store/clock · Files: `tests/unit/test_bench_runner.py` · Refs: AC-06, AC-07 · Done: 2026-11-01, 8 tests (+4 report tests)

## Phase 3 — Core
- [x] **M4-T220** `bench_plan.py` · Depends: T210 · Done: 2026-11-01, bench_plan.py
- [x] **M4-T221** `bench_math.py` · Depends: T211 · Done: 2026-11-01, bench_math.py
- [x] **M4-T222** `bench_report.py` + `bench.py` (Runner, adapters, CLI), `make bench` · Depends: T212, T220, T221 · Done: 2026-11-01, bench_report.py, bench.py, `make bench`

## Phase 4 — Integration
- [x] **M4-T230** C-06 CLI contract test for `ids_monitor.bench` (`--help` 0, bad flag 2, summary line) · Files: `tests/contract/test_bench_cli.py` · Done: 2026-11-01, 3 tests
- [ ] **M4-T231** Live smoke E1 level 1, 60 s (AC-08) · Files: `tests/integration/test_bench_live.py` (written, skips) · Done: _
- [ ] **M4-T232** Full runs (AC-09), P3 phase · Done: _

## Phase 5 — Polish
- [x] **M4-T240** README, spec AC table, dev log · Done: 2026-11-01

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 | 1 | 1 | |
| 2 | 3 | 3 | |
| 3 | 3 | 3 | |
| 4 | 3 | 1 | platform up, replay data, bundle, M1/M3 install (T231, T232) |
| 5 | 1 | 1 | |

## Blockers log
| Date | Task | Blocked on | Resolution |
|---|---|---|---|
| 2026-11-01 | T231, T232 | No `runtime/data` (M1 prepare), no bundle (M2), M1/M3 not installed, Docker VM 7.65 GB < 10 GB budget | At I-03 (2–4 Nov) on the integration machine |
