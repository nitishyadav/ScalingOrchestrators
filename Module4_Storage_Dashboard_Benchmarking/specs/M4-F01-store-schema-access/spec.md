# Spec: M4-F01 — Store schema and access

| Field | Value |
|---|---|
| Feature ID | M4-F01 |
| Module | Module4_Storage_Dashboard_Benchmarking |
| Owner | Vidhi Kant Gupta |
| Reviewers | Kumari Priyanka (M3, writer of C-04 and provider of C-05) |
| Status | **Verified** (2026-11-01: 45 unit/contract + 6 live tests green). M3 review happens with C-04 PR-05 |
| Version | 1.0.0 |
| Created / Updated | 2026-11-01 / 2026-11-01 |
| Proposal trace | G6 (dashboard), F4, F5 (drift), P1–P5 (benchmark reads), Const. IV (mock for M3/M4) |
| Contracts touched | C-04 (provides, 1.0.0-rc.1), C-05 (consumes, 0.1.0-replica), C-06 (consumes, 1.0.0-rc.7) |
| Decisions applied | D-02 / M4-ADR-001 (key), D-01 (latency), ADR-007 (eval-only), ADR-013 (drift metric) |

## 1. Summary
This feature puts the C-04 and C-05 tables into Cassandra and checks that the live tables match the contracts.
It gives the dashboard (M4-F02) and the benchmark harness (M4-F03) one way to read scored windows and pipeline metrics.
It also generates realistic synthetic rows, so that M4 can be built and demonstrated before M3's stream job writes real data.

## 2. Context and motivation
M3 writes scored windows (C-04) and per-batch metrics (C-05). M4 owns the C-04 schema and reads both.
Integration I-03 (M3 ↔ M4, 2–4 Nov) needs the schema applied and a verified read path. The dashboard and the experiments need a
shared, tested way to answer "what happened in the last 300 s" and "what happened in run X".

## 3. Scope
**In scope**
- Applying and checking the C-04 and C-05 DDL, including detecting the C-04 0.1.0 key and recreating the table only when asked explicitly.
- Reading windows over a time span (optionally one run), the latest metrics of a run, and the recent runs.
- The drift summary and the top flagged source IPs over a set of windows.
- Writers for C-04 and C-05 rows, used by the synthetic generator and the tests.
- A deterministic synthetic generator (one-shot and follow mode).

**Out of scope**
- The dashboard UI (M4-F02), experiment orchestration (M4-F03), and figures (M4-F04).
- The production writer of C-04 and C-05 (M3-F04).
- The Cassandra service itself (M1-F01 platform).

## 4. Actors and user stories
- **US-1:** As the M4 operator, I want one command that creates or verifies the store, so that M3 can start writing and drift from the contract is caught early.
- **US-2:** As M4-F02 (dashboard), I want the windows of the last N seconds, the drift summary and the top flagged IPs, so that I can render G6.
- **US-3:** As M4-F03 (harness), I want all windows and metrics of one run, so that I can compute P1–P5 and F2/F3.
- **US-4:** As the M4 developer, or M3 before I-03, I want contract-valid synthetic data in Cassandra, so that I can build and demo without the stream job.

