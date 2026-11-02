# M4-ADR-002: Benchmark throughput and latency method

| Field | Value |
|---|---|
| Status | **Accepted** (2026-11-01) |
| Owner | Vidhi Kant Gupta (M4) |
| Feature | M4-F03 |
| Related | D-01, D-05, D-13, C-05 §3 ("the aggregation is defined by M4-F03"), replica results 2026-10-25 |

## Context
P1, P3 and P4 need a throughput figure; P2 needs one latency figure per run. The replica harness used, at a fixed 5,000 ev/s,
the median of Spark's per-batch `processed_rows_per_sec` as "capacity". Its E1 run then showed partitions 1 → 16 getting *slower*
(7,013 → 5,085 rows/s, efficiency 0.22 at 4). With a 1 s trigger and a fixed input rate, every batch is small, and that figure is
mostly `rows / per-batch overhead`. More partitions mean more tasks per batch and more overhead, so the metric falls even if the system could
process more. It does not answer "how much can it sustain". The replica's E1 also used 2 executors (2 task slots), which caps the speedup
at 2×, so 4 partitions could not reach efficiency 0.5 even in theory.

## Options (throughput, P1/P3/P4)
| | Option | For | Against |
|---|---|---|---|
| A | Spark per-batch `processed_rows_per_sec` at a fixed rate (replica) | No producer requirement | Measures overhead, not capacity (above) |
| B | **Saturating rate + sustained throughput** Σ `input_rows` / steady span | Measures what was actually processed per second; contract-clean (C-06 flags only) | Needs the producer to outrun Spark; when it does not, the figure is a lower bound |
| C | Pre-load a backlog, then drain it from `earliest` | Independent of producer speed | Needs `--starting-offsets` (not in C-06 → CR); one huge first batch unless `maxOffsetsPerTrigger` is added (another CR); memory risk at 768 MB executors |

## Decision
**B.** E1/E2 replay at 15,000 ev/s (above the replica's single-node capacity) and report sustained throughput. Each run records the producer's
achieved rate. A run whose sustained throughput is ≥ 95 % of it is flagged `producer_bound`, because it kept up and its throughput is only a lower bound.
Efficiency over two levels is then:
- exact when neither level is producer-bound;
- a **lower bound (≥)** when only the higher level is;
- **inconclusive** when the baseline level is.

E1 uses 4 executors, so that up to 4 partitions are never capped by task slots.
P1 runs at 12,000 ev/s and passes when sustained ≥ 10,000 ev/s. Spark's `processed_rows_per_sec` is still reported, as a secondary column.

**Latency (P2):** the P2 figure of a run is the **median of per-batch p95** (`latency_p95_ms`, D-01), over steady-state batches that wrote rows.
This matches the dashboard headline. The tail figure is the 95th percentile of the per-batch p95s, reported next to it. A run-level p95 over all rows would be
better, but C-05 publishes only per-batch percentiles. Recomputing from C-04 would see only each window's last update (upserts), so the result would be biased.

## Consequences
- The report can state honestly whether a scaling result is exact, a lower bound or inconclusive.
- If the producer cannot reach 15,000 ev/s on the demo machine, E1/E2 will be lower bounds. Option C then becomes a CR to C-06 (M3 job flags).
- Throughput at saturation comes with high latency by design. Latency targets are judged only on the fixed-rate runs (LAT, E3, REC).
