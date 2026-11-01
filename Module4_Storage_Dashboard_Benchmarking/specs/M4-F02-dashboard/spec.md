# Spec: M4-F02 — Live dashboard

| Field | Value |
|---|---|
| Feature ID | M4-F02 |
| Module | Module4_Storage_Dashboard_Benchmarking |
| Owner | Vidhi Kant Gupta |
| Reviewers | Kumari Priyanka (M3, provider of the data shown) |
| Status | **Implemented** (2026-11-01). Becomes Verified after the AC-11 visual check |
| Version | 1.1.0 |
| Created / Updated | 2026-11-01 / 2026-11-01 |
| Proposal trace | G6 (live dashboard), F4 (alert visible ≤ 5 s after write), F5 (drift banner correct), P1/P2 (shown live) |
| Contracts touched | C-04 1.0.0-rc.1 (reads), C-05 0.1.0-replica (reads), C-06 1.0.0-rc.7 (config, service `dashboard` on 8501) |
| Decisions applied | ADR-013 (drift = anomalous-window share), D-01 (latency), ADR-007 (eval-only never shown as a verdict) |

## 1. Summary
This feature is a live operations dashboard for the anomaly-detection pipeline. It shows:
- throughput, latency and anomaly rate, as headline numbers and over time;
- the drift/retraining banner;
- the top flagged source IPs.

It refreshes every 3 s, so an alert written by the stream job appears within 5 s. A past run can be opened and shown as it ended.

## 2. Context and motivation
G6 requires a live dashboard with a retraining/drift alert when more than 15 % of recent windows are flagged. F4 and F5 are measured on it,
and it is the centrepiece of the 29 Nov demo. The data comes only from C-04 and C-05 through M4-F01 (`Store`, `view`).

Lessons from the replica (playbook §8, read-only reference):
- Headline numbers use medians of recent batches, because the single latest batch is often partial or idle.
- A finished run must be shown as of its end, not as an empty "now".

## 3. Scope
**In scope:** headline numbers, drift banner, three time-series charts, top flagged IPs, run and span selection,
anchoring for finished runs, empty states, a data table behind every chart.
**Out of scope:** controlling the pipeline (M1/M3 CLIs), experiment orchestration (M4-F03), report figures (M4-F04), authentication.

## 4. Actors and user stories
- **US-1:** As an operator watching a run, I want the throughput, latency and anomaly rate at a glance, so that I know the pipeline is healthy.
- **US-2:** As an operator, I want an unmistakable banner when more than 15 % of recent windows are anomalous, so that I know retraining is due (G6, F5).
- **US-3:** As an analyst, I want to see which source IPs are flagged, and why, so that I can investigate them.
- **US-4:** As a presenter, I want to open any run from the last 7 days and see its final state.

## 5. Functional requirements
| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M4-FR-020 | Headline numbers MUST show: input throughput (median `input_rows_per_sec` of the last 10 batches with input, ev/s); p95 latency (median `latency_p95_ms` of the last 10 batches that wrote rows, ms) against the 500 ms target; anomaly rate over the span against the 15 % threshold; windows in the span. A missing value shows "—" | P0 | US-1 | G6, P1, P2 |
| M4-FR-021 | The drift banner MUST show, with an icon and a text label, "Drift alert: anomaly rate X % > 15 % — retraining recommended" when C-04 `drift_alert` holds over the last 300 s of the view, and "No drift" otherwise. Colour is never the only signal | P0 | US-2 | G6, F5, ADR-013 |
| M4-FR-022 | Charts MUST show: input vs processed rows/s per batch; anomaly rate per 10 s `window_end` with a 15 % reference line; latency p50/p95 per batch with a 500 ms reference line. Each chart has one y-axis, hover tooltips, and a legend when it has 2 series | P0 | US-1 | G6 |
| M4-FR-023 | MUST show the top 10 flagged source IPs (anomalous windows, max score, last seen, rule ids), from M4-F01 `top_flagged` | P0 | US-3 | G6 |
| M4-FR-024 | The live area MUST refresh every 3 s | P0 | US-1 | F4 |
| M4-FR-025 | MUST offer a run selector (C-05 `runs`, newest first, default newest) and a span control (60–900 s, default 300 s) | P1 | US-4 | — |
| M4-FR-026 | When the selected run's newest metrics batch is more than 30 s old, the view MUST be anchored at that batch time ("as of run end"). A control can force "now". A caption states which anchor is used | P1 | US-4 | — |
| M4-FR-027 | With no data, every element MUST show a "waiting for data" state, never an error. If Cassandra is unreachable, a single error message names host and port, and the page keeps retrying | P0 | all | — |
| M4-FR-028 | Every chart MUST have its data available as a table | P1 | all | accessibility |
| M4-FR-029 | Connection settings come only from C-06. `make run` serves the dashboard on port 8501 (C-06 service `dashboard`) | P0 | all | C-06 |
| M4-FR-030 | The dashboard MUST NOT read eval-only columns (`label_attack`, `label_type`) | P0 | all | ADR-007, Const. VII |

## 6. Non-functional requirements
| ID | Category | Requirement | Trace |
|---|---|---|---|
| M4-NFR-010 | Latency | From a C-04 write to its visibility on the page ≤ 5 s: 3 s refresh plus one refresh cycle | F4 |
| M4-NFR-011 | Performance | One refresh cycle (read + view model + charts) ≤ 2 s at the full rate (≈ 75k windows in 300 s) | F4 |
| M4-NFR-012 | Testability | All logic other than Streamlit calls is pure and unit-tested. The page is smoke-tested headlessly | Const. VIII |

