# Plan: M4-F04 — Results Analysis and Figures (REPLICA)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Stack | matplotlib 3.9.2 (host only, `versions.md` rc.4), pandas |

| Component | File |
|---|---|
| Report discovery, scorecard (pure) | `src/ids_monitor/analyze.py` `latest_reports`, `scorecard` |
| Figures | `analyze.figures` (one function per figure, each skipped if its inputs are missing) |
| CLI | `python -m ids_monitor.analyze [--results-dir D]` |
