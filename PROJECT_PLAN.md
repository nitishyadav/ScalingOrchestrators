# Project Plan — Real-Time Network Intrusion Detection

| | |
|---|---|
| Source proposal | `../1_PHASE_1_IDEA_GEN/des_project_proposal 3.html` |
| Plan version | 0.1 (draft for team review) |
| Date | 2026-10-21 |
| Key dates | Report due **15 Nov 2026**, live demo **29 Nov 2026** |

---

## 1. Proposal analysis

### 1.1 What we are building

```
 CIC-IDS2017 CSVs
      │
 ┌────▼─────────────┐   Kafka topic     ┌─────────────────────────┐   Cassandra      ┌──────────────────────┐
 │ Log producer     │  (1–16 parts)     │ PySpark Structured      │   time-series    │ Streamlit dashboard  │
 │ replay + attack  ├──────────────────►│ Streaming               ├─────────────────►│ throughput, anomaly  │
 │ injector         │   JSON events     │ 30 s window / 10 s slide│   anomaly sink   │ rate, top-10 IPs,    │
 └──────────────────┘                   │ 4 features / src_ip     │                  │ drift banner (>15 %) │
                                        │ rules ∥ IF (pandas_udf) │                  └──────────────────────┘
          ┌──────────────────────┐      └───────────▲─────────────┘
          │ Offline training     │  model + scaler  │
          │ (Colab, sklearn IF)  ├──────────────────┘
          └──────────────────────┘
 All services: Docker Compose, pseudo-distributed on one MacBook (M-series, 16 GB)
```

### 1.2 Design goals (traceable IDs)

| ID | Goal (from proposal §1.3) |
|---|---|
| G1 | Throughput ≥ 10,000 events/s end-to-end without falling behind |
| G2 | Detection latency p95 < 500 ms (Kafka entry → Cassandra write) |
| G3 | Genuine ML: offline sklearn Isolation Forest, broadcast, vectorised `pandas_udf`, no hardcoded thresholds in the scoring path |
| G4 | Hybrid detection: rule flag and ML flag computed separately and both stored |
| G5 | Scalability measurement: vary Kafka partitions and Spark executors independently |
| G6 | Live dashboard: throughput, anomaly rate, retraining/drift alert when > 15 % of recent windows are flagged |

### 1.3 Success metrics (traceable IDs)

| ID | Metric (from proposal §3.2–3.3) | Target |
|---|---|---|
| P1 | Sustained throughput at 16 partitions × 4 executors | ≥ 10,000 ev/s |
| P2 | p95 end-to-end latency at 5,000 ev/s | < 500 ms |
| P3 | E1 scaling efficiency, 1 → 4 partitions | ≥ 0.5 |
| P4 | E2 scaling efficiency, 1 → 4 executors | ≥ 0.5 |
| P5 | Recovery after Spark worker restart (checkpointing) | < 30 s |
| F1 | IF precision / recall on held-out CIC-IDS2017 days | ≥ 0.80 / ≥ 0.75 |
| F2 | False-positive rate on benign-only run (windows) | < 5 % |
| F3 | Rule-only vs hybrid comparison per attack category | Produced |
| F4 | Alert visible in dashboard after Cassandra write | ≤ 5 s |
| F5 | Drift banner fires when anomaly rate > 15 % | Correct |

Experiments: **E1** partitions {1, 4, 8, 16} (2 executors, 5k ev/s); **E2** executors {1, 2, 4}
(8 partitions, 5k ev/s); **E3** attack share {0, 5, 20 %} (8 partitions, 2 executors).
Each run lasts 10 min with samples every 30 s. Efficiency = (T_N / T_1) / N.

### 1.4 Issues to resolve in Phase 0 (blocking decisions)

These are gaps or inconsistencies in the proposal that would cause integration failures if each
member resolved them differently. Each one becomes an ADR in `docs/adr/` and is reflected in
the relevant contract.

