# Plan: M4-F01 — Store Schema and Access (REPLICA)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Stack | Python 3.11, `cassandra-driver==3.29.2` (arm64 wheel verified), `ids_contracts` |

## Design
| Component | File | Notes |
|---|---|---|
| Connection | `src/ids_monitor/store.py` `connect(cfg)` | A single-node `AddressTranslator` maps every discovered address back to the configured contact host. Cassandra advertises its in-container IP, which the Mac cannot reach |
| Schema | `store.apply_schema`, `store.check_schema` + CLI `ids_monitor.schema` | Statements split from the contract CQL files. `check` reads `system_schema.columns` |
| Reader | `store.StoreReader` | Pure helpers `partitions_between`, `drift_summary`, `aggregate_top`, `row_to_dict` are unit-tested without Cassandra |
| Writer | `store.StoreWriter` | Prepared INSERTs, `LOCAL_ONE`, epoch ms → UTC datetime |
| Mock | `src/ids_monitor/synthetic.py` + `mocks/synthetic_rows.py` wrapper | Seeded. Windows every 10 s per IP. Metrics every 5 s. A `runs` row |

## Constitution check
All articles ✅. The replica imports only `ids_contracts`. Config via C-06. The mock comes first, the dashboard (F02) later. Eval-only columns are written by the generator only as synthetic ground truth and are never read for decisions.

## Tests
Unit (pure helpers, generator validity and determinism, CLI codes with a fake session), contract (generated rows vs `ids_contracts.store/metrics` validators, CQL statement split vs contract files), integration `docker` (AC-01, AC-04).
