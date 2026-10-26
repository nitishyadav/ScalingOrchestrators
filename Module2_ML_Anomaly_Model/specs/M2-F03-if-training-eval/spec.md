# Spec: M2-F03 — Isolation Forest Training and Evaluation (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Status | **Implemented (replica)** 2026-10-22: AC-01..05 ✅. Targets: F1 recall ✅, F2 ✅, **F1 precision ❌ (structural, D-14)** |
| Trace | §1.2 (Isolation Forest trained offline on CIC-IDS2017), Week 4, G3, **F1** (precision ≥ 0.80, recall ≥ 0.75 on Fri DDoS + PortScan), **F2** (benign-only FPR < 5 %), **F3** (rule vs hybrid per category), D-04, D-11, ADR-011 |
| Contracts | C-01 (replay dataset), C-02 (features via M2-F02), C-03 (bundle provided) |

## Data protocol (no leakage)
| Split | Rows | Use |
|---|---|---|
| Train | Monday, `row_idx` < 80 % (benign only) | Fit the model |
| Benign hold-out | Monday, last 20 % | F2 FPR ("clean benign-only run") and the threshold constraint |
| Validation | Tuesday, Wednesday, Thursday (full days) | Threshold selection only |
| **Test** | `Friday-WorkingHours-Afternoon-DDos`, `Friday-WorkingHours-Afternoon-PortScan` (each replayed alone) | **Reported** F1 and F3 numbers. Never used for any choice |

Every split is replayed at R_ref = 5,000 ev/s (`features_from_replay`), so offline windows equal online windows (ADR-011).
A window is positive iff `label_attack` (C-02 eval-only, ADR-007).

## Requirements
| ID | Requirement |
|---|---|
| M2-FR-021 | Model = Pipeline(`log1p` → StandardScaler → IsolationForest(n_estimators=200, random_state=42)) on the C-02 `FEATURE_ORDER` features. Input stays raw C-02 features (C-03 unchanged) |
| M2-FR-022 | Threshold candidates = percentiles {90, 95, 97, 98, 99, 99.5, 99.9} of the train anomaly scores. Choose the one maximising **validation** hybrid F1 subject to benign hold-out hybrid FPR < 5 %. If none qualifies, use the lowest-FPR candidate and flag `fpr_constraint_met: false` |
| M2-FR-023 | Report on test: precision, recall, F1 and FPR for **ml-only, rule-only, hybrid**; recall per attack category (`label_type`); confusion counts; F2 FPR on the benign hold-out; window counts per split |
| M2-FR-024 | Write a C-03 bundle `runtime/bundle/1.0.0-replica/` (manifest `metrics` = hybrid test precision/recall + hold-out FPR, `test_files`), optionally installed to `MODEL_BUNDLE_PATH`, plus a report `docs/measurements/F03-training-<date>.{json,md}`. Deterministic for a given seed |
| M2-FR-025 | Targets are **reported, not forced**: the report states PASS/FAIL per F1/F2 |

## Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M2-F03-AC-01 | Metric maths (precision, recall, FPR, F1, per category) are exact on hand-built cases, including zero-division | unit | ✅ `test_binary_metrics`, `test_binary_metrics_zero_division`, `test_per_category_recall` |
| M2-F03-AC-02 | Threshold selection uses only train + validation + hold-out. Changing test labels changes no choice | unit | ✅ `test_threshold_selection_respects_fpr_constraint`, `test_no_qualifying_threshold_is_flagged`, `test_test_labels_never_influence_choices` |
| M2-F03-AC-03 | Same seed → identical threshold and scores. The bundle passes C-03 and loads with `Bundle.load` | unit | ✅ `test_deterministic_and_bundle_valid`, `test_report_markdown_has_pass_fail` |
| M2-F03-AC-04 | Real data: training runs end to end, the report is written with all metrics, the bundle is valid, and the chosen threshold satisfies the hold-out FPR constraint (or is flagged) | data | ✅ `test_training_on_real_data`. Report `docs/measurements/F03-training-2026-10-22.md` (F1 recall 0.941 PASS, F2 FPR 1.21 % PASS, **F1 precision 0.058 FAIL → D-14**) |
| M2-F03-AC-05 | Live: with the trained bundle installed, the stream job runs and the dashboard shows the run (and fewer benign false positives than the dummy) | integration | ✅ `DEV-live-trained` runs with `1.0.0-replica`, shown on the dashboard. Benign windows flagged 1.00 % vs dummy 1.27 % (preliminary, 0.7 min vs 12.3 min) |
