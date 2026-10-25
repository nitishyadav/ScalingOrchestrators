# ADR-011: Constant-rate replay with a matching offline time model

| Field | Value |
|---|---|
| Status | **Proposed** (M1 + M2 must both accept) |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-11 |
| Affects | C-01 §4.4, C-02, M1-F03, M2-F02, M2-F03, E3 |

## Context
With ADR-006, online windows contain events at the replay rate R. If M2 computed training windows from the original
2017 timing, rate-dependent features (`packet_rate`, `total_bytes`, `unique_ports` per window) would follow a different
distribution than at serving time. That is training/serving skew, and it would silently break F1 and F2.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Constant-rate replay at R. Offline simulates `ts_i = t0 + i·1000/R_ref` | Exact parity at R_ref. Simple producer rate control | Not the original traffic timing. Detection quality is only valid at R_ref |
| B. Replay preserving original inter-arrival times × speed-up | More realistic timing | Minute-resolution timestamps make the timing unknown inside a minute. Rate is hard to control for benchmarks |
| C. Rate-invariant features (normalise by window count) | Robust to rate | Changes the proposal's feature set. Weaker signal |

## Decision
Option A, with **R_ref = 5000 ev/s**. The producer emits in `row_idx` order (C-01 §4.4). M2 simulates the same timestamps when
building training windows. F1, F2, F3 and E3 are evaluated at R_ref. E1 and E2 vary throughput, and their detection numbers are not reported.

## Consequences
- The golden fixtures and parity tests guarantee identical windows offline and online.
- The report must state that detection quality is measured at the reference rate.