| ID | Issue | Why it matters | Recommendation | Decides in |
|---|---|---|---|---|
| D-01 | **Latency target versus windowing.** With a 30 s window and 1 min watermark in *append* mode, a window is only emitted after about 90 s, so 500 ms p95 is impossible as written. | P2 cannot be met or measured without a precise definition. | Use **update** output mode and define latency = `detected_at − max(event_ts in window)`, measured per micro-batch. Report the append-mode figure separately for completeness. | C-05, M3 |
| D-02 | **Cassandra key design.** A partition key of `date_bucket` alone puts *all* of a day's writes into one partition, which creates a hotspot rather than avoiding one. Having `detected_at` in the key also creates duplicate rows per window under update mode. | Write throughput (P1) and correctness of the counts shown on the dashboard. | Key on `((date_bucket, hour, shard), window_end DESC, src_ip)` and upsert per window. M4 to finalise. | C-04, M4 |
| D-03 | **Dataset variant.** The CIC-IDS2017 *MachineLearningCVE* CSVs have no `Source IP` or `Timestamp`. Only the *GeneratedLabelledFlows / TrafficLabelling* CSVs have them. | The `src_ip` grouping key and the replay timing depend on these columns. | Use the TrafficLabelling CSVs. | C-01, M1 |
| D-04 | **Held-out split.** *(Confirmed from data 2026-10-21: PortScan only in Fri-Afternoon-PortScan (158,930); Thursday afternoon has 36 Infiltration; Monday 100 % benign.)* The proposal says "Thursday Port Scan", but PortScan is in *Friday-Afternoon-PortScan*. Thursday contains Web Attacks and Infiltration. | F1 must be evaluated on the files we actually name. | Train on Monday (benign) and part of Tue/Wed. Test on Fri-DDoS and Fri-PortScan. Confirm. | M2 |
| D-05 | **Scaling target inconsistency.** P3 (efficiency ≥ 0.5 at 4 partitions) means a **≥ 2.0×** gain, while the Week 8 milestone says **≥ 1.5×** (efficiency 0.375). | The report must not contradict itself. | Keep ≥ 0.5 as the target and ≥ 1.5× as the minimum acceptable result, and state both explicitly. | Team |
| D-06 | **Event timestamp semantics.** Replaying 2017 timestamps would break watermarks and latency. | Watermarks (M3) and latency (M4) depend on it. | The producer sets `timestamp` = emission time (epoch ms) and keeps the original as `orig_ts`. | C-01 |
| D-07 | **Ground truth in the stream.** The event schema has no label, so E3, F2 and F3 cannot be scored online. | Online evaluation needs ground truth. | Add **eval-only** fields `label` and `is_injected`. They must never be read in the scoring path (Constitution Art. VII). Window label = attack if ≥ 1 malicious event (to confirm). | C-01, C-02 |
| D-08 | **Feature formulas are underspecified.** CIC rows are *flows*, not packets, so it is unclear what `packet_rate` counts. `syn_ack_ratio` divides by zero when there are no ACKs. The mapping to `bytes_sent` is not given. | Training/serving skew silently breaks F1. | Fix exact formulas, column mappings and zero-handling in C-02, with a golden fixture. | C-02 |
| D-09 | **Version pins.** A joblib/pickle file from sklearn X may not load in sklearn Y, and Colab's version can drift. | The model must load inside Spark executors. | Pin Python, Spark (3.5.x), scikit-learn, pandas and pyarrow in `contracts/versions.md`, and train in Colab with the same pins. | C-03, C-06 |
| D-10 | **Throughput and latency transport to the dashboard.** The proposal reads throughput from the Spark listener but never says where the dashboard gets it from. | Needed for F4, G6 and the benchmark harness. | M3 writes `StreamingQueryListener` progress to a Cassandra `pipeline_metrics` table. | C-05 |
| D-11 | **Replay time model.** Online windows hold events at the *replay* rate, while offline windows built from the original 2017 timestamps hold events at the *original* rate. Rate-based features (`packet_rate`, `total_bytes`) then follow different distributions, which is training/serving skew. | F1 and F2 would silently degrade online. | The producer emits at a constant rate R. Offline training simulates the same timestamps at R_ref = 5000 ev/s. Detection quality is evaluated at R_ref. | C-01, C-02, M1, M2 |

