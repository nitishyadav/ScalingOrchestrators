# Spec: M1-F03 — Replay Producer

| Field | Value |
|---|---|
| Feature ID | M1-F03 |
| Module | Module1_Data_Ingestion_Platform |
| Owner | Aswin S. |
| Reviewers | Kumari Priyanka (M3 consumes the stream), Vidhi Kant Gupta (M4 drives it in benchmarks) |
| Status | **Verified** (2026-10-22, all 10 ACs ✅. Gates pre-approved by owner on 2026-10-21: "proceed and also go ahead and develop") |
| Version | 0.1.0 |
| Created / Updated | 2026-10-21 / 2026-10-21 |
| Proposal trace | §2.1 (Python producer re-emits flows as JSON at a configurable rate), G1, P1, P2, E1–E3, Week 3 milestone (> 5,000 ev/s) |
| Contracts touched | C-01 1.0.0-rc.5 (provides: the live event stream §2.1, §3.1), C-06 1.0.0-rc.5 (provides: `ids_ingest.producer`) |
| Decisions applied | ADR-006 (timestamp = emission time), ADR-007 (eval-only label), ADR-011 (constant-rate replay in `row_idx` order), M1-ADR-002 (confluent-kafka) |

## 1. Summary
This feature delivers the command that replays the prepared dataset into Kafka as C-01 events at a constant, configurable rate.
Each event is keyed by source IP and stamped with its emission time. It runs for a fixed duration (looping the data if needed) and
reports exactly what was delivered. A fixture mode replays the 126 golden events with their original spacing. That mode is
Module 1's stand-in for consumers.

