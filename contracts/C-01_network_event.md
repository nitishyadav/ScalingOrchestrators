# Contract C-01: Network Event

| Field | Value |
|---|---|
| Contract ID | C-01 |
| Version | 1.0.0-rc.5 |
| Status | **In Review** |
| Provider (owner) | M1 — Aswin S. |
| Consumers | M3 (Kafka stream), M2 (replay dataset, golden fixture) |
| Medium | Kafka topic (JSON) + replay dataset (Parquet) |
| Machine-readable schema | `contracts/schemas/event.schema.json` |
| Validator | `ids_contracts.events` (`validate_event`, `check_event`, `validate_replay_columns`) |
| Golden fixtures | `contracts/fixtures/events_golden.jsonl` (generator: `contracts/fixtures/_gen/gen_events_golden.py`) |
| Decisions applied | ADR-003 (dataset variant), ADR-006 (timestamp semantics), ADR-007 (eval-only fields), ADR-011 (replay time model) |

## 1. Purpose
This contract defines the single unit of data that enters the pipeline: one **network event** derived from one
CIC-IDS2017 flow record, or synthesised by the attack injector. It has two forms:

- **Live form:** a JSON message on Kafka, consumed by the M3 stream job.
- **At-rest form:** the *replay dataset* (Parquet), consumed by M2 for offline training and replayed by the M1 producer.

## 2. Transport and location

### 2.1 Kafka (live form)
| Item | Value |
|---|---|
| Topic | `network-events` (env `KAFKA_TOPIC`, C-06) |
| Partitions | `KAFKA_PARTITIONS`, 1–16 (varied in E1) |
| Replication factor | 1 (single broker) |
| Retention | `retention.ms = 1800000` (30 min). At 10k ev/s this is about 4–5 GB, which bounds disk use during benchmarks |
| Message key | `src_ip` as UTF-8 bytes. All events of one source IP land on one partition, which keeps per-IP order. Partitioner: murmur2 (the Java/Spark default). Producers using librdkafka/confluent-kafka MUST set `partitioner=murmur2_random`, because librdkafka's default (`consistent_random`, CRC32) maps keys to different partitions |
| Message value | One JSON object, UTF-8, compact (no newlines), fields per §3. No envelope |
| Compression | The producer MAY use `lz4`. Consumers must accept any Kafka codec (Spark handles this transparently) |
| Kafka record timestamp | CreateTime. Informational only. **The `timestamp` field is authoritative** |

### 2.2 Replay dataset (at-rest form)
| Item | Value |
|---|---|
| Location | `${DATA_DIR}/replay/` (C-06) |
| Layout | Hive-partitioned Parquet: `day=<Monday\|Tuesday\|Wednesday\|Thursday\|Friday>/part-*.parquet` |
| Manifest | `${DATA_DIR}/replay/_manifest.json` (schema below, validator `ids_contracts.events.validate_manifest`) |
| Order | Rows are in **replay order**, given by `row_idx` (see §4.4) |

**Manifest schema** (JSON object, all keys required):

| Key | Type | Meaning |
|---|---|---|
| `contract`, `contract_version` | string | `"C-01"` and the C-01 version the dataset was built against |
| `tool`, `tool_version` | string | `"ids_ingest.prepare"` and the M1 package version |
| `created_at` | string | ISO-8601 UTC |
| `inputs` | array | One object per source file: `source_file`, `day`, `sha256`, `verified` (bool, equal to `CIC_REFERENCE`), `data_rows`, `valid_rows`, `dropped` (`{reason: count}`, reasons from `DROP_REASONS`). Invariant: `data_rows = valid_rows + Σ dropped` |
| `days` | object | `{Day: {rows, files: [source_file…], content_sha256, path}}`. `content_sha256` = SHA-256 over `"\|".join(str(v) for v in row) + "\n"` for every row in `row_idx` order, using the 10 non-partition columns in §3.4 order. It identifies the *data*, independent of Parquet encoding |
| `total_rows` | int | Equals Σ `inputs.valid_rows` and Σ `days.rows` |
| `labels` | object | `{label: count}`, summing to `total_rows` |

