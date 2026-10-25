# ADR-006: Event `timestamp` is producer emission time

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-06 |
| Affects | C-01, C-02, C-05, M1-F03, M3, M4-F03 |

## Context
The CIC flows carry 2017 timestamps at minute resolution. Spark windows and watermarks run on event time, and the
latency metric is `detected_at − event time` (proposal §3.1). Replaying 2017 times would make every event "late" relative to
a 2026 wall clock, and would make latency meaningless.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. `timestamp` = emission time (epoch ms). Keep the original as `orig_ts` | Watermarks work, latency is measurable end to end | Original inter-arrival timing is not reproduced (handled in ADR-011) |
| B. Original 2017 time shifted to now | Preserves original timing | Minute resolution creates bursts. Rate control conflicts with timing. Harder to benchmark at a fixed rate |
| C. Use the Kafka record timestamp only | No field needed | Ties event time to the broker. Not visible in the JSON for offline use |

## Decision
Option A. The producer stamps `timestamp` (epoch ms UTC) immediately before send. `orig_ts` is kept as text for traceability only.

## Consequences
- Latency (C-05) starts at a well-defined point. Windows contain events at the replay rate.
- Offline features must simulate emission timing. See ADR-011.
