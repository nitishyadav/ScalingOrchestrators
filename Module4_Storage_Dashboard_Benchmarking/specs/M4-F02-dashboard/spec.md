# Spec: M4-F02 — Live Dashboard (REPLICA)

> **REPLICA built by Aswin S. Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8).

| Field | Value |
|---|---|
| Feature ID | M4-F02 |
| Status | **Verified (replica)** 2026-10-22, 0.2.0 re-verified 2026-10-25, 6/6 ACs (built on request: "any results can be shown in dashboard now?") |
| Version | 0.2.0-replica |
| Proposal trace | §2.1 (Streamlit polls Cassandra), §1.3 G6, Week 7 (throughput chart, anomaly-rate gauge, top-10 IPs, drift banner, 3 s refresh), F4, F5 |
| Contracts | C-04, C-05 (read via M4-F01 `StoreReader`), C-06 (config; dashboard port 8501) |

## 1. Summary
This feature is a Streamlit operations view of the pipeline. It shows live throughput, p95 latency, anomaly rate, top-10 flagged source IPs
and a drift banner (anomaly rate > 15 % over the last 300 s), refreshing every 3 s. It works today on the M4 synthetic stand-in, and
unchanged on real M3 output later. A `--demo` mode renders from in-memory synthetic data with no Cassandra at all.

## 2. Functional requirements
| ID | Requirement | Trace |
|---|---|---|
| M4-FR-011 | KPI tiles: input throughput (median of the last 10 batches with input, ev/s), p95 latency (median per-batch p95 of the last 10 batches with rows, ms, with the 500 ms target; *0.2: medians instead of the single latest batch, whose partial or idle values misled*), anomaly rate (last N s, with the 15 % threshold), windows scored (last N s) | G6, P2 |
| M4-FR-012 | Drift banner: when `drift_alert` holds, a critical banner with an icon and the text "Drift alert: anomaly rate X % > 15 % — retraining recommended". Otherwise a calm "No drift" status, also with an icon and label | G6, F5 |
| M4-FR-013 | Charts: throughput over batches. Anomaly rate per 10 s window, with a 15 % rule. Latency p50/p95 per batch (one ms axis), with a 500 ms rule. Hover tooltips on all of them | Week 7 |
| M4-FR-014 | A top-10 flagged IPs table (anomalous windows, max score, last seen, rule ids) | Week 7 |
| M4-FR-015 | The live area refreshes every 3 s, so new windows appear ≤ 5 s after being written | F4 |
| M4-FR-016 | A run selector (from `ids.runs`, newest first) and a time-span control (60–900 s, default 300) | — |
| M4-FR-017 | The view model (`build_view`) is pure, so the logic is tested without Streamlit or Cassandra. Empty data renders "waiting for data" states, never errors | — |
| M4-FR-018 | *(0.2, 2026-10-25)* **Finished runs:** if a run's newest metrics batch is more than 30 s old, the view is anchored at that batch time ("as of run end") instead of now, so any past run (within the 7-day TTL) shows its final state. A sidebar control can force "Now". The caption states which reference is used | owner request 2026-10-25 |

## 3. Acceptance criteria
| ID | Criterion | Type | Status |
|---|---|---|---|
| M4-F02-AC-01 | `build_view` on synthetic data: KPIs equal the latest batch, the rate series equals per-window anomalous/total, latency ascends in time, top ≤ 10, drift consistent with C-04 | unit | ✅ `test_view_from_synthetic_data`, `test_view_below_threshold_has_no_alert` |
| M4-F02-AC-02 | `build_view` with no runs or no rows → `None` KPIs, empty series, no exception | unit | ✅ `test_empty_store_renders_waiting_state`, `test_explicit_run_and_stale_rows` |
| M4-F02-AC-03 | `--demo` app run (Streamlit AppTest) renders without exceptions: 4 metrics, a drift banner with alert text at share 0.2, a top-10 table | unit (AppTest) | ✅ `test_demo_page_renders_kpis_banner_and_table`, `test_demo_page_without_drift` |
| M4-F02-AC-04 | Live: with the platform and a `synthetic --follow` run, the app (AppTest) renders the live run with the alert. The server answers `/_stcore/health` with `ok` | integration | ✅ `test_ac04_live_page_shows_a_fresh_run`, `test_ac04_server_health` |
| M4-F02-AC-06 | A run that ended an hour ago renders with data, anchored at its last batch (auto). With "Now" it is empty. A live run (last batch < 30 s ago) is anchored at now | unit | ✅ `test_finished_run_is_anchored_at_its_end`, `test_live_run_is_anchored_at_now`, `test_kpis_skip_idle_trailing_batches` (2026-10-25) |
| M4-F02-AC-05 | The categorical palette (2 series) passes the dataviz validator in light and dark modes | check | ✅ validator: light worst CVD ΔE 24.7 / normal 33.6; dark 26.8 / 31.8; contrast ≥ 3:1 (all PASS) |
