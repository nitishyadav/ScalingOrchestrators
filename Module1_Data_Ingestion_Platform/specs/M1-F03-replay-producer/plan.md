# Plan: M1-F03 — Replay Producer

| Field | Value |
|---|---|
| Feature ID | M1-F03 |
| Spec version implemented | 0.1.0 |
| Owner | Aswin S. |
| Status | **Approved** (G2 pre-approved 2026-10-21) |

## 1. Approach summary
A single-process producer built from three swappable parts. A **source** yields C-01 record dicts (from the replay Parquet in batches,
or from the golden fixture with time offsets). A **pacer** decides when event *i* may go out. A **sink** wraps the confluent-kafka
`Producer` and counts acknowledgements. The main loop stamps each record (uuid4 and emission time), samples it through `validate_event`,
JSON-encodes it via `ids_contracts.events.encode_event` and sends it, keyed by `src_ip`. The clock is injected, so pacing is unit-tested
deterministically. M1-F04 will plug an injecting source wrapper in front of the same loop.

## 2. Technical context
| Item | Choice |
|---|---|
| Kafka client | `confluent-kafka==2.6.1`: `linger.ms=5`, `compression.type=lz4`, `acks=1`, `partitioner=murmur2_random` (matches the Java/Spark default, C-01 rc.5), `broker.address.family=v4` (avoids the Colima IPv6 warning, open item #12), `queue.buffering.max.messages=500000` |
| Parquet | `pyarrow` `ParquetFile.iter_batches(batch_size=8192)` |
| Pacing | Event *i* is due at `t0 + i/R` (monotonic clock). Sleep only when more than 2 ms ahead (bursts ≤ 2 ms, so the long-run average is exact) |
| Timestamps | `time.time_ns() // 1_000_000` at emission (replay). `start_ms + offset` (fixture) |

## 3. Constitution check
| Article | ✅ | Notes |
|---|---|---|
| I Spec before code | ✅ | Gates pre-approved by the owner |
| II Contracts only | ✅ | Emits exactly C-01. CLI per C-06 rc.5 |
| III Isolation | ✅ | Reads `runtime/data/replay` and `contracts/fixtures`. Imports only `ids_contracts` |
| IV Mock-first | ✅ | `--source fixture` is M1's live mock for M3 |
| V Makefile | ✅ | No new standard targets |
| VI Config via env | ✅ | `KAFKA_*`, `PRODUCER_RATE`, `RUN_DURATION_S`, `ATTACK_*`, `RUN_ID`, `DATA_DIR` |
| VII Honest ML | ✅ | `label` passed through, never read for decisions |
| VIII Tests from AC | ✅ | §6 |
| IX Pins | ✅ | No new dependencies |
| X Measured claims | ✅ | AC-05 saved under `docs/measurements/` |
| XI Ownership / CR | ✅ | C-01 rc.5, C-06 rc.5 pre-approval, logged |
| XII Simplicity | ✅ | No new infrastructure |

## 4. Design
| Component | File | Responsibility |
|---|---|---|
| `ReplaySource` | `src/ids_ingest/producer.py` | Manifest check (exists, valid, reference hashes unless allowed), iterate days → batches → records, loop or exhaust |
| `FixtureSource` | same | Yields `(offset_ms, record)` from the golden fixture |
| `Clock` | same | `monotonic()`, `wall_ms()`, `sleep()`; `FakeClock` in tests |
| `KafkaSink` | same | `check()` (broker/topic → partitions), `send(key, value)` with BufferError retry, delivery counters, `flush()` |
| `run()` | same | Pacing loop, stamping, validation sampling, stop flag, per-second histogram → `RunStats` |
| `main()` | same | argparse, `load_runtime_config`, signal handlers, summary, exit codes |

Requirement mapping: FR-021 → `ReplaySource`. FR-022 → `make_event` + `KafkaSink` config. FR-023/024 → `run()`. FR-025 → `FixtureSource` +
`run(mode="fixture")`. FR-026 → `KafkaSink.check`. FR-027 → `RunStats` + `main`. FR-028 → `should_validate(i)`. FR-029 → signal → stop flag →
flush. FR-030 → `main`.

## 5. Contract updates (before code)
- **C-01 rc.5** §2.1: producers using librdkafka MUST set `partitioner=murmur2_random` (the librdkafka default `consistent_random` hashes differently).
- **C-06 rc.5** §5 producer row: add `--no-loop` and `--allow-unverified`; summary fields as FR-027.

## 6. Test strategy
| Level | What | AC |
|---|---|---|
| Unit (`FakeClock`, `FakeSink`) | Event build, replay order/days/loop/exhaust, reference check, pacing distribution, fixture offsets, validation guard, failure threshold, stop flag, attack-mode guard, CLI codes | AC-03, 04, 06, 07, 08, 09 |
| Contract | Every event from the committed mock sample → strict C-01. Key = `src_ip`. Compact JSON. Sink config has `murmur2_random`. CLI `--help`/bad flag | AC-10 |
| Integration (`docker`) | Live topic: rate/accounting/validity, order on 1 partition, fixture gaps, SIGTERM, missing topic, broker down | AC-01, 02, 04, 07, 08 |
| Performance (`docker and perf`) | 12k ev/s × 60 s at 16 partitions. Max rate for 20 s. Saved JSON | AC-05 |

## 7. Risks
| Risk | Mitigation |
|---|---|
| The Python per-event cost limits the rate | Batch decoding (8,192 rows), sample-only validation, no per-event sleep. Measured in AC-05 |
| The librdkafka partitioner differs from Java's | Explicit `murmur2_random` (C-01 rc.5) |
