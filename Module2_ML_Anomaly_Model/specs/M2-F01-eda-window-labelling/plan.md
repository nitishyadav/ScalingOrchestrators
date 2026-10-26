# Plan: M2-F01 — EDA and Window Labelling (REPLICA)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Stack | pandas, pyarrow, scikit-learn (`roc_auc_score`), **matplotlib 3.9.2** (new host-only pin, `versions.md`) |

| Component | File | Notes |
|---|---|---|
| Profiles (pure) | `eda.flow_profile`, `attack_concentration`, `window_summary`, `purity`, `separation` | pandas in, plain dicts/frames out |
| Data | `eda.load_days(replay_dir)` | Per-day parquet (as M2-F03), features per day via `features_from_replay(..., extended=True)` |
| Figures | `eda.figures(...)` | matplotlib Agg, light theme, 2 px lines, legend + direct labels, recessive grid, no dual axes |
| CLI | `main()` | `--replay-dir`, `--out-dir` |
