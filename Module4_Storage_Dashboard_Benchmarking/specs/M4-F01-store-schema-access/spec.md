# Spec: M4-F01 — Store Schema and Access (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8). It will be replaced at integration.

| Field | Value |
|---|---|
| Feature ID | M4-F01 |
| Owner (canonical) / builder | Vidhi Kant Gupta / Aswin S. (replica) |
| Status | **Verified (replica)** 2026-10-22, 5/5 ACs |
| Version | 0.1.0-replica |
| Proposal trace | §2.2 (Cassandra time-series sink), Week 7 (dashboard queries Cassandra with `cassandra-driver`), G6, F4, F5 |
| Contracts | C-04 0.1.0-replica (provides, as owner-side), C-05 0.1.0-replica (consumes), C-06 rc.6 (config, CLI conventions) |

## 1. Summary
This feature provides three things on top of Cassandra for everything M4 does next (dashboard, benchmarks):
1. A one-command, idempotent schema setup.
2. A small Python access layer: recent windows, drift rate, top flagged IPs, per-batch metrics and runs.
3. A synthetic-data generator that writes contract-valid C-04/C-05 rows. This is **M4's stand-in**, so the dashboard can be built before the Spark job exists.

## 2. Functional requirements
| ID | Requirement | Trace |
|---|---|---|
| M4-FR-001 | `python -m ids_monitor.schema apply` MUST execute `contracts/schemas/ids_schema.cql` and `metrics_schema.cql` (idempotent). `… check` MUST verify that the live tables have exactly the contract columns and types, exiting 1 on drift | C-04, C-05 |
| M4-FR-002 | The access layer MUST read windows with `window_end` in the last *N* seconds, using only partition-key queries over the UTC hour buckets the span covers (no `ALLOW FILTERING`), optionally filtered by `run_id` | C-04 §4 |
| M4-FR-003 | MUST compute the drift summary (`total`, `anomalous`, `rate`, `alert` per `ids_contracts.store.drift_alert`) and the top-N flagged source IPs (anomalous window count, max score, last seen, rule ids) | G6, F5 |
| M4-FR-004 | MUST read the latest N `pipeline_metrics` rows for a run, and the most recent `runs` rows | C-05 |
| M4-FR-005 | MUST provide writers for C-04/C-05 rows (used by the generator and by tests). They write with `LOCAL_ONE` and accept epoch-ms timestamps | C-04 §3 |
| M4-FR-006 | `python -m ids_monitor.synthetic` MUST write deterministic (seeded), contract-valid windows and metrics for a run ending "now", with a configurable anomaly share. `--follow S` keeps writing new 10 s windows in real time for S seconds | Const. IV |
| M4-FR-007 | Every CLI follows C-06 §5 (exit codes, one JSON summary line). Config only via `load_runtime_config` | C-06 |

## 3. Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M4-F01-AC-01 | `schema apply` twice → exit 0 both times. `schema check` → exit 0 with 3 tables matching the contract | integration | ✅ `test_ac01_apply_twice_and_check` |
| M4-F01-AC-02 | Hour-bucket enumeration covers a span crossing an hour or day boundary. Row conversion round-trips epoch ms. Drift and top-N aggregate correctly | unit | ✅ `test_store_logic.py` (partitions, ms round-trip, drift, top-N) |
| M4-F01-AC-03 | Every synthetic window passes `store.validate_row` and every metrics/run row passes the C-05 validators. The same seed gives identical rows | unit + contract | ✅ `test_synthetic.py`, `test_generated_rows_satisfy_c04_c05` |
| M4-F01-AC-04 | Live: write a synthetic run (share 0.2), then the recent windows for that run equal the rows written, the drift rate ≈ 0.2 with the alert on, top-10 is ordered, and the metrics and latest run are readable | integration | ✅ `test_ac04_write_and_read_back_a_synthetic_run` (all columns round-trip) |
| M4-F01-AC-05 | CLIs: `--help` 0, bad flag 2, summary line. Cassandra down → exit 1 with a hint | unit + contract | ✅ CLI unit + contract tests, `test_ac05_unreachable_store_is_reported` |

## 4. Change log
| Version | Date | Change |
|---|---|---|
| 0.1.0-replica | 2026-10-22 | Initial replica spec |
