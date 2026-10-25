# Module 1 — Data Ingestion and Platform

| | |
|---|---|
| Owner | **Aswin S.** |
| Python package | `ids_ingest` |
| Status | **Complete**: M1-F01 ✅ · M1-F02 ✅ · M1-F03 ✅ · M1-F04 ✅ (owner-verified; awaiting team review) |
| Contracts owned | C-01 Network Event (rc.1), C-06 Runtime Config and Control (rc.2), `versions.md` (rc.2), all In Review |
| Contracts consumed | none (upstream source) |

## Purpose
This module stands up the pseudo-distributed platform (Kafka, Spark, Cassandra on Docker Compose),
turns the CIC-IDS2017 flows into contract-conformant events, and replays them into Kafka at a
controlled rate, with on-demand attack injection.

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M1-F01 Platform cluster (compose, health checks, resource limits, topic admin 1–16 partitions) | [specs/M1-F01-platform-cluster/](specs/M1-F01-platform-cluster/spec.md) | ✅ Verified (11/11 ACs) |
| M1-F02 Dataset preparation (TrafficLabelling CSVs → replay Parquet) | [specs/M1-F02-dataset-preparation/](specs/M1-F02-dataset-preparation/spec.md) | ✅ Verified (10/10 ACs) |
| M1-F03 Replay producer (rate-controlled, keyed by `src_ip`, timestamp rewrite) | [specs/M1-F03-replay-producer/](specs/M1-F03-replay-producer/spec.md) | ✅ Verified (10/10 ACs) |
| M1-F04 Attack injector (DDoS, SYN flood, port scan; 0/5/20 % share) | [specs/M1-F04-attack-injector/](specs/M1-F04-attack-injector/spec.md) | ✅ Verified (9/9 ACs) |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Event stream on Kafka | C-01 | M3 | `python -m ids_ingest.producer --source fixture` (126 golden events, exact gaps) |
| Replay dataset (Parquet) | C-01 | M2 | `mocks/replay_sample.parquet` (8,046 rows, all 15 labels) |
| Platform + control CLI | C-06 | All, M4 harness | compose file usable standalone |

## Consumes ← providers
None.

## Quick start

**One-time engine setup** (M1-ADR-003). Use either engine.
```bash
# Colima (CLI): Homebrew install, then
brew install colima docker docker-compose
mkdir -p ~/.docker && echo '{"cliPluginsExtraDirs":["/opt/homebrew/lib/docker/cli-plugins"]}' > ~/.docker/config.json
colima start --cpu 6 --memory 10 --disk 60 --vm-type vz        # `colima stop` to free the RAM
# Docker Desktop: Settings → Resources → 6 CPUs, 10 GB memory
```

**Module commands** (from this folder; the workspace venv `../.venv` is used automatically)
```bash
make install          # ids-contracts + this package (Python 3.11)
make test             # unit + static compose checks (no Docker needed)
make contract-test    # C-06 doc ↔ compose ↔ CLI agreement
make run              # = python -m ids_ingest.platform up   (first run builds the Spark image, about 5–10 min)
make integration-test # live tests on the running platform (AC-01..AC-08)
```

**Platform control** (C-06 §5. Each command prints one JSON summary line; exit codes 0 ok / 1 runtime / 2 usage)
```bash
python -m ids_ingest.platform up [--workers 1..4] [--timeout 180]
python -m ids_ingest.platform status
python -m ids_ingest.platform restart-worker --index 1     # recovery tests (P5)
python -m ids_ingest.platform down                         # keeps Kafka/Cassandra data
python -m ids_ingest.platform clean --yes                  # also deletes the data volumes
python -m ids_ingest.topic_admin --partitions 8 [--recreate]
```

**Submitting a Spark job (M3).** Always submit from `spark-client`, so the driver's Python matches the workers (ADR-009):
```bash
docker compose -p ids -f Module1_Data_Ingestion_Platform/platform/docker-compose.yml \
  exec spark-client spark-submit /workspace/<path-to-your-job>.py
```
Inside the platform: workspace at `/workspace` (read-only), `runtime/` writable, `IDS_ROOT=/workspace`,
`KAFKA_BOOTSTRAP=kafka:29092`, `CASSANDRA_HOSTS=cassandra`. The Kafka and Cassandra connector jars are already on the classpath,
so don't use `--packages`.

