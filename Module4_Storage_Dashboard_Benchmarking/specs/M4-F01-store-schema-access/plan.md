# Plan: M4-F01 — Store schema and access

| Field | Value |
|---|---|
| Feature ID | M4-F01 |
| Spec version implemented | 1.0.0 |
| Owner | Vidhi Kant Gupta |
| Status | Approved |
| Updated | 2026-11-01 |

## 1. Approach summary
This is a small Python package on top of `cassandra-driver`.
- **Pure logic is separate from I/O.** DDL parsing, schema diffing, key enumeration, row conversion, drift/top-N and synthetic generation are plain
  functions, unit-tested without Cassandra.
- **I/O goes through one session object** (`execute`, `prepare`). Unit tests use a recording fake. Integration tests use the live service.
- **The DDL is read from the contract files**, never copied. `check` reads `system_schema.columns`.
- **Reads enumerate partitions** with `ids_contracts.store.partition_keys` and run one prepared `WHERE date_bucket=? AND bucket=? AND window_end>=? AND window_end<=?` per bucket.
  The `run_id` filter is applied client-side (C-04 §5).

## 2. Technical context
| Item | Choice | Pin (`contracts/versions.md`) |
|---|---|---|
| Language | Python | 3.11.x |
| Driver | `cassandra-driver` | 3.29.2 |
| Shared contract code | `ids_contracts` (store, metrics, config) | editable install |
| Runtime | Host process. Cassandra from the M1 platform compose | `cassandra:4.1.10` |
| Tests | pytest. `-m docker` for live tests | 8.3.x |

## 3. Constitution check
| Article | Compliant? | Notes |
|---|---|---|
| I Spec before code | ✅ | Spec 1.0.0 Approved. Tasks M4-T0xx cited in commits |
| II Contracts only coupling | ✅ | Reads and writes only the C-04/C-05 tables. Config from C-06 |
| III Module isolation | ✅ | Imports only `ids_contracts` |
| IV Mock-first | ✅ | `ids_monitor.synthetic` is the mock of M3's output (`make mock`) |
| V Uniform Makefile | ✅ | `run` = schema apply + check. `mock` = synthetic |
| VI Config via env | ✅ | `load_runtime_config` only. The keyspace name comes from `CASSANDRA_KEYSPACE` |
| VII Honest ML | ✅ | The drift threshold comes from `ids_contracts.store`. Labels are never read by view functions (tested) |
| VIII Tests from AC | ✅ | Every AC maps to tests (§7) |
| IX Pins, seeds | ✅ | Generator seeded (`--seed`, default 42), recorded in the summary line |
| X Measured claims | ✅ | Perf AC-12 measured by a scripted test; output recorded in the dev log |
| XI Ownership | ✅ | M4 code only. M3 changes go through C-04 review |
| XII Simplicity | ✅ | No new infrastructure |

## 4. Design
### 4.1 Components
```
contracts/schemas/*.cql ─► schema.py (parse, diff, apply, check, CLI) ─► Cassandra
                                       ▲
db.py (connect from C-06) ─────────────┤
                                       ▼
store.py (Store: read_windows / read_recent / latest_metrics / latest_runs / write_*) ◄── synthetic.py (generate + CLI)
   │ rows as dicts, timestamps as epoch ms
   ▼
view.py (drift_summary, top_flagged)  ──► M4-F02 dashboard, M4-F03 harness
cli.py (C-06 exit codes, summary line)
```

### 4.2 Requirement → component mapping
| Requirement | Component | Notes |
|---|---|---|
| FR-001, FR-002, FR-003 | `schema.py` | `parse_ddl`, `live_schema`, `diff_schema`, `apply_schema(recreate=)` |
| FR-004, FR-005, FR-008, FR-009 | `store.py` | `Store` |
| FR-006, FR-007, FR-013 | `view.py` | Pure functions over row dicts |
| FR-010, FR-011 | `synthetic.py` | `generate_run`, `follow` |
| FR-012, NFR-003 | `db.py`, `cli.py` | `connect(cfg)`, `run_command` |

### 4.3 File layout
```
Module4_Storage_Dashboard_Benchmarking/
├── src/ids_monitor/{__init__,cli,db,schema,store,view,synthetic}.py
├── tests/unit/{conftest,test_schema,test_store,test_view,test_synthetic,test_cli}.py
├── tests/contract/test_c04_c05_contract.py
└── tests/integration/test_store_live.py      (-m docker)
```

### 4.4 Interface implementation
- **Timestamps:** written as epoch ms (the driver serialises `int` as ms). Read back as naive UTC `datetime` and converted to epoch ms.
- **Writes:** prepared `INSERT` at `LOCAL_ONE`, after `validate_row` / `validate_metrics_row` / `validate_run_row`. They are idempotent upserts.
- **Old key detection:** if the partition key of the live `window_scores` ≠ `(date_bucket, bucket)`, raise `SchemaMigrationRequired`.
  `--recreate` runs `DROP TABLE` and then applies the DDL.
- **Keyspace:** the DDL text has `ids.`. It is rewritten to `CASSANDRA_KEYSPACE` (C-06, default `ids`).

## 5. Configuration
| Env var (C-06) | Default | Used for |
|---|---|---|
| `CASSANDRA_HOSTS` | `localhost` | Contact points |
| `CASSANDRA_PORT` | `9042` | Port |
| `CASSANDRA_KEYSPACE` | `ids` | Keyspace |
| `RUN_ID` | `DEV-local` | Default run for the generator (`DEV-synthetic` if left at the default) |

## 6. Mock and stub strategy
| Dependency | Mock during development | Swapped at |
|---|---|---|
| M3 writer (C-04) | `python -m ids_monitor.synthetic` | I-03 |
| M3 metrics (C-05) | Same generator | I-03 |
| Cassandra (unit tests) | `FakeSession` in `tests/unit/conftest.py` | Integration tests |

## 7. Test strategy
| Level | What | Maps to AC |
|---|---|---|
| Unit | DDL parse/diff, old-key detection, partition enumeration and query shape, client-side run filter, row conversion, write validation, drift, top-N, generator determinism, CLI exit codes | AC-02..AC-09, AC-11 |
| Contract | Generated rows validate against C-04/C-05. The parsed DDL equals the `ids_contracts` constants | AC-09 |
| Integration | apply ×2 + check, recreate from the 0.1.0 key, write → read round trip, follow mode, perf | AC-01, AC-03, AC-04, AC-07, AC-10, AC-12 |

## 8. Risks and alternatives
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| Copy the DDL into the module | No file dependency | Drifts from the contract | No |
| Read the DDL from `contracts/schemas` | One source of truth | Needs the workspace path (C-06 `IDS_ROOT`) | **Yes** |
| `execute_concurrent` for writes | Faster bulk writes | More code. Only synthetic data is written | Later, if perf needs it |

## 9. Done means
- [ ] All tasks in `tasks.md` complete
- [ ] `make test` and `make contract-test` green, and `make integration-test` green with Cassandra up
- [ ] Every AC in the spec ✅ with test reference
- [ ] README updated
