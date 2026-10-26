# Spec: M1-F02 — Dataset Preparation

| Field | Value |
|---|---|
| Feature ID | M1-F02 |
| Module | Module1_Data_Ingestion_Platform |
| Owner | Aswin S. |
| Reviewers | Nitish Kumar Yadav (M2 trains from the replay dataset) |
| Status | **Verified** (2026-10-21, all 10 ACs ✅; M2 consumer review still requested) |
| Version | 0.1.0 |
| Created / Updated | 2026-10-21 / 2026-10-21 |
| Proposal trace | §2.3 (CIC-IDS2017, replay as JSON events), F1, F2, F3 (ground truth), G1 (replay volume) |
| Contracts touched | C-01 1.0.0-rc.3 (provides: replay dataset §2.2/§3.4 and manifest); C-06 1.0.0-rc.4 (provides: `ids_ingest.prepare` command) |
| Decisions applied | ADR-003 (TrafficLabelling), ADR-007 (eval-only labels), ADR-011 (replay order = `row_idx`) |

## 1. Summary
This feature turns the eight raw CIC-IDS2017 TrafficLabelling CSVs into the **replay dataset**: a clean, typed, ordered,
day-partitioned Parquet dataset in exactly the C-01 at-rest form, with a manifest that proves what went in and what came out.
It is the single source for the replay producer (M1-F03) and for offline training (M2), so both see exactly the same rows in exactly the same order.

## 2. Context and motivation
The raw files have quirks (padded headers, a duplicated column, 288,602 empty rows, non-ASCII label bytes, inconsistent
timestamps; see C-01 §3.2). If M1 and M2 each cleaned the CSVs their own way, training and replay would disagree, which is the
training/serving skew that ADR-011 exists to prevent. One deterministic preparation step, verified against reference checksums
and row counts, removes that risk and makes every replica reproducible.

## 3. Scope
**In scope**
- Verify raw inputs against `CIC_REFERENCE` (file present, SHA-256).
- Apply the C-01 §3.2 column mapping, normalisation and drop rules, counting drops per reason.
- Write the replay dataset (C-01 §3.4) with a contiguous `row_idx` per day and a manifest.
- Re-verify an existing replay dataset against its manifest and C-01 (`--verify-only`).
- Produce the M1 consumer mock `mocks/replay_sample.parquet` (a small labelled sample).

**Out of scope**
- Downloading the dataset (it requires a registration form, so it is a manual step).
- Window features and model training (M2). Emission timestamps and injection (M1-F03, M1-F04).

## 4. Actors and user stories
- **US-1:** As M2, I want a typed, ordered replay dataset with labels and per-file provenance, so that I can build training windows that match replay exactly.
- **US-2:** As the M1 producer, I want rows in a fixed replay order per day, so that replay is reproducible and offline timing can be simulated (ADR-011).
- **US-3:** As any team member, I want to prove my prepared data is identical to everyone else's, so that results are comparable across replicas.
- **US-4:** As a member without the full dataset yet, I want a small realistic sample, so that I can develop against C-01 immediately.

## 5. Functional requirements

| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M1-FR-011 | `prepare` MUST check that every `CIC_REFERENCE` source file is present under `${DATA_DIR}/raw/TrafficLabelling/` and that its SHA-256 matches. A missing file MUST fail (exit 1). A checksum mismatch MUST fail (exit 1) unless `--allow-unverified` is given, in which case the manifest records `verified: false` for that file. | P0 | US-3 | C-01 §3.2 |
| M1-FR-012 | Each CSV row MUST be mapped and validated exactly per C-01 §3.2 (headers stripped, latin-1, labels normalised). Invalid rows MUST be dropped and counted per reason: `empty_row`, `wrong_field_count`, `missing_field`, `non_numeric`, `nan_or_inf`, `negative`, `bad_port`, `bad_ip`, `unknown_label`. | P0 | US-1 | C-01 §3.2 |
| M1-FR-013 | Output MUST be Hive-partitioned Parquet at `${DATA_DIR}/replay/day=<Day>/`, with exactly the C-01 §3.4 columns and Arrow types. `row_idx` MUST be 0-based and contiguous per day, following the canonical file order and then the CSV row order. Rows MUST be stored in `row_idx` order. | P0 | US-1, US-2 | C-01 §3.4, ADR-011 |
| M1-FR-014 | `${DATA_DIR}/replay/_manifest.json` MUST record: contract id and version, creation time, the tool version, per input file (`source_file`, `sha256`, `verified`, `data_rows`, `valid_rows`, `dropped` by reason), per day (`rows`, `files`, `content_sha256`), `total_rows` and label counts. | P0 | US-1, US-3 | C-01 §2.2 |
| M1-FR-015 | Writing MUST be atomic. A failed or interrupted run MUST leave any previous replay dataset untouched. If the existing manifest already matches the current inputs, contract version and tool version, `prepare` MUST do nothing (`action: "noop"`) unless `--force` is given. | P1 | US-3 | — |
| M1-FR-016 | `prepare --verify-only` MUST check an existing replay dataset: schema per C-01 §3.4, row counts per day equal to the manifest, contiguous `row_idx`, `content_sha256` per day recomputed and equal. Any mismatch MUST exit 1 and name what differs. | P0 | US-3 | C-01 §6 |
| M1-FR-017 | `prepare --sample` MUST write `Module1_…/mocks/replay_sample.parquet`: a deterministic sample from the replay dataset with the C-01 §3.4 columns, containing **every label** present in the replay dataset, with at most 10,000 rows, and kept in `(day, row_idx)` order. | P1 | US-4 | Const. IV |
| M1-FR-018 | Every invocation MUST follow C-06 §5: exit codes 0/1/2 and one JSON summary line (`action`, `total_rows`, `days`, `elapsed_s`, plus `dropped` totals). | P0 | — | C-06 |

## 6. Non-functional requirements

| ID | Category | Requirement (measurable) | Trace |
|---|---|---|---|
| M1-NFR-011 | Performance | A full preparation of all 8 files takes **≤ 5 min** on the reference machine (M3, 16 GB) | — |
| M1-NFR-012 | Memory | Peak RSS **≤ 2 GB** (rows are streamed in chunks, never a whole day in memory) | R1 |
| M1-NFR-013 | Determinism | Two runs on the same inputs produce identical `content_sha256` for every day | US-3, Art. IX |
| M1-NFR-014 | Size | The replay dataset is **≤ 300 MB** on disk. The sample is **≤ 1 MB** | — |

## 7. Interfaces

### 7.1 Provided
| Contract | Version | What exactly is provided |
|---|---|---|
| C-01 | 1.0.0-rc.4 | §2.2 replay dataset layout, **manifest schema** and **reference content hashes** (formalised by this feature), §3.4 columns |
| C-06 | 1.0.0-rc.4 | §5 `ids_ingest.prepare [--force] [--verify-only] [--allow-unverified] [--sample]` |

### 7.2 Consumed
| Contract | Version | What is used | Mock used until the real one is available |
|---|---|---|---|
| C-01 | 1.0.0-rc.2 | `CIC_REFERENCE`, `CIC_COLUMN_MAP`, `normalise_label`, `LABELS`, `REPLAY_COLUMNS`, `validate_replay_columns` | n/a (shared package) |
| C-06 | 1.0.0-rc.3 | `DATA_DIR`, `load_runtime_config`, exit codes, summary line | n/a |

## 8. Data
Input: 8 CSVs, 1.1 GB, 3,119,345 data rows. Expected output: **2,830,743 rows** across 5 days. Per-file valid counts must equal
`CIC_REFERENCE`, and the label totals must equal those recorded in C-01 §3.2. The replay dataset and the raw CSVs are git-ignored under `runtime/`.
Only the small sample in `mocks/` is committed.

## 9. Acceptance criteria

| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| M1-F02-AC-01 | **Given** the verified raw CSVs **When** `prepare` runs **Then** it exits 0 with `total_rows = 2,830,743`, per-file `valid_rows` equal to `CIC_REFERENCE`, and the only drops are 288,602 `empty_row` | FR-011..014, FR-018 | integration (real data) | ✅ `test_ac01_full_dataset` (2,830,743 rows, hashes = C-01 reference) |
| M1-F02-AC-02 | **Given** a synthetic CSV with one row of each defect (empty, short row, blank field, text in a number, `NaN`, `Infinity`, negative, port 70000, bad IP, unknown label, `\x96` label, padded headers, duplicated column) **When** prepared **Then** each defect is dropped under its reason and the valid rows survive with normalised labels | FR-012 | unit | ✅ `test_defect_matrix` |
| M1-F02-AC-03 | **Given** the output **When** read back **Then** the columns and types equal C-01 §3.4 (`validate_replay_columns` is empty), `row_idx` is 0..n−1 per day in order, and every row converted to an event (adding `event_id`, `timestamp`, `is_injected=false`) passes `validate_event(strict=True)` | FR-013 | contract | ✅ `tests/contract/test_c01_replay_contract.py` |
| M1-F02-AC-04 | **Given** a missing input file **Then** exit 1. **Given** a tampered input **Then** exit 1. **With** `--allow-unverified` **Then** exit 0 and the manifest shows `verified: false` | FR-011 | unit | ✅ `test_missing_input_fails`, `test_tampered_input_fails_unless_allowed` |
| M1-F02-AC-05 | **Given** a completed run **When** run again **Then** `action: "noop"`. **With** `--force` **Then** it rebuilds with identical `content_sha256` per day | FR-015, NFR-013 | unit + integration | ✅ `test_noop_then_force_is_deterministic`, `test_ac05_rerun_is_noop_and_force_is_deterministic` |
| M1-F02-AC-06 | **Given** an existing dataset **When** a run fails midway (simulated) **Then** the previous dataset and manifest are unchanged and no temporary directory remains | FR-015 | unit | ✅ `test_failed_run_leaves_previous_dataset_intact` |
| M1-F02-AC-07 | **Given** a prepared dataset **When** `--verify-only` **Then** exit 0. **When** a Parquet file is altered or removed **Then** exit 1 naming the day | FR-016 | unit + integration | ✅ `test_verify_only_*`, `test_ac07_verify_only_on_real_data` |
| M1-F02-AC-08 | **Given** the prepared dataset **When** `--sample` **Then** `mocks/replay_sample.parquet` has ≤ 10,000 rows, all labels present in the dataset, the C-01 schema, ≤ 1 MB, and is byte-identical when regenerated | FR-017 | unit + integration | ✅ `test_sample_*`, `test_ac08_mock_sample`, contract `test_committed_mock_sample_satisfies_c01` |
| M1-F02-AC-09 | **Given** the real data **Then** the full run takes ≤ 5 min, peak RSS ≤ 2 GB, and the dataset is ≤ 300 MB | NFR-011, -012, -014 | perf (measured, saved) | ✅ `test_ac09_performance_measured`: 27.1 s · 139 MB · 34.3 MB (`docs/measurements/AC-09-M1-F02-2026-10-21.json`) |
| M1-F02-AC-10 | **Given** any invocation **When** it succeeds **Then** the last stdout line is a C-06 summary. **When** given a bad flag **Then** exit 2 | FR-018 | contract | ✅ `test_cli_*` |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| Disk full while writing | The run fails (exit 1). The temporary output is removed and the previous dataset is intact (atomicity) |
| An extra, unknown CSV in the raw folder | Ignored, and listed in the summary as `ignored_files` |
| Raw folder name with a trailing space (as downloaded) | Not handled. The documented location is `${DATA_DIR}/raw/TrafficLabelling/` and the README says to copy there |
| Contract version bump | The manifest no longer matches, so the next `prepare` rebuilds (no silent reuse) |

## 11. Assumptions and dependencies
- Raw files are placed manually (download form). A copy for the M1 owner already exists, verified 2026-10-21.
- pyarrow 17.0.0 (pinned in `versions.md`) is available on the host.

## 12. Open questions
- None blocking.

## 13. Review checklist
- [x] No implementation details beyond the contract-mandated formats
- [x] Every FR is testable and has at least one AC
- [x] Every NFR has a number and a unit
- [x] Interfaces reference contracts by ID and version
- [x] Eval-only fields: `label` is carried as data (C-01) and never used for any decision here except stratifying the mock sample
- [x] No open `[NEEDS CLARIFICATION]`
- [ ] Consumer review (M2)

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | 2026-10-21 | Aswin S. (with AI) | Initial draft |
| 0.1.0 | 2026-10-21 | Aswin S. (with AI) | Implemented and verified on the real data (see AC table) |
