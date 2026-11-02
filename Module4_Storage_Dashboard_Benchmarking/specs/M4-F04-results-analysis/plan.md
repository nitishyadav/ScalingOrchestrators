# Plan: M4-F04 — Results and report figures

| Field | Value |
|---|---|
| Spec | 1.0.0 (Approved 2026-11-01) |
| Status | **Approved** |
| Stack | matplotlib 3.9.2 (pinned, Agg backend), standard library. No new dependency |

## Components
| File | Contents |
|---|---|
| `src/ids_monitor/analyze.py` | `latest_reports`, `scorecard`, `f3_table`, `load_evidence`, `results_markdown`, `analyze(results_dir)`, CLI `main()` |
| `src/ids_monitor/figures.py` | `style()` (rcParams: palette, muted axes, `svg.hashsalt`, no metadata dates), one function per figure taking plain rows and returning a `Figure`, `save(fig, dir, name)` → PNG (200 dpi) + SVG |

## Data flow
`<EXP>-<stamp>.json` (M4-F03) → `latest_reports` → `scorecard` (verdicts from `checks`) + `f3_table` (E3 `by_category`) →
figures (report rows + `raw/<run_id>/samples.csv` for P1 + `raw/<run_id>/metrics.csv` and `recovery` for REC) → `RESULTS.md`, `scorecard.json`, `f3.csv`.

## Determinism
`rcParams["svg.hashsalt"] = "ids-m4"`, `metadata={"Date": None}` (SVG) and `{"Software": None}` (PNG); sorted iteration; fixed figure sizes.
