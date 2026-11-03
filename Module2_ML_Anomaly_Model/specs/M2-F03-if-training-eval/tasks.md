# Tasks: M2-F03 — IF Training and Evaluation (REPLICA)

- [x] **M2-T070** Spec with the no-leakage data protocol · Done: 2026-10-22
- [x] **M2-T071** Tests first: `tests/unit/test_train.py` (metrics, selection, leakage guard, determinism, report) · Done: 2026-10-22
- [x] **M2-T072** Refactor `bundle.py` (`write_bundle`, `rule_flags`) so trained and dummy bundles share one writer · Done: 2026-10-22
- [x] **M2-T073** `src/ids_model/train.py` (splits, log1p→scaler→IF, threshold selection, evaluation, report, CLI) · Done: 2026-10-22
- [x] **M2-T074** Real-data run + `tests/integration/test_train_real_data.py` (marker `data`). Report saved · Done: 2026-10-22
- [x] **M2-T075** Install `1.0.0-replica` at `runtime/bundle/current`. Live run `DEV-live-trained` · Done: 2026-10-22
- [x] **M2-T076** Diagnostics tests first: `tests/unit/test_diagnose_ml.py` (separable vs hidden attack, threshold-vs-feature verdict, IF score saturation) · Done: 2026-10-31
- [x] **M2-T077** `src/ids_model/diagnose_ml.py` (AUC, benign-percentile position, ML-only P/R by percentile, feature shift; report `D15-ml-diagnosis-<date>.{md,json}`). Diagnosis only: no threshold or feature choice uses the test split · Done: 2026-10-31
- [x] **M2-T078** Run on the real replay dataset and record the reading per category: threshold problem for DDoS and PortScan (AUC 0.991, recall 0 at p99.9) · Done: 2026-11-03
- [x] **M2-T079** Tests first, then `select_threshold` by validation recall (ties: lowest hold-out FPR); `VERSION` 1.2.0-replica; spec FR-022; M2-ADR-001 · Done: 2026-11-03
- [x] **M2-T080** Real-data run: percentile 99, threshold 0.6531; ML-only test recall 1.000; hybrid precision 0.023 (report `F03-training-2026-11-03.md`) · Done: 2026-11-03