Two members have identical replay data **if and only if** their per-day `content_sha256` values are equal.

**Reference replay data** (prepared 2026-10-21 from the §3.2 reference inputs; also `ids_contracts.events.REPLAY_CONTENT_SHA256`).
A correctly prepared replay dataset MUST reproduce these hashes:

| Day | Rows | Reference `content_sha256` |
|---|---|---|
| Monday | 529,918 | `0c4e8d6c4d0396921692bdf74b2369fc6fb6973b33e0ded1fea8fb90db3c7bdd` |
| Tuesday | 445,909 | `83e9850002902736f7ff712e54311de90a80a3a4bdfafd48dc3ccc540289b493` |
| Wednesday | 692,703 | `27da03964e1505a7adab8dbbc9d344c28ab0ed1856cd7bcd19336110283a707a` |
| Thursday | 458,968 | `edc0c2432a87166aca81c1f6f3171061962a9feda985af94845ddf1dff7e7a95` |
| Friday | 703,245 | `43d3015a1c1be8fe34660233f137cf9945febf163c35ca3e1e51e6a6b260ca45` |


## 3. Schema

### 3.1 Event fields (live form)

| Field | Type | Req | Unit / format | Constraints | Description | Example |
|---|---|---|---|---|---|---|
| `event_id` | string | yes | UUID text | Valid UUID (any version) | Unique per emitted event. The producer uses uuid4, fixtures use uuid5 | `"3f0c…"` |
| `timestamp` | integer | yes | epoch **milliseconds**, UTC | ≥ 1 000 000 000 000 (rejects seconds by mistake) | **Emission time** set by the producer just before send (ADR-006) | `1767225600123` |
| `src_ip` | string | yes | IPv4/IPv6 text | Parses as an IP address | Source host of the flow | `"172.16.0.1"` |
| `dst_ip` | string | yes | IPv4/IPv6 text | Parses as an IP address | Destination host | `"192.168.10.50"` |
| `dst_port` | integer | yes | port | 0–65535 | Destination port | `80` |
| `bytes_sent` | integer | yes | bytes | 0 – 2^63−1 | Forward-direction payload bytes of the flow | `1032` |
| `syn_flag` | integer | yes | count | ≥ 0 | Number of SYN flags in the flow | `1` |
| `ack_flag` | integer | yes | count | ≥ 0 | Number of ACK flags in the flow | `0` |
| `orig_ts` | string or null | no | Opaque CIC text, e.g. `7/7/2017 3:56` (formats vary, never parse it) | — | Original CIC timestamp. Null or absent for injected events | `"7/7/2017 3:56"` |
| `label` | string | no, **eval-only** | enum (§3.3) | Member of the label set | Ground-truth class | `"DDoS"` |
| `is_injected` | boolean | no, **eval-only** | — | true ⇒ `label` starts with `INJ_` | Generated by the attack injector | `false` |

JSON booleans are not accepted where an integer is required (for example `syn_flag: true` is invalid).

### 3.2 Mapping from CIC-IDS2017 TrafficLabelling CSVs (provider obligation)
Header names are matched **after stripping surrounding whitespace**. The files are read as `latin-1`.

| CIC column | Event field | Transformation |
|---|---|---|
| `Source IP` | `src_ip` | trim |
| `Destination IP` | `dst_ip` | trim |
| `Destination Port` | `dst_port` | int |
| `Total Length of Fwd Packets` | `bytes_sent` | int (non-integral floats are rounded half-up) |
| `SYN Flag Count` | `syn_flag` | int |
| `ACK Flag Count` | `ack_flag` | int |
| `Timestamp` | `orig_ts` | trim, keep as text |
| `Label` | `label` | normalise per §3.3 |

