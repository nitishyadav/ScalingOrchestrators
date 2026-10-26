# Spec: M3-F03 — Hybrid Scoring (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Shared plan and tasks: [M3-F01 plan](../M3-F01-stream-ingest/plan.md).

| Field | Value |
|---|---|
| Status | **Verified (replica)** 2026-10-22 · 0.1.0-replica · re-verified on C-02/C-03 0.2.0-replica 2026-10-25 |
| Trace | §1.2 (model broadcast to Spark workers, vectorised pandas_udf), §1.3 G3, G4, C-03 |

| ID | Requirement |
|---|---|
| M3-FR-021 | Load the C-03 bundle from `MODEL_BUNDLE_PATH` on the driver (validate manifest and rules, version guard ADR-009) and **broadcast** the model |
| M3-FR-022 | `anomaly_score` via a **vectorised `pandas_udf`** over the 4 features in C-02 order. `ml_flag = score ≥ manifest.threshold` |
| M3-FR-023 | Rules compiled from `rules.yaml` into Spark expressions (no thresholds in code). `rule_ids` = fired ids in file order. `is_anomaly = ml_flag OR rule_flag` (C-03 §5) |

| AC | Criterion | Type | Status |
|---|---|---|---|
| M3-F03-AC-01 | Rule → SQL compilation is exact for every operator and for `combine: any`/`all` | unit | ✅ `test_rule_compilation`, `test_rule_compilation_rejects_injection` |
| M3-F03-AC-02 | **Golden parity:** scoring the golden windows in Spark reproduces `scores_golden.csv` (score within 1e-9, flags and rule ids exact) | integration (spark) | ✅ `test_spark_scores_equal_golden` (within 1e-9) |
