# Contract C-0x: <Contract Name>

<!--
A contract is the ONLY way two modules may depend on each other.
It must be precise enough that two people who never talk can build both sides and they still work together.
Save it as contracts/C-0x_<snake_name>.md. Machine-readable parts go in contracts/schemas/, examples in contracts/fixtures/.
-->

| Field | Value |
|---|---|
| Contract ID | C-0x |
| Version | 1.0.0 (MAJOR = breaking, MINOR = additive, PATCH = clarification) |
| Status | Draft / In Review / Approved / Superseded |
| Provider (owner) | MN — <name> |
| Consumers | MK, MJ |
| Medium | Kafka topic / Cassandra table / file bundle / CLI + env |
| Machine-readable schema | `contracts/schemas/<file>` |
| Golden fixtures | `contracts/fixtures/<file>` |
| Decisions applied | D-xx, ADR-xxx |

## 1. Purpose
<!-- What crosses this boundary and why. -->

## 2. Transport and location
<!-- e.g. Kafka topic name, key, partitioning; table name and keyspace; directory path; CLI command. Names come from C-06. -->

## 3. Schema

| Field | Type | Required | Unit / format | Constraints | Description | Example |
|---|---|---|---|---|---|---|
| | | yes/no | | | | |

## 4. Semantics
- **Keys and partitioning:**
- **Ordering guarantees:**
- **Time semantics (event time vs processing time, timezone, precision):**
- **Idempotency / duplicates:**
- **Null / missing / default handling:**
- **Eval-only fields (never used in scoring):**

## 5. Examples
```json
{ }
```

## 6. Validation
- Validator: `ids_contracts.<module>.validate_<thing>()` (in `contracts/python/`)
- Golden fixture(s) and how to use them:

## 7. Obligations
**Provider MUST**
- Emit only data that validates against §3
- …

**Consumers MUST**
- Ignore unknown fields (forward compatibility for MINOR versions)
- …

## 8. Error handling
<!-- What happens with invalid data on each side: drop, dead-letter, fail fast? -->

## 9. Contract tests
| Side | Test | Location |
|---|---|---|
| Provider | Output validates against the schema | `ModuleN/tests/contract/` |
| Consumer | Accepts golden fixture and produces the expected result | `ModuleK/tests/contract/` |

## 10. Compatibility and versioning
- MINOR: adding optional fields is allowed, and consumers must tolerate them.
- MAJOR: removing or renaming fields, or changing types or meaning, requires a CR and approval from all affected owners.

## 11. Approvals
| Role | Member | Version approved | Date |
|---|---|---|---|
| Provider | | | |
| Consumer | | | |
| Consumer | | | |

## 12. Change log
| Version | Date | CR | Change |
|---|---|---|---|
| 1.0.0 | | — | Initial approved version |
