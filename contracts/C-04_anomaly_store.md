# Contract C-04: Anomaly Store

> **PROVISIONAL REPLICA.** Authored by Aswin S. (M1) in replica mode from the playbook §5.5 (D-02). The canonical owner, **Vidhi Kant Gupta (M4)**,
> authors and approves v1.0, and this file is then replaced.

| Field | Value |
|---|---|
| Contract ID | C-04 |
| Version | 0.1.0-replica |
| Status | **Provisional (replica)** |
| Provider (owner) | M4: Vidhi Kant Gupta (this draft by M1) |
| Consumers | M3 (writer), M4 (reader: dashboard, benchmarks) |
| Medium | Cassandra table `ids.window_scores` |
| DDL | `schemas/ids_schema.cql` (idempotent. Applied live on 2026-10-22, see SYNC_LOG) |
| Code | `ids_contracts.store` (`COLUMNS`, `partition_key`, `validate_row`, `drift_alert`) |
| Decisions applied | D-02 (key design), D-01 (latency inputs), ADR-007 (eval-only columns) |

## 1. Purpose
This contract defines the one table where scored windows land. M3 writes it. M4 reads it for the dashboard (G6) and the experiments (E1–E3).

## 2. Key design (D-02)
`PRIMARY KEY ((date_bucket, hour), window_end, src_ip)`, clustering `window_end DESC, src_ip ASC`.
- **Partition** = one UTC hour of one day (`partition_key(window_end)`). This bounds the partition size and spreads writes over time, rather than
  piling a whole day into one partition as the proposal's `date_bucket`-only key would.
- **One row per (window, src_ip).** Update-mode re-emissions **upsert** the same row, so there are no duplicates.

## 3. Columns
See `ids_schema.cql` (21 columns). Notes:
| Column | Meaning |
|---|---|
| `window_start`, `window_end`, `src_ip`, the 4 features, `event_count`, `max_event_ts` | From C-02 |
| `anomaly_score`, `ml_flag`, `rule_flag`, `rule_ids`, `is_anomaly` | From C-03 §5 (`rule_ids` is `''` when no rule fired) |
| `detected_at` | Set by the sink at write time (UTC). Latency = `detected_at − max_event_ts` (C-05) |
| `bundle_version`, `run_id` | Provenance (C-03, C-06) |
| `label_attack`, `label_type` | **Eval-only** (C-02). Never used for any decision |

Table options: `default_time_to_live = 604800` (7 days). Write consistency `LOCAL_ONE`. Single node, `SimpleStrategy` RF 1.

## 4. Read patterns (M4)
| Need | Query shape |
|---|---|
| Recent windows (dashboard, drift) | For each (date_bucket, hour) covering the last 300 s: `WHERE date_bucket=? AND hour=? AND window_end >= ?` |
| Top flagged IPs | The same partitions, filtered client-side on `is_anomaly` |
| Run analysis (E1–E3) | The same, restricted to the run's time span and filtered on `run_id` |

**Drift rule (G6, F5):** over rows with `window_end` in the last **300 s**, `anomaly_rate = count(is_anomaly) / count(*)`. Show the banner if it is **> 0.15**
(`drift_alert`).

## 5. Validation
`validate_row(row)` (timestamps as epoch ms) checks types, the key derivation (`date_bucket`/`hour` from `window_end` UTC), the 30 s window,
`is_anomaly = ml_flag OR rule_flag`, and the `rule_flag`/`rule_ids` consistency. A contract test checks that `COLUMNS` equals the DDL.

## 6. Approvals
| Role | Member | Version | Date |
|---|---|---|---|
| Provider | Vidhi Kant Gupta (M4) | — | |
| Consumer | Kumari Priyanka (M3) | — | |
| Replica author | Aswin S. (M1) | 0.1.0-replica | 2026-10-22 |

## 7. Change log
| Version | Date | Change |
|---|---|---|
| 0.1.0-replica | 2026-10-22 | Provisional replica from the playbook §5.5. DDL applied to the live Cassandra 4.1.10 |
