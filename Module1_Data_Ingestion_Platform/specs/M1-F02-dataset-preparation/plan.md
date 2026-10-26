# Plan: M1-F02 — Dataset Preparation

| Field | Value |
|---|---|
| Feature ID | M1-F02 |
| Spec version implemented | 0.1.0 |
| Owner | Aswin S. |
| Status | **Approved** (G2, 2026-10-21) |
| Updated | 2026-10-21 |

## 1. Approach summary
A single streaming pass per day. The pass reads each CSV with Python's `csv` module (latin-1), selects the mapped columns
**by position** (so the duplicated `Fwd Header Length` cannot interfere), validates and normalises each row with the
`ids_contracts.events` helpers, and buffers valid rows into 100,000-row chunks. Each chunk is written through a `pyarrow.parquet.ParquetWriter`
into a temporary directory, and a running SHA-256 is updated over a canonical serialisation of every written row (the `content_sha256`).
After all days succeed, the manifest is written and the temporary directory is swapped in atomically. The profiling run on 2026-10-21 shows
the pure-Python pass takes about 23 s for all files, well inside the 5-minute budget, so no pandas or Spark is needed.

## 2. Technical context
| Item | Choice | Pin |
|---|---|---|
| Language | Python | 3.11 |
| CSV parsing | stdlib `csv` (latin-1, streaming) | — |
| Parquet | `pyarrow` (`ParquetWriter`, snappy, one file per day: `part-00000.parquet`) | 17.0.0 |
| Validation | `ids_contracts.events` (`normalise_label`, `LABELS`, `CIC_REFERENCE`, `verify_cic_file`, `validate_replay_columns`, `validate_event`) | C-01 rc.2 → rc.3 |

## 3. Constitution check
| Article | Compliant? | Notes |
|---|---|---|
| I Spec before code | ✅ | Spec 0.1.0 |
| II Contracts only coupling | ✅ | Output is exactly C-01 §3.4. The manifest schema is formalised in C-01 rc.3 |
| III Module isolation | ✅ | Reads `runtime/data/raw`, writes `runtime/data/replay` and `Module1/mocks/` only |
| IV Mock-first | ✅ | `mocks/replay_sample.parquet` (FR-017). `make mock` regenerates it |
| V Uniform Makefile | ✅ | `make mock` builds the sample. No new targets |
| VI Config via env | ✅ | `DATA_DIR` from C-06 |
| VII Honest ML | ✅ | Labels are carried, never used to filter valid rows. The sample stratifies by label for coverage only |
| VIII Tests from AC | ✅ | §7 |
| IX Pins, seeds | ✅ | Deterministic, no randomness. pyarrow pinned |
| X Measured claims | ✅ | AC-09 measurement saved to `docs/measurements/` |
| XI Ownership / CR | ✅ | C-01 rc.3 (manifest schema) and C-06 rc.4 (`prepare` CLI) before approval, logged in SYNC_LOG |
| XII Simplicity | ✅ | stdlib + pyarrow only |

## 4. Design

### 4.1 Components
```
raw/TrafficLabelling/*.csv ─► verify (sha256) ─► per day, in CIC_FILE_ORDER:
        csv.reader(latin-1) ─► RowCleaner (map + validate + normalise, drop counter)
              ─► chunk (100k rows) ─► ParquetWriter(tmp/day=X/part-00000.parquet) + content hasher
   ─► manifest.json (tmp) ─► atomic swap: replay → replay.old ; tmp → replay ; rm replay.old
```

| Component | File | Responsibility |
|---|---|---|
| `RowCleaner` | `src/ids_ingest/prepare.py` | Header → column positions. Row → (record, None) or (None, reason) |
| `DayWriter` | same | Chunked Arrow table creation with the exact C-01 schema, ParquetWriter, content hash, row count |
| `prepare_all` | same | Verification, iteration in canonical order, manifest, atomic swap, noop detection |
| `verify_replay` | same | `--verify-only` checks (schema, counts, contiguity, content hash) |
| `make_sample` | same | Deterministic stratified sample (FR-017) |
| CLI `main` | same | argparse, `load_runtime_config`, summary line, exit codes |

