# Tasks: M4-F02 — Live dashboard

| Field | Value |
|---|---|
| Feature ID | M4-F02 |
| Plan version | 1.0 |
| Owner | Vidhi Kant Gupta |
| Target finish | 2026-11-03 |

## Phase 1 — Setup
- [x] **M4-T101** Check Streamlit 1.39 `st.fragment(run_every)`, `AppTest`, Altair availability · Refs: plan §2 · Done: 2026-11-01, Streamlit 1.39.0, Altair 5.5.0, AppTest

## Phase 2 — Tests first
- [x] **M4-T110** [P] View-model tests · Files: `tests/unit/test_dashboard_model.py` · Refs: AC-01, 02, 03, 04, 05, 10 · Done: 2026-11-01, 12 tests
- [x] **M4-T111** [P] Chart-spec tests · Files: `tests/unit/test_charts.py` · Refs: AC-03 · Done: 2026-11-01, 4 tests
- [x] **M4-T112** [P] Headless page tests with a fake store · Files: `tests/unit/test_dashboard_app.py` · Refs: AC-02, 04, 06 · Done: 2026-11-01, 4 headless tests

## Phase 3 — Core
- [x] **M4-T120** `dashboard_model.py` · Depends: T110 · Refs: FR-020, 021, 023, 026, 027, 030 · Done: 2026-11-01, dashboard_model.py
- [x] **M4-T121** `charts.py` · Depends: T111 · Refs: FR-022, 028 · Done: 2026-11-01, charts.py (palette validated light + dark)
- [x] **M4-T122** `dashboard.py` page + 3 s fragment · Depends: T112, T120, T121 · Refs: FR-024, 025, 027, 029 · Done: 2026-11-01, dashboard.py + dashboard_app.py

## Phase 4 — Integration
- [x] **M4-T130** `make run` serves the dashboard on 8501 · Refs: FR-029 · Done: 2026-11-01, health ok on 8501
- [x] **M4-T131** Live tests: headless render on synthetic data, write → visible ≤ 5 s, 75k cycle ≤ 2 s · Files: `tests/integration/test_dashboard_live.py` · Refs: AC-07, 08, 09 · Done: 2026-11-01, 3 live tests: F4 3.44 s, 75k cycle 1.61 s

## Phase 5 — Polish
- [ ] **M4-T140** README, manual check (AC-11), spec AC table, dev log · Done: _ (README, spec, dev log done; owner sign-off pending)
- [x] **M4-T141** Restyle (spec 1.1.0): `ui.py`, `.streamlit/config.toml`, tiles/strip/header, UTC axes, bar baseline fix, mock `--jitter` · Files: `tests/unit/test_ui.py` + updated chart/page tests · Done: 2026-11-01, 74 unit + 9 live passed

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 | 1 | 1 | |
| 2 | 3 | 3 | |
| 3 | 3 | 3 | |
| 4 | 2 | 2 | |
| 5 | 2 | 1 | AC-11 sign-off (owner) |

## Blockers log
| Date | Task | Blocked on | Resolution |
|---|---|---|---|
