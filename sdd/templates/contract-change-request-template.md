# CR-xxx: <Short title>

<!-- Save as contracts/changes/CR-xxx-<slug>.md. A contract file is never edited without an approved CR (except PATCH typos). -->

| Field | Value |
|---|---|
| CR ID | CR-xxx |
| Contract | C-0x <name> |
| Version change | 1.0.0 → 1.1.0 / 2.0.0 |
| Type | PATCH (clarify) / MINOR (additive) / MAJOR (breaking) |
| Requested by | <name>, Module N |
| Date | YYYY-MM-DD |
| Status | Proposed / Approved / Rejected / Applied |

## 1. Motivation
<!-- What problem did you hit? Link to spec, task or bug. -->

## 2. Proposed change
```diff
- old field / rule
+ new field / rule
```

## 3. Impact analysis
| Module | Affected? | What must change | Effort | Owner ack |
|---|---|---|---|---|
| M1 | yes/no | | | ⬜ |
| M2 | | | | ⬜ |
| M3 | | | | ⬜ |
| M4 | | | | ⬜ |

## 4. Migration plan
<!-- Order of changes, fixture updates, whether both versions must be supported temporarily. -->

## 5. Alternatives considered
-

## 6. Decision
| Member | Approve / Reject | Date |
|---|---|---|
| | | |

Once applied: bump the version in the contract file, update the schema and fixtures, add a change-log line,
and notify everyone to re-run `make contract-test`.
