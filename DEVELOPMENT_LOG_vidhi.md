# Development Log — Vidhi Kant Gupta (M4 Storage, Dashboard and Benchmarking)

An append-only record of every step taken, at every level of development (PR-20).
Never rewrite past entries. Add a correcting entry instead.

## Levels

| Level | Name | Typical steps | Procedures |
|---|---|---|---|
| L0 | Project | Proposal analysis, plan, decisions, environment readiness | PR-00, PR-03 |
| L1 | SDD framework | Workspace, constitution, workflow, templates, playbook | PR-01, PR-02 |
| L2 | Contracts | Contract docs, schemas, `ids_contracts`, golden fixtures, CRs, syncs | PR-04–06, PR-13, PR-14 |
| L3 | Module | Module README, Makefile, mocks, module ADRs | PR-12 |
| L4 | Feature | spec.md → plan.md → tasks.md, verification | PR-07–09, PR-11 |
| L5 | Task / code | TDD loop per task (`MN-Txxx`) | PR-10 |
| L6 | Integration | Module swaps, pairwise and E2E integration | PR-15, PR-16 |
| L7 | Experiments and report | E1–E3, recovery, FPR, figures, report, Git push | PR-17, PR-19 |

## Progress by level

| Level | Status | Last step | Next step |
|---|---|---|---|
| L0 Project | ✅ Oriented, owner-build plan agreed | S-001 | — |
| L1 SDD framework | 🟡 Constitution not yet signed by M4 | — | PR-02: sign the M4 row |
| L2 Contracts | 🟡 C-04 1.0.0-rc.1 In Review | S-005 | PR-05: M3 review of C-04; review C-05 |
| L3 Module | 🟡 Owner skeleton created, M4-ADR-001 Accepted | S-004 | — |
| L4 Feature | 🟡 M4-F01, F02 Verified · M4-F03 Implemented (AC-01..07) | S-011 | F03 live smoke at I-03, full runs in P3; M4-F04 |
| L5 Task / code | 🟡 F01, F02 done · F03 M4-T201..T230, T240 done | S-011 | M4-T231 (smoke), T232 (runs) |
| L6 Integration | ⬜ | — | I-03 with M3 (2–4 Nov) |
| L7 Experiments | ⬜ | — | P3 (5–10 Nov) |

## Step log

### S-001 · 2026-11-01 · L0 Project · PR-00
**What:** Oriented on the repo as M4 owner. Module 4 held a complete replica by Aswin S. (F01–F04), and C-04 was 0.1.0-replica.
Agreed on a **fresh owner build**: own specs, plans, tasks and code, with the replica used only as a reference (playbook §8).
Priority order from the calendar: C-04 → F01 → F02 (before I-03, 2–4 Nov) → F03 (before P3, 5 Nov) → F04 (report, 15 Nov).
**Why:** Playbook §8: the replica is discarded at integration and replaced by the owner's folder.
**Artifacts:** none in the repo.
**Verification:** n/a.
**Decisions / issues:** none.

### S-002 · 2026-11-01 · L3 Module · PR-01
**What:** Created branch `m4-owner`. Copied the replica to `runtime/reference/m4-replica/` (git-ignored) for reading, removed it from the
module folder on this branch, and created the owner skeleton: `specs/ src/ids_monitor/ tests/{unit,contract,integration}/ mocks/ docs/adr/ results/`,
`Makefile` (the Art. V targets; `run` and `mock` are stubs until M4-F01/F02), `pyproject.toml`, `requirements.txt` (pins from versions.md), and the README.
**Why:** Owner mode needs a clean module folder that is built feature by feature under the SDD gates.
**Artifacts:** `Module4_Storage_Dashboard_Benchmarking/*`, `DEVELOPMENT_LOG_vidhi.md`.
**Verification:** `make install && make test && make contract-test` (see the session output).
**Decisions / issues:** none.

### S-003 · 2026-11-01 · L0 Project · —
**What:** Environment readiness. Installed Python 3.11 and OpenJDK 17 (Homebrew), and created the shared `.venv` (Python 3.11).
Ran `make install` in M4 (pinned dependencies installed).
**Why:** Python 3.11 and Java 17 are required by contracts/versions.md. Before this, only Python 3.14 was present and Java was missing.
**Artifacts:** `.venv/` (git-ignored).
**Verification:** `make install` OK. `make test` and `make contract-test` collect no tests yet (the skeleton has none). `pytest contracts/python`: 103 passed.
Java 17 is keg-only and not on PATH yet. Docker daemon not running.
**Decisions / issues:** Add openjdk@17 to PATH. Start Docker before live tests.

