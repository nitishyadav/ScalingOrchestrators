# Plan: MN-Fxx — <Feature Name>

<!--
PLAN = HOW. Written only after spec.md is Approved.
Every functional requirement in the spec must map to a component below.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Spec version implemented | x.y.z |
| Owner | <name> |
| Status | Draft / Approved |
| Updated | YYYY-MM-DD |

## 1. Approach summary
<!-- One paragraph describing the technical approach. -->

## 2. Technical context
| Item | Choice | Pinned version (from `contracts/versions.md`) |
|---|---|---|
| Language | Python | |
| Key libraries | | |
| Runtime | Docker service / host process / Spark job / Colab | |
| Storage / IO | | |

## 3. Constitution check
| Article | Compliant? | Notes / justification |
|---|---|---|
| I Spec before code | ✅ / ❌ | |
| II Contracts only coupling | | |
| III Module isolation (no cross-module imports) | | |
| IV Mock-first / standalone | | |
| V Uniform Makefile targets | | |
| VI Config via env (C-06) | | |
| VII Honest ML (no hardcoded thresholds, no eval fields in scoring) | | |
| VIII Tests from AC | | |
| IX Version pins, seeds | | |
| X Measured claims | | |
| XI Ownership / CR | | |
| XII Simplicity (no new infra) | | |

## 4. Design

### 4.1 Components
<!-- A diagram (ASCII or mermaid) plus a short description of each component's responsibility. -->
```
<component A> ──► <component B> ──► <contract output>
```

### 4.2 Requirement → component mapping
| Requirement | Component / file | Notes |
|---|---|---|
| MN-FR-001 | `src/<pkg>/<file>.py` | |

### 4.3 File layout
```
ModuleN_<name>/
├── src/<pkg>/
│   ├── __init__.py
│   └── ...
├── tests/unit/test_....py
├── tests/contract/test_....py
└── mocks/...
```

### 4.4 Interface implementation
<!-- How this feature satisfies the contracts it provides or consumes: serialisation, keys, retries, idempotency. -->

## 5. Configuration
| Env var (C-06 name) | Default | Used for |
|---|---|---|
| | | |

## 6. Mock and stub strategy
| Dependency | Mock used during development | Swapped for the real one at |
|---|---|---|
| | | Integration I-xx |

## 7. Test strategy
| Level | What | Tooling | Maps to AC |
|---|---|---|---|
| Unit | | pytest | |
| Contract | Output validates against C-0x; accepts golden fixtures | pytest + `ids_contracts` | |
| Integration | | docker compose | |
| Performance | | benchmark script | |
| Manual | | screenshot / checklist | |

## 8. Risks and alternatives considered
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| | | | |
<!-- Write an ADR when the choice is significant. -->

## 9. Done means
- [ ] All tasks in `tasks.md` complete
- [ ] `make test` and `make contract-test` green
- [ ] Every AC in the spec marked ✅ with test reference
- [ ] README updated (run instructions, env vars)
