# Plan: M4-F02 — Live Dashboard (REPLICA)

| Field | Value |
|---|---|
| Status | **Approved** (replica) |
| Stack | `streamlit==1.39.0` (pinned in `versions.md`), Altair 5 (bundled), pandas 2.2.3 |

## Design
| Component | File | Notes |
|---|---|---|
| View model | `src/ids_monitor/view.py` `build_view(reader, now_ms, run_id, seconds)` | Pure: everything the page shows, as plain data |
| Demo reader | `view.DemoReader` | In-memory `StoreReader` lookalike over `synthetic.generate()` (no Cassandra) |
| Page | `src/ids_monitor/dashboard.py` (Streamlit) | Sidebar (run, span), `@st.fragment(run_every=3)` live area, Altair charts with tooltips |

## Chart decisions (dataviz skill)
| Element | Form | Colour | Notes |
|---|---|---|---|
| Throughput, p95, rate, windows | Stat tiles (`st.metric`) | Text tokens | Headline numbers are not charts |
| Throughput over batches | Line, 1 series | Slot 1 blue | The title names the series (no legend) |
| Anomaly rate per window | Line, 1 series + dashed 15 % rule | Slot 1 blue, rule in muted ink | Rule labelled "15 % drift threshold" |
| Latency p50 / p95 | Line, 2 series, **one ms axis** + dashed 500 ms rule | Slot 1 blue (p50), slot 2 orange (p95) | Legend + direct end labels. No dual axis |
| Drift banner | Status | `st.error` / `st.success` with icon + label | A status colour never carries meaning alone |
| Top-10 | Table (`st.dataframe`) | — | Doubles as the accessible table view |

Hover: Altair nearest-point selection with a vertical rule and a tooltip on line charts. 2 px lines, ≥ 8 px hover points. Grid recessive.

## Make target
`make run` → schema apply/check, then `streamlit run src/ids_monitor/dashboard.py --server.port 8501 --server.headless true`.
`make demo` (extra) → the same page with `-- --demo` (no Cassandra needed).