### S-004 · 2026-11-01 · L3 Module · PR-03
**What:** Wrote and accepted **M4-ADR-001**, the partition key for `ids.window_scores`.
The decision is `((date_bucket, bucket), window_end DESC, src_ip ASC)` with `bucket = (60·hour + minute) // 5` UTC (0..287).
Options considered: keep `(date_bucket, hour)`, use hour + crc32 shard (D-02), or use a 5-minute bucket.
**Why:** D-02 left the key to M4.
C-02 windows slide every 10 s (360 `window_end` per hour), with ≈ 1.7–3k `src_ip` per `window_end` (from the M2-F03 window counts).
So an hour partition holds ≈ 0.6–1.1M rows (≈ 100–300 MB), above Cassandra's ≈ 100k-row / 100 MB guidance.
A 5-minute bucket gives ≈ 50–90k rows (12–25 MB), a drift read touches ≤ 2 partitions, and the key needs no hash parity between Spark and Python.
Cross-check: replica E1 p8 wrote 748k upserts in 600 s, which fits ≈ 140k distinct rows each upserted ≈ 5× in update mode.
**Artifacts:** `Module4_Storage_Dashboard_Benchmarking/docs/adr/M4-ADR-001-store-partition-key.md`.
**Verification:** sizing is an estimate. The live measurement (`nodetool tablehistograms`) is a follow-up in M4-F01.
**Decisions / issues:** breaking for the 0.1.0 writer (`hour` → `bucket`). The live table needs a one-time `DROP`.

### S-005 · 2026-11-01 · L2 Contracts · PR-04, PR-06
**What:** Authored **C-04 1.0.0-rc.1** (owner version, template format, status In Review).
- DDL `contracts/schemas/ids_schema.cql` uses the new key.
- `ids_contracts.store`: `BUCKET_S`, `partition_key` (5-minute), new `partition_keys(start, end)` for readers, `NULLABLE` (eval-only pair only),
  and a slide-alignment check in `validate_row`.
- C-04 tests moved out of `test_replica_contracts.py` into the owner-owned `contracts/python/tests/test_store.py`. They cover the DDL ↔ constants check,
  bucket and day boundaries, 30 `window_end`s per bucket, `partition_keys` coverage, valid and invalid rows, and the drift rule.
- Updated the contracts README registry, `SYNC_LOG.md`, and the PROJECT_PLAN D-02 row (resolved).

**Why:** PR-04, to replace the M1 replica with the owner contract before I-03 (2–4 Nov).
**Artifacts:** `contracts/C-04_anomaly_store.md`, `contracts/schemas/ids_schema.cql`, `contracts/python/ids_contracts/store.py`,
`contracts/python/tests/test_store.py`, `contracts/python/tests/test_replica_contracts.py`, `contracts/README.md`, `contracts/SYNC_LOG.md`, `PROJECT_PLAN.md`.
**Verification:** `pytest contracts/python`: **130 passed**. Before this step it was 103 passed; the new store tests replace the 2 replica store tests.
M3 tests were not run (M3 deps are not in the shared venv). By reading the code: the M3 contract test still passes because its columns are derived,
but the M3 sink `app.py:119` (`to_store` builds `hour`) and `tests/integration/test_e2e_live.py:78-79` (queries by `hour`) must change to `bucket`.
These are M3's changes, not mine (Art. III).
**Decisions / issues:** C-04 depends on ADR-013 (drift = anomalous-window share), which is still *Proposed (replica)* and is mine to accept.

### S-006 · 2026-11-01 · L2 Contracts · PR-03
**What:** Accepted ADR-013 (the drift banner keeps the anomalous-window share, > 15 % over 300 s; F5 is validated with a 100 % injection phase in E3).
**Why:** C-04 §5 depends on it, and it was a replica draft waiting for the M4 owner.
**Artifacts:** `docs/adr/ADR-013-drift-metric.md` (status).
**Verification:** n/a.
**Decisions / issues:** none.

