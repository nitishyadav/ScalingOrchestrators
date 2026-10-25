# Spec: M2-F01 — EDA and Window Labelling (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Status | **Implemented (replica)** 2026-10-25 |
| Version | 0.1.0-replica |
| Trace | PROJECT_PLAN M2-F01 ("explore the replay dataset, check feature distributions per attack type, define the window label rule"), D-04, D-07/ADR-007, D-14/ADR-012 |
| Contracts | C-01 (replay dataset, read only), C-02 0.2.0 (window features via M2-F02 `features_from_replay`) |

## 1. Summary
`python -m ids_model.eda` profiles the C-01 replay dataset at two levels: **flows** (rows per day and label, source/target
concentration of attacks) and **windows** (C-02 windows at R_ref per day: attack windows, label purity, and per-feature separation
between benign and attack windows). It writes a dated report and figures to `docs/measurements/`. The window-label rule (C-02
`window_label`: attack iff ≥ 1 non-benign event, majority non-benign label) is checked against the purity of attack windows.

## 2. Functional requirements
| ID | Requirement |
|---|---|
| M2-FR-001 | Flow profile per day: rows, benign, attack, attack share, distinct source IPs; rows per label (all days) |
| M2-FR-002 | Attack concentration: attack rows per source IP (top 5, share of all attack rows) and per destination IP (top 5) |
| M2-FR-003 | Windows per day at R_ref = 5,000 ev/s (C-02 0.2.0, per day from its first row): windows, attack windows, share, per `label_type` |
| M2-FR-004 | Purity of attack windows = attack events / events: quantiles, and the share of attack windows with purity ≥ 0.5 and ≥ 0.99 |
| M2-FR-005 | Separation per C-02 feature (`RULE_FEATURES`, base + ratios): ROC AUC of the raw feature for attack vs benign windows (direction-free: max(AUC, 1 − AUC)), and p5/p50/p95 per class |
| M2-FR-006 | Figures (PNG, dataviz palette slots 1–2: benign blue `#2a78d6`, attack orange `#eb6834`): rows per day (stacked bars), attack rows per label, ECDFs of the model inputs (V3) and of 2 volume features, benign vs attack windows |
| M2-FR-007 | Outputs: `docs/measurements/F01-eda-<date>.{md,json}` and `docs/measurements/figures/F01-*.png`. Last stdout line = C-06 summary |

## 3. Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M2-F01-AC-01 | Flow profile and concentration on a synthetic frame: exact counts and shares | unit | ✅ `test_flow_profile_and_concentration` |
| M2-F01-AC-02 | Window summary, purity and separation on a synthetic window frame (a perfectly separating feature has AUC 1.0; a constant one 0.5) | unit | ✅ `test_window_summary_purity_and_separation` |
| M2-F01-AC-03 | End to end on `Module1…/mocks/replay_sample.parquet` (into a temp dir): report, JSON and all figures written | unit | ✅ `test_end_to_end_on_replay_sample`; figures checked visually |
| M2-F01-AC-04 | Full run on the replay dataset: day row counts equal the C-01 manifest `valid_rows`; findings recorded in the report | measurement | ⬜ |
