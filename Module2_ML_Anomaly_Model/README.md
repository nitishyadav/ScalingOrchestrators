> **REPLICA built by Aswin S. (M1). Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 2 — ML Anomaly Model

| | |
|---|---|
| Owner | **Nitish Kumar Yadav** |
| Python package | `ids_model` |
| Status | Replica: M2-F02 ✅ · M2-F03 ✅ implemented (targets: see D-14) · M2-F04 ✅ · M2-F01 ✅ EDA (`make eda`) · C-02/C-03 0.2.0, bundle 1.1.0-replica |
| Contracts owned | C-02 Feature Definition, C-03 Detection Bundle |
| Contracts consumed | C-01 (replay dataset format), C-06 (paths, version pins) |

## Purpose
This module trains an unsupervised Isolation Forest offline (Colab) on windowed CIC-IDS2017 features
that exactly match what Spark computes at runtime, evaluates it against F1 and F2, and packages the model
and the rule set as a self-describing detection bundle for the stream job.

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M2-F01 EDA and window labelling rule | [specs/M2-F01-eda-window-labelling/](specs/M2-F01-eda-window-labelling/spec.md) | ✅ Implemented (replica). `make eda` → `docs/measurements/F01-eda-<date>.md` |
| M2-F02 Reference feature builder (pandas) + golden fixture | [specs/M2-F02-reference-features/](specs/M2-F02-reference-features/spec.md) | ✅ Verified (replica, 3/3) |
| M2-F03 IF training and evaluation (precision, recall, FPR) | [specs/M2-F03-if-training-eval/](specs/M2-F03-if-training-eval/spec.md) | ✅ Implemented (replica). Bundle 1.1.0 (V3 inputs, ADR-012): F1 recall 0.941 ✅ · F2 1.00 % ✅ · F1 window precision 0.112 ❌ (flow level 0.846; D-14) |
| M2-F04 Detection bundle + rules + offline rule-vs-hybrid | [specs/M2-F04-detection-bundle/](specs/M2-F04-detection-bundle/spec.md) | ✅ Verified (replica, 6/6: dummy bundle + golden scores) |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Feature definition + golden fixtures | C-02 | M3 | `contracts/fixtures/features_golden.csv` |
| Detection bundle (model, scaler, manifest, rules) | C-03 | M3 | `mocks/dummy_bundle/` (ship on day 1) |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Replay dataset (Parquet) | C-01 | M1 | Raw CIC CSV sample mapped with the C-01 column table |

## Quick start
```bash
make install && make test && make contract-test
make mock              # dummy bundle → mocks/dummy_bundle + runtime/bundle/current; golden scores → contracts/fixtures/scores_golden.csv
make run               # validate the bundle at MODEL_BUNDLE_PATH
make integration-test  # the bundle loads and scores identically inside the Spark image (platform up)
python -m ids_model.train [--install]   # real training (about 5 s): bundle runtime/bundle/1.0.0-replica + docs/measurements/F03-training-<date>.{md,json}
```
```python
from ids_model.features import build_features, features_from_replay   # C-02 in pandas (golden parity)
from ids_model.bundle import Bundle                                     # C-03: Bundle.load(path).score(features_df)
```
The dummy bundle flags the golden port scan and SYN flood via `R-SYN-FLOOD` only. Its ML threshold (0.654) comes from synthetic data, so
`ml_flag` is false on all golden windows. Real training is M2-F03.
