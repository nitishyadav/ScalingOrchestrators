# Contract C-04: Anomaly Store

| Field | Value |
|---|---|
| Contract ID | C-04 |
| Version | 1.0.0-rc.1 |
| Status | **In Review** (sent to M3 for PR-05) |
| Provider (owner) | M4: Vidhi Kant Gupta (owns the schema and the read side) |
| Consumers | M3 (writer: the stream sink), M4 (reader: dashboard, benchmarks) |
| Medium | Cassandra table `ids.window_scores` |
| Machine-readable schema | `contracts/schemas/ids_schema.cql` (idempotent DDL) |
| Code | `ids_contracts.store` (`COLUMNS`, `partition_key`, `partition_keys`, `validate_row`, `drift_alert`) |
| Golden fixtures | none (rows are produced live). `contracts/python/tests/test_store.py` holds the canonical example row |
| Decisions applied | D-02 / **M4-ADR-001** (key design), D-01 (latency inputs), ADR-007 (eval-only columns), ADR-012 (base features stored), ADR-013 (drift metric) |

## 1. Purpose
This contract defines the one table where scored windows land. M3 writes one row per (window, `src_ip`). M4 reads it for the live dashboard (G6, F4, F5)
and for the experiments (E1–E3, P2 latency, F2/F3).

## 2. Transport and location
| Item | Value |
|---|---|
| Cassandra | `cassandra:4.1.10`, host and port from C-06 (`CASSANDRA_HOST`, `CASSANDRA_PORT`) |
| Keyspace | `ids`, `SimpleStrategy`, replication factor 1 (single node) |
| Table | `ids.window_scores` |
| Write consistency | `LOCAL_ONE` |
| Read consistency | `LOCAL_ONE` |
| TTL | `default_time_to_live = 604800` (7 days). Writers do not set a per-row TTL |
| Who applies the DDL | M4-F01 init step (idempotent). M3 must not create or alter the table |

## 3. Schema
Timestamps are CQL `timestamp` (UTC, millisecond precision). In `ids_contracts.store` they are represented as epoch ms (`int`).

| Column | CQL type | Required | Unit / format | Constraints | Description | Example |
|---|---|---|---|---|---|---|
| `date_bucket` | text | yes, **partition key** | `YYYY-MM-DD` | UTC date of `window_end` | Day part of the partition | `2026-01-01` |
| `bucket` | int | yes, **partition key** | 5-minute index | `(60·hour + minute) // 5` of `window_end` UTC, 0..287 | Bucket part of the partition (M4-ADR-001) | `145` (12:05–12:09:59) |
| `window_end` | timestamp | yes, **clustering DESC** | ms | multiple of 10 s; `= window_start + 30 s` | C-02 window end (exclusive) | `2026-01-01T12:05:30Z` |
| `src_ip` | text | yes, **clustering ASC** | dotted IPv4/IPv6 | non-empty | C-02 group key | `172.16.0.1` |
| `window_start` | timestamp | yes | ms | multiple of 10 s (C-02 slide) | C-02 window start (inclusive) | `2026-01-01T12:05:00Z` |
| `total_bytes` | bigint | yes | bytes | ≥ 0 | C-02 base feature | `48213` |
| `unique_ports` | int | yes | count | ≥ 1 | C-02 base feature | `3` |
| `syn_ack_ratio` | double | yes | ratio | ≥ 0 | C-02 base feature | `0.5` |
| `packet_rate` | double | yes | flows / s | `event_count / 30` | C-02 base feature | `0.1` |
| `event_count` | int | yes | count | ≥ 1 | Events in the window | `3` |
| `anomaly_score` | double | yes | C-03 score | higher = more anomalous | Model score (C-03 §5) | `0.41` |
| `ml_flag` | boolean | yes | | `anomaly_score ≥ threshold` | Model verdict | `false` |
| `rule_flag` | boolean | yes | | `= (rule_ids != '')` | Any rule fired | `true` |
| `rule_ids` | text | yes | comma-separated rule ids | `''` when no rule fired | Rules that fired (C-03) | `R-SYN-FLOOD` |
| `is_anomaly` | boolean | yes | | `= ml_flag OR rule_flag` | Hybrid verdict | `true` |
| `max_event_ts` | timestamp | yes | ms | in `[window_start, window_end)` except late events (C-02) | Latest event time in the window (D-01) | `2026-01-01T12:05:29Z` |
| `detected_at` | timestamp | yes | ms | set by the sink at write time, UTC | Processing time of this upsert | `2026-01-01T12:05:29.600Z` |
| `bundle_version` | text | yes | semver | C-03 manifest | Provenance | `1.1.0-replica` |
| `run_id` | text | yes | C-06 `RUN_ID_PATTERN` | | Provenance, used to filter runs | `E1-p8-e2-r5000-a0-202610251327` |
| `label_attack` | boolean | no (**eval-only**) | | C-02 window label | Ground truth | `false` |
| `label_type` | text | no (**eval-only**) | | C-02 window label type | Ground truth | `BENIGN` |

