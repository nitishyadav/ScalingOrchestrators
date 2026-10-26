# Development Log — <Name> (<Owned module>)

<!--
An append-only record of EVERY step taken, at every level of development.
- One entry per meaningful step (a document written, a decision taken, a task implemented, a test run, an integration).
- Never rewrite history. If something was wrong, add a new entry that corrects it.
- The AI assistant appends an entry at the end of every working session (PR-20).
-->

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
| L0 Project | | | |
| L1 SDD framework | | | |
| L2 Contracts | | | |
| L3 Module | | | |
| L4 Feature | | | |
| L5 Task / code | | | |
| L6 Integration | | | |
| L7 Experiments | | | |

## Step log

<!-- Copy this block for each step. IDs are sequential: S-001, S-002, … -->

### S-xxx · YYYY-MM-DD · L? <Level name> · <Procedure PR-xx>
**What:** <what was done, one or two sentences>
**Why:** <requirement, decision or gate it serves (G*, P*, F*, D-xx, FR, AC)>
**Artifacts:** <files created or changed>
**Verification:** <tests run and their result, review done, or "n/a">
**Decisions / issues:** <ADR, CR or open question raised, or "none">

## Open items

| # | Item | Level | Owner | Due | Status |
|---|---|---|---|---|---|