| D-12 | **Drift metric vs attack share** *(found 2026-10-22, first end-to-end run)*. The drift banner (G6, F5) uses the share of anomalous *windows*. Windows are per source IP, so 20 % injected *events* from 7 attacker IPs among hundreds of benign IPs gives only about 2 % anomalous windows (113 / 5,223). The banner would not fire at the E3 20 % level. | F5 cannot be shown as specified. | **Resolved 2026-10-25 (ADR-013, replica):** event-weighting measured at 87–94 % at 20 % injection, so it overstates. Keep the window share, and validate F5 with a 100 % injection phase in E3 (the proposal's Week 7 milestone). | C-04 §4 (M4), M1-F04 |
| D-13 | **Latency target P2** *(measured 2026-10-22)*. At 2,000 ev/s with a 1 s trigger, the median per-batch p95 latency is **1,223 ms** (target < 500 ms). The trigger interval alone adds up to 1 s. | P2 likely not met as configured. | Profile batch time (Cassandra write, `toPandas`, UDF), try a 250–500 ms trigger, and report honestly against D-01's definition | M3 (owner), M4-F03 |

| D-14 | **F1 precision is structurally unreachable as designed** *(measured 2026-10-22, M2-F03 replica)*. On the Friday test files at R_ref, only **17 of 21,279 windows** contain attacks. All CIC attack flows come from **one source IP (172.16.0.1)**, and the 45 s replay yields about 9 attacker windows. Window-level hybrid: recall 0.941, FPR 1.2 %, **precision 0.058**. Flow-level (window verdict applied to its flows): precision about 0.60, recall 1.0, **but about 87 % of benign flows sit in flagged windows**: the 4 volume-dominated features at 5,000 ev/s compression (an 8 h day replayed in about 2 min) make busy benign hosts look like floods. Also: IsolationForest does not extrapolate (out-of-range points score like the training extremes). | The F1 target (0.80 / 0.75) cannot be met with per-`src_ip` windows + 4 volume features + this replay compression, whatever the model. | Team decision (owner M2, with M3/M4). Options: (a) report window- and flow-level metrics honestly with this analysis; (b) add rate-invariant/relative features (C-02 change: e.g. bytes per flow, SYN share, port entropy); (c) evaluate detection at a slower replay rate; (d) additional grouping (`dst_ip` windows for DDoS). **Recommend (a) now + (b) as the improvement**, since it fits the remaining time. **Resolved 2026-10-25 (ADR-012, replica):** (b) adopted. C-02 0.2.0 V3 inputs give flow P/R 0.846 / 1.000 (benign flows flagged 87 % → 23 %), and window P/R 0.112 / 0.941 with bundle 1.1.0. F1 at window level is still not met; report per (a) | C-02 (M2), M2-F03, report |

Provisional resolutions for all of D-01..D-11, which everyone builds against until the ADRs are accepted, are in
[SDD_PLAYBOOK.md §5](SDD_PLAYBOOK.md).

---

## 2. Module decomposition

The pipeline has four natural stages, so each member owns one stage end to end. Each module
consists of 4 features (`MN-F01..F04`) of roughly equal size.

### M1 — Data Ingestion and Platform · Owner: **Aswin S.** · Package `ids_ingest`

| Feature | Description | Proposal trace |
|---|---|---|
| M1-F01 Platform cluster | Docker Compose: Kafka (+ZooKeeper/KRaft), Spark master + scalable workers, Cassandra. Health checks, resource limits for the 16 GB Mac, topic admin (create/alter partitions 1–16). | G5, Wk 1–2 |
| M1-F02 Dataset preparation | Download the CIC-IDS2017 TrafficLabelling CSVs, clean them, map them to C-01 fields, write the **replay dataset** (Parquet) with labels and day splits. | D-03, Wk 1–2 |
| M1-F03 Replay producer | Configurable-rate JSON producer (target ≥ 12k ev/s so it is never the bottleneck), keyed by `src_ip`, rewrites timestamps, runs for a fixed duration. | G1, Wk 3 |
| M1-F04 Attack injector | DDoS burst, SYN flood and port-scan generators, with a configurable malicious share (0/5/20 %) and ground-truth tags. | E3, F5, Wk 3 |

**Provides:** Kafka topic data (C-01), the replay dataset (C-01 format) for M2, and the platform and control CLI (C-06).
**Consumes:** nothing (it is the upstream source).

### M2 — ML Anomaly Model · Owner: **Nitish Kumar Yadav** · Package `ids_model`

| Feature | Description | Proposal trace |
|---|---|---|
| M2-F01 EDA and window labelling | Explore the replay dataset, check feature distributions per attack type, define the window label rule. | D-04, D-07 |
| M2-F02 Reference feature builder | A pandas implementation of C-02 (30 s / 10 s windows, 4 features per `src_ip`). Produces the **golden fixture** that M3 must match. | D-08, Wk 4 |
| M2-F03 IF training and evaluation | Reproducible Colab notebook: scaler + Isolation Forest, contamination tuning, precision, recall and FPR on held-out days. | G3, F1, F2, Wk 4 |
| M2-F04 Detection bundle and rules | Package model + scaler + `manifest.json` + `rules.yaml` (C-03). Ship a **dummy bundle on day 1**. Offline rule-only vs hybrid comparison. | G3, G4, F3 |

**Provides:** the detection bundle (C-03) and the feature definition plus golden fixture (C-02).
**Consumes:** the replay dataset (C-01 format) from M1.

### M3 — Spark Stream Processing · Owner: **Kumari Priyanka** · Package `ids_stream`

| Feature | Description | Proposal trace |
|---|---|---|
| M3-F01 Stream ingest | Kafka source, JSON parse against C-01, 1 min watermark, malformed-record handling, trigger config. | Wk 5 |
| M3-F02 Windowed features | 30 s / 10 s sliding windows per `src_ip` computing the 4 C-02 features, with a parity test against the M2 golden fixture. | D-08, Wk 5 |
| M3-F03 Hybrid scoring | Broadcast the C-03 bundle, score with a vectorised `pandas_udf`, apply rules from `rules.yaml`, and emit `anomaly_score`, `ml_flag`, `rule_flag` and `is_anomaly`. | G3, G4, Wk 6 |
| M3-F04 Sink, metrics and recovery | Cassandra sink (C-04), query-progress metrics (C-05), checkpointing, worker-restart recovery < 30 s, executor/partition config knobs. | G1, G2, P5, Wk 6 |

**Provides:** anomaly rows (C-04, as producer) and pipeline metrics (C-05, owner).
**Consumes:** C-01 (Kafka), C-02 and C-03 (bundle), C-04 (schema), C-06 (config).

### M4 — Storage, Dashboard and Benchmarking · Owner: **Vidhi Kant Gupta** · Package `ids_monitor`

| Feature | Description | Proposal trace |
|---|---|---|
| M4-F01 Store schema and access | Keyspace/table DDL (C-04), init script, read repository (`cassandra-driver`), **synthetic row generator** as a mock for M3. | D-02, Wk 1–2 |
| M4-F02 Streamlit dashboard | Throughput chart, anomaly-rate gauge, top-10 flagged IPs, drift banner (> 15 % of recent windows), 3 s refresh. | G6, F4, F5, Wk 7 |
| M4-F03 Benchmark harness | Scripted E1/E2/E3 runs: sets partitions, rate, executors and attack share via C-06, runs 10 min, samples every 30 s, computes p95 latency and efficiency, saves raw results. | G5, P1–P5, Wk 8 |
| M4-F04 Results and report figures | Scaling plots, online rule-vs-hybrid table, F2 benign run, consolidated results for the report. | F2, F3, Wk 8 |

**Provides:** the store schema (C-04), dashboard, benchmark results and report figures.
**Consumes:** C-04 and C-05 (reads), C-06 (control CLI of M1 and M3).

### Effort balance check

| Module | Heavy part | Light part |
|---|---|---|
| M1 | Platform on 16 GB Mac, producer reaching ≥ 12k ev/s | Injector logic |
| M2 | Reaching F1 targets, train/serve parity | Packaging |
| M3 | Spark windowing + `pandas_udf` + checkpointing | Parsing |
| M4 | Benchmark automation and analysis | DDL |

Report writing is split by module, with each owner writing their own section. M4 assembles the results chapter.

---

## 3. Integration architecture (how plug-and-play works)

### 3.1 The only four seams

```
            C-01 events (Kafka topic)                 C-04 anomaly rows, C-05 metrics (Cassandra)
   ┌────┐ ──────────────────────────────► ┌────┐ ──────────────────────────────────────────► ┌────┐
   │ M1 │                                 │ M3 │                                             │ M4 │
   └─┬──┘                                 └─▲──┘                                             └─┬──┘
     │ C-01 replay dataset (Parquet)        │ C-02 features + C-03 detection bundle (files)    │
     ▼                                      │                                                  │
   ┌────┐ ────────────────────────────────── ┘                                                 │
   │ M2 │                                                                                      │
   └────┘           C-06 config + control CLI (env vars, producer/topic/job flags) ◄───────────┘
```

Modules never import each other's code. They meet only through a **Kafka topic**, **files**
(the replay dataset and the detection bundle), **Cassandra tables**, and **CLI/env** (C-06).
The one shared Python package is `ids_contracts` (in `contracts/python/`). It contains constants,
schema models, validators and fixtures. It contains no business logic.

### 3.2 Contract registry (written in Phase 0, details in [contracts/README.md](contracts/README.md))

| ID | Contract | Owner (provider) | Consumers | Medium |
|---|---|---|---|---|
| C-01 | Network Event Schema (+ replay dataset format) | M1 | M3, M2 | Kafka JSON / Parquet |
| C-02 | Feature Definition + golden fixture | M2 | M3 | Spec + CSV fixture |
| C-03 | Detection Bundle (model, scaler, manifest, rules) | M2 | M3 | Directory of files |
| C-04 | Anomaly Store Schema | M4 | M3 (writer) | Cassandra CQL |
| C-05 | Pipeline Metrics | M3 | M4 | Cassandra CQL |
| C-06 | Runtime Config and Control Interface | M1 | All | Env vars, CLI flags, service names, version pins |

### 3.3 Plug-and-play mechanisms

1. **Mock-first.** By the end of Phase 0 each module ships a stand-in for what it provides, so nobody waits on anybody:
   - M1: `contracts/fixtures/events_golden.jsonl` plus `producer --source fixture`
   - M2: `mocks/dummy_bundle/` (an IF trained on random data with a valid C-03 manifest)
   - M3: `mocks/fake_stream_writer.py` (writes valid C-04/C-05 rows)
   - M4: `schemas/ids_schema.cql` plus `mocks/synthetic_rows.py`
2. **Golden fixtures.** One shared input (`events_golden.jsonl`) and expected outputs
   (`features_golden.csv`, `scores_golden.csv`). Both M2's pandas implementation and M3's
   Spark implementation must reproduce them, which removes training/serving skew.
3. **Contract tests.** Each module has `tests/contract/`. A provider proves its output validates
   against the contract, and a consumer proves it accepts the golden fixtures.
4. **Uniform module interface.** Every module has a `Makefile` with the same targets:
   `install`, `test`, `contract-test`, `run`, `mock`, `clean`. The integration scripts rely only on these.
5. **Folder is the unit of exchange.** To integrate a teammate's version, replace their
   `ModuleN_*` folder in your tree and run `make contract-test` in all four modules. If everything
   passes, the swap is safe. Each member may build their own version of every module, but only
   the owner's version is canonical.
6. **Versioned contracts.** Contracts use semantic versioning. A breaking change requires a Change Request
   approved by every affected owner (template `sdd/templates/contract-change-request-template.md`).

---

## 4. Timeline (compressed to real dates)

The proposal assumed 8 weeks, but the report is due **15 Nov**, about 3.5 weeks from today. The
four modules are therefore built **in parallel against mocks** rather than in sequence.

| Phase | Dates | Goal | Exit gate |
|---|---|---|---|
| **P0 Spec and contracts** | Wed 21 – Sat 24 Oct | Ratify the constitution, resolve D-01..D-11, write and approve C-01..C-06 v1.0, write the F01/F02 specs per module | All 6 contracts **Approved v1.0**. Mocks + golden fixtures committed. |
| **P1 Parallel build** | Sun 25 Oct – Sun 1 Nov | Each module implements F01–F03 against mocks | `make test` and `make contract-test` green in each module |
| **P2 Pairwise integration** | Mon 2 – Wed 4 Nov | I-1 M1↔M3 (Kafka), I-2 M2↔M3 (bundle + feature parity), I-3 M3↔M4 (Cassandra) | Integration checklists signed |
| **P3 End-to-end + experiments** | Thu 5 – Tue 10 Nov | Real model in stream, F04 features, E1/E2/E3, recovery test, benign FPR run | Raw results saved, metrics table filled |
| **P4 Report** | Wed 11 – Sun 15 Nov | Each owner writes their module section, M4 assembles the results, team edits | **Report submitted 15 Nov** |
| **P5 Demo hardening** | 16 – 29 Nov | Push to Git, demo script, slides, rehearsal | **Live demo 29 Nov** |

Daily: 10-minute async stand-up (done / next / blocked on contract?).
Twice a week: a 30-minute sync to review open specs, CRs and integration status.

---

## 5. Traceability matrix

| Goal / metric | M1 | M2 | M3 | M4 |
|---|---|---|---|---|
| G1 / P1 throughput | F01, F03 | | F04 | F03 |
| G2 / P2 latency | F03 (timestamps) | | F04 | F03 |
| G3 genuine ML | | F03, F04 | F03 | |
| G4 hybrid | | F04 | F03 | F04 |
| G5 / P3 / P4 scaling | F01 (knobs) | | F04 (knobs) | F03, F04 |
| P5 recovery | F01 | | F04 | F03 |
| E3 attack share | F04 | | | F03 |
| F1 / F2 detection quality | F02 | F01–F03 | | F04 (online) |
| F3 rule vs hybrid | | F04 (offline) | F03 | F04 (online) |
| G6 / F4 / F5 dashboard | F04 (drive drift) | | | F02 |

---

## 6. Risks

| ID | Risk | Likelihood | Mitigation | Owner |
|---|---|---|---|---|
| R1 | 16 GB Mac cannot fit Kafka + ZK + Spark (4 executors) + Cassandra | High | Container memory limits, KRaft instead of ZK, Cassandra heap capped at 1–2 GB, producer on host | M1 |
| R2 | IF with 4 features misses F1 (0.80 / 0.75) | Medium | Contamination tuning, threshold calibration recorded in the manifest, report honestly, hybrid improves recall | M2 |
| R3 | Model pickle fails to load in the Spark image | Medium | Version pins (D-09), contract test that loads the bundle in the Spark image | M2, M3 |
| R4 | Training/serving feature skew | High if unmanaged | Golden fixture parity tests (C-02) | M2, M3 |
| R5 | Integration surprises discovered late | Medium | Mock-first, pairwise integration in P2, contract tests | All |
| R6 | `pandas_udf` / Arrow overhead limits throughput | Medium | Tune `maxRecordsPerBatch`, broadcast once, profile early | M3 |
| R7 | Timeline is compressed | High | Strict scope: P0 gates are not optional, nice-to-haves go to P5 | All |

---

## 7. Next steps (Phase 0 checklist)

- [ ] All 4 members read this plan, `CONSTITUTION.md` and `sdd/WORKFLOW.md`, then sign the constitution
- [ ] Resolve D-01..D-11 and record each as an ADR in `docs/adr/`
- [ ] Contract owners draft C-01..C-06 from `sdd/templates/contract-template.md`, consumers review, then approve v1.0
- [ ] Write `contracts/versions.md` (pins) and the golden fixtures
- [ ] Each owner writes `MN-F01` spec, plan and tasks from the templates
- [ ] Each owner ships their mock (see §3.3)
- [ ] Optional but recommended: run `git init` locally (no remote) for history until the Git push in P5
