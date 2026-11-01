# Tasks: M4-F04 — Results and report figures

| Field | Value |
|---|---|
| Feature ID | M4-F04 |
| Plan version | 1.0 |
| Owner | Vidhi Kant Gupta |
| Target finish | 2026-11-03 (code); AC-06 after the P3 runs (≤ 12 Nov) |

## Phase 1 — Setup
- [x] **M4-T301** M4-F03 1.1.0: per-category rule/ML/hybrid rates and `windows.csv.gz` (F3 input) · Done: 2026-11-01, `test_f3_rule_vs_hybrid_per_category`

## Phase 2 — Tests first
- [x] **M4-T310** [P] Selection, scorecard, F3, evidence tests · Files: `tests/unit/test_analyze.py` · Refs: AC-01, 02, 03, 05 · Done: 2026-11-01, 7 tests (+ `results_fixture.py`)
- [x] **M4-T311** [P] Figure tests · Files: `tests/unit/test_figures.py` · Refs: AC-04 · Done: 2026-11-01, 6 tests

## Phase 3 — Core
- [x] **M4-T320** `analyze.py` · Depends: T310 · Done: 2026-11-01, analyze.py
- [x] **M4-T321** `figures.py` · Depends: T311 · Done: 2026-11-01, figures.py
- [x] **M4-T322** CLI + `make analyze` + contract test · Files: `tests/contract/test_analyze_cli.py` · Done: 2026-11-01, `make analyze`, 2 contract tests

## Phase 4 — Integration
- [x] **M4-T330** Visual check on a synthetic full result set (all 6 figures) · Done: 2026-11-01, 6 figures reviewed; fixed: ideal curve on log x, legend overlap, clipped labels/points, recovery line drawn across the outage
- [ ] **M4-T331** Run on the real M4-F03 results (AC-06) · Done: _

## Phase 5 — Polish
- [x] **M4-T340** README, spec AC table, dev log · Done: 2026-11-01