### 4.2 Requirement → component mapping
| Requirement | Component | Notes |
|---|---|---|
| FR-011 | `prepare_all` + `verify_cic_file` | |
| FR-012 | `RowCleaner` | Positions are taken from the stripped header via first occurrence. The row length is checked against the header |
| FR-013 | `DayWriter` | Schema `pa.schema([("row_idx", int64), ("source_file", string), ("orig_ts", string), ("src_ip", string), ("dst_ip", string), ("dst_port", int32), ("bytes_sent", int64), ("syn_flag", int32), ("ack_flag", int32), ("label", string)])`. `day` comes from the partition directory |
| FR-014 | `prepare_all` | Manifest schema in C-01 rc.3 §2.2 |
| FR-015 | `prepare_all` | `replay.tmp-<pid>`, `os.replace`, cleanup in `finally`. Noop if the manifest inputs, contract version and tool version all match |
| FR-016 | `verify_replay` | Recomputes the content hash by re-reading the Parquet in `row_idx` order |
| FR-017 | `make_sample` | Per label: the first `ceil(10000 / n_labels)` rows in (day, row_idx) order, capped at 10,000, sorted. Written with fixed Parquet options so the file is byte-identical when regenerated |
| FR-018 | `main` | |

**Content hash:** `sha256` over `"|".join(str(v) for v in row) + "\n"` for every row in `row_idx` order, using the 10 non-partition columns.
It is independent of Parquet encoding and metadata, so it identifies the data rather than the file.

### 4.3 File layout
```
Module1_Data_Ingestion_Platform/
├── src/ids_ingest/prepare.py
├── mocks/replay_sample.parquet            (committed, ≤ 1 MB)
├── tests/unit/test_prepare.py             (synthetic CSVs in tmp_path)
├── tests/contract/test_c01_replay_contract.py
├── tests/integration/test_prepare_real_data.py   (marker: data; skipped if raw files are absent)
└── docs/measurements/AC-09-<date>.json
```

## 5. Configuration
| Env var (C-06) | Default | Used for |
|---|---|---|
| `DATA_DIR` | `./runtime/data` | `raw/TrafficLabelling/` input, `replay/` output |
| `RUN_ID` | `DEV-local` | Summary line |

## 6. Mock and stub strategy
| Dependency | During development | Swapped at |
|---|---|---|
| Real 1.1 GB CSVs | Synthetic CSVs built in `tmp_path` with the same header quirks | Integration test (`-m data`) |
| Reference checksums | Unit tests monkeypatch `CIC_REFERENCE` to the synthetic files | Real `CIC_REFERENCE` in integration |

## 7. Test strategy
| Level | What | Maps to AC |
|---|---|---|
| Unit | Defect matrix. Verification failures. Noop/force. Atomic failure. Verify-only tamper. Sample properties and determinism. CLI exit codes | AC-02, 04, 05, 06, 07, 08, 10 |
| Contract | Read the output with pyarrow and check `validate_replay_columns`. Every row to an event passes `validate_event(strict=True)`. `row_idx` contiguous | AC-03 |
| Integration (`-m data`) | Real data: 2,830,743 rows, per-file counts, drops, label totals, verify-only, rerun noop, sample | AC-01, 05, 07, 08 |
| Performance (`-m data`) | Wall time, peak RSS (`resource.getrusage`), output size. Saved as JSON | AC-09 |

## 8. Risks and alternatives considered
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| stdlib csv + pyarrow writer | Exact control over quirks, streaming, about 23 s measured | Per-row Python | ✅ |
| `pyarrow.csv` vectorised | Faster | The duplicated header and empty rows need workarounds. Reason-level drop accounting is harder | |
| pandas `read_csv` | Familiar | Not in the host env. Duplicated column auto-renamed. Memory per day | |
| Spark | Scales | Overkill for 1.1 GB. Couples M1-F02 to the platform | |

## 9. Done means
- [ ] All tasks complete. `make test` / `make contract-test` green. `-m data` green on the real files
- [ ] Every AC ✅. AC-09 measurement saved
- [ ] C-01 rc.3 (manifest schema) and C-06 rc.4 (`prepare` command) published in SYNC_LOG
- [ ] README: how to place the raw files and run `prepare`
