> **REPLICA built by Aswin S. (M1). Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 4 — Storage, Dashboard and Benchmarking

| | |
|---|---|
| Owner | **Vidhi Kant Gupta** |
| Python package | `ids_monitor` |
| Status | Replica: M4-F01 ✅ · M4-F02 ✅ (0.2.0) · M4-F03 ✅ harness · M4-F04 ✅ analysis |
| Contracts owned | C-04 Anomaly Store |
| Contracts consumed | C-05 (metrics), C-06 (config + control CLI of M1/M3) |

## Purpose
This module owns the Cassandra time-series schema and its read access, the live Streamlit operations
dashboard with its drift alert, and the scripted benchmark harness that produces every number in the report
(E1, E2, E3, latency, recovery, FPR).

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M4-F01 Store schema, init and read repository + synthetic data generator | [specs/M4-F01-store-schema-access/](specs/M4-F01-store-schema-access/spec.md) | ✅ Verified (replica, 5/5) |
| M4-F02 Streamlit dashboard (throughput, anomaly gauge, top-10 IPs, drift banner) | [specs/M4-F02-dashboard/](specs/M4-F02-dashboard/spec.md) | ✅ Verified (replica, 6/6; 0.2.0 finished runs) |
| M4-F03 Benchmark harness (E1/E2/E3, P1, LAT, REC: p95 latency, efficiency, recovery) | [specs/M4-F03-benchmark-harness/](specs/M4-F03-benchmark-harness/spec.md) | ✅ Implemented (replica). Unit AC-01..04, live smoke AC-05 |
| M4-F04 Results analysis and report figures | [specs/M4-F04-results-analysis/](specs/M4-F04-results-analysis/spec.md) | ✅ Implemented (replica). Unit AC-01..03 |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Keyspace and table DDL | C-04 | M3 | `contracts/schemas/ids_schema.cql` + `python -m ids_monitor.schema apply` |
| Dashboard, benchmark results, figures | — | Team / report | — |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Anomaly rows + metrics | C-04, C-05 | M3 | `mocks/synthetic_rows.py` (own) or M3's `fake_stream_writer.py` |
| Control CLI (partitions, rate, attack share, executors) | C-06 | M1, M3 | `bench --dry-run` prints the commands only |

## Quick start
```bash
make install
make test && make contract-test
make run                     # schema apply + check (idempotent), against Cassandra on localhost:9042
make mock                    # 10 min of synthetic windows + metrics ending now (run_id DEV-synthetic)
python mocks/synthetic_rows.py --seconds 300 --anomaly-share 0.3 --follow 600   # keep writing live windows
make integration-test        # live tests (platform must be up)
make run                     # … then serves the dashboard on http://localhost:8501 (reads C-04/C-05 from Cassandra)
make demo                    # dashboard on in-memory synthetic data, no platform needed
```
**Dashboard (M4-F02):**
- **KPI tiles:** throughput, p95 latency, anomaly rate, windows scored.
- **Drift banner:** shown when the anomaly rate exceeds 15 % over the last 300 s.
- **Charts:** throughput, anomaly rate (with the 15 % rule), p50/p95 latency (one axis, with the 500 ms rule). All have hover tooltips.
- **Top-10 table:** flagged source IPs.
- **Controls:** run selector and time span. The page refreshes every 3 s.
- **Colours:** reference-palette slots 1–2, validated in light and dark (dataviz).
- **Pin a run:** `streamlit run src/ids_monitor/dashboard.py -- --run-id ID`.
Python access (used by the dashboard and benchmarks):
```python
from ids_contracts.config import load_runtime_config
from ids_monitor.store import connect, StoreReader
r = StoreReader(connect(load_runtime_config()))
r.recent_windows(now_ms, seconds=300, run_id=None); r.drift(now_ms); r.top_flagged(now_ms, n=10); r.metrics(run_id); r.runs()
```
Host connections use a single-node address translator (Cassandra advertises its container IP, which the Mac cannot reach).

**Benchmarks (M4-F03)** — the platform must be up and idle (the harness recreates the topic):
```bash
python -m ids_monitor.bench --experiment E1 --dry-run                 # plan + commands, touches nothing
python -m ids_monitor.bench --experiment E1 --levels 1 --duration 60  # smoke (about 90 s)
make bench EXP=E2                                                     # one experiment, 600 s per level
make bench-all                                                        # E1, E2, LAT, E3, P1, REC (about 3 h)
make analyze                                                          # scorecard + figures → results/analysis/
```
| Experiment | Levels | Answers |
|---|---|---|
| E1 | partitions 1, 4, 8, 16 (2 executors, 5,000 ev/s) | P3 efficiency |
| E2 | executors 1, 2, 4 (8 partitions) | P4 efficiency |
| E3 | attack share 0, 5, 20, 100 % (mixed) | F2 (0 % = benign-only run), F5 (100 % = all-attack load, ADR-013) |
| P1 | 16 × 4 at 12,000 ev/s | P1 sustained ≥ 10,000 ev/s |
| LAT | trigger 1 s, 500 ms, 250 ms | P2, D-13 |
| REC | worker 1 restarted mid-run | P5 |

Each level: topic recreate → stream job → replay (`--days Monday`, looped) → drain → graceful stop → C-05/C-04 read-back.
Raw: `results/raw/<run_id>/` (config, CLI summaries, metrics.csv, samples.csv every 30 s, detection/recovery). Per experiment: `results/<EXP>-<stamp>.{json,md}`.
Ctrl-C stops the current run gracefully and keeps what was collected.
