# Tasks: MN-Fxx — <Feature Name>

<!--
Rules:
- Each task is ≤ ½ day, touches named files, and cites the FR/AC it serves.
- [P] = can run in parallel with other [P] tasks in the same phase (different files, no dependency).
- Write test tasks BEFORE the implementation tasks they verify.
- Tick the box and fill "Done" when a task is complete. Cite the task ID in commit messages.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Plan version | x.y |
| Owner | <name> |
| Target finish | YYYY-MM-DD |

## Phase 1 — Setup
- [ ] **MN-T001** Create package skeleton `src/<pkg>/…`, `Makefile` with standard targets · Files: … · Refs: Const. V · Done: _
- [ ] **MN-T002** [P] Add dependencies with pinned versions · Files: `requirements.txt` · Refs: Const. IX · Done: _

## Phase 2 — Tests first
- [ ] **MN-T010** [P] Contract test: output validates against C-0x v1.0 · Files: `tests/contract/test_….py` · Refs: AC-01 · Done: _
- [ ] **MN-T011** [P] Unit test for … · Files: `tests/unit/test_….py` · Refs: AC-02 · Done: _

## Phase 3 — Core implementation
- [ ] **MN-T020** Implement … · Files: … · Depends: T010 · Refs: FR-001 · Done: _
- [ ] **MN-T021** … · Depends: T020 · Refs: FR-002 · Done: _

## Phase 4 — Mock and integration readiness
- [ ] **MN-T030** Ship/update mock in `mocks/` for consumers · Refs: Const. IV · Done: _
- [ ] **MN-T031** Run against other modules' mocks end-to-end · Refs: AC-0x · Done: _

## Phase 5 — Polish and verify
- [ ] **MN-T040** Update module README (run steps, env vars) · Done: _
- [ ] **MN-T041** Mark AC table in spec.md ✅ with test references · Done: _

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 Setup | | | |
| 2 Tests | | | |
| 3 Core | | | |
| 4 Mock / Integration | | | |
| 5 Polish | | | |

## Blockers log
| Date | Task | Blocked on (contract / module / decision) | Resolution |
|---|---|---|---|