### S-007 · 2026-11-01 · L4/L5 Feature · PR-07..PR-11
**What:** Built **M4-F01 Store schema and access** end to end: spec 1.0.0, plan, tasks M4-T001..T041, then the code.
- `schema.py`: apply/check, plus `--recreate` for the 0.1.0 key.
- `store.py`: partition-key reads per 5-minute bucket, validated writes.
- `view.py`: drift summary and top flagged IPs. It never reads labels.
- `synthetic.py`: the seeded mock of M3, including follow mode.
- `cli.py` / `db.py`: C-06 exit codes and summary line.
- `make run` = schema apply. `make mock` = synthetic data.
**Why:** M3 ↔ M4 integration (I-03, 2–4 Nov) needs the schema and a verified read path. M4-F02/F03 build on `Store` + `view`.
**Artifacts:** `Module4_…/specs/M4-F01-store-schema-access/*`, `src/ids_monitor/{cli,db,schema,store,view,synthetic}.py`, `tests/{unit,contract,integration}/*`, `Makefile`, `README.md`.
**Verification:** `make test` 43 passed. `make contract-test` 2 passed. `make integration-test` 6 passed, run on a local `cassandra:4.1.10` container `ids-m4-cassandra`.
AC-12 perf: 75,000 rows from 2 partitions in **1.48 s** (target ≤ 3 s), drift and top-N in 0.012 s.
All 12 ACs ✅. Spec status: Verified.
**Decisions / issues:** The first live run failed in the round-trip test. Two synthetic runs shared IPs and window_ends, so run b upserted over run a. That is the correct C-04 key semantics, so the fix was in the test (distinct IPs).
Note: concurrent runs that share (window, `src_ip`) overwrite each other, because `run_id` is not in the key. Experiments run one at a time.

### S-008 · 2026-11-01 · L4/L5 Feature · PR-07..PR-11
**What:** Built **M4-F02 Live dashboard**: spec 1.0.0, plan and tasks M4-T101..T140.
- `dashboard_model.py` (pure view model): medians of the last 10 qualifying batches, drift banner over the last 300 s, per-window anomaly rate, top 10 IPs,
  "as of run end" anchoring, empty states.
- `charts.py`: Altair, one y-axis per chart, dashed reference lines at 15 % and 500 ms, hover tooltips.
  Reference palette blue/orange, validated light + dark (CVD ΔE 24.7, all checks pass).
- `dashboard.py` + `dashboard_app.py`: sidebar controls, `st.fragment(run_every=3)`.
- `make run` = schema apply + Streamlit on 8501.
**Why:** G6, F4, F5. This is the centrepiece of the demo.
**Artifacts:** `Module4_…/specs/M4-F02-dashboard/*`, `src/ids_monitor/{dashboard_model,charts,dashboard,dashboard_app}.py`,
`tests/unit/{test_dashboard_model,test_charts,test_dashboard_app}.py`, `tests/integration/test_dashboard_live.py`, `Makefile`, `README.md`.
**Verification:** `make test` 63 passed. `make contract-test` 2 passed. Live tests 9 passed (F01 + F02).
- **F4 (AC-08):** write → visible worst case **3.44 s** (target ≤ 5 s).
- **AC-09:** 75,000 windows → view + 3 charts in **1.61 s** (target ≤ 2 s).
- `make run` serves on 8501 (health ok).
- AC-11 visual check: pending. The Chrome extension was not connected, so there is no screenshot yet.
**Decisions / issues:**
- The first AC-09 run counted 72,500 windows because writing 75k rows takes ≈ 10 s and "now" moved past a slide. Fixed by pinning the dashboard clock in that test.
- Altair is not pinned in versions.md: 5.5.0 is installed via streamlit 1.39. A CR to M1 could add it.
- Streamlit emits an Altair theme deprecation warning (harmless).

### S-009 · 2026-11-01 · L4/L5 Feature · PR-07..PR-11
**What:** Restyled the M4-F02 dashboard (spec 1.1.0, M4-T141), after the owner said it looked basic. The FRs and view-model logic are unchanged.
- New `ui.py` (pure HTML/CSS builders) and `.streamlit/config.toml` (dark theme).
- Layout: header with run + LIVE/ENDED badge, drift strip with icon, text and gauge, KPI tiles with a status label, trend vs the previous 10 batches and a sparkline,
  charts in cards with Chart/Data tabs, top-IP table with bars.
- `dashboard_model.py`: added `latency_status`, `anomaly_status`, previous-10 medians, IP counts.
**Why:** a professional-looking demo (29 Nov). Status is never colour alone (icon + label).
**Verification:** `make test` 74 passed. Live 9 passed. Screenshot `Module4_…/docs/img/m4-f02-dashboard.png` (headless Chrome via CDP).
**Decisions / issues:**
- **Bug found by looking at the page:** anomaly-rate bars had no zero baseline (x/x2 only), so they rendered as slivers. Fixed with `y2 = 0`, plus a regression test.
- Chart axes were in the viewer's local time while the header said UTC. All axes and tooltips are now UTC.
- Synthetic latency was 1–4.5 s (unrealistic vs P2). It is now ≈ 100–410 ms. The mock CLI adds `--jitter` (default 0.4) so the anomaly share varies per window.
  The function default stays 0, so the tests are unchanged.
