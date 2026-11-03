# M2-ADR-001: Choose the ML threshold by validation recall, not validation F1

| Field | Value |
|---|---|
| Status | **Proposed** (M2 owner) |
| Date | 2026-11-03 |
| Affects | M2-F03 (FR-022), bundle 1.2.0-replica. No contract change (the threshold lives in the C-03 manifest) |

## Context
Bundle 1.1.0 chose percentile 99.9 (threshold 0.7688) by maximising validation hybrid F1. The validation set has 119,536 windows and 37 attacks, so
F1 rises with every stricter percentile (0.007 at p90 to 0.039 at p99.9) and the selection collapsed to the strictest candidate. The D15 diagnosis
(`docs/measurements/D15-ml-diagnosis-2026-11-03.md`) shows the model ranks attacks well (AUC 0.991 on test, 0.995 to 1.000 on every validation category) but
their scores plateau at about the 99.6th benign percentile, just under p99.9. ML-only test recall was 0.000.

## Decision
Among candidates with benign hold-out hybrid FPR < 5 %, pick the highest **validation** hybrid recall; ties go to the lowest hold-out FPR. Validation F1 is still reported.
The test split plays no part in the choice.

## Result (real data, seed 42)
Percentile 99 (threshold 0.6531), bundle 1.2.0-replica. ML-only test recall 0.000 to 1.000. Hybrid test recall 0.941 to 1.000. Hold-out FPR (F2) 1.00 % to 1.31 %.

## Consequences
- Cost: hybrid test window precision falls 0.112 to 0.023 and test FPR 0.60 % to 3.35 %. F1 precision stays FAIL (structural, D-14). The report must show both sides of this trade.
- The ML half now contributes to F3 (per-category recall), so the rule-vs-hybrid comparison is meaningful.
- Alternative kept in reserve: percentile 99.5 (validation recall 0.973, hold-out FPR 1.28 %) if a lower false-positive rate is preferred.