Canonical source files and replay order, with `source_file` = file name without `.pcap_ISCX.csv`
(names **verified** against the downloaded files on 2026-10-21):

| Day | Files in order |
|---|---|
| Monday | `Monday-WorkingHours` |
| Tuesday | `Tuesday-WorkingHours` |
| Wednesday | `Wednesday-workingHours` |
| Thursday | `Thursday-WorkingHours-Morning-WebAttacks`, `Thursday-WorkingHours-Afternoon-Infilteration` |
| Friday | `Friday-WorkingHours-Morning`, `Friday-WorkingHours-Afternoon-PortScan`, `Friday-WorkingHours-Afternoon-DDos` |

**Reference input (verified 2026-10-21).** Every member's raw CSVs must match these checksums, so that all replicas replay identical data.
The same values are in `ids_contracts.events.CIC_REFERENCE`.

| Day | `source_file` | SHA-256 of the CSV | Data rows | Valid rows (C-01) | Attack labels |
|---|---|---|---|---|---|
| Monday | `Monday-WorkingHours` | `96f26aea87d513073769b48ce204c2921791149e1c6225f7db65a3fed7973820` | 529,918 | 529,918 | BENIGN only |
| Tuesday | `Tuesday-WorkingHours` | `ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815` | 445,909 | 445,909 | FTP-Patator 7,938 · SSH-Patator 5,897 |
| Wednesday | `Wednesday-workingHours` | `ed538e85b84181e8897dedb3d37d365982f44b27eccd67c477581a8b65f3d170` | 692,703 | 692,703 | DoS Hulk 231,073 · GoldenEye 10,293 · slowloris 5,796 · Slowhttptest 5,499 · Heartbleed 11 |
| Thursday | `Thursday-WorkingHours-Morning-WebAttacks` | `e3deaff483d18b53b100a441dff9b8919416df8876b4edcc0f0d1e4bf48397d0` | 458,968 | 170,366 | Web Attack Brute Force 1,507 · XSS 652 · Sql Injection 21 (288,602 empty rows dropped) |
| Thursday | `Thursday-WorkingHours-Afternoon-Infilteration` | `d74238e054023c8bd4d8056650463cadb25c100fb0e26ebd4272c07b5c022c4b` | 288,602 | 288,602 | Infiltration 36 |
| Friday | `Friday-WorkingHours-Morning` | `c061cd98f39d8054aeaed6244a5129a20b3985983d0d022b860ae8aa07fe8d21` | 191,033 | 191,033 | Bot 1,966 |
| Friday | `Friday-WorkingHours-Afternoon-PortScan` | `7e2ddaa80a5849ba629463296b6128436c161b4a32e8034bb5beae06b0c45e08` | 286,467 | 286,467 | PortScan 158,930 (55 %) |
| Friday | `Friday-WorkingHours-Afternoon-DDos` | `1f779b4f0d78f9225554c4de53b5a2c07912b60dcd136ee4c5c1d0d2496b7cc4` | 225,745 | 225,745 | DDoS 128,027 (57 %) |
| **Total** | | | **3,119,345** | **2,830,743** | BENIGN 2,273,097 (80.3 %) |

**Known quirks of the raw files (provider obligations):**
- Every header has leading spaces, and the column `Fwd Header Length` appears **twice**. Select the mapped columns by their stripped names; never rely on de-duplicated names.
- The Thursday WebAttacks file has 288,602 completely empty rows at the end. Drop them (reason `empty_row`).
- Web-attack labels contain the byte `\x96` in latin-1, which `normalise_label` turns into `-`.
- `Timestamp` formats are **inconsistent**: Monday uses `dd/mm/yyyy hh:mm:ss`, the other days `d/m/yyyy h:mm` with a 12-hour clock and **no AM/PM**.
  `orig_ts` is therefore kept as opaque text and **must never be parsed** (ADR-006, ADR-011).
