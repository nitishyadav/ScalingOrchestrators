# Contract C-06: Runtime Config and Control Interface

| Field | Value |
|---|---|
| Contract ID | C-06 |
| Version | 1.0.0-rc.7 |
| Status | **In Review** |
| Provider (owner) | M1 — Aswin S. |
| Consumers | M2, M3, M4 (all) |
| Medium | Environment variables, CLI commands, Docker Compose service names |
| Machine-readable | `integration/.env.example`; `ids_contracts.config` (`ENV_SPEC`, `load_config`, `summary_line`) |
| Decisions applied | ADR-009 (version pins, see `contracts/versions.md`) |

## 1. Purpose
This contract fixes **how every module is configured and controlled**, so that:
- no module hardcodes a host, port, path or rate (Constitution Art. VI), and
- the M4 benchmark harness can drive M1 and M3 through stable commands and flags without importing their code.

## 2. Configuration resolution

**Precedence:** CLI flag > environment variable > default in `ids_contracts.config.ENV_SPEC`.

1. Modules read **process environment variables** only. `make run` targets load `integration/.env` if it exists
   (a local copy of `.env.example`, git-ignored).
2. Every module obtains its configuration through `ids_contracts.config.load_runtime_config(overrides=…)` (it layers `integration/.env` < process env < overrides, then calls `load_config`), which validates
   types and ranges and raises `ConfigError` on bad values. CLI flags are passed in as `overrides` keyed by env-var name.
3. **Workspace root:** relative paths are resolved against `IDS_ROOT` if set. Otherwise they are resolved against the nearest
   parent directory containing `CONSTITUTION.md`. This lets commands run from any module folder.

## 3. Environment variables

| Variable | Type | Default | Constraint | Read by |
|---|---|---|---|---|
| `IDS_ROOT` | path | auto-detected | existing directory | all |
| `KAFKA_BOOTSTRAP` | str | `localhost:9092` | `host:port[,host:port]` | M1, M3 |
| `KAFKA_TOPIC` | str | `network-events` | non-empty | M1, M3 |
| `KAFKA_PARTITIONS` | int | `8` | 1–16 | M1 (topic admin), M4 (harness tags) |
| `CASSANDRA_HOSTS` | str | `localhost` | comma-separated hosts | M3, M4 |
| `CASSANDRA_PORT` | int | `9042` | 1–65535 | M3, M4 |
| `CASSANDRA_KEYSPACE` | str | `ids` | identifier | M3, M4 |
| `SPARK_MASTER_URL` | str | `spark://localhost:7077` | `spark://…` or `local[*]` | M3 |
| `SPARK_WORKERS` | int | `2` | 1–4 (worker containers, 2 cores each) | M1 (platform), M4 (harness tags) |
| `SPARK_EXECUTORS` | int | `2` | 1–8 | M3 |
| `SPARK_EXECUTOR_CORES` | int | `1` | 1–8 | M3 |
| `SPARK_EXECUTOR_MEMORY` | str | `768m` | e.g. `512m`, `1g` (768m lets 4 executors fit the 10 GB budget, M1-F01 plan §4.4) | M3 |
| `TRIGGER_INTERVAL` | str | `1 second` | `<n> second(s)` or `<n> millisecond(s)` | M3 |
| `DATA_DIR` | path | `./runtime/data` | — | M1, M2 |
| `MODEL_BUNDLE_PATH` | path | `./runtime/bundle/current` | — | M2 (writes), M3 (reads) |
| `CHECKPOINT_DIR` | path | `./runtime/checkpoints` | — | M3 |
| `RESULTS_DIR` | path | `./Module4_Storage_Dashboard_Benchmarking/results` | — | M4 |
| `PRODUCER_RATE` | int | `5000` | 1–100000 events/s | M1 |
| `RUN_DURATION_S` | int | `600` | 1–86400 | M1, M4 |
| `ATTACK_MODE` | str | `none` | `none\|ddos\|synflood\|portscan\|mixed` | M1 |
| `ATTACK_SHARE` | float | `0.0` | 0.0–1.0. Must be 0 when the mode is `none` and > 0 otherwise | M1 |
| `RUN_ID` | str | `DEV-local` | §6 pattern | M1, M3, M4 |

