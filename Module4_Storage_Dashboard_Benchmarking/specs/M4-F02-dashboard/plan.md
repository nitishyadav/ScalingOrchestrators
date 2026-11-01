# Plan: M4-F02 — Live dashboard

| Field | Value |
|---|---|
| Feature ID | M4-F02 |
| Spec version implemented | 1.0.0 |
| Owner | Vidhi Kant Gupta |
| Status | Approved |
| Updated | 2026-11-01 |

## 1. Approach summary
There are three layers:
- **`dashboard_model.py` (pure).** `build_view(windows, metrics, runs, now_ms, span_s, …)` returns one `View` dataclass. It holds everything the page shows, including anchor choice, headline numbers, drift, chart rows, top IPs and empty-state flags.
- **`charts.py` (pure).** It turns `View` series into Altair specs: one y-axis per chart, reference rules, tooltips and the reference palette.
- **`dashboard.py` (Streamlit only).** It holds layout, controls and a `st.fragment(run_every="3s")` around the live area, which reads through M4-F01 `Store`.

Everything except the Streamlit layer is unit-tested. The page is smoke-tested with `streamlit.testing.v1.AppTest`, headless, against a fake store and against live Cassandra.

## 2. Technical context
| Item | Choice | Pin |
|---|---|---|
| UI | Streamlit (`st.fragment(run_every=…)`, `st.metric`, `st.altair_chart`, `st.dataframe`) | 1.39.0 |
| Charts | Altair (installed with Streamlit, so no new pin) | 5.x via streamlit |
| Data | M4-F01 `Store`, `view.drift_summary`, `view.top_flagged` | — |

## 3. Constitution check
| Article | Compliant? | Notes |
|---|---|---|
| I Spec before code | ✅ | Spec 1.0.0 Approved |
| II Contracts only | ✅ | Reads C-04/C-05 via M4-F01 |
| III Isolation | ✅ | Imports `ids_contracts` and `ids_monitor` only |
| IV Mock-first | ✅ | Runs on `make mock` data |
| V Makefile | ✅ | `make run` = schema apply + `streamlit run` on 8501 |
| VI Config via env | ✅ | `load_runtime_config`. Port 8501 is the C-06 service port |
| VII Honest ML | ✅ | The 15 % and 500 ms references come from `ids_contracts.store.DRIFT_THRESHOLD` and a P2 constant. Labels are never read (AC-10) |
| VIII Tests from AC | ✅ | §7 |
| IX Pins | ✅ | No new dependency |
| X Measured claims | ✅ | AC-08/09 timings recorded in the dev log |
| XI Ownership | ✅ | M4 only |
| XII Simplicity | ✅ | Streamlit + Altair, both already in the stack |

## 4. Design
```
Store (M4-F01) ──► dashboard.load_data(store, run, span) ──► dashboard_model.build_view ──► View
                                                                                   │
                                     charts.throughput / anomaly_rate / latency ◄──┤
                                     dashboard.render(View)  (st.metric, banner, charts, table, data expander)
```
| Requirement | Component |
|---|---|
| FR-020, FR-021, FR-026, FR-027 (data side), FR-030 | `dashboard_model.py` |
| FR-022, FR-028 | `charts.py` (+ data tables in `dashboard.py`) |
| FR-023 | `view.top_flagged` via `dashboard_model` |
| FR-024, FR-025, FR-027 (UI), FR-029 | `dashboard.py`, `Makefile` |

Visual rules (dataviz method, reference palette validated in light and dark):
- Two-series charts use slot 1 blue `#2a78d6` and slot 2 orange `#eb6834`. Single-series charts use blue.
- Reference lines use muted ink `#898781`, dashed, with a direct label.
- Lines are 2 px. Bars have rounded ends at the data end.
- Status colours are reserved for the banner and always carry an icon and a label.
- No dual axes.

## 5. Configuration
| Env var (C-06) | Default | Used for |
|---|---|---|
| `CASSANDRA_HOSTS`, `CASSANDRA_PORT`, `CASSANDRA_KEYSPACE` | `localhost`, `9042`, `ids` | `Store` |

## 6. Mocks
| Dependency | Mock | Swapped at |
|---|---|---|
| M3 C-04/C-05 writes | `make mock MOCK_ARGS="--follow 600"` | I-03 |
| Cassandra in unit/AppTest | fake `Store` injected by monkeypatching `dashboard.open_store` | integration tests |

## 7. Test strategy
| Level | What | AC |
|---|---|---|
| Unit | `build_view`: medians, empty, anchor, drift, top, per-window rates, label guard. `charts`: one y-axis, tooltip, rule values | AC-01..05, AC-10 |
| Headless | `AppTest` with a fake store: banner text, table, empty state, store-down message | AC-02, AC-04, AC-06 |
| Integration | `AppTest` against Cassandra with synthetic data. Write → visible timing. 75k-window cycle time | AC-07..09 |
| Manual | `make run`, open http://localhost:8501, screenshot | AC-11 |

## 8. Risks and alternatives
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| `st.line_chart` built-ins | Less code | No reference lines, palette or tooltip control | No |
| Altair specs | Full control, testable as dicts | Slightly more code | **Yes** |
| `streamlit-autorefresh` component | — | New dependency | No: `st.fragment(run_every)` is built in |

## 9. Done means
- [ ] All tasks complete, all tests green, every AC ✅, README updated
