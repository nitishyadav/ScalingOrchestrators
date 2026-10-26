# Spec: M2-F02 — Reference Feature Builder (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · Version 0.1.0-replica · re-verified on C-02/C-03 0.2.0-replica 2026-10-25 |
| Trace | §2.3 (four features per source IP per window), Week 4 ("carefully align the training feature columns to match what Spark will compute"), F1, D-08, D-11 |
| Contracts | C-02 0.1.x-replica (implements), C-01 (consumes: events, replay dataset) |

## Requirements
| ID | Requirement |
|---|---|
| M2-FR-001 | `build_features(events_df)` MUST implement C-02 exactly: 30 s/10 s epoch-aligned sliding windows per `src_ip`, the 4 features, `event_count`, `max_event_ts`, eval-only `label_attack`/`label_type`, columns in `GOLDEN_COLUMNS` order, sorted by (`window_start`, `src_ip`) |
| M2-FR-002 | Features MUST read only C-01 `SCORING_FIELDS`. Labels feed only the eval-only columns |
| M2-FR-003 | `replay_timestamps(n, t0_ms, rate)` MUST give the ADR-011 offline timing `t0 + floor(i·1000/R)` (integer ms), so training windows match replay at R_ref = 5,000 ev/s |
| M2-FR-004 | `features_from_replay(df, rate, t0_ms)` MUST stamp replay rows in their given (`row_idx`) order, then build features. It is vectorised (pandas), so a full replay day is feasible |

## Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M2-F02-AC-01 | On `events_golden.jsonl`, the output equals `features_golden.csv` (23 rows, `rows_equal`) | contract | ✅ `test_golden_feature_parity` (23/23 rows) |
| M2-F02-AC-02 | Changing every `label` leaves the 4 features unchanged. An empty input gives an empty frame with the golden columns | unit | ✅ `test_labels_never_change_features`, `test_empty_input`, `test_without_labels_eval_columns_default_benign` |
| M2-F02-AC-03 | `replay_timestamps` at R = 5,000: 5 events per ms, monotone, starting at t0. On the committed M1 replay sample, `features_from_replay` passes `validate_feature_row` for every row | unit | ✅ `test_replay_timestamps`, `test_features_from_replay_sample_are_valid` |
