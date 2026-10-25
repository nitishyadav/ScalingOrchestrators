# SDD Workflow

How a piece of work moves from idea to integrated code in this project.
Step-by-step procedures (PR-00..PR-19) are in [../SDD_PLAYBOOK.md §6](../SDD_PLAYBOOK.md).

## 1. Document hierarchy

```
CONSTITUTION.md                      rules that apply to everything
   └── PROJECT_PLAN.md               goals (G*), metrics (P*, F*), modules, decisions (D-*)
         └── contracts/C-0x_*.md     interfaces between modules (versioned, shared)
               └── ModuleN/specs/MN-Fxx-<slug>/
                     ├── spec.md     WHAT and WHY (no technology choices)
                     ├── plan.md     HOW (tech, design, tests, constitution check)
                     └── tasks.md    ordered, small, testable steps
                           └── code + tests   (each change cites a task ID)
```

Higher documents constrain lower ones. If a lower document needs to break a higher one, change
the higher one first (ADR or CR).

## 2. Lifecycle and gates

| # | Stage | Output | Gate to pass before moving on |
|---|---|---|---|
| 0 | **Contract** | `contracts/C-0x_*.md` (from `contract-template.md`) | Provider + all consumers approve, status **Approved**, golden fixture exists |
| 1 | **Specify** | `spec.md` | No `[NEEDS CLARIFICATION]` left. Every FR has an AC. Reviewed by ≥ 1 consumer-module owner |
| 2 | **Plan** | `plan.md` | Constitution Check all ✅. Every FR mapped to a component. Mock and test strategy defined |
| 3 | **Tasks** | `tasks.md` | Every task ≤ ½ day, has file paths and FR/AC refs, dependencies marked |
| 4 | **Implement** | code + tests | Tests for each AC are written first or alongside. `make test` green |
| 5 | **Verify** | AC table in `spec.md` updated to ✅ | `make contract-test` green. Every AC verified |
| 6 | **Integrate** | `integration/checklists/I-xx.md` | Checklist signed by both module owners |

Status values for any document: `Draft → In Review → Approved → Implemented → Verified` (or `Superseded`).

## 3. IDs and naming

| Thing | Format | Example |
|---|---|---|
| Feature folder | `MN-Fxx-<kebab-slug>/` | `M1-F03-replay-producer/` |
| Functional requirement | `MN-FR-xxx` | `M1-FR-004` |
| Non-functional requirement | `MN-NFR-xxx` | `M3-NFR-002` |
| Acceptance criterion | `MN-Fxx-AC-xx` | `M3-F02-AC-03` |
| Task | `MN-Txxx` | `M2-T012` |
| Contract | `C-0x` (file `C-0x_<snake_name>.md`) | `C-01_network_event.md` |
| Change request | `CR-xxx` (in `contracts/changes/`) | `CR-003` |
| ADR (project / module) | `ADR-xxx` / `MN-ADR-xxx` | `ADR-001-latency-definition.md` |
| Integration | `I-xx` | `I-02-M2-M3-bundle.md` |
| Decision from the plan | `D-xx` | `D-01` |

Requirement keywords follow RFC 2119: **MUST**, **SHOULD** and **MAY**.

## 4. Templates

| Template | Use it when |
|---|---|
| [spec-template.md](templates/spec-template.md) | Starting any feature |
| [plan-template.md](templates/plan-template.md) | After the spec is approved |
| [tasks-template.md](templates/tasks-template.md) | After the plan is approved |
| [contract-template.md](templates/contract-template.md) | Defining any cross-module interface |
| [contract-change-request-template.md](templates/contract-change-request-template.md) | Changing an approved contract |
| [adr-template.md](templates/adr-template.md) | Any decision with alternatives (D-xx, tech choices) |
| [integration-checklist-template.md](templates/integration-checklist-template.md) | Connecting two or more modules |
| [module-readme-template.md](templates/module-readme-template.md) | Each module's README |
| [development-log-template.md](templates/development-log-template.md) | Your personal step-by-step log (`DEVELOPMENT_LOG.md`, PR-20) |

To start a feature:
```bash
cd ModuleN_<name>/specs
mkdir MN-Fxx-<slug> && cp ../../sdd/templates/{spec,plan,tasks}-template.md MN-Fxx-<slug>/
# then rename the files to spec.md, plan.md and tasks.md
```

## 5. Review rules

- **Spec:** reviewed by the owner plus at least one owner of a module that consumes this feature's output.
- **Contract:** provider plus **every** consumer must approve. MAJOR changes need all 4.
- **Plan/Tasks:** the owner can self-approve, but the Constitution Check must be completed honestly.
- Write review comments inline as `> **[Reviewer-Initials]:** comment`, and resolve them before approval.

## 6. Change handling

| Change | Process |
|---|---|
| Typo or clarification in your own spec | Edit it and add a change-log line |
| New requirement in your own module | Update spec → plan → tasks, then bump the spec version |
| Anything that changes a contract | CR → impact analysis → approvals → bump contract version → update fixtures → every affected module re-runs `make contract-test` |
| Disagreement | Write an ADR with options, then decide at the twice-weekly sync |

## 7. Working with an AI coding assistant (Claude Code)

Give the assistant the spec rather than a vague request:
- *"Read `CONSTITUTION.md`, `contracts/C-01_network_event.md` and `Module1_.../specs/M1-F03-replay-producer/`.
  Implement task M1-T004 only. Write the test for M1-F03-AC-02 first."*
- *"Review `spec.md` for ambiguity and list anything that should be `[NEEDS CLARIFICATION]`."*
- *"Check `plan.md` against the constitution and report any violations."*

The assistant must not change files outside the current module or under `contracts/` without
a CR. This is the same rule that applies to people.
