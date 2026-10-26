# Integration I-xx: <MA ↔ MB — seam name>

<!-- Save as integration/checklists/I-xx-<slug>.md. One checklist per integration event. -->

| Field | Value |
|---|---|
| Integration ID | I-xx |
| Modules | MA (<owner>) ↔ MB (<owner>) |
| Seam / contracts | C-0x v?, C-0y v? |
| Date | YYYY-MM-DD |
| Environment | Docker Compose on <machine>, `contracts/versions.md` rev ? |
| Result | ⬜ Pass / ⬜ Pass with issues / ⬜ Fail |

## 1. Module versions under test
| Module | Source (whose copy) | Spec versions | Notes |
|---|---|---|---|
| MA | owner canonical | | |
| MB | owner canonical | | |

## 2. Pre-checks (each module run alone)
- [ ] MA: `make test` green
- [ ] MA: `make contract-test` green against the contract versions above
- [ ] MB: `make test` green
- [ ] MB: `make contract-test` green
- [ ] Both sides use the same `contracts/` revision (identical files)
- [ ] Env file matches C-06 (no local overrides)

## 3. Integration steps
| # | Step | Command | Expected | Actual | ✅/❌ |
|---|---|---|---|---|---|
| 1 | Start platform | `make -C Module1_Data_Ingestion_Platform run` | all services healthy | | |
| 2 | | | | | |
| 3 | Smoke test: golden fixture end-to-end | | output equals expected fixture | | |

## 4. Acceptance checks
| Check | Evidence (log, screenshot, query output) | ✅/❌ |
|---|---|---|
| Data crosses the seam with no validation errors | | |
| Volume / rate check | | |
| Failure case (stop one side, then restart) | | |

## 5. Issues found
| # | Description | Side | Contract gap? (→ CR) | Owner | Status |
|---|---|---|---|---|---|

## 6. Sign-off
| Member | Module | Signed |
|---|---|---|
| | MA | |
| | MB | |
