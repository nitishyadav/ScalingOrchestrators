# Module 4 — Storage, Dashboard and Benchmarking

| | |
|---|---|
| Owner | **Vidhi Kant Gupta** |
| Python package | `ids_monitor` |
| Status | Building (canonical owner build, started 2026-11-01) |
| Contracts owned | C-04 Anomaly Store |
| Contracts consumed | C-05 Pipeline Metrics (M3), C-06 Runtime Config and Control (M1) |

## Purpose
This module owns the Cassandra table where scored windows land, and the read access to it. It also owns the live Streamlit
operations dashboard with its drift alert (G6), and the scripted benchmark harness that produces every number in the report
(E1–E3, P1, latency, recovery, FPR).

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M4-F01 Store schema and access | specs/M4-F01-store-schema-access/ | Implemented (see spec AC table) |
| M4-F02 Live dashboard | specs/M4-F02-dashboard/ | Implemented (AC-11 visual check pending) |
| M4-F03 Benchmark harness | specs/M4-F03-benchmark-harness/ | Not started |
| M4-F04 Results analysis | specs/M4-F04-results-analysis/ | Not started |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Keyspace and `window_scores` DDL | C-04 | M3 (writer) | `contracts/schemas/ids_schema.cql` |
| Dashboard, benchmark results, figures | — | Team / report | — |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Scored windows | C-04 | M3 | M4-F01 synthetic generator (`make mock`) |
| Per-batch metrics and runs | C-05 | M3 | M4-F01 synthetic generator (`make mock`) |
| Control CLIs (topic, producer, job, worker restart) | C-06 | M1, M3 | harness `--dry-run` |

## Quick start
```bash
make install
make test
make contract-test
make run    # apply + check the C-04/C-05 schema, then serve the dashboard on http://localhost:8501
make mock   # synthetic C-04/C-05 rows for the last 300 s (M4-F01)
make integration-test   # live tests; needs Cassandra on CASSANDRA_HOSTS:CASSANDRA_PORT
```

### M4-F01 commands (C-06 conventions: exit 0 ok / 1 runtime / 2 usage, one JSON summary line last)
```bash
python -m ids_monitor.schema apply              # create keyspace + tables, then check for drift
python -m ids_monitor.schema apply --recreate   # drop + recreate tables whose primary key changed (0.1.0 → 1.0 key)
python -m ids_monitor.schema check              # exit 1 and list every difference from the contracts
python -m ids_monitor.synthetic --n-ips 50 --windows 30 --anomaly-share 0.1 --seed 42 [--follow 600]
make mock MOCK_ARGS="--anomaly-share 0.3 --follow 300"
```

### Dashboard (M4-F02)
`make run`, then open http://localhost:8501. For live demo data in a second terminal: `make mock MOCK_ARGS="--anomaly-share 0.2 --follow 600 --run-id DEV-demo"`.
- **Sidebar:** run (newest first; *Latest run (auto)* follows new runs), span 60–900 s, *Anchor at now*. A finished run is shown as of its last batch.
- **Live area** (refreshes every 3 s): caption (run, live / as of run end), drift banner (> 15 % of windows in the last 300 s), headline numbers
  (median throughput and p95 latency of the last 10 batches, anomaly rate, windows), throughput / latency / anomaly-rate charts with data tables, and the top 10 flagged IPs.

### Using the store from Python (M4-F02, M4-F03)
```python
from ids_contracts.config import load_runtime_config
from ids_monitor import db
from ids_monitor.store import Store
from ids_monitor.view import drift_summary, top_flagged

cluster, session = db.connect(load_runtime_config())
store = Store(session)                       # keyspace defaults to "ids"; pass cfg.cassandra_keyspace
recent = store.read_recent(300)              # ReadResult(rows, invalid, partitions), rows newest first
drift_summary(recent.rows), top_flagged(recent.rows, n=10)
store.latest_metrics("DEV-synthetic", limit=60), store.latest_runs()
db.close(cluster)
```

### Local Cassandra without the full platform
```bash
docker run -d --name ids-m4-cassandra -p 9042:9042 -e MAX_HEAP_SIZE=1G -e HEAP_NEWSIZE=256M cassandra:4.1.10
```
The full platform (Kafka, Spark, Cassandra) is started by M1: `python -m ids_ingest.platform`.

## Environment variables (from C-06)
| Variable | Default | Purpose |
|---|---|---|
| `CASSANDRA_HOSTS` | `localhost` | Store hosts |
| `CASSANDRA_PORT` | `9042` | Store port |
| `CASSANDRA_KEYSPACE` | `ids` | Keyspace |
| `RESULTS_DIR` | `./Module4_Storage_Dashboard_Benchmarking/results` | Benchmark outputs |
| `RUN_DURATION_S` | `600` | Default length of a benchmark run |
| `KAFKA_PARTITIONS`, `SPARK_WORKERS`, `RUN_ID` | see C-06 | Harness run tags |

## Layout
```
specs/   src/ids_monitor/   tests/{unit,contract,integration}/   mocks/   docs/adr/   results/
```

## Integration notes
This folder replaces the replica built by Aswin S. (playbook §8, PR-15). The replica remains in git history on `main`.