## 2. Context and motivation
Every throughput, latency and scaling number in the project (P1–P5, E1–E3) is measured against the event stream this feature produces.
The producer must therefore be **accurate** (the rate requested is the rate delivered), **fast** (never the bottleneck: ≥ 12,000 ev/s,
so that the pipeline's 10,000 ev/s target is testable), **faithful** (C-01 events, replay order, emission timestamps) and **controllable**
(stable flags, graceful stop, a machine-readable summary for the M4 harness). The full replay lasts 9.4 min at 5,000 ev/s but only
4.7 min at 10,000 ev/s, so 10-minute runs need looping.

## 3. Scope
**In scope:** replay source (all or selected days, looping), fixture source, constant-rate pacing, event construction, delivery
accounting, validation guard, pre-flight checks, graceful stop, summary line.
**Out of scope:** attack injection (M1-F04; the `--attack-*` flags are accepted only with mode `none` until then), topic creation (`topic_admin`),
the stream processing itself (M3).

## 4. Actors and user stories
- **US-1:** As the M4 harness, I want to request an exact rate and duration and read back the delivered rate, so that E1–E3 runs are controlled and auditable.
- **US-2:** As M3, I want events that are valid C-01, keyed by `src_ip` and stamped at emission, so that partitioning, windows and latency are correct.
- **US-3:** As M3 developing without the full data, I want the golden events replayed with their exact spacing, so that my windows match the golden features.
- **US-4:** As an operator, I want to stop a run at any time without losing in-flight events, so that counts stay exact.

## 5. Functional requirements

| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M1-FR-021 | `--source replay` (default) MUST read the C-01 replay dataset in day order and then `row_idx` order, restricted to `--days` if given. It MUST refuse (exit 1) if the dataset or manifest is missing, or if its per-day `content_sha256` differs from the C-01 reference, unless `--allow-unverified` is given. | P0 | US-1, US-2 | C-01 §2.2, ADR-011 |
| M1-FR-022 | Each event MUST be built per C-01 §3.1: `event_id` (uuid4), `timestamp` = wall-clock emission time in epoch ms, the replay fields, `label`, `is_injected=false`. It is keyed by `src_ip`, compact JSON in contract field order, using the murmur2 partitioner. | P0 | US-2 | C-01 §2.1, §3.1, ADR-006 |
| M1-FR-023 | Events MUST be emitted at a constant target rate R (`--rate` / `PRODUCER_RATE`): event *i* is not emitted before `start + i/R`. | P0 | US-1 | ADR-011 |
| M1-FR-024 | The run MUST end after `--duration` seconds (`RUN_DURATION_S`). If the source is exhausted first, it MUST restart from the beginning (counting `loops`), unless `--no-loop` is given, in which case it ends with `exhausted: true`. | P0 | US-1 | — |
| M1-FR-025 | `--source fixture` MUST replay `contracts/fixtures/events_golden.jsonl` in file order, emitting each event at `start + (ts − ts₀)` and setting `timestamp = start_ms + (ts − ts₀)`, so all inter-event gaps (including the late event) are preserved exactly. It MUST ignore `--rate`, `--days` and looping. | P0 | US-3 | C-06 §5 |
| M1-FR-026 | Before sending, the producer MUST check that the broker is reachable and the topic exists, failing with exit 1 and a hint (`topic_admin`) otherwise. | P0 | US-1 | — |
| M1-FR-027 | Delivery MUST be confirmed by broker acknowledgement. The summary MUST report `produced`, `sent` (acknowledged), `failed`, `invalid`, `achieved_rate` (= sent / elapsed), the per-second rate percentiles (`rate_p05`, `rate_p50`, `rate_p95`), `loops`, `exhausted`, `partitions`, `injected` (0 until M1-F04) and `status`. The run MUST exit 1 if `(failed + invalid) / produced > 0.1 %`. | P0 | US-1 | C-01 §8 |
| M1-FR-028 | Events MUST be checked with `validate_event(strict=True)`: all in fixture mode, and in replay mode the first 1,000 plus every 1,000th. An invalid event MUST NOT be sent and MUST be counted. | P1 | US-2 | C-01 §7 |
| M1-FR-029 | SIGINT/SIGTERM MUST stop production, flush in-flight messages (≤ 30 s), print the summary with `status: "stopped"` and exit 0. | P0 | US-4 | — |
| M1-FR-030 | `--attack-mode` / `--attack-share` MUST be accepted per C-06. Any mode other than `none` MUST exit 2 with "available from M1-F04" until that feature lands. | P1 | — | C-06 §5 |

## 6. Non-functional requirements

| ID | Category | Requirement (measurable) | Trace |
|---|---|---|---|
| M1-NFR-021 | Throughput | With `--rate 12000` for 60 s at 16 partitions, `achieved_rate` ≥ 11,760 ev/s (within 2 %) and `failed = 0` | G1, P1 |
| M1-NFR-022 | Pacing accuracy | For R ∈ {1,000, 5,000}, `achieved_rate` is within ±2 % of R, and `rate_p05` ≥ 0.9·R | E1–E3 |
| M1-NFR-023 | Start-up | The first event is sent within 5 s of start | — |
| M1-NFR-024 | Memory | Peak RSS ≤ 500 MB (the dataset is streamed in batches) | R1 |
| M1-NFR-025 | Ceiling | The maximum single-process rate is measured and recorded (no target), so the report can state the producer's headroom | Art. X |

## 7. Interfaces
### 7.1 Provided
| Contract | Version | What exactly is provided |
|---|---|---|
| C-01 | 1.0.0-rc.5 | Live event stream (§2.1, §3.1). rc.5 makes the librdkafka `murmur2_random` partitioner explicit |
| C-06 | 1.0.0-rc.5 | §5 `ids_ingest.producer` flags (adds `--no-loop`, `--allow-unverified`) and summary fields |

### 7.2 Consumed
| Contract | Version | What is used | Mock until available |
|---|---|---|---|
| C-01 | rc.4+ | Replay dataset + `REPLAY_CONTENT_SHA256`, golden fixture, `encode_event`, `validate_event` | n/a |
| C-06 | rc.4+ | `load_runtime_config`, exit codes, summary line | n/a |

## 8. Data
Input: `${DATA_DIR}/replay/` (2,830,743 rows) or the 126-event fixture. Output: Kafka topic `${KAFKA_TOPIC}` (`retention.ms` 30 min).

## 9. Acceptance criteria

| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M1-F03-AC-01 | **Given** a 4-partition topic **When** replaying Monday at 5,000 ev/s for 20 s **Then** exit 0, `failed = 0`, `achieved_rate` within ±2 %, the topic holds exactly `sent` messages, and sampled messages are strict-valid C-01 keyed by `src_ip` with `timestamp` inside the run window | FR-021..FR-023, FR-027, NFR-022 | integration | ✅ `test_ac01_rate_accounting_and_validity` |
| M1-F03-AC-02 | **Given** a 1-partition topic **When** replaying Monday **Then** the consumed sequence equals the replay rows in `row_idx` order | FR-021, ADR-011 | integration | ✅ `test_ac02_single_partition_preserves_replay_order` |
| M1-F03-AC-03 | **Given** a small dataset **When** the duration exceeds one pass **Then** `loops ≥ 1` and the order restarts at row 0. **With** `--no-loop` **Then** the run ends early with `exhausted: true` | FR-024 | unit | ✅ `test_replay_order_then_loop`, `test_loops_until_duration`, `test_no_loop_ends_when_data_runs_out` |
| M1-F03-AC-04 | **Given** fixture mode **Then** all 126 events arrive, and their timestamp gaps equal the fixture's exactly, including the late event (last, 47 s behind) | FR-025 | unit + integration | ✅ `test_fixture_preserves_gaps_exactly`, `test_ac04_fixture_gaps_live` |
| M1-F03-AC-05 | **Given** 16 partitions **When** `--rate 12000` for 60 s **Then** `achieved_rate` ≥ 11,760 and `failed = 0`. The maximum rate is measured. Both are saved | NFR-021, NFR-025 | perf | ✅ `test_ac05_producer_throughput`: 11,999.6 ev/s, 0 failed. Ceiling ≥ 100k (`docs/measurements/AC-05-M1-F03-2026-10-22.json`) |
| M1-F03-AC-06 | **Given** a fake clock **When** R = 1,000 for 5 s **Then** 5,000 events are produced, timestamps never decrease, and every full second holds R ± 1 | FR-023, NFR-022 | unit | ✅ `test_constant_rate_with_fake_clock` |
| M1-F03-AC-07 | **Given** a running replay **When** SIGTERM arrives **Then** exit 0, `status: "stopped"`, `failed = 0`, and the topic holds exactly `sent` messages | FR-029 | unit + integration | ✅ `test_stop_flag`, `test_ac07_sigterm_stops_gracefully` |
| M1-F03-AC-08 | Missing topic → exit 1 with a `topic_admin` hint. Unreachable broker → exit 1 within 20 s. Missing replay dataset → exit 1 with a `prepare` hint. Non-reference data → exit 1 unless `--allow-unverified`. Bad `--days` / `--rate 0` / bad flag → exit 2. Attack mode ≠ none → exit 2 | FR-021, FR-026, FR-030 | unit + integration | ✅ `test_cli_*_exit_*`, `test_ac08_missing_topic_and_unreachable_broker` |
| M1-F03-AC-09 | **Given** a source with invalid records **Then** they are not sent and are counted. Above 0.1 %, or with failed deliveries above 0.1 %, the run exits 1 | FR-027, FR-028 | unit | ✅ `test_invalid_records_are_not_sent`, `test_cli_delivery_failures_exit_1` |
| M1-F03-AC-10 | **Given** any run **Then** the last stdout line is a C-06 summary with the FR-027 fields. `--help` exits 0 | FR-027 | contract | ✅ `tests/contract/test_c01_producer_contract.py`, `test_cli_fixture_summary`, C-06 CLI contract |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| Local producer queue full (`BufferError`) | Poll and retry, never drop silently |
| Broker restarts mid-run | librdkafka retries. Undelivered messages after the final flush count as `failed` |
| Rate above what the machine can do | Runs flat out. `achieved_rate` < R is reported honestly. Exit 0 unless deliveries fail |
| `--days` order given out of canonical order | Normalised to canonical day order |

## 11. Assumptions and dependencies
The topic is created beforehand with `topic_admin`. The replay dataset was prepared by M1-F02.

## 12. Open questions
None.

## 13. Review checklist
- [x] Every FR has an AC. NFRs measurable. Contracts referenced by version. No `[NEEDS CLARIFICATION]`
- [x] Eval-only `label` is passed through as data only (never used for any decision in the producer)
- [ ] Consumer review (M3 / M4)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | 2026-10-21 | Aswin S. (with AI) | Initial version (gates pre-approved by owner) |
| 0.1.1 | 2026-10-22 | Aswin S. (with AI) | AC-06 tolerance stated as ±1 % (bursts ≤ 2 ms can shift an event across a second boundary). Verified |