Inside the compose network, the values differ only for addresses: `KAFKA_BOOTSTRAP=kafka:29092`,
`CASSANDRA_HOSTS=cassandra`, `SPARK_MASTER_URL=spark://spark-master:7077`.

## 4. Platform services (Docker Compose)

| Service | Host port(s) | In-network address | Notes |
|---|---|---|---|
| `kafka` | 9092 | `kafka:29092` | KRaft single node (M1-ADR-001). Topic auto-creation disabled, so topics come only via `topic_admin` |
| `zookeeper` | — | — | **Not used** (KRaft, M1-ADR-001) |
| `spark-master` | 7077, 8080 (UI) | `spark-master:7077` | |
| `spark-worker` | — | — | `SPARK_WORKERS` containers, 2 cores each (4 executor slots by default). Same `/workspace` (ro) + `runtime/` (rw) mounts as `spark-client`, so executors share checkpoint and data paths |
| `spark-client` | — | — | Job-submission container, same image as the workers. Workspace at `/workspace` (ro), `runtime/` rw, `IDS_ROOT=/workspace` |
| `cassandra` | 9042 | `cassandra:9042` | Heap capped (R1) |
| `dashboard` (M4) | 8501 | — | Streamlit |

Service names and host ports are part of this contract. Images, versions and resource limits are M1-internal (see `versions.md`).

## 5. Control commands (stable CLI)

All commands run as `python -m <package>.<module>`. They exit with **0** on success, **1** on a runtime error
and **2** on a usage or config error. On success they print **exactly one JSON summary line** as the last line of stdout
(`ids_contracts.config.summary_line`), with at least `{"status":"ok","command":…,"run_id":…}`.

| Command | Owner | Flags (→ env override) | Summary extra fields |
|---|---|---|---|
| `ids_ingest.platform up\|down\|status\|restart-worker\|clean` | M1 | `up --workers N` (→ `SPARK_WORKERS`), `--timeout S`; `restart-worker --index i`; `clean --yes` | `services`, `ready`, `workers` |
| `ids_ingest.prepare` | M1 | `--force` (rebuild even if up to date), `--allow-unverified` (accept checksum mismatches, recorded in the manifest), `--verify-only` (check an existing dataset), `--sample` (also write `Module1_…/mocks/replay_sample.parquet`) | `action` (`create\|rebuild\|noop\|verify`), `total_rows`, `days`, `dropped`, `elapsed_s`, `peak_rss_mb` |
| `ids_ingest.topic_admin` | M1 | `--partitions N` (→ `KAFKA_PARTITIONS`), `--recreate` | `topic`, `partitions` |
| `ids_ingest.producer` | M1 | `--source replay\|fixture`, `--rate` (→ `PRODUCER_RATE`), `--duration` (→ `RUN_DURATION_S`), `--days Monday,Friday` (default all), `--no-loop` (stop when the data runs out), `--allow-unverified` (replay data whose hashes differ from C-01 §2.2), `--attack-mode` (→ `ATTACK_MODE`), `--attack-share` (→ `ATTACK_SHARE`), `--attack-start S` (seconds from run start, default 0), `--attack-duration D` (seconds, default until the end), `--seed` (default 42; reproducible injection), `--run-id` (→ `RUN_ID`). Attack flags are replay-only | `source`, `produced`, `sent` (acknowledged), `failed`, `invalid`, `injected`, `target_rate`, `achieved_rate`, `rate_p05`, `rate_p50`, `rate_p95`, `loops`, `exhausted`, `partitions`, `duration_s`, `attack_mode`, `attack_share`, `achieved_share` (injected / produced while active), `injected_by_type`, `seed`, `attack_window_s`; `status` is `ok` or `stopped` (SIGINT/SIGTERM, still exit 0) |
| `ids_stream.job` | M3 | `--executors` (→ `SPARK_EXECUTORS`), `--trigger` (→ `TRIGGER_INTERVAL`), `--run-id`, `--await-seconds N` (stop after N s; default runs until killed) | `batches`, `rows_written` |
| `ids_monitor.bench` | M4 | `--experiment E1\|E2\|E3\|P1\|LAT\|REC`, `--levels a,b` (subset), `--duration` (→ `RUN_DURATION_S`), `--warmup S` (default 60), `--dry-run` | `experiment`, `runs` (run IDs), `failed`, `results_dir`, `report` |