- AC-07 live test was flaky: 300 s of data in a 300 s span, plus AppTest start-up time. It now writes 200 s.

### S-010 · 2026-11-01 · L4 Feature · PR-11
**What:** The owner checked the restyled dashboard at http://localhost:8501 and signed off. M4-F02 is **Verified**: AC-11 ✅, M4-T140 ticked.
**Verification:** all 11 ACs pass (spec §9).

### S-011 · 2026-11-01 · L4/L5 Feature · PR-07..PR-11
**What:** Built **M4-F03 Benchmark harness**: spec 1.0.0, plan, tasks M4-T201..T240, and **M4-ADR-002** (method).
- `bench_plan.py`: experiments E1/E2/E3/P1/LAT/REC, C-06 run IDs, commands using C-06 CLIs and flags only.
- `bench_math.py`: steady state, sustained throughput, producer-bound flag, backlog, p95, 30 s samples, efficiency, detection, drift banner, recovery.
- `bench_report.py`: raw files, a per-experiment JSON + Markdown report with checks against P1–P5, F2 and F5.
- `bench.py`: subprocess adapters, `Runner` (topic → job → registered → producer → restart → drain → stop → collect; failures and Ctrl-C), CLI.
- `make bench`.
**Why:** G5 and P1–P5. Every number in the report comes from here.
**Decisions (M4-ADR-002), from the replica's 25 Oct results:**
- E1/E2 run at a **saturating 15,000 ev/s** and use **sustained throughput**, not Spark's per-batch `processed_rows_per_sec`.
  At a fixed rate that figure mostly measures per-batch overhead, which is why the replica's E1 got *slower* with more partitions (efficiency 0.22).
- A level that keeps up with the producer is flagged, so its efficiency is a lower bound, or inconclusive if it is the baseline.
- E1 uses 4 executors. With 2, the speedup is capped at 2× and P3 can never pass.
- P2 figure = the median of per-batch p95, with the tail reported next to it.
- Only C-06 flags are used. M3's job also has `--starting-offsets` and `--shuffle-partitions`, which are not in C-06.
**Verification:** `make test` 112 passed (38 new). `make contract-test` 5 passed (3 new: `--help` 0, bad flag / unknown level / warm-up 2, dry-run summary line).
`make bench EXP=REC BENCH_ARGS=--dry-run` prints the 4 exact commands. AC-01..07 ✅.
**Issues found by the tests:**
- The job's JSON summary was not saved. Fixed.
- `--duration 60` collided with the 60 s default warm-up (the documented smoke command would have exited 2). The default is now min(60, duration / 4).
**Blocked:** AC-08 live smoke and AC-09 full runs. On this machine there is no replay data, no bundle, M1/M3 are not installed, and the Docker VM has 7.65 GB (< 10 GB budget).
`tests/integration/test_bench_live.py` is written and skips with the reason.

## Open items

| # | Item | Level | Owner | Due | Status |
|---|---|---|---|---|---|
| 1 | Sign the constitution (M4 row) | L1 | Vidhi | 2 Nov | Open |
| 2 | C-04 1.0.0-rc.1 + M4-ADR-001 key sizing, then send to Priyanka (M3) | L2 | Vidhi | 2 Nov | Authored (S-004, S-005). **Send to Priyanka** |
| 3 | Review C-05 as a consumer | L2 | Vidhi | 2 Nov | Open |
| 4 | M3 review and approval of C-04 1.0.0-rc.1. M3 sink and e2e test move `hour` → `bucket`. Drop the live table once | L2 | Priyanka / Vidhi | 2 Nov | Open |
| 5 | Accept or replace ADR-013 (drift metric, replica draft) | L2 | Vidhi | 2 Nov | Done (S-006) |
| 6 | M4-F01: init detects the 0.1.0 key (`--recreate`) — done (S-007). Still to do: measure partition sizes at the real rate during I-03 | L4 | Vidhi | 3 Nov | Partly done |
| 7 | M4-F02 AC-11: open http://localhost:8501 and sign off (screenshot added in S-009) | L4 | Vidhi | 2 Nov | Done (S-010) |
| 8 | CR to M1: pin altair 5.5.0 in versions.md (it comes in via streamlit) | L2 | Vidhi | 3 Nov | Open |
| 9 | M4-F03 live smoke (AC-08) on the platform: needs replay data, bundle, M1/M3 installed, ≥ 10 GB Docker | L4 | Vidhi | 4 Nov (I-03) | Open |
| 10 | M4-F03 full runs E1, E2, E3, P1, LAT, REC (AC-09, ≈ 3.5 h) | L7 | Vidhi | 10 Nov | Open |
