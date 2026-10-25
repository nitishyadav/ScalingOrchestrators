# Spec: M3-F02 — Windowed Features (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Shared plan and tasks: [M3-F01 plan](../M3-F01-stream-ingest/plan.md).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · 0.1.0-replica · re-verified on C-02/C-03 0.2.0-replica 2026-10-25 |
| Trace | §2.1 (30 s windows, 10 s slide, four features per source IP), Week 5–6, C-02, D-08 |

| ID | Requirement |
|---|---|
| M3-FR-011 | `groupBy(window(event_time, "30 seconds", "10 seconds"), src_ip)`, update output mode (D-01) |
| M3-FR-012 | Features exactly per C-02: `sum(bytes_sent)`, `size(collect_set(dst_port))`, `sum(syn)/(sum(ack)+1)`, `count/30`, plus `event_count` and `max_event_ts`. Eval-only `label_attack`/`label_type` from bounded per-label counts (no unbounded lists in state) |
| M3-FR-013 | No model input reads `label` or `is_injected` (Art. VII) |

| AC | Criterion | Type | Status |
|---|---|---|---|
| M3-F02-AC-01 | **Golden parity:** the Spark job's own transforms on `events_golden.jsonl` (file stream, one batch) reproduce `features_golden.csv` exactly (23 rows) | integration (spark) | ✅ `test_spark_features_equal_golden` (23/23 rows, exact) |
