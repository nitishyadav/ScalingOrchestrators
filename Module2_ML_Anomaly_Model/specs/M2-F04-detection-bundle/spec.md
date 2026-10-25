# Spec: M2-F04 — Detection Bundle (dummy) + Golden Scores (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8). Real training is M2-F03 (later).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · Version 0.1.0-replica · re-verified on C-02/C-03 0.2.0-replica 2026-10-25 |
| Trace | §1.2 (offline-trained Isolation Forest, serialised, broadcast), Week 4 (`joblib`), G3, G4, D-09, risk R3 |
| Contracts | C-03 0.1.x-replica (provides: the bundle and `scores_golden.csv`), C-02 (feature order), `versions.md` |

## Requirements
| ID | Requirement |
|---|---|
| M2-FR-011 | `make-dummy` MUST build a C-03 bundle: a Pipeline(StandardScaler, IsolationForest(n_estimators=100, random_state=42)) fitted on seeded synthetic C-02-shaped features. `threshold` = the 99th percentile of training `anomaly_score`. `manifest.json` and `rules.yaml` (C-03 §4 placeholders) are valid. `bundle_version "0.0.0-dummy"`. Written to `mocks/dummy_bundle/`, and with `--install` also copied to `MODEL_BUNDLE_PATH` |
| M2-FR-012 | `Bundle.load(path)` MUST validate the manifest and rules (C-03) and refuse a bundle whose `sklearn_version`/`numpy_version` differ from the running ones (ADR-009) |
| M2-FR-013 | `Bundle.score(features)` MUST return `anomaly_score`, `ml_flag`, `rule_flag`, `rule_ids`, `is_anomaly` per C-03 §5, vectorised, and equal to the `ids_contracts.bundle` reference semantics row by row |
| M2-FR-014 | `golden-scores` MUST write `contracts/fixtures/scores_golden.csv` = `features_golden.csv` scored by the dummy bundle (the M3 parity target) |

## Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M2-F04-AC-01 | The dummy bundle's manifest and rules pass the C-03 validators. The feature order equals C-02. The recorded versions equal `versions.md` | contract | ✅ `test_committed_dummy_bundle_is_valid_c03` |
| M2-F04-AC-02 | Rebuilding the dummy with the same seed gives identical scores on the golden features | unit | ✅ `test_same_seed_same_scores` |
| M2-F04-AC-03 | Vectorised `score()` equals the per-row reference (`rule_hits` + `decide`) on the golden rows and on 1,000 random rows | unit | ✅ `test_vectorised_score_equals_reference` (23 golden + 1,000 random rows) |
| M2-F04-AC-04 | `scores_golden.csv` regenerates within 1e-9 and has 23 rows keyed like `features_golden.csv` | contract | ✅ `test_scores_golden_regenerates_and_matches_features` |
| M2-F04-AC-05 | **Cross-environment (R3):** inside the platform's `spark-client` (Python 3.10, the same pins) the committed bundle loads and reproduces `scores_golden.csv` within 1e-9 | integration | ✅ `test_bundle_scores_identically_inside_spark_client` (Python 3.10 in the image, within 1e-9) |
| M2-F04-AC-06 | A version mismatch or an invalid manifest → `BundleError` | unit | ✅ `test_version_mismatch_refused`, `test_invalid_manifest_or_missing_file_refused` |
