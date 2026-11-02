# M4-ADR-001: Anomaly store partition key — 5-minute time buckets

| Field | Value |
|---|---|
| Status | **Accepted** (M4 owner, 2026-11-01). Applied in C-04 1.0.0-rc.1, which goes to M3 for review (PR-05) |
| Date | 2026-11-01 |
| Deciders | Vidhi Kant Gupta (M4, C-04 owner). Reviewed by Kumari Priyanka (M3, writer) through C-04 PR-05 |
| Resolves | D-02 (Cassandra key design, "M4 to finalise") |
| Affects | C-04 (DDL, `ids_contracts.store`), M3-F04 sink, M4-F01 init/read repository, M4-F02, M4-F03 |

## Context
- D-02 rejected the proposal's `date_bucket`-only key: one partition per day is a write hotspot, and having `detected_at` in the key
  duplicates rows under update mode. D-02 suggested `((date_bucket, hour, shard), window_end DESC, src_ip)` and left the final choice to M4.
- The C-04 0.1.0 replica uses `((date_bucket, hour), window_end DESC, src_ip)`.
- **Cardinality.** C-02 windows are sliding (30 s long, 10 s slide), so there are **360 `window_end` values per hour**. One row is
  stored per (`window_end`, `src_ip`).
  - M2-F03 (2026-10-25) counted 21,279 windows on the Friday test files (about 512k flows, about 102 s at R_ref = 5,000 ev/s, so about 12.5 `window_end`s).
    That is **≈ 1.7k distinct `src_ip` per `window_end`**. Monday gives ≈ 2.9k.
  - Cross-check against the replica E1 run `E1-p8-e2-r5000-a0-202610251327`: 748,098 upserts in 600 s (60 `window_end`s). With ≈ 2.3k IPs per `window_end`,
    that is ≈ 140k distinct rows, each upserted about 5 times in update mode. This is consistent.
- **Partition size with the replica key** at 5,000 ev/s: 360 × 1.7–3k ≈ **0.6–1.1M rows per hour partition**, about 100–300 MB at an estimated 150–300 B per row.
  The usual Cassandra guidance is ≤ 100k rows and ≤ 100 MB per partition. Larger partitions slow compaction, repair and reads that slice them.
- Readers (C-04 §4): the dashboard and drift rule read the last 300 s every 3 s. E1–E3 analysis reads one run's 10-minute span.
- Deployment: one Cassandra 4.1.10 node, RF 1, 7-day TTL. Spreading writes across nodes is not a concern. Partition size and read fan-out are.
- The writer (Spark, M3) and the readers (Python, M4) must derive the key identically.

## Options
| Option | Key | Rows per partition (5,000 ev/s) | Reads for the last 300 s | Pros | Cons |
|---|---|---|---|---|---|
| A. Keep the replica key | `((date_bucket, hour), …)` | 0.6–1.1M | 1–2 | No M3 change | Over the size guidance by about 10× |
| B. Hour + hash shard (D-02) | `((date_bucket, hour, shard), …)`, `shard = crc32(src_ip) % 16` | 40–70k | 16–32 | Smaller partitions | 16× read fan-out. Spark `crc32` and Python `zlib.crc32` must match. Shard count is fixed in the key |
| **C. 5-minute time bucket** | `((date_bucket, bucket), …)`, `bucket = (60·hour + minute) // 5` | **50–90k** | **≤ 2** | Within the guidance. Minimal fan-out. Pure time arithmetic, the same in Spark and Python | All current writes go to one partition (harmless with one node). M3 changes one expression |

## Decision
We adopt **option C**:

```
PRIMARY KEY ((date_bucket, bucket), window_end, src_ip)
  WITH CLUSTERING ORDER BY (window_end DESC, src_ip ASC)
date_bucket = 'YYYY-MM-DD' of window_end, UTC
bucket      = (60 · hour + minute) // 5 of window_end, UTC   -- int, 0..287
```

- `BUCKET_S = 300`. A `window_end` exactly on a boundary (for example 12:05:00) belongs to the bucket that starts there.
- `window_end` is always a multiple of 10 s, and 300 is a multiple of 10, so every bucket holds exactly 30 `window_end` values.
- Readers enumerate partitions with `ids_contracts.store.partition_keys(start_ms, end_ms)`. Writers use `partition_key(window_end_ms)`
  or its Spark equivalent: `date_format(window_end, 'yyyy-MM-dd')` and `floor((hour(window_end)*60 + minute(window_end)) / 5)`,
  with `spark.sql.session.timeZone = UTC`.
- The rest of the key, upsert semantics, TTL, consistency and columns stay as in 0.1.0, apart from `hour` being replaced by `bucket`.

## Consequences
- Positive: partitions are about 12–25 MB at the full replay rate. The drift read touches at most 2 partitions, and a 10-minute run touches at most 3.
  The key is easy to check in `validate_row`.
- Negative / trade-offs:
  - **Breaking for 0.1.0 writers.** The column `hour` becomes `bucket`. The M3 sink (`app.py`, `to_store`) and the M3 e2e test query must change.
    The live table must be dropped once (`DROP TABLE IF EXISTS ids.window_scores`) because `CREATE TABLE IF NOT EXISTS` keeps an old key.
  - 288 partitions per day instead of 24 (negligible).
- Follow-ups:
  - [x] C-04 1.0.0-rc.1: DDL, `ids_contracts.store` (`BUCKET_S`, `partition_key`, `partition_keys`), contract tests.
  - [ ] Send to M3 (Priyanka) for PR-05 review. M3 updates its sink after approval.
  - [ ] M4-F01: the init step detects the 0.1.0 key in `system_schema.columns` and recreates the table (an explicit flag, never silent).
  - [ ] M4-F01 live check: measure real partition sizes (`nodetool tablehistograms ids window_scores`) during an E1-rate run and record them here.
    If the 95th percentile is > 100 MB, revisit `BUCKET_S` through a CR.
