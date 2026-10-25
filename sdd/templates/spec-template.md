# Spec: MN-Fxx — <Feature Name>

<!--
SPEC = WHAT and WHY. No technology or implementation choices here (those go in plan.md).
Mark every unknown as [NEEDS CLARIFICATION: question]. A spec cannot be Approved while any remain.
Delete these comment blocks once filled.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Module | ModuleN_<name> |
| Owner | <name> |
| Reviewers | <consumer-module owner(s)> |
| Status | Draft / In Review / Approved / Implemented / Verified |
| Version | 0.1.0 |
| Created / Updated | YYYY-MM-DD / YYYY-MM-DD |
| Proposal trace | G?, P?, F? (see PROJECT_PLAN §1.2–1.3) |
| Contracts touched | C-0x (provides v?), C-0y (consumes v?) |
| Decisions applied | D-xx, ADR-xxx |

## 1. Summary
<!-- 2–4 sentences: what this feature delivers and for whom. -->

## 2. Context and motivation
<!-- Why this feature is needed and where it sits in the pipeline. Link to PROJECT_PLAN sections. -->

## 3. Scope
**In scope**
- …

**Out of scope** (and who handles it, if anyone)
- …

## 4. Actors and user stories
<!-- Actors can be people (operator, evaluator) or modules (M3 stream job). -->
- **US-1:** As a <actor>, I want <capability> so that <benefit>.
- **US-2:** …

## 5. Functional requirements

| ID | Requirement (MUST / SHOULD / MAY) | Priority | Story | Trace |
|---|---|---|---|---|
| MN-FR-001 | The <component> MUST … | P0 | US-1 | G? |
| MN-FR-002 | | | | |

## 6. Non-functional requirements

| ID | Category | Requirement (measurable) | Trace |
|---|---|---|---|
| MN-NFR-001 | Performance | MUST sustain ≥ X ev/s on the reference machine | P1 |
| MN-NFR-002 | Reliability | | |
| MN-NFR-003 | Resource | MUST run within N GB RAM / M CPUs | R1 |
| MN-NFR-004 | Observability | | |

## 7. Interfaces

### 7.1 Provided (this feature produces)
| Contract | Version | What exactly is provided |
|---|---|---|
| C-0x | 1.0 | |

### 7.2 Consumed (this feature depends on)
| Contract | Version | What is used | Mock used until the real one is available |
|---|---|---|---|
| C-0y | 1.0 | | `contracts/fixtures/...` or `ModuleK/mocks/...` |

## 8. Data
<!-- Inputs, outputs, volumes, retention. Reference contract fields; do not redefine them. -->

## 9. Acceptance criteria

| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| MN-Fxx-AC-01 | **Given** … **When** … **Then** … | MN-FR-001 | unit / contract / integration / perf / manual | ⬜ |
| MN-Fxx-AC-02 | | | | ⬜ |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| Malformed input | |
| Upstream unavailable | |
| Restart / replay | |

## 11. Assumptions and dependencies
- …

## 12. Open questions
- [NEEDS CLARIFICATION: …] (owner: …, due: …)

## 13. Review checklist (complete before setting status to Approved)
- [ ] No implementation details (frameworks, code structure) in this spec
- [ ] Every FR is testable and has at least one AC
- [ ] Every NFR has a number and a unit
- [ ] Interfaces reference contracts by ID and version, with no ad-hoc formats
- [ ] Eval-only fields are not used in any scoring requirement (Constitution Art. VII)
- [ ] No open `[NEEDS CLARIFICATION]`
- [ ] At least one consumer-module owner has reviewed

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | YYYY-MM-DD | | Initial draft |