C-02 0.2.0 ratio columns (`bytes_per_flow`, `port_ratio`, `syn_share`) are **not** stored (ADR-012). They can be recomputed from the base columns.

## 4. Semantics
- **Keys and partitioning (M4-ADR-001):** `PRIMARY KEY ((date_bucket, bucket), window_end, src_ip)` with `CLUSTERING ORDER BY (window_end DESC, src_ip ASC)`.
  One partition is one 5-minute UTC bucket of `window_end`: 30 `window_end` values, estimated at 50–90k rows (12–25 MB) at 5,000 ev/s.
  A `window_end` exactly on a boundary (for example 12:05:00) belongs to the bucket that starts there.
  Writers derive the key with `partition_key(window_end_ms)`, or in Spark with `date_format(window_end,'yyyy-MM-dd')` and
  `floor((hour(window_end)*60 + minute(window_end))/5)`, with `spark.sql.session.timeZone=UTC`.
- **Ordering guarantees:** within a partition, newest `window_end` first, then `src_ip` ascending. There is no order across partitions. Readers enumerate partitions
  with `partition_keys(start_ms, end_ms)` (newest first).
- **Time semantics:** `window_*` and `max_event_ts` are event time (C-01 `timestamp` = emission time, D-06). `detected_at` is processing time.
  **Latency** = `detected_at − max_event_ts` (D-01). It is computed per batch by M3 (C-05). M4 can recompute it from this table.
- **Idempotency / duplicates:** writes are **upserts**. Update mode (C-02) re-emits a window whenever it changes, and the latest write wins.
  There is never more than one row per (window, `src_ip`). `detected_at` is the time of the last upsert.
- **Null / missing / default handling:** every column except the eval-only pair is required and non-null. `rule_ids` is `''` (never null) when no rule fired.
- **Eval-only fields:** `label_attack`, `label_type` (ADR-007). They are never read by scoring, alerting or the drift rule. They are used only for offline evaluation (F2, F3, E3).

## 5. Read patterns (M4)
| Need | Query shape |
|---|---|
| Recent windows (dashboard, drift) | For each `(d, b)` in `partition_keys(now − 300 s, now)` (≤ 2 partitions): `SELECT … FROM ids.window_scores WHERE date_bucket=? AND bucket=? AND window_end >= ?` |
| Top flagged IPs | The same partitions, filtered client-side on `is_anomaly` |
| Run analysis (E1–E3) | `partition_keys(run_start, run_end)` (≤ 3 for a 10-minute run), restricted to the run span, filtered client-side on `run_id` |

No secondary indexes or `ALLOW FILTERING`.

**Drift rule (G6, F5, ADR-013):** over rows with `window_end` in the last **300 s** (`DRIFT_WINDOW_S`), `anomaly_rate = count(is_anomaly) / count(*)`.
The banner shows when it is **> 0.15** (`DRIFT_THRESHOLD`, `drift_alert`). With no rows, there is no alert.