**Memory budget** (M1-F01 plan §4.4): kafka 1.25 G · cassandra 2 G · spark-master 0.5 G · 2 × spark-worker 2.25 G · spark-client 1.25 G = 9.5 GiB.
Defaults: 2 workers × 2 cores = 4 executor slots at `SPARK_EXECUTOR_MEMORY=768m`.

**Dataset preparation (M1-F02).** The CIC download needs a registration form, so it is a manual step.
```bash
# 1. Put the 8 TrafficLabelling CSVs here (names must be exact; see C-01 §3.2):
#    runtime/data/raw/TrafficLabelling/*.pcap_ISCX.csv
python -m ids_ingest.prepare                 # checks SHA-256 → runtime/data/replay/day=<Day>/part-00000.parquet + _manifest.json
python -m ids_ingest.prepare --verify-only   # re-checks schema, row counts and content hashes against the manifest
python -m ids_ingest.prepare --sample        # (or `make mock`) refreshes mocks/replay_sample.parquet
make data-test                               # real-data acceptance tests (about 75 s)
```
The expected result is 2,830,743 rows (Mon 529,918 · Tue 445,909 · Wed 692,703 · Thu 458,968 · Fri 703,245). Each day's `content_sha256` must
equal C-01 §2.2, which proves your replay data is identical to everyone else's. Measured: 27 s, 139 MB RAM, 34 MB on disk.

Reading it (M2): `pyarrow.dataset.dataset("runtime/data/replay", format="parquet", partitioning="hive")`. Rows per day are in `row_idx` (replay) order.

**Replay producer (M1-F03).** Create the topic first, then replay:
```bash
python -m ids_ingest.topic_admin --partitions 8
python -m ids_ingest.producer --rate 5000 --duration 600              # all days, loops if the data runs out
python -m ids_ingest.producer --days Friday --rate 10000 --duration 60 --run-id DEV-friday
python -m ids_ingest.producer --source fixture                        # M1 mock for M3: the 126 golden events, exact gaps (~88 s)
```
Events are C-01 JSON keyed by `src_ip` (murmur2 partitioner), `timestamp` = emission time, `is_injected=false`. The last stdout line is the
C-06 summary (`sent`, `failed`, `achieved_rate`, `rate_p05/p50/p95`, `loops`, …). SIGINT/SIGTERM stops gracefully (`status: "stopped"`, exit 0).
Measured: 11,999.6 ev/s at `--rate 12000` (60 s, 16 partitions, 0 failed). The ceiling is ≥ 100,000 ev/s (the C-06 maximum).

**Attack injection (M1-F04).** Mixed into the replay at an exact share of all events, optionally in a time window:
```bash
python -m ids_ingest.producer --rate 5000 --duration 600 --attack-mode synflood --attack-share 0.05      # E3: 5 %
python -m ids_ingest.producer --rate 5000 --duration 600 --attack-mode mixed --attack-share 0.20         # E3: 20 %
python -m ids_ingest.producer --rate 5000 --duration 180 --attack-mode ddos --attack-share 0.3 \
       --attack-start 60 --attack-duration 60                                                           # drift demo: attack from 60 s to 120 s
```
| Mode | Sources (RFC 5737, never in the CIC data) | Signature (victim 192.168.10.50) | Label |
|---|---|---|---|
| `ddos` | 203.0.113.10–11 | port 80, 1,000–3,000 bytes, ACK | `INJ_DDOS` |
| `synflood` | 198.51.100.20–23 | port 80, 0–60 bytes, SYN without ACK | `INJ_SYNFLOOD` |
| `portscan` | 192.0.2.30 | ports 1→65535 sweep, 0 bytes, SYN without ACK | `INJ_PORTSCAN` |
| `mixed` | all of the above | cycles ddos → synflood → portscan | — |

Injected events have `is_injected=true` and `orig_ts=null`. Replay events are never dropped, reordered or read (Art. VII). `--seed` (default 42) makes
injection reproducible. The summary adds `achieved_share`, `injected_by_type` and `attack_window_s`. Measured: 11,999.6 ev/s at 12k with mixed 20 % (144,000 injected).

## Environment variables read (C-06)
`IDS_ROOT`, `DATA_DIR`, `KAFKA_BOOTSTRAP`, `KAFKA_TOPIC`, `KAFKA_PARTITIONS`, `SPARK_WORKERS`, `PRODUCER_RATE`, `RUN_DURATION_S`, `ATTACK_MODE`, `ATTACK_SHARE`, `RUN_ID`, plus `integration/.env` if present.