- No IPv6 addresses and no fractional byte counts occur, although the contract allows both.

**Rows dropped** during preparation, each counted per reason in the manifest: any mapped field missing; NaN or ±Infinity;
negative numeric value; IP that does not parse; port outside 0–65535; label not in the label set after normalisation.

### 3.3 Label set (eval-only)
CIC labels, normalised by trimming and replacing the non-ASCII dash in the web-attack labels with `-`:
`BENIGN`, `DDoS`, `PortScan`, `Bot`, `Infiltration`, `Heartbleed`, `DoS Hulk`, `DoS GoldenEye`, `DoS slowloris`,
`DoS Slowhttptest`, `FTP-Patator`, `SSH-Patator`, `Web Attack - Brute Force`, `Web Attack - XSS`, `Web Attack - Sql Injection`.

Injected labels: `INJ_DDOS`, `INJ_SYNFLOOD`, `INJ_PORTSCAN`.

### 3.4 Replay dataset columns (at-rest form)

| Column | Arrow type | Description |
|---|---|---|
| `row_idx` | int64 | 0-based replay position within the day (§4.4) |
| `source_file` | string | Canonical source file stem (§3.2) |
| `orig_ts` | string | As in §3.1 |
| `src_ip` | string | As in §3.1 |
| `dst_ip` | string | As in §3.1 |
| `dst_port` | int32 | As in §3.1 |
| `bytes_sent` | int64 | As in §3.1 |
| `syn_flag` | int32 | As in §3.1 |
| `ack_flag` | int32 | As in §3.1 |
| `label` | string | As in §3.3 (eval-only) |
| `day` | string (partition column) | `Monday` … `Friday` |

`event_id`, `timestamp` and `is_injected` are **not** stored. The producer adds them at emission time
(`is_injected = false` for replayed rows).

## 4. Semantics
- **Keys and partitioning:** the Kafka key is `src_ip`, using the default murmur2 partitioner. Do not use a custom partitioner.
- **Ordering:** order is preserved per partition only. Events are approximately non-decreasing in `timestamp`.
  Consumers must tolerate out-of-order events up to the 60 s watermark (C-02).
- **Time semantics (ADR-006):** `timestamp` is producer wall-clock emission time in epoch ms UTC.
  It is the event-time column for windows (C-02) and the start point for latency (C-05). `orig_ts` is never used for windowing online.
- **4.4 Replay order (ADR-011):** within a day, rows follow the canonical file order (§3.2), then the original CSV row order.
  CIC timestamps are minute-resolution and are not reordered. The producer emits rows in `row_idx` order at a constant rate R,
  so offline training can reproduce online timing as `ts_i = t0 + i · 1000 / R`.
- **Duplicates:** delivery is at-least-once. `event_id` lets consumers deduplicate. M3 MAY ignore rare duplicates.
- **Null handling:** required fields are never null. `orig_ts` may be null or absent.
- **Eval-only fields (ADR-007):** `label` and `is_injected` exist **only** for evaluation. They MUST NOT be used in
  feature computation, rules or scoring (Constitution Art. VII). `ids_contracts.events.SCORING_FIELDS` lists the fields
  that features may read.

## 5. Examples
```json
{"event_id":"6ba7b811-9dad-11d1-80b4-00c04fd430c8","timestamp":1767225600123,"src_ip":"172.16.0.1","dst_ip":"192.168.10.50","dst_port":80,"bytes_sent":1032,"syn_flag":1,"ack_flag":0,"orig_ts":"7/7/2017 3:56","label":"DDoS","is_injected":false}
{"event_id":"0e7c2a4e-5d1b-4f6a-9b1e-2c3d4e5f6a7b","timestamp":1767225600900,"src_ip":"172.16.0.20","dst_ip":"192.168.10.50","dst_port":80,"bytes_sent":60,"syn_flag":1,"ack_flag":0,"orig_ts":null,"label":"INJ_SYNFLOOD","is_injected":true}
```