## 5. Functional requirements
| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M4-FR-001 | `apply` MUST create the keyspace and the C-04/C-05 tables from the contract DDL files. It MUST be idempotent | P0 | US-1 | C-04 §8, C-05 |
| M4-FR-002 | `check` MUST compare the live tables with the contracts (columns, types, partition key, clustering) and report every difference. It exits non-zero on any drift | P0 | US-1 | C-04 §9 |
| M4-FR-003 | If `ids.window_scores` exists with a different primary key, `apply` MUST stop with an error naming the migration. With an explicit recreate option it MUST drop and recreate the table | P0 | US-1 | M4-ADR-001, C-04 §11 |
| M4-FR-004 | The reader MUST return the C-04 rows with `window_end` in [start, end], optionally only one `run_id`, using only partition-key queries (no secondary index, no `ALLOW FILTERING`) | P0 | US-2, US-3 | C-04 §5 |
| M4-FR-005 | The reader MUST return the C-04 rows of the last N seconds relative to a given "now" | P0 | US-2 | C-04 §5 |
| M4-FR-006 | MUST compute the drift summary `total`, `anomalous`, `rate`, `alert` over windows, with `alert` defined by C-04 `drift_alert` | P0 | US-2 | G6, F5, ADR-013 |
| M4-FR-007 | MUST compute the top-N flagged source IPs: anomalous-window count, max score, last `window_end`, union of rule ids. Ordered by count, then max score, both descending | P0 | US-2 | G6, F4 |
| M4-FR-008 | MUST read the latest N C-05 `pipeline_metrics` rows of a run (newest first), and the latest N `runs` rows | P0 | US-2, US-3 | C-05 |
| M4-FR-009 | MUST write C-04 and C-05 rows. Every row is validated with the `ids_contracts` validator first, and an invalid row is rejected with its errors | P1 | US-4 | C-04 §7, C-05 |
| M4-FR-010 | The synthetic generator MUST produce contract-valid C-04 windows (10 s slide, 30 s length) and C-05 metrics for a run, deterministic for a given seed and end time, with a configurable number of IPs and anomaly share | P0 | US-4 | Const. IV |
| M4-FR-011 | The synthetic generator MUST support a follow mode that keeps writing the next window every 10 s of wall time for a given duration | P1 | US-4 | Const. IV |
| M4-FR-012 | Every command MUST take its connection settings only from C-06 (`CASSANDRA_HOSTS`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE`, `RUN_ID`). It follows the C-06 exit codes and prints one JSON summary line last | P0 | all | C-06 |
| M4-FR-013 | Drift and top-IP computations MUST NOT read eval-only columns | P0 | US-2 | ADR-007, Const. VII |

## 6. Non-functional requirements
| ID | Category | Requirement | Trace |
|---|---|---|---|
| M4-NFR-001 | Performance | Reading the last 300 s at the full replay rate (≈ 2.5k IPs × 30 windows ≈ 75k rows) MUST take ≤ 3 s, the dashboard refresh period | G6 |
| M4-NFR-002 | Performance | Drift and top-N over 100k windows MUST take ≤ 0.5 s in-process | G6 |
| M4-NFR-003 | Reliability | When Cassandra is unreachable, the commands exit 1 with a clear message within 15 s. No traceback is the final output | C-06 |
| M4-NFR-004 | Testability | All logic except the driver calls MUST be unit-testable without Cassandra | Const. VIII |

## 7. Interfaces
### 7.1 Provided
| Contract | Version | What exactly is provided |
|---|---|---|
| C-04 | 1.0.0-rc.1 | Applied DDL, live check, read path. Synthetic rows serve as the M3-side mock |

### 7.2 Consumed
| Contract | Version | What is used | Mock until the real one is available |
|---|---|---|---|
| C-05 | 0.1.0-replica | `pipeline_metrics`, `runs` (read, and written by the generator) | This feature's synthetic generator |
| C-06 | 1.0.0-rc.7 | Cassandra settings, `RUN_ID`, exit codes, summary line | — |

## 8. Data
Inputs and outputs are C-04 and C-05 rows as defined there. The generator default is 50 IPs × 30 windows (300 s) per run, which takes seconds to write.
Volumes at the real rate are in M4-ADR-001.

## 9. Acceptance criteria
| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M4-F01-AC-01 | **Given** an empty Cassandra **When** `apply` runs twice **Then** both runs succeed and `check` reports no drift | FR-001, FR-002 | integration | ✅ `integration/test_store_live.py::test_ac01_apply_twice_then_check_clean` |
| M4-F01-AC-02 | **Given** live table metadata with a missing column, a changed type or another key **When** checked **Then** each difference is reported and the exit code is 1 | FR-002 | unit | ✅ `unit/test_schema.py::test_drift_is_reported_per_difference`, `unit/test_cli.py::test_schema_cli_check_reports_drift_exit_1` |
| M4-F01-AC-03 | **Given** `window_scores` with the 0.1.0 `hour` key **When** `apply` runs **Then** it exits 1 naming the migration. **When** `apply --recreate` runs **Then** the table has the 1.0 key | FR-003 | unit + integration | ✅ `unit/test_schema.py::test_apply_refuses_old_key_without_recreate`, `::test_apply_recreate_drops_only_mismatched_table`, `integration/…::test_ac03_old_key_refused_then_recreated` |
| M4-F01-AC-04 | **Given** windows across two buckets and two runs **When** reading [start, end] for one run **Then** exactly that run's windows in the span are returned, using one partition-key query per bucket and no `ALLOW FILTERING` | FR-004, FR-005 | unit + integration | ✅ `unit/test_store.py::test_read_windows_one_query_per_bucket_and_run_filter`, `integration/…::test_ac04_ac07_roundtrip` |
| M4-F01-AC-05 | **Given** 100 windows of which 16 are anomalous **When** summarised **Then** rate = 0.16 and alert = true. With 15 there is no alert. With 0 windows the rate is 0 and there is no alert | FR-006 | unit | ✅ `unit/test_view.py::test_drift_*` |
| M4-F01-AC-06 | **Given** windows from several IPs **When** top-N is computed **Then** the order, counts, max score, last seen and rule ids are correct, and labels are never read | FR-007, FR-013 | unit | ✅ `unit/test_view.py::test_top_flagged_order_and_fields`, `::test_eval_only_columns_are_never_read` |
| M4-F01-AC-07 | **Given** metrics and runs written **When** read **Then** the newest N are returned in order | FR-008 | unit + integration | ✅ `unit/test_store.py::test_metrics_and_runs_reads`, `integration/…::test_ac04_ac07_roundtrip` |
| M4-F01-AC-08 | **Given** a row that fails the contract validator **When** written **Then** it is rejected with the validator's errors and nothing is sent to Cassandra | FR-009 | unit | ✅ `unit/test_store.py::test_write_windows_validates_before_sending`, `::test_write_metrics_and_run_validate` |
| M4-F01-AC-09 | **Given** a seed and an end time **When** the generator runs twice **Then** the rows are identical, all valid against C-04/C-05, and the anomaly share is within ±5 points of the request | FR-010 | unit + contract | ✅ `unit/test_synthetic.py`, `contract/test_c04_c05_contract.py` |
| M4-F01-AC-10 | **Given** follow mode for 20 s **When** it runs **Then** new windows aligned to the 10 s slide are written | FR-011 | integration | ✅ `unit/test_synthetic.py::test_next_window_ends_for_follow_mode`, `integration/…::test_ac10_follow_mode_writes_new_windows` |
| M4-F01-AC-11 | **Given** C-06 env values **When** any command runs **Then** it connects with them, prints one JSON summary line last, exits 0 on success, 1 on a runtime error (Cassandra down) and 2 on bad usage | FR-012, NFR-003 | unit + integration | ✅ `unit/test_cli.py`, `integration/…::test_ac11_unreachable_cassandra_exits_1_quickly` |
| M4-F01-AC-12 | **Given** about 75k windows in the last 300 s **When** read **Then** it takes ≤ 3 s. Drift and top-N on 100k windows take ≤ 0.5 s | NFR-001, NFR-002 | perf (integration) | ✅ `integration/…::test_ac12_read_last_300s_at_full_rate`: **75,000 rows / 2 partitions in 1.48 s**, drift+top 0.012 s (2026-11-01). `unit/test_view.py::test_performance_100k_windows` |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| Span crosses midnight UTC | Buckets of both days are read (`partition_keys`) |
| start > end | Empty result, no query |
| Live row fails validation on read | Skipped and counted (`invalid`), never raised |
| Cassandra unavailable | Exit 1, message names host and port (NFR-003) |
| Keyspace missing at `check` | Drift is reported for every table, exit 1 |
| Generator re-run with the same seed and end | Same keys, so it upserts the same rows (idempotent) |

## 11. Assumptions and dependencies
- The Cassandra service from M1-F01 (`cassandra:4.1.10`, port 9042) runs locally for integration tests.
- C-05 stays at 0.1.0-replica until M3 publishes v1.0. A change there is absorbed through PR-14.

## 12. Open questions
None.

## 13. Review checklist
- [x] No implementation details in this spec (command names are the C-06 interface, not an implementation)
- [x] Every FR is testable and has at least one AC
- [x] Every NFR has a number and a unit
- [x] Interfaces reference contracts by ID and version
- [x] Eval-only fields are not used in any scoring or alerting requirement (FR-013)
- [x] No open `[NEEDS CLARIFICATION]`
- [ ] At least one consumer-module owner has reviewed (M3, together with C-04 PR-05)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Initial approved version |
| 1.0.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Verified (PR-11): every AC ✅ |
