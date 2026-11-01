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
| M4-F01 Store schema and access | specs/M4-F01-store-schema-access/ | Not started |
| M4-F02 Live dashboard | specs/M4-F02-dashboard/ | Not started |
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
make mock   # synthetic C-04/C-05 rows (M4-F01)
make run    # schema + dashboard (M4-F01, M4-F02); needs env from C-06
```

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
