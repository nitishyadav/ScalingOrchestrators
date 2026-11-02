# Tasks: M2-F03 — IF Training and Evaluation (REPLICA)

- [x] **M2-T070** Spec with the no-leakage data protocol · Done: 2026-10-22
- [x] **M2-T071** Tests first: `tests/unit/test_train.py` (metrics, selection, leakage guard, determinism, report) · Done: 2026-10-22
- [x] **M2-T072** Refactor `bundle.py` (`write_bundle`, `rule_flags`) so trained and dummy bundles share one writer · Done: 2026-10-22
- [x] **M2-T073** `src/ids_model/train.py` (splits, log1p→scaler→IF, threshold selection, evaluation, report, CLI) · Done: 2026-10-22
- [x] **M2-T074** Real-data run + `tests/integration/test_train_real_data.py` (marker `data`). Report saved · Done: 2026-10-22
- [x] **M2-T075** Install `1.0.0-replica` at `runtime/bundle/current`. Live run `DEV-live-trained` · Done: 2026-10-22
- [x] **M2-T076** Diagnostics tests first: `tests/unit/test_diagnose_ml.py` (separable vs hidden attack, threshold-vs-feature verdict, IF score saturation) · Done: 2026-10-31
- [x] **M2-T077** `src/ids_model/diagnose_ml.py` (AUC, benign-percentile position, ML-only P/R by percentile, feature shift; report `D15-ml-diagnosis-<date>.{md,json}`). Diagnosis only: no threshold or feature choice uses the test split · Done: 2026-10-31
- [ ] **M2-T078** Run on the real replay dataset (needs `runtime/data/replay/`) and record the reading per category