Notes:
- `--recreate` deletes and recreates the topic. It is required when *reducing* partitions, because Kafka cannot shrink a topic.
- `ids_stream.job` wraps `spark-submit` and must stop gracefully on SIGTERM, flushing the current batch.
- The producer with `--source fixture` replays `contracts/fixtures/events_golden.jsonl`, rewriting `timestamp` relative to now
  while preserving the inter-event gaps. This is the M1 mock (Constitution Art. IV).

## 6. Run IDs
Pattern: `^((E1|E2|E3|P1|LAT|REC)-p\d{1,2}-e\d{1,2}-r\d+-a\d{1,3}(-t\d{1,5})?-\d{12}|DEV-[A-Za-z0-9_.-]+)$`

- Experiment runs: `E1-p4-e2-r5000-a0-202611061430` (partitions, executors, rate, attack %, `YYYYMMDDHHMM` UTC). `P1` (sustained throughput),
  `LAT` (trigger sweep, adds `-t<trigger ms>`: `LAT-p8-e2-r5000-a0-t250-202611061430`) and `REC` (recovery) are measurement runs of M4-F03
- Development runs: `DEV-<anything>`

The run ID is stored in C-04 and C-05 rows, so every result can be traced back to its configuration.

## 7. Runtime directory layout (git-ignored)
```
runtime/
├── data/raw/            CIC CSVs as downloaded
├── data/replay/         C-01 replay dataset (+ _manifest.json)
├── bundle/<version>/    C-03 bundles;  bundle/current → the active one (copy or symlink)
└── checkpoints/<query>  Spark checkpoints (M3)
```

## 8. Obligations
**Provider (M1) MUST:** keep `.env.example`, `ENV_SPEC` and this document identical in content, and provide the platform
services and commands listed in §4–§5.

**Every module MUST:** read config only via `load_config`, never hardcode values from §3, honour the exit codes and summary line,
and document the variables it reads in its README.

## 9. Contract tests
| Test | Location |
|---|---|
| Defaults load. Env and override precedence. Range and type errors. Attack-mode/share consistency. Run-ID pattern. Summary line | `contracts/python/tests/test_config.py` |
| `.env.example` keys equal `ENV_SPEC` names | `contracts/python/tests/test_config.py` |
| Each CLI: `--help` exits 0. A bad flag exits 2. The last stdout line parses as a JSON summary | each owner's `tests/contract/` |

## 10. Approvals
| Role | Member | Version approved | Date |
|---|---|---|---|
| Provider | Aswin S. (M1) | 1.0.0-rc.6 (author) | 2026-10-22 |
| Consumer | Nitish Kumar Yadav (M2) | | |
| Consumer | Kumari Priyanka (M3) | | |
| Consumer | Vidhi Kant Gupta (M4) | | |

## 11. Change log
| Version | Date | CR | Change |
|---|---|---|---|
| 1.0.0-rc.1 | 2026-10-21 | — | Initial draft for review, from playbook §5.7 |
| 1.0.0-rc.7 | 2026-10-25 | — (pre-approval) | Run IDs `P1`/`LAT`/`REC` and the optional `-t<ms>` segment; `ids_monitor.bench` flags and summary (M4-F03) |
| 1.0.0-rc.6 | 2026-10-22 | — (pre-approval) | Attack injection flags (`--seed`, `--attack-start`, `--attack-duration`) and summary fields (M1-F04) |
| 1.0.0-rc.5 | 2026-10-21 | — (pre-approval) | Producer flags `--no-loop`, `--allow-unverified` and full summary fields (M1-F03) |
| 1.0.0-rc.4 | 2026-10-21 | — (pre-approval) | Added the `ids_ingest.prepare` command (M1-F02) |
| 1.0.0-rc.3 | 2026-10-21 | — (pre-approval) | KRaft decided, so `zookeeper` is not used. Workers mount the workspace and runtime like `spark-client`. Every CLI reads `integration/.env` via `load_runtime_config` |
| 1.0.0-rc.2 | 2026-10-21 | — (pre-approval) | From the M1-F01 spec: `spark-client` service, `ids_ingest.platform` command, `SPARK_WORKERS`, `SPARK_EXECUTOR_MEMORY` default 768m |