## 7. Interfaces
### 7.1 Provided
| What | Where |
|---|---|
| Dashboard web page | `http://localhost:8501` (C-06 service `dashboard`) |

### 7.2 Consumed
| Contract | Version | What is used | Mock until real |
|---|---|---|---|
| C-04 | 1.0.0-rc.1 | windows in the span (M4-F01 `Store.read_windows`) | `make mock` (M4-F01 synthetic) |
| C-05 | 0.1.0-replica | `pipeline_metrics` of the run, `runs` | `make mock` |
| C-06 | 1.0.0-rc.7 | `CASSANDRA_*` | — |

## 8. Data
At the full rate, the 300 s span holds ≈ 75k windows (2 partitions) and ≈ 300 metrics rows. The page keeps nothing between refreshes.

## 9. Acceptance criteria
| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M4-F02-AC-01 | **Given** metrics with idle and partial batches **When** headline numbers are built **Then** they are the medians over the last 10 qualifying batches, and "—" when there are none | FR-020 | unit | ✅ `unit/test_dashboard_model.py::test_kpis_*`, `::test_batches_outside_span_are_ignored` |
| M4-F02-AC-02 | **Given** 16 % anomalous windows in the last 300 s **Then** the banner is critical, with an icon and the text above. **Given** 15 % **Then** "No drift" | FR-021 | unit + headless | ✅ `unit/test_dashboard_model.py::test_banner_*`, `unit/test_dashboard_app.py::test_alert_banner_and_top_table`, `::test_no_drift_banner` |
| M4-F02-AC-03 | **Given** windows and metrics **Then** the chart data holds one point per batch and per `window_end` with correct rates. Each chart has one y-axis, a tooltip, and its reference line at 0.15 / 500 ms | FR-022 | unit | ✅ `unit/test_dashboard_model.py::test_series_rows`, `unit/test_charts.py` |
| M4-F02-AC-04 | **Given** flagged windows **Then** the table lists at most 10 IPs in `top_flagged` order with all 4 fields | FR-023 | unit + headless | ✅ `unit/test_dashboard_model.py::test_top_is_capped_at_10_in_order`, `unit/test_dashboard_app.py::test_alert_banner_and_top_table` |
| M4-F02-AC-05 | **Given** a run whose last batch is 10 min old **Then** the anchor is that batch time and the caption says "as of run end". **Given** "now" forced **Then** the anchor is now | FR-026 | unit | ✅ `unit/test_dashboard_model.py::test_anchor_*`, `::test_caption_names_the_anchor` |
| M4-F02-AC-06 | **Given** no runs and no windows **Then** the page renders "waiting for data" with no exception. **Given** Cassandra down **Then** one error naming host:port | FR-027 | headless | ✅ `unit/test_dashboard_app.py::test_empty_store_waits_for_data`, `::test_store_down_single_error` |
| M4-F02-AC-07 | **Given** synthetic data in Cassandra **When** the page runs headlessly **Then** it renders the numbers, banner, 3 charts, the table, and the data tables, with no exception | FR-020..025, FR-028 | integration (headless) | ✅ `integration/test_dashboard_live.py::test_ac07_page_renders_on_synthetic_data` |
| M4-F02-AC-08 | **Given** anomalous rows written at t **Then** the next refresh shows them, and the measured write → visible time ≤ 5 s | FR-024, NFR-010 | integration | ✅ `integration/…::test_ac08_write_to_visible_within_5s`: **worst case 3.44 s** (3 s refresh + 0.05 s cycle), 2026-11-01 |
| M4-F02-AC-09 | **Given** 75k windows **Then** one refresh cycle ≤ 2 s | NFR-011 | integration (perf) | ✅ `integration/…::test_ac09_cycle_at_full_rate`: **75,000 windows in 1.61 s**, 2026-11-01 |
| M4-F02-AC-10 | **Given** rows whose eval-only columns raise on access **Then** the view model still builds | FR-030 | unit | ✅ `unit/test_dashboard_model.py::test_eval_only_never_read` |
| M4-F02-AC-11 | **Given** `make run` **Then** the page is served on 8501 (manual check, screenshot in the dev log) | FR-029 | manual | 🟡 Served on 8501 via `make run`; screenshot `docs/img/m4-f02-dashboard.png` (headless Chrome, 2026-11-01). Owner sign-off pending |

## 10. Edge cases
| Case | Expected behaviour |
|---|---|
| Run with metrics but no windows yet | Throughput and latency show, anomaly rate "—", banner "No drift" (no data) |
| Batches with `windows_written = 0` | Latency is null there. They are excluded from the p95 headline and shown as gaps |
| Span crosses midnight UTC | Handled by `partition_keys` |
| Invalid live rows | Counted and shown in the caption ("n invalid rows skipped") |

## 11. Assumptions
- Streamlit 1.39 (pinned) with `st.fragment(run_every=…)`. Altair is the chart library bundled with Streamlit (no new infrastructure).

## 12. Open questions
None.

## 13. Review checklist
- [x] No implementation details beyond the interface
- [x] Every FR has at least one AC
- [x] Every NFR has a number and a unit
- [x] Contracts referenced by ID and version
- [x] Eval-only fields not used (FR-030)
- [x] No open `[NEEDS CLARIFICATION]`
- [ ] Consumer-module review (M3 sees it at I-03)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Initial approved version |
| 1.1.0 | 2026-11-01 | Vidhi Kant Gupta (with AI) | Presentation only, FRs unchanged: dark theme, header with LIVE/ENDED badge, drift strip with gauge, KPI tiles with status label + trend + sparkline, Chart/Data tabs (FR-028), all times UTC. Fixed: anomaly-rate bars had no zero baseline. AC-07 test writes 200 s of data (was flaky at 300 s) |
