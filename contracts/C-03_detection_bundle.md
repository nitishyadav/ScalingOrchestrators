# Contract C-03: Detection Bundle

> **PROVISIONAL REPLICA.** Authored by Aswin S. (M1) in replica mode from the playbook §5.4. The canonical owner, **Nitish Kumar Yadav (M2)**,
> authors and approves v1.0, and this file is then replaced.

| Field | Value |
|---|---|
| Contract ID | C-03 |
| Version | 0.2.0-replica |
| Status | **Provisional (replica)** |
| Provider (owner) | M2: Nitish Kumar Yadav (this draft by M1) |
| Consumers | M3 (scoring in Spark) |
| Medium | A directory of files at `MODEL_BUNDLE_PATH` (C-06) |
| Schemas | `schemas/manifest.schema.json`, `schemas/rules.schema.json` |
| Code | `ids_contracts.bundle` (`validate_manifest`, `validate_rules`, reference `rule_hits`, `decide`) |
| Decisions applied | ADR-009 (identical library pins), D-09 |

## 1. Purpose
This contract fixes the package that carries the trained model and the rule set from offline training (M2) to online scoring (M3),
and the exact decision semantics, so that both sides compute the same flags.

## 2. Layout
```
runtime/bundle/<bundle_version>/     ← MODEL_BUNDLE_PATH points at one of these, or at runtime/bundle/current (copy or symlink)
├── model.joblib     sklearn Pipeline([("scaler", StandardScaler()), ("iforest", IsolationForest(...))])
├── manifest.json    §3
└── rules.yaml       §4
```
`model.joblib` must load with the `versions.md` pins (scikit-learn 1.5.2, numpy 1.26.4, joblib 1.4.2) in the Spark image.

## 3. `manifest.json`
| Key | Type | Meaning |
|---|---|---|
| `bundle_version` | string | `"0.0.0-dummy"` for the dummy bundle. SemVer for real ones |
| `created_at` | string | ISO-8601 UTC |
| `python_version`, `sklearn_version`, `numpy_version` | string | Versions used for training (must equal `versions.md`) |
| `feature_order` | list | Must equal C-02 `FEATURE_ORDER` |
| `score_definition` | string | Exactly `"anomaly_score = -model.score_samples(X); higher = more anomalous"` |
| `threshold` | number | `ml_flag = anomaly_score ≥ threshold` |
| `training` | object | `data`, `seed`, `n_estimators`, `contamination`, `R_ref` |
| `metrics` | object | `precision`, `recall`, `fpr` (null for the dummy), `test_files` |
| `contract_versions` | object | At least `{"C-02": …, "C-03": …}` |

## 4. `rules.yaml`
```yaml
version: 1
combine: any                 # rule_flag = any rule fires ("all" = every rule fires)
rules:
  - id: R-SYN-FLOOD
    all: [{feature: syn_ack_ratio, op: ">=", value: 5.0}]
  - id: R-PORT-SCAN
    all: [{feature: unique_ports, op: ">=", value: 50}]
  - id: R-DDOS-RATE
    all: [{feature: packet_rate, op: ">=", value: 100.0}, {feature: unique_ports, op: "<=", value: 3}]
```
Features must be C-02 `RULE_FEATURES` (base features or ratios, 0.2.0), not only the model inputs. Operators are `>=`, `>`, `<=`, `<`, `==`. A rule fires when **all** of its conditions hold.
The values above are placeholders that M2 tunes.

## 5. Decision semantics (identical in M2 offline evaluation and M3 online scoring)
For each feature row x (in `feature_order`):
1. `anomaly_score = -model.score_samples([x])[0]`
2. `ml_flag = anomaly_score ≥ threshold`
3. `hits = rule_hits(rules, x)` (fired rule ids, in file order). `rule_flag = any(hits)` (or all, when `combine: all`)
4. `is_anomaly = ml_flag OR rule_flag`. `rule_ids = ",".join(hits)`

The reference implementation is `ids_contracts.bundle.rule_hits` / `decide`. Vectorised implementations must agree with it on the golden rows.

**Golden scores:** `fixtures/scores_golden.csv` (columns `SCORE_COLUMNS` = window key + `anomaly_score, ml_flag, rule_flag, rule_ids, is_anomaly`;
booleans `true`/`false`) is `features_golden.csv` scored by the dummy bundle. M3 must reproduce it (`anomaly_score` within `SCORE_TOLERANCE` = 1e-9, the rest exactly).
Reader: `ids_contracts.bundle.read_scores_csv`.
Thresholds live **only** in the bundle, never in code (Art. VII).

## 6. Dummy bundle
M2 ships `Module2_ML_Anomaly_Model/mocks/dummy_bundle/`: an IsolationForest fitted (seed 42) on synthetic data shaped like C-02 features,
`bundle_version "0.0.0-dummy"`, null metrics, and the §4 rules. With it, `fixtures/scores_golden.csv` (the golden features scored by the dummy) is produced
by M2-F04 and used by M3 for parity.

## 7. Approvals
| Role | Member | Version | Date |
|---|---|---|---|
| Provider | Nitish Kumar Yadav (M2) | — | |
| Consumer | Kumari Priyanka (M3) | — | |
| Replica author | Aswin S. (M1) | 0.1.0-replica | 2026-10-22 |

## 8. Change log
| Version | Date | Change |
|---|---|---|
| 0.1.0-replica | 2026-10-22 | Provisional replica from the playbook §5.4. Validators, reference semantics and JSON schemas |
| 0.1.1-replica | 2026-10-22 | `scores_golden.csv` format (`SCORE_COLUMNS`, `read_scores_csv`, tolerance) for M2-F04 / M3 parity |
| 0.2.0-replica | 2026-10-25 | Follows C-02 0.2.0: `feature_order` const is the new `FEATURE_ORDER`; rules may reference any `RULE_FEATURES`. Dummy bundle and `scores_golden.csv` regenerated (golden rows now cover benign, ML-only, rule-only and both) |