## 6. Example row
```json
{"date_bucket": "2026-01-01", "bucket": 0, "window_end": 1767225630000, "src_ip": "10.0.0.1", "window_start": 1767225600000,
 "total_bytes": 10, "unique_ports": 1, "syn_ack_ratio": 0.5, "packet_rate": 0.1, "event_count": 3,
 "anomaly_score": 0.4, "ml_flag": false, "rule_flag": true, "rule_ids": "R-SYN-FLOOD", "is_anomaly": true,
 "max_event_ts": 1767225629000, "detected_at": 1767225629400, "bundle_version": "0.0.0-dummy",
 "run_id": "DEV-local", "label_attack": false, "label_type": "BENIGN"}
```

## 7. Validation
`ids_contracts.store.validate_row(row)` (timestamps as epoch ms) returns a list of errors (empty = valid). It checks:
all columns present; types; non-null for non-eval columns; `(date_bucket, bucket) == partition_key(window_end)`; `window_end − window_start = 30 s`;
`window_start` on the 10 s slide; `is_anomaly = ml_flag OR rule_flag`; `rule_flag = (rule_ids != '')`.

## 8. Obligations
**Provider (M4) MUST**
- Apply `ids_schema.cql` before any writer starts (M4-F01 init). Keep `ids_contracts.store` equal to the DDL (contract test).
- Read only by partition key (no `ALLOW FILTERING`). Never use eval-only columns for alerting.

**Writer (M3) MUST**
- Write only rows that pass `validate_row`. Derive the key exactly as in §4, in UTC.
- Upsert one row per (window, `src_ip`) at `LOCAL_ONE`. Set `detected_at` at write time. Never create, alter or truncate the table.

**All consumers MUST** ignore unknown columns (MINOR versions may add nullable columns).

## 9. Error handling
- **Writer:** a row that fails validation is a bug in the writer. In tests, fail fast. Online, M3 counts it as malformed (C-05) and does not write it.
- **Write failure (Cassandra down):** the M3 micro-batch fails and is retried from the checkpoint (M3-F04 recovery). Upserts make the retry safe.
- **Reader:** a row that fails validation is skipped and counted on the dashboard. Empty partitions are normal.
- **Schema drift:** if the live table still has the 0.1.0 key (`hour`), M4-F01 init stops with an error naming the one-time migration (§11).
  It drops the table only with an explicit `--recreate` flag.

## 10. Contract tests
| Side | Test | Location |
|---|---|---|
| Shared | DDL ↔ `COLUMNS`/key; key derivation at bucket and day boundaries; `partition_keys` coverage; row validation; drift rule | `contracts/python/tests/test_store.py` |
| Writer (M3) | Sink output rows pass `validate_row`; Spark key expression equals `partition_key` | `Module3_…/tests/contract/` |
| Reader (M4) | Repository reads synthetic rows written with this key; the dashboard computes drift with `drift_alert` | `Module4_…/tests/contract/` |

## 11. Compatibility and versioning
- MINOR: adding nullable columns is allowed, and readers must tolerate them.
- MAJOR: any change to the key, column names, types or meaning requires a CR (PR-13) approved by M3 and M4.
- **Migration from 0.1.0-replica (breaking):** the column `hour` became `bucket`. `CREATE TABLE IF NOT EXISTS` never changes an existing table, so drop it
  once with `DROP TABLE IF EXISTS ids.window_scores;` and apply `ids_schema.cql` again. The data is dev-only, with a 7-day TTL. The M3 sink changes one expression (`hour` → `bucket`).

## 12. Approvals
| Role | Member | Version approved | Date |
|---|---|---|---|
| Provider | Vidhi Kant Gupta (M4) | 1.0.0-rc.1 | 2026-11-01 |
| Consumer (writer) | Kumari Priyanka (M3) | — | |
| Replica author (0.1.0) | Aswin S. (M1) | 0.1.0-replica | 2026-10-22 |

## 13. Change log
| Version | Date | CR | Change |
|---|---|---|---|
| 0.1.0-replica | 2026-10-22 | — | Provisional replica from the playbook §5.5 by M1. DDL applied to the live Cassandra 4.1.10 |
| 1.0.0-rc.1 | 2026-11-01 | — (pre-approval) | Owner version. **Key `(date_bucket, hour)` → `(date_bucket, bucket)`, 5-minute buckets (M4-ADR-001)**. `partition_keys` helper. Non-eval columns required. Slide-alignment check. Full field table, obligations, error handling, migration |