## 6. Validation
- Python: `ids_contracts.events.validate_event(evt, strict=False) -> list[str]` (empty means valid).
  `strict=True` additionally rejects unknown fields, which is how the provider tests itself.
- JSON Schema: `contracts/schemas/event.schema.json` (draft 2020-12, strict: no additional properties).
- Replay dataset: `ids_contracts.events.validate_replay_columns(mapping_of_column_to_arrow_type)`.
- Golden fixture: `events_golden.jsonl` has 126 events, 4 source IPs and one late event. See `contracts/fixtures/README.md`.
- Raw input: `ids_contracts.events.verify_cic_file(path)` checks a CSV's SHA-256 against `CIC_REFERENCE`.

## 7. Obligations
**Provider (M1) MUST**
- Emit only events that pass `validate_event(strict=True)`.
- Set `timestamp` at emission time in epoch ms, and never replay 2017 times as `timestamp`.
- Key every message by `src_ip`.
- Write the replay dataset exactly per §3.4 with a manifest.
- Keep `events_golden.jsonl` deterministic (regenerating it produces a byte-identical file).

**Consumers MUST**
- Ignore unknown fields (forward compatibility for MINOR versions).
- Treat `timestamp` as epoch ms UTC event time.
- Never read `label` or `is_injected` in the scoring path.

## 8. Error handling
| Side | Situation | Behaviour |
|---|---|---|
| M1 preparation | CSV row violates §3.2 | Drop it and count it per reason in the manifest |
| M1 producer | Event fails validation | Do not send. Log it and count it. Exit non-zero if more than 0.1 % fail |
| M3 consumer | Value is not JSON or required fields are missing or invalid | Drop the record and increment a malformed counter. Never crash the query |

## 9. Contract tests
| Side | Test | Location |
|---|---|---|
| Shared | Golden fixture passes the Python validator and the JSON Schema. Invalid cases are rejected | `contracts/python/tests/test_events.py` |
| Provider (M1) | Producer output and the replay Parquet validate | `Module1_Data_Ingestion_Platform/tests/contract/` |
| Consumer (M3) | Spark parse of `events_golden.jsonl` yields 126 rows with correct types. Malformed lines are dropped | `Module3_Spark_Stream_Processing/tests/contract/` |
| Consumer (M2) | Training loader reads the replay columns per §3.4 | `Module2_ML_Anomaly_Model/tests/contract/` |

## 10. Compatibility and versioning
MINOR: new optional fields or new labels. MAJOR: changing a type, unit or meaning, or removing or renaming a field. These follow CR rules.

## 11. Approvals
| Role | Member | Version approved | Date |
|---|---|---|---|
| Provider | Aswin S. (M1) | 1.0.0-rc.5 (author) | 2026-10-21 |
| Consumer | Kumari Priyanka (M3) | | |
| Consumer | Nitish Kumar Yadav (M2) | | |

## 12. Change log
| Version | Date | CR | Change |
|---|---|---|---|
| 1.0.0-rc.1 | 2026-10-21 | — | Initial draft for review, from playbook §5.2 |
| 1.0.0-rc.5 | 2026-10-21 | — (pre-approval) | librdkafka producers must use `partitioner=murmur2_random` (M1-F03) |
| 1.0.0-rc.4 | 2026-10-21 | — (pre-approval) | Reference per-day replay `content_sha256` (from the M1-F02 real-data run) |
| 1.0.0-rc.3 | 2026-10-21 | — (pre-approval) | Formal replay **manifest schema** + `validate_manifest` + `DROP_REASONS` (from the M1-F02 spec) |
| 1.0.0-rc.2 | 2026-10-21 | — (pre-approval) | Verified against the downloaded dataset: file names, reference SHA-256 and row counts (2,830,743 valid), raw-file quirks, `orig_ts` declared opaque. Fixture Monday dates corrected to day-first |
