# SDD Playbook — Real-Time Network Intrusion Detection

**Team Scaling Orchestrators · DES, IISc · 2026**

This is the single document every team member, and every member's AI assistant, follows to build
the project with **Spec-Driven Development (SDD)**. Together with the project proposal
(`des_project_proposal.html`), it holds everything needed to:

1. Recreate the identical workspace (folders, rules, templates). See the Appendix.
2. Build a **complete personal version of the whole pipeline** (all 4 modules) before integration.
3. Keep every personal version **plug-compatible** with everyone else's, so that at integration each
   module can be swapped for its owner's canonical copy without code changes.

> Generated file. Edit `sdd/playbook_core.md` or the source files, then run `bash sdd/build_playbook.sh`.

---

## 0. How to use this document

### For humans
1. Give your AI assistant two files: **this playbook** and **the project proposal**.
2. Paste the starter prompt below and fill in your name and module.
3. Approve the work at every **gate** (§3). The AI stops and asks you at each one.
4. When an owner publishes an approved contract or module, run **PR-14 / PR-15** to sync.

### Starter prompt (copy, fill in, paste)

```text
You are my engineering assistant on a 4-person team project built with Spec-Driven Development.
Attached are: (1) the project proposal (des_project_proposal.html) and (2) SDD_PLAYBOOK.md.

I am <YOUR NAME>. I OWN module <M1|M2|M3|M4>. I will also build REPLICA versions of the other
three modules so that I can run the complete pipeline locally before team integration.

My workspace root is: <ABSOLUTE PATH>
Already done: <nothing | list of procedures/specs already completed>
Contracts I have received from owners: <none | C-0x vY.Z, ...>

Follow SDD_PLAYBOOK.md §1 (AI instructions) strictly. Start with procedure PR-00.
```

---

## 1. Instructions for AI assistants (normative)

If you are an AI assistant reading this document, these rules override your defaults.

1. **Sources of truth, in order:** approved contracts in `contracts/` → this playbook (including the Appendix files)
   → the proposal. If the proposal conflicts with a decision here (§5.1), follow this playbook and say so.
2. **Use the canonical names in §4 exactly.** Never rename folders, packages, Make targets, topics,
   tables, columns, environment variables, CLI flags or feature IDs. Invented names break integration.
3. **Follow SDD order.** Contract → spec → plan → tasks → code. Do not write production code for a feature
   until its `spec.md`, `plan.md` and `tasks.md` exist and the human has approved them (gates G1–G3, §3).
4. **Stop at every gate** and ask the human for approval. Present a short summary, open questions and what comes next.
5. **Work one task at a time** (`MN-Txxx`). Write the test for the task's acceptance criterion first, then the code.
   Tick the task in `tasks.md`. If you commit, cite the task ID in the commit message.
6. **Respect module boundaries** (Constitution Art. III). While working inside `ModuleN_*`, do not edit other modules.
   Never import another module's package. The only shared import is `ids_contracts`.
7. **Do not edit `contracts/` freely.** In *owner mode* you may draft the contracts your human owns.
   In *replica mode* you may create **provisional** contracts from §5, marked `Status: Provisional (replica)`.
   Never mark a contract `Approved` unless the human confirms that all owners approved it.
8. **Replica modules are clearly labelled.** Put this as the first line of every non-owned module's README:
   `> REPLICA built by <name>. Canonical owner: <owner>. Will be replaced at integration.`
9. **Keep it honest (Art. VII).** No hardcoded detection thresholds in code. Eval-only fields (`label`,
   `is_injected`, `label_*`) are never used for features or scoring. Never fabricate metrics.
10. **Ask before** installing system-wide software, pulling large Docker images, downloading the dataset (about 2 GB),
    deleting files, or anything outside the workspace root.
11. **Mark unknowns** as `[NEEDS CLARIFICATION: …]` in specs and ask the human. Never guess silently.
12. **End every working session** with a status block (PR-18 format) and append the steps taken to `DEVELOPMENT_LOG.md` (PR-20).

---

## 2. Project at a glance

```
            C-01 events (Kafka "network-events")       C-04 window_scores · C-05 pipeline_metrics (Cassandra "ids")
   ┌────┐ ───────────────────────────────────► ┌────┐ ─────────────────────────────────────────────► ┌────┐
   │ M1 │                                      │ M3 │                                                │ M4 │
   └─┬──┘                                      └─▲──┘                                                └─┬──┘
     │ C-01 replay dataset (Parquet)              │ C-02 features + C-03 detection bundle (files)        │
     ▼                                            │                                                      │
   ┌────┐ ────────────────────────────────────────┘                                                      │
   │ M2 │                       C-06 env vars + control CLI (partitions, rate, attack, executors) ◄──────┘
   └────┘
```

| Module | Folder | Owner | Package | Owns contracts |
|---|---|---|---|---|
| M1 Data Ingestion and Platform | `Module1_Data_Ingestion_Platform` | Aswin S. | `ids_ingest` | C-01, C-06, `versions.md` |
| M2 ML Anomaly Model | `Module2_ML_Anomaly_Model` | Nitish Kumar Yadav | `ids_model` | C-02, C-03 |
| M3 Spark Stream Processing | `Module3_Spark_Stream_Processing` | Kumari Priyanka | `ids_stream` | C-05 |
| M4 Storage, Dashboard and Benchmarking | `Module4_Storage_Dashboard_Benchmarking` | Vidhi Kant Gupta | `ids_monitor` | C-04 |

The full analysis, features per module, timeline, decisions and risks are in **Appendix A2 (`PROJECT_PLAN.md`)**.
The binding rules are in **Appendix A3 (`CONSTITUTION.md`)**.

---

## 3. The SDD method in one page

```
CONSTITUTION ─► PROJECT_PLAN ─► CONTRACTS ─► spec.md ─► plan.md ─► tasks.md ─► code + tests ─► verify ─► integrate
   (rules)       (goals, IDs)   (seams)      (WHAT)     (HOW)      (steps)     (one task       (ACs)     (checklist)
                                                                                at a time)
```

| Gate | Passes when | Who approves |
|---|---|---|
| **G0 Contract** | Contract complete, schema + validator + golden fixture exist | Provider + all consumers (replica: human, marked Provisional) |
| **G1 Spec** | No `[NEEDS CLARIFICATION]`, every FR has an AC, consumer reviewed | Owner + one consumer owner |
| **G2 Plan** | Constitution Check all ✅, FR→component map complete | Owner |
| **G3 Tasks** | Tasks ≤ ½ day, file paths, FR/AC refs, dependencies | Owner |
| **G4 Verify** | `make test` + `make contract-test` green, all ACs ✅ | Owner |
| **G5 Integrate** | Integration checklist signed by both sides | Both owners |

IDs: `MN-Fxx` feature · `MN-FR-xxx` / `MN-NFR-xxx` requirement · `MN-Fxx-AC-xx` acceptance ·
`MN-Txxx` task · `C-0x` contract · `CR-xxx` change request · `ADR-xxx` decision · `I-0x` integration ·
`D-xx` open decision. Full rules are in **Appendix A4 (`sdd/WORKFLOW.md`)**.

---

## 4. Canonical names (must not deviate)

### 4.1 Workspace tree

```
<root>/                                   e.g. 2_PHASE_2_PROJECT_DEVELOPMENT/
├── README.md  PROJECT_PLAN.md  CONSTITUTION.md  SDD_PLAYBOOK.md  DEVELOPMENT_LOG.md  .gitignore
├── sdd/        WORKFLOW.md, templates/ (9 templates), playbook_core.md, build_playbook.sh
├── contracts/  README.md, C-0x_*.md, versions.md, SYNC_LOG.md, changes/, schemas/, fixtures/, python/ids_contracts/
├── integration/ README.md, checklists/, e2e/, docker-compose.yml, .env.example
├── docs/adr/   ADR-xxx-<slug>.md
├── runtime/    (git-ignored) data/raw, data/replay, bundle/<version>, bundle/current, checkpoints
└── Module{1..4}_<name>/
    ├── README.md  Makefile  requirements.txt
    ├── specs/MN-Fxx-<slug>/{spec.md, plan.md, tasks.md}
    ├── src/<package>/   tests/{unit,contract,integration}/   mocks/   docs/adr/
```

### 4.2 Feature folders (exact)

| M1 | M2 | M3 | M4 |
|---|---|---|---|
| `M1-F01-platform-cluster` | `M2-F01-eda-window-labelling` | `M3-F01-stream-ingest` | `M4-F01-store-schema-access` |
| `M1-F02-dataset-preparation` | `M2-F02-reference-features` | `M3-F02-windowed-features` | `M4-F02-dashboard` |
| `M1-F03-replay-producer` | `M2-F03-if-training-eval` | `M3-F03-hybrid-scoring` | `M4-F03-benchmark-harness` |
| `M1-F04-attack-injector` | `M2-F04-detection-bundle` | `M3-F04-sink-metrics-recovery` | `M4-F04-results-analysis` |

### 4.3 Contract files, shared code ownership and mocks

| Contract | File | Schema / fixture files | `ids_contracts` module | Owner |
|---|---|---|---|---|
| C-01 | `C-01_network_event.md` | `schemas/event.schema.json`, `fixtures/events_golden.jsonl` | `events.py` | M1 |
| C-02 | `C-02_feature_definition.md` | `fixtures/features_golden.csv` | `features.py` | M2 |
| C-03 | `C-03_detection_bundle.md` | `schemas/manifest.schema.json`, `schemas/rules.schema.json`, `fixtures/scores_golden.csv` | `bundle.py` | M2 |
| C-04 | `C-04_anomaly_store.md` | `schemas/ids_schema.cql` | `store.py` | M4 |
| C-05 | `C-05_pipeline_metrics.md` | `schemas/metrics_schema.cql` | `metrics.py` | M3 |
| C-06 | `C-06_runtime_config_control.md` | `integration/.env.example` | `config.py` | M1 |

Mocks each owner ships (Constitution Art. IV):

| Module | Mock | Purpose |
|---|---|---|
| M1 | `contracts/fixtures/events_golden.jsonl`, `Module1_…/mocks/replay_sample.parquet`, `producer --source fixture` | Events without the real dataset |
| M2 | `Module2_…/mocks/dummy_bundle/` | Valid C-03 bundle (IF fit on synthetic data) |
| M3 | `Module3_…/mocks/fake_stream_writer.py` | Writes valid C-04 and C-05 rows without Spark |
| M4 | `contracts/schemas/ids_schema.cql`, `Module4_…/mocks/synthetic_rows.py` | Schema plus dashboard data without the pipeline |

### 4.4 Make targets (every module, Art. V)
`install` · `test` · `contract-test` · `run` · `mock` · `clean`

### 4.5 Runtime names (provisional defaults, final in C-06)

| Item | Value |
|---|---|
| Kafka topic | `network-events`, message key = `src_ip` |
| Cassandra keyspace / tables | `ids` / `window_scores` (C-04), `pipeline_metrics` and `runs` (C-05) |
| Compose services | `kafka` (+ `zookeeper` if not KRaft), `spark-master`, `spark-worker`, `cassandra` |
| Ports (host) | Kafka 9092 (internal `kafka:29092`), Cassandra 9042, Spark master 7077, Spark UI 8080, Streamlit 8501 |
| CLI: topic admin | `python -m ids_ingest.topic_admin --partitions N [--recreate]` |
| CLI: producer | `python -m ids_ingest.producer --source replay\|fixture --rate 5000 --duration 600 --attack-mode none\|ddos\|synflood\|portscan\|mixed --attack-share 0.0 --run-id ID` |
| CLI: stream job | `python -m ids_stream.job --executors 2 --trigger "1 second" --run-id ID` (wraps `spark-submit`) |
| CLI: benchmark | `python -m ids_monitor.bench --experiment E1\|E2\|E3 [--dry-run]` |
| CLI: dashboard | `streamlit run Module4_Storage_Dashboard_Benchmarking/src/ids_monitor/dashboard.py` |
| Run ID format | `<E1\|E2\|E3\|DEV>-p<partitions>-e<executors>-r<rate>-a<attack%>-<YYYYMMDDHHMM>` |

---

## 5. Provisional contract baseline v0.1

> **Status: PROVISIONAL.** These are the defaults every replica builds against, so that independent builds
> are compatible from day one. Each owner turns their section into the real contract (PR-04). Where the approved
> v1.0 differs, the approved contract wins and everyone re-syncs (PR-14).
>
> **Already published drafts supersede this section:** C-01 1.0.0-rc.5, C-06 1.0.0-rc.6 and `versions.md` 1.0.0-rc.3
> (M1, 2026-10-21). Their full text, the `ids_contracts` package (events + config), the tests and the fixture generator are in the
> Appendix. Recreate them verbatim, then run `python contracts/fixtures/_gen/gen_events_golden.py` to obtain a **byte-identical**
> `events_golden.jsonl`. Verify with `cd contracts/python && python -m pytest`, which must report 71 passed.

### 5.1 Provisional resolution of open decisions (see PROJECT_PLAN §1.4)

| ID | Provisional resolution |
|---|---|
| D-01 | Output mode **update**, trigger 1 s. Latency per written row = `detected_at − max_event_ts`. Report p50/p95 per batch (C-05). Append-mode latency is reported separately for reference. |
| D-02 | `window_scores` partition key `(date_bucket, hour)`, clustering `window_end DESC, src_ip`. A window row is upserted on every update. |
| D-03 | Use CIC-IDS2017 **TrafficLabelling** (GeneratedLabelledFlows) CSVs. |
| D-04 | Train on Monday (benign only). Validate on Tue–Thu. Test (F1) on **Friday-Afternoon-DDoS** and **Friday-Afternoon-PortScan**. |
| D-05 | Target efficiency ≥ 0.5 at 4 partitions. Minimum acceptable ≥ 1.5× gain. The report states both. |
| D-06 | `timestamp` = producer emission time (epoch ms, UTC). The original time is kept in `orig_ts`. |
| D-07 | Eval-only `label` + `is_injected` on events. A window is an attack window if **any** event in it has `label ≠ "BENIGN"`. |
| D-08 | Formulas are fixed in §5.3. `packet_rate` = events (flows) per second in the window. |
| D-09 | Pins in §5.8. |
| D-10 | Spark writes per-batch progress to `ids.pipeline_metrics`. The dashboard and harness read from there. |
| D-11 | **Replay time model.** The producer emits records in original order at a constant rate R. Offline training simulates the same timestamps: `ts_i = t0 + i·1000/R_ref` with **R_ref = 5000 ev/s**. Detection quality (F1–F3, E3) is evaluated at R_ref. E1/E2 measure throughput only. |

### 5.2 C-01 Network Event (owner M1)

Kafka topic `network-events`, key `src_ip` (UTF-8), value = one JSON object per event (UTF-8, no envelope).

| Field | Type | Req | Meaning / mapping from CIC TrafficLabelling column (strip header whitespace) |
|---|---|---|---|
| `event_id` | string (UUID4) | yes | Unique per emitted event |
| `timestamp` | int64 epoch ms UTC | yes | Emission time set by the producer (D-06) |
| `src_ip` | string IPv4 | yes | `Source IP` |
| `dst_ip` | string IPv4 | yes | `Destination IP` |
| `dst_port` | int 0–65535 | yes | `Destination Port` |
| `bytes_sent` | int64 ≥ 0 | yes | `Total Length of Fwd Packets` |
| `syn_flag` | int ≥ 0 | yes | `SYN Flag Count` |
| `ack_flag` | int ≥ 0 | yes | `ACK Flag Count` |
| `orig_ts` | string | no | Original `Timestamp` text |
| `label` | string | no, **eval-only** | `Label` (e.g. `BENIGN`, `DDoS`, `PortScan`). Injected events use `INJ_DDOS`, `INJ_SYNFLOOD`, `INJ_PORTSCAN` |
| `is_injected` | bool | no, **eval-only** | true if generated by the attack injector |

Example:
```json
{"event_id":"9b2f…","timestamp":1767225600123,"src_ip":"172.16.0.1","dst_ip":"192.168.10.50",
 "dst_port":80,"bytes_sent":1032,"syn_flag":1,"ack_flag":0,"orig_ts":"7/7/2017 3:56","label":"DDoS","is_injected":false}
```
Rules: rows with an unparseable IP, port, or negative/NaN/Infinity numeric values are dropped by M1 during preparation.
Consumers ignore unknown fields. **Replay dataset** (for M2): `runtime/data/replay/day=<Monday|Tuesday|…>/part-*.parquet`.
It contains all fields above except `event_id` and `timestamp`, plus `day` and `row_idx` (original order), sorted by `row_idx`.

### 5.3 C-02 Feature Definition (owner M2)

| Item | Definition |
|---|---|
| Event time | `timestamp` (ms) → timestamp type |
| Windows | Sliding, length **30 s**, slide **10 s**, aligned to the Unix epoch. An event at `t` belongs to the windows starting at `floor(t/10s)·10s − k·10s` for k ∈ {0, 1, 2}, each covering `[start, start+30s)` |
| Watermark | 60 s on event time |
| Group key | (`window_start`, `window_end`, `src_ip`) |
| `total_bytes` | `sum(bytes_sent)` → int64 |
| `unique_ports` | exact distinct count of `dst_port` → int (Spark streaming: `size(collect_set(dst_port))`, because `countDistinct` is not supported in streaming) |
| `syn_ack_ratio` | `sum(syn_flag) / (sum(ack_flag) + 1)` → float64 |
| `packet_rate` | `count(*) / 30.0` → float64 (events per second) |
| Auxiliary (not model inputs) | `event_count = count(*)`, `max_event_ts = max(timestamp)` |
| Model input order | **`[total_bytes, unique_ports, syn_ack_ratio, packet_rate]`** |
| Window ground truth (eval-only) | `label_attack = any(label ≠ "BENIGN")`, `label_type` = most frequent non-benign label, or `BENIGN` |
| Golden fixtures | Input `events_golden.jsonl`. Expected output `features_golden.csv` (one row per window × src_ip, sorted by window_start, src_ip). Float tolerance 1e-9 |

### 5.4 C-03 Detection Bundle (owner M2)

```
runtime/bundle/<bundle_version>/        # MODEL_BUNDLE_PATH points at one of these (or bundle/current)
├── model.joblib     # sklearn Pipeline([("scaler", StandardScaler()), ("iforest", IsolationForest(...))])
├── manifest.json
└── rules.yaml
```
`manifest.json` fields: `bundle_version`, `created_at`, `python_version`, `sklearn_version`, `numpy_version`,
`feature_order` (must equal C-02), `score_definition` (`"anomaly_score = -model.score_samples(X); higher = more anomalous"`),
`threshold` (ml_flag = anomaly_score ≥ threshold), `training` (`data`, `seed`, `n_estimators`, `contamination`, `R_ref`),
`metrics` (`precision`, `recall`, `fpr`, `test_files`), `contract_versions` (`{"C-02": "…", "C-03": "…"}`).

`rules.yaml`:
```yaml
version: 1
combine: any                       # rule_flag = true if any rule fires
rules:
  - id: R-SYN-FLOOD
    all: [{feature: syn_ack_ratio, op: ">=", value: 5.0}]
  - id: R-PORT-SCAN
    all: [{feature: unique_ports, op: ">=", value: 50}]
  - id: R-DDOS-RATE
    all: [{feature: packet_rate, op: ">=", value: 100.0}, {feature: unique_ports, op: "<=", value: 3}]
```
(The values are placeholders that M2 tunes. Operators: `>=`, `>`, `<=`, `<`, `==`.)
Decision: `ml_flag` from the threshold, `rule_flag` from the rules, **`is_anomaly = ml_flag OR rule_flag`**. All three are stored.
The dummy bundle has `bundle_version = "0.0.0-dummy"` and is fit on synthetic data with seed 42.

### 5.5 C-04 Anomaly Store (owner M4)

```sql
CREATE KEYSPACE IF NOT EXISTS ids
  WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

CREATE TABLE IF NOT EXISTS ids.window_scores (
  date_bucket    text,        -- 'YYYY-MM-DD' of window_end, UTC
  hour           int,         -- 0..23 of window_end, UTC
  window_end     timestamp,
  src_ip         text,
  window_start   timestamp,
  total_bytes    bigint,
  unique_ports   int,
  syn_ack_ratio  double,
  packet_rate    double,
  event_count    int,
  anomaly_score  double,
  ml_flag        boolean,
  rule_flag      boolean,
  rule_ids       text,        -- comma-separated ids of rules that fired, '' if none
  is_anomaly     boolean,
  max_event_ts   timestamp,
  detected_at    timestamp,   -- set by the sink at write time, UTC
  bundle_version text,
  run_id         text,
  label_attack   boolean,     -- eval-only
  label_type     text,        -- eval-only
  PRIMARY KEY ((date_bucket, hour), window_end, src_ip)
) WITH CLUSTERING ORDER BY (window_end DESC, src_ip ASC)
  AND default_time_to_live = 604800;
```
Writes are idempotent upserts (same key = same window). Write consistency `LOCAL_ONE`.
Drift rule for the dashboard (G6): over rows with `window_end` in the last **300 s**,
`anomaly_rate = count(is_anomaly) / count(*)`. Show the drift banner if it is **> 0.15**.

### 5.6 C-05 Pipeline Metrics (owner M3)

```sql
CREATE TABLE IF NOT EXISTS ids.pipeline_metrics (
  run_id                 text,
  batch_ts               timestamp,
  batch_id               bigint,
  input_rows             bigint,
  input_rows_per_sec     double,
  processed_rows_per_sec double,
  batch_duration_ms      bigint,
  latency_p50_ms         double,   -- over rows written in this batch: detected_at - max_event_ts (D-01)
  latency_p95_ms         double,
  latency_max_ms         double,
  windows_written        int,
  anomalies_written      int,
  kafka_partitions       int,
  executors              int,
  PRIMARY KEY ((run_id), batch_ts)
) WITH CLUSTERING ORDER BY (batch_ts DESC);

CREATE TABLE IF NOT EXISTS ids.runs (
  bucket      text,         -- always 'all'
  started_at  timestamp,
  run_id      text,
  config_json text,         -- partitions, executors, rate, attack mode/share, bundle_version, trigger
  PRIMARY KEY ((bucket), started_at)
) WITH CLUSTERING ORDER BY (started_at DESC);
```
The stream job writes one `runs` row at start and one `pipeline_metrics` row per micro-batch.

### 5.7 C-06 Runtime Config and Control (owner M1)

`integration/.env.example` (every module reads only these names):
```dotenv
KAFKA_BOOTSTRAP=localhost:9092          # inside compose network: kafka:29092
KAFKA_TOPIC=network-events
KAFKA_PARTITIONS=8
CASSANDRA_HOSTS=localhost               # inside compose network: cassandra
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ids
SPARK_MASTER_URL=spark://localhost:7077
SPARK_WORKERS=2
SPARK_EXECUTORS=2
SPARK_EXECUTOR_CORES=1
SPARK_EXECUTOR_MEMORY=768m
TRIGGER_INTERVAL=1 second
DATA_DIR=./runtime/data
MODEL_BUNDLE_PATH=./runtime/bundle/current
CHECKPOINT_DIR=./runtime/checkpoints
RESULTS_DIR=./Module4_Storage_Dashboard_Benchmarking/results
PRODUCER_RATE=5000
RUN_DURATION_S=600
ATTACK_MODE=none
ATTACK_SHARE=0.0
RUN_ID=DEV-local
```
CLI flags override the env vars and are listed in §4.5. Every CLI exits non-zero on failure and prints one JSON summary line on success.

### 5.8 Version pins (provisional `contracts/versions.md`, owner M1)

| Component | Pin |
|---|---|
| Python | 3.11 (Spark images and local). In Colab, install the pins below with `pip` before training |
| PySpark / Spark | 3.5.x (one exact patch, same in image and local) |
| Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.12:<spark version>` |
| Cassandra connector | `com.datastax.spark:spark-cassandra-connector_2.12:3.5.x` |
| scikit-learn | 1.5.2 (**identical in Colab and Spark workers**) |
| numpy / pandas / pyarrow | 1.26.4 / 2.2.x / ≥ 15 |
| Kafka / Cassandra images | Official Apache images: Kafka 3.7+ (KRaft allowed per R1), Cassandra 4.1 |
| Python libs | `kafka-python` or `confluent-kafka` (M1 chooses), `cassandra-driver` 3.29.x, `streamlit` 1.3x, `pytest` 8.x, `jsonschema` 4.x, `pyyaml` 6.x |

Spark worker images **must include** scikit-learn, numpy, pandas and pyarrow at these pins, because `pandas_udf` runs on the workers.

---

## 6. Procedures

Each procedure lists **When**, **Who**, **Steps** and **Done when**. "AI" means your assistant does the step and you approve it.

### PR-00 — Orient (first session of any AI assistant)
- **When:** the first time an assistant joins. **Who:** AI + human.
- **Steps:**
  1. Read the proposal and this whole playbook, including the Appendix.
  2. Ask the human the starter-prompt questions they have not answered: name, owned module, workspace path, what is done, contracts received.
  3. Restate in at most 10 lines: the owned module, the replica modules, the current phase (PROJECT_PLAN §4), and which D-xx decisions are provisional or approved.
  4. Propose the next procedure to run (usually PR-01).
- **Done when:** the human confirms the summary.

### PR-01 — Bootstrap the workspace
- **When:** once per member. **Who:** AI.
- **Steps:**
  1. Create the tree in §4.1, including every `ModuleN_*` folder with `specs/ src/<package>/ tests/{unit,contract,integration}/ mocks/ docs/adr/`, plus `runtime/`. Add `.gitkeep` to empty folders.
  2. Write every file in the **Appendix** verbatim at its stated path.
  3. Add `runtime/` to `.gitignore` if it is missing.
  4. Optional: run `git init` locally, with no remote until Phase 5.
  5. List the tree and compare it with §4.1.
- **Done when:** the tree matches and no code exists yet.

### PR-02 — Ratify the constitution
- **When:** Phase 0, once for the team. **Who:** all 4.
- **Steps:** read `CONSTITUTION.md`, raise objections as ADRs, then each member fills their signature row. Every member copies the signed version into their workspace.
- **Done when:** 4 signatures, and every workspace has the same file.

### PR-03 — Record a decision (ADR)
- **When:** for each D-xx, and for any choice with alternatives. **Who:** the proposer drafts, the team decides at a sync.
- **Steps:**
  1. Copy `sdd/templates/adr-template.md` to `docs/adr/ADR-0xx-<slug>.md` (project-wide) or `ModuleN/docs/adr/MN-ADR-0xx-<slug>.md`.
  2. Fill in the context and options. Use the §5.1 provisional resolution as the default option.
  3. After the decision, set the status to `Accepted` and update the affected contracts and specs.
- **Done when:** the ADR is Accepted and the follow-ups are listed.

### PR-04 — Author a contract
- **When:** Phase 0. **Who:** the contract owner in owner mode. In replica mode, the AI drafts it as Provisional.
- **Steps:**
  1. Copy `sdd/templates/contract-template.md` to `contracts/C-0x_<name>.md`.
  2. Fill it in from §5.x. Every field gets a type, unit, constraints and an example. Time semantics and error handling are explicit.
  3. Write the machine-readable schema in `contracts/schemas/` and the validator in `contracts/python/ids_contracts/<file>.py`.
  4. Create or refresh the golden fixture (PR-06).
  5. Owner mode: set the status to `In Review` and send it to the consumers (PR-05). Replica mode: set `Status: Provisional (replica)`.
- **Done when:** the provider contract test passes on the fixture.

### PR-05 — Review and approve a contract
- **When:** a contract is In Review. **Who:** every consumer owner.
- **Reviewer checklist:**
  - [ ] Could I build my side using only this document, its schema and its fixture?
  - [ ] All fields typed, with units and nullability?
  - [ ] Keys, ordering, time semantics, duplicates and error handling stated?
  - [ ] Eval-only fields identified?
  - [ ] Matches the PROJECT_PLAN decisions and ADRs?
- **Steps:** comment inline as `> **[Initials]:**`. The owner resolves the comments. Each consumer fills the Approvals row. The owner sets `1.0.0 Approved` and distributes it (PR-14).
- **Done when:** all consumers have approved.

### PR-06 — Build the shared contract package and golden fixtures
- **When:** Phase 0, alongside PR-04. **Who:** each contract owner for their files (§4.3). In replica mode, the AI builds all of them.
- **Steps:**
  1. Package layout: `contracts/python/pyproject.toml` (name `ids-contracts`) and `contracts/python/ids_contracts/{__init__,events,features,bundle,store,metrics,config}.py`. These contain constants, dataclass/pydantic models and `validate_*` functions only. No business logic.
  2. Every module installs it with `pip install -e ../contracts/python`.
  3. `events_golden.jsonl` (M1) is deterministic: about 120 events, epoch base `1767225600000` (2026-01-01T00:00:00Z), spanning 0–90 s, and 4 source IPs. It includes a benign IP, a port-scan IP (many distinct `dst_port` values), a SYN-heavy IP (`syn_flag=1`, `ack_flag=0`) and a high-rate IP. Labels are set accordingly.
  4. `features_golden.csv` (M2) is produced only by the M2 reference feature builder from `events_golden.jsonl`.
  5. `scores_golden.csv` (M2) is produced by scoring `features_golden.csv` with the dummy bundle.
- **Done when:** `pytest contracts/python` passes and every fixture validates.

### PR-07 — Specify a feature (gate G1)
- **When:** before any feature work. **Who:** the feature owner and AI.
- **Steps:**
  1. `mkdir ModuleN_*/specs/MN-Fxx-<slug>`. Copy the spec, plan and tasks templates into it and rename them to `spec.md`, `plan.md` and `tasks.md`.
  2. Fill in `spec.md`: **WHAT and WHY only**. Use requirement IDs, measurable NFRs, a Given/When/Then AC for every FR, and contract references by ID and version.
  3. Mark every unknown `[NEEDS CLARIFICATION]` and resolve each with the human.
  4. Have a consumer-module owner review it (in replica mode, the human reviews), then set the status to `Approved`.
- **Done when:** the review checklist in the spec template is fully ticked.

### PR-08 — Plan a feature (gate G2)
- **Steps:** fill in `plan.md`: technical context with pins, a Constitution Check (every article), components, an FR→file map, configuration (C-06 names only), the mock strategy and the test strategy. Write an ADR for any significant choice.
- **Done when:** the Constitution Check is all ✅ or each ❌ has an approved ADR.

### PR-09 — Break a feature into tasks (gate G3)
- **Steps:** fill in `tasks.md` in phases: Setup → Tests first → Core → Mock/Integration → Polish. Each task is ≤ ½ day, names its files, lists dependencies and FR/AC references, and is marked `[P]` if it can run in parallel.
- **Done when:** every FR and AC is covered by at least one task.

### PR-10 — Implement a task (TDD loop)
- **When:** one task at a time. **Who:** AI, with the human approving each task.
- **Steps:**
  1. Pick the next unblocked task and state its ID, files and the AC it serves.
  2. Write or extend the test that encodes the AC. Run it and confirm it **fails**.
  3. Write the minimal code to make it pass. Use C-06 config only, and import only `ids_contracts` across modules.
  4. Run `make test` and `make contract-test` for this module.
  5. Tick the task, fill in "Done", and log any blocker. If using git, commit with `MN-Txxx: <summary>`.
- **Done when:** the tests are green and the task is ticked. Then stop and report (PR-18 format).

### PR-11 — Verify a feature (gate G4)
- **Steps:** run all tests. Fill in the spec's AC table with ✅ and test references (manual checks need evidence, such as a screenshot or query output). Update the module README (run steps, env vars). Set the spec status to `Verified`.
- **Done when:** every AC is ✅.

### PR-12 — Ship or update a mock
- **When:** before others need your output, and after any contract change. **Who:** the provider.
- **Rules:** the mock is contract-conformant (validated by your provider contract test), deterministic (fixed seeds) and runnable with `make mock`. Announce the update to the team with the contract version.

### PR-13 — Change an approved contract (CR)
- **Steps:**
  1. Copy `sdd/templates/contract-change-request-template.md` to `contracts/changes/CR-xxx-<slug>.md`.
  2. Fill in the motivation, the diff, the SemVer type and the impact per module.
  3. Get approval from all affected owners (all 4 for MAJOR).
  4. The owner applies it: bump the version, update the schema, fixtures and validator, and add a change-log line. Then distribute it (PR-14).
- **Never** edit an approved contract without a CR (PATCH typo fixes excepted).

### PR-14 — Sync canonical contracts (until Git exists)
- **When:** an owner publishes a new contract version. **Who:** every member.
- **Steps:**
  1. The owner sends a zip with `contracts/C-0x_*.md`, the related `schemas/` and `fixtures/` files, and their `ids_contracts/<file>.py`.
     The simplest form is the whole folder from the workspace root: `zip -r contracts_<date>.zip contracts -x '*/__pycache__/*'`.
  2. Each receiver **replaces** those files in their tree. Do not hand-merge them.
  3. Run `make contract-test` in **all four** module folders and fix your replica modules where needed.
  4. Add a line to `contracts/SYNC_LOG.md`: date, contract, version, sender.
- **Done when:** all contract tests are green on the new version.

### PR-15 — Swap in a teammate's canonical module
- **Steps:**
  1. Confirm that both trees have identical `contracts/` (compare SYNC_LOG entries and versions).
  2. Move your replica `ModuleN_*` aside and put the owner's folder in its place. Do not merge them.
  3. Run `make install && make test && make contract-test` in every module.
  4. Run the relevant integration checklist (PR-16).
- **Done when:** everything is green. If anything fails, the failing side fixes it, or raises a CR if the contract is wrong.

### PR-16 — Pairwise integration
- **When:** Phase 2/3 (I-01 to I-04, see `integration/README.md`). **Who:** both owners.
- **Steps:** copy `sdd/templates/integration-checklist-template.md` to `integration/checklists/I-0x-<slug>.md`. Run the pre-checks, then the steps, then the acceptance checks (including one failure or restart case). Log issues and route contract gaps to PR-13. Both owners sign.

### PR-17 — Run an experiment
- **When:** Phase 3. **Who:** the M4 owner runs the harness, and the others support it.
- **Rules:** experiments run **only** through `python -m ids_monitor.bench`. The run ID follows §4.5. Raw outputs and the full config are saved under `RESULTS_DIR/raw/<run_id>/`. Nothing is hand-edited (Art. X). A failed run is kept and labelled, never silently re-run.

### PR-18 — Status reporting
Each member, daily, and every AI at the end of each session:
```text
[Name | Module | Date]
Done:     M1-T004, M1-T005 (M1-F03 tests green)
Next:     M1-T006
Blocked:  waiting for C-04 v1.0 (Vidhi) | none
Contracts in my tree: C-01 1.0.0, C-02 0.1-prov, ...
```

### PR-20 — Keep the development log
- **When:** after every meaningful step, and at the latest at the end of every working session. **Who:** each member (the AI writes it, the human checks it).
- **Steps:**
  1. On the first session, create `DEVELOPMENT_LOG.md` at the workspace root from `sdd/templates/development-log-template.md`.
  2. For every step, append an entry `S-xxx · date · level · procedure` with **What / Why / Artifacts / Verification / Decisions**.
     Levels: L0 Project, L1 SDD framework, L2 Contracts, L3 Module, L4 Feature, L5 Task/code, L6 Integration, L7 Experiments/report.
  3. Update the "Progress by level" table and the "Open items" table.
  4. The log is append-only. Correct mistakes with a new entry and never rewrite old ones.
- **Done when:** every file change in the session is covered by an entry.

### PR-19 — Prepare the Git push (Phase 5)
- [ ] All contracts Approved; `contracts/` identical across members
- [ ] Only **canonical** modules in the repo (replicas removed)
- [ ] `runtime/`, datasets, checkpoints and large models are git-ignored; scripts that recreate them are included
- [ ] Every module: README run steps, `make test` and `make contract-test` green
- [ ] Results in `RESULTS_DIR` match the report numbers
- [ ] Integration checklists I-01 to I-04 signed

---

## 7. Building the full pipeline on your own (replica build order)

Every member builds all four modules locally. Give your **own** module full depth. **Replica** modules
must be contract-conformant but can be minimal.

| Step | Work | Minimal replica depth (if not your module) | Checkpoint |
|---|---|---|---|
| 1 | PR-00 → PR-01 → PR-03 (provisional) | — | Workspace matches §4.1 |
| 2 | PR-04 + PR-06 for C-01..C-06 (provisional from §5) | All six | `pytest contracts/python` green |
| 3 | M1-F01 platform cluster | Compose with 4 services + topic admin | All containers healthy |
| 4 | M4-F01 schema + access | DDL applied + `synthetic_rows.py` | Tables exist |
| 5 | M1-F02 dataset preparation | One CSV day → replay Parquet | Parquet validates against C-01 |
| 6 | M1-F03 replay producer | Fixture + replay at a set rate | Console consumer sees events |
| 7 | M2-F02 reference features | pandas windowing → `features_golden.csv` | Fixture produced |
| 8 | M2-F04 (part 1) dummy bundle | `mocks/dummy_bundle/` | Bundle validates |
| 9 | M3-F01 + M3-F02 ingest + features | Spark output equals `features_golden.csv` | Parity test green |
| 10 | M3-F03 hybrid scoring | Dummy bundle + rules via `pandas_udf` | Equals `scores_golden.csv` |
| 11 | M3-F04 sink + metrics + checkpoint | Writes C-04/C-05 | **E2E smoke: fixture → Kafka → Spark → Cassandra** |
| 12 | M4-F02 dashboard | Throughput, anomaly rate, top-10, drift banner | Dashboard shows live data |
| 13 | M2-F01 + F03 + F04 real model | Short IF training on the replay data | Real bundle swapped in, pipeline still green |
| 14 | M1-F04 attack injector | One attack mode + share | Drift banner fires above 15 % |
| 15 | M4-F03 benchmark harness | `--dry-run` + one short E1 point | Raw results saved |
| 16 | M4-F04 results analysis | One plot from saved results | Figure generated |

After step 11 you have a working personal pipeline. After step 16 you have a complete one.

---

## 8. Owner mode vs replica mode

| | Owner mode (your module) | Replica mode (the other three) |
|---|---|---|
| Purpose | Canonical implementation used by the team | Lets you run and test the whole pipeline alone |
| Contracts | You author and approve yours (PR-04/05) | Use provisional §5, then replace with approved versions (PR-14) |
| Depth | Full: all FRs, NFRs, ACs and performance | Minimal but contract-conformant |
| README first line | Normal header | `> REPLICA built by <name>. Canonical owner: <owner>.` |
| At integration | Delivered to teammates (PR-15) | **Discarded**, replaced by the owner's folder |
| Lessons learned | — | Sent to the owner as an issue or CR proposal, never as merged code |

---

## 9. Phase checkpoints (team calendar)

| Phase | Dates (2026) | Must be true at the end |
|---|---|---|
| P0 Spec and contracts | 21–24 Oct | Constitution signed; D-01..D-11 ADRs Accepted; C-01..C-06 v1.0 Approved; mocks + fixtures shared |
| P1 Parallel build | 25 Oct – 1 Nov | Each member: own module F01–F03 Verified; replica pipeline at step 11 |
| P2 Pairwise integration | 2–4 Nov | I-01, I-02 and I-03 checklists signed using canonical modules |
| P3 E2E + experiments | 5–10 Nov | I-04 signed; E1/E2/E3, recovery and benign-FPR runs saved |
| P4 Report | 11–15 Nov | Report submitted 15 Nov |
| P5 Demo + Git | 16–29 Nov | PR-19 done; demo on 29 Nov |

---

# Appendix — Workspace files (create verbatim in PR-01)

Each block is the **exact content** of the file at the path in its heading, relative to the workspace root.
Generated on 2026-10-22. Note: `sdd/playbook_core.md` is this document minus the Appendix; recreate it by copying §0–§9.

## A1. `README.md`

````markdown
# Real-Time Network Intrusion Detection — Phase 2 Development

**Team Scaling Orchestrators** · Data Engineering at Scale (DES) · IISc · 2026

A streaming pipeline that replays CIC-IDS2017 network flows through **Apache Kafka**, computes
windowed traffic features in **PySpark Structured Streaming**, scores them with an offline-trained
**Isolation Forest** (broadcast + `pandas_udf`) alongside a rule check, stores results in
**Apache Cassandra** and shows them on a **Streamlit** dashboard.

The project is built with **Spec-Driven Development (SDD)**. Nothing is coded until its spec is
approved, and modules interact only through versioned **contracts**. Any member's version
of a module can therefore be swapped in for any other's.

## Team and modules

| Module | Folder | Owner | One-line scope |
|---|---|---|---|
| M1 | [Module1_Data_Ingestion_Platform](Module1_Data_Ingestion_Platform/) | Aswin S. | Docker platform, dataset preprocessing, Kafka replay producer, attack injector |
| M2 | [Module2_ML_Anomaly_Model](Module2_ML_Anomaly_Model/) | Nitish Kumar Yadav | Offline features, Isolation Forest training/eval, detection bundle (model + rules) |
| M3 | [Module3_Spark_Stream_Processing](Module3_Spark_Stream_Processing/) | Kumari Priyanka | Spark streaming job: windows, features, hybrid scoring, Cassandra sink, recovery |
| M4 | [Module4_Storage_Dashboard_Benchmarking](Module4_Storage_Dashboard_Benchmarking/) | Vidhi Kant Gupta | Cassandra schema, Streamlit dashboard, drift alert, E1–E3 benchmark harness |

## Folder map

```
2_PHASE_2_PROJECT_DEVELOPMENT/
├── README.md                ← you are here
├── SDD_PLAYBOOK.md          ← shareable guide for humans and AI tools (generated by sdd/build_playbook.sh)
├── DEVELOPMENT_LOG.md       ← append-only step-by-step record of everything done, by level (PR-20)
├── PROJECT_PLAN.md          ← analysis, module split, timeline, decisions, risks
├── CONSTITUTION.md          ← non-negotiable engineering rules for all modules
├── sdd/
│   ├── WORKFLOW.md          ← the SDD lifecycle, gates, IDs, naming
│   └── templates/           ← spec / plan / tasks / contract / CR / ADR / integration templates
├── contracts/               ← THE ONLY shared surface between modules (specs, schemas, fixtures, ids_contracts pkg)
├── integration/             ← cross-module integration checklists, compose overlay, e2e tests
├── docs/adr/                ← project-wide architecture decision records
├── Module1_Data_Ingestion_Platform/
├── Module2_ML_Anomaly_Model/
├── Module3_Spark_Stream_Processing/
└── Module4_Storage_Dashboard_Benchmarking/
```

Every module has the same internal layout:

```
ModuleN_<name>/
├── README.md        ← owner, scope, provides/consumes, how to run
├── specs/           ← MN-Fxx-<slug>/{spec.md, plan.md, tasks.md}
├── src/<package>/   ← module code (ids_ingest | ids_model | ids_stream | ids_monitor)
├── tests/{unit,contract,integration}/
├── mocks/           ← stand-ins this module PROVIDES so others can work without it
└── docs/adr/        ← module-local decisions
```

## Read in this order

0. [SDD_PLAYBOOK.md](SDD_PLAYBOOK.md): **the shareable, self-contained guide**. Give it to your AI assistant together with the proposal
   to recreate this workspace and build your own full pipeline (procedures PR-00..PR-19, provisional contract baseline)
1. [PROJECT_PLAN.md](PROJECT_PLAN.md): what we build, who builds what, and when
2. [CONSTITUTION.md](CONSTITUTION.md): rules every module must follow
3. [sdd/WORKFLOW.md](sdd/WORKFLOW.md): how a feature goes from idea to integrated code
4. [contracts/README.md](contracts/README.md): the interfaces between modules
5. Your module's `README.md`

## Status

**Phase 0: Specification and contracts.** Everything stays local and will be pushed to a Git
repository once the pipeline is complete.
````

## A2. `PROJECT_PLAN.md`

````markdown
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

| D-12 | **Drift metric vs attack share** *(found 2026-10-22, first end-to-end run)*. The drift banner (G6, F5) uses the share of anomalous *windows*. Windows are per source IP, so 20 % injected *events* from 7 attacker IPs among hundreds of benign IPs gives only about 2 % anomalous windows (113 / 5,223). The banner would not fire at the E3 20 % level. | F5 cannot be shown as specified. | Options: (a) event-weighted rate (Σ event_count of anomalous windows / Σ event_count), (b) more attacker source IPs in the injector, (c) a lower threshold. **Recommend (a)**, which keeps the 15 % rule meaningful. | C-04 §4 (M4), M1-F04 |
| D-13 | **Latency target P2** *(measured 2026-10-22)*. At 2,000 ev/s with a 1 s trigger, the median per-batch p95 latency is **1,223 ms** (target < 500 ms). The trigger interval alone adds up to 1 s. | P2 likely not met as configured. | Profile batch time (Cassandra write, `toPandas`, UDF), try a 250–500 ms trigger, and report honestly against D-01's definition | M3 (owner), M4-F03 |

| D-14 | **F1 precision is structurally unreachable as designed** *(measured 2026-10-22, M2-F03 replica)*. On the Friday test files at R_ref, only **17 of 21,279 windows** contain attacks. All CIC attack flows come from **one source IP (172.16.0.1)**, and the 45 s replay yields about 9 attacker windows. Window-level hybrid: recall 0.941, FPR 1.2 %, **precision 0.058**. Flow-level (window verdict applied to its flows): precision about 0.60, recall 1.0, **but about 87 % of benign flows sit in flagged windows**: the 4 volume-dominated features at 5,000 ev/s compression (an 8 h day replayed in about 2 min) make busy benign hosts look like floods. Also: IsolationForest does not extrapolate (out-of-range points score like the training extremes). | The F1 target (0.80 / 0.75) cannot be met with per-`src_ip` windows + 4 volume features + this replay compression, whatever the model. | Team decision (owner M2, with M3/M4). Options: (a) report window- and flow-level metrics honestly with this analysis; (b) add rate-invariant/relative features (C-02 change: e.g. bytes per flow, SYN share, port entropy); (c) evaluate detection at a slower replay rate; (d) additional grouping (`dst_ip` windows for DDoS). **Recommend (a) now + (b) as the improvement**, since it fits the remaining time | C-02 (M2), M2-F03, report |

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
````

## A3. `CONSTITUTION.md`

````markdown
# Project Constitution

These are the non-negotiable rules for every module. Every `plan.md` must include a
**Constitution Check** confirming compliance. A deviation needs an ADR approved by the whole team.

| | |
|---|---|
| Version | 1.0.0-draft |
| Ratified | _pending: all 4 sign below_ |

---

### Article I — Spec before code
No production code is written without an **Approved** `spec.md`, a `plan.md` and a `tasks.md`.
Every commit and code change references a task ID (`MN-Txxx`). Every task traces to a requirement
(`MN-FR-xxx` / `MN-NFR-xxx`), and every requirement traces to a proposal goal or metric (G*, P*, F*).

### Article II — Contracts are the only coupling
Modules interact **only** through the contracts in `contracts/` (C-01..C-06). If an interaction
is not described in a contract, it is not allowed.

### Article III — Module isolation
1. Module code never imports another module's package (`ids_ingest`, `ids_model`, `ids_stream`, `ids_monitor`).
   The only shared import is `ids_contracts`.
2. A module folder is self-contained: its own dependencies (`requirements.txt` / `pyproject.toml`),
   its own Dockerfile or compose fragment if it needs one, and its own tests.
3. A module never reads or writes files inside another module's folder. Shared files travel
   through paths defined in C-06 (for example `DATA_DIR`, `MODEL_BUNDLE_PATH`).

### Article IV — Mock-first, standalone-runnable
Every module ships a mock of what it **provides** in `mocks/` (or a golden fixture in `contracts/fixtures/`)
before its real implementation. Every module can run and pass its tests with the other three replaced by mocks.

### Article V — Uniform module interface
Every module has a `README.md` (from `sdd/templates/module-readme-template.md`) and a `Makefile`
with exactly these targets:

| Target | Meaning |
|---|---|
| `make install` | Install module dependencies |
| `make test` | Unit tests |
| `make contract-test` | Contract tests against `contracts/` |
| `make run` | Run the module's real component using env from C-06 |
| `make mock` | Run/publish the module's mock for others |
| `make clean` | Remove generated artifacts |

### Article VI — Configuration through the environment
Hosts, ports, topic names, keyspaces, paths, rates and counts come from environment variables
named in **C-06**. They are never hardcoded. Each module documents the variables it reads.

### Article VII — Honest ML
1. The scoring path uses only the model and the rules from the C-03 bundle. There are **no hardcoded thresholds** in code.
2. Eval-only fields (`label`, `is_injected`) **must never** be used in feature computation or scoring.
   A contract test enforces this.
3. Offline and online features must reproduce the C-02 golden fixture.

### Article VIII — Tests derive from specs
Each acceptance criterion (`AC-xx`) maps to at least one automated test, or to a documented manual check
when it cannot be automated (for example a dashboard visual). Tests are written before or alongside the code, never "later".

### Article IX — Reproducibility and version pins
Python, Spark, scikit-learn, pandas, pyarrow, Kafka and Cassandra versions are pinned in
`contracts/versions.md` and used everywhere, including Colab. Random seeds are fixed and recorded.
Raw data and large artifacts are not committed (see `.gitignore`); the scripts that produce them are.

### Article X — Measured claims only
Every number in the report comes from a scripted run whose raw output is saved under
`Module4_Storage_Dashboard_Benchmarking/results/` along with its config. No hand-entered results.

### Article XI — Ownership and change control
1. The owner's version of a module is canonical. Others may build private versions for their own testing,
   but they never edit another owner's canonical module. Instead they raise an issue or a CR.
2. Contract changes follow the CR process: semantic versioning, impact analysis, and approval from every affected owner.
3. A breaking contract change (MAJOR) needs approval from all 4 members.

### Article XII — Simplicity
Use only the stack in the proposal (Kafka, PySpark, Cassandra, Docker Compose, scikit-learn, Streamlit)
plus small standard libraries. Adding any new infrastructure component requires an ADR.

---

## Amendments
Propose an amendment with an ADR in `docs/adr/`. It is adopted only with all 4 signatures and bumps this document's version.

## Signatures

| Member | Module | Signed (date) |
|---|---|---|
| Aswin S. | M1 | |
| Nitish Kumar Yadav | M2 | |
| Kumari Priyanka | M3 | |
| Vidhi Kant Gupta | M4 | |
````

## A4. `sdd/WORKFLOW.md`

````markdown
# SDD Workflow

How a piece of work moves from idea to integrated code in this project.
Step-by-step procedures (PR-00..PR-19) are in [../SDD_PLAYBOOK.md §6](../SDD_PLAYBOOK.md).

## 1. Document hierarchy

```
CONSTITUTION.md                      rules that apply to everything
   └── PROJECT_PLAN.md               goals (G*), metrics (P*, F*), modules, decisions (D-*)
         └── contracts/C-0x_*.md     interfaces between modules (versioned, shared)
               └── ModuleN/specs/MN-Fxx-<slug>/
                     ├── spec.md     WHAT and WHY (no technology choices)
                     ├── plan.md     HOW (tech, design, tests, constitution check)
                     └── tasks.md    ordered, small, testable steps
                           └── code + tests   (each change cites a task ID)
```

Higher documents constrain lower ones. If a lower document needs to break a higher one, change
the higher one first (ADR or CR).

## 2. Lifecycle and gates

| # | Stage | Output | Gate to pass before moving on |
|---|---|---|---|
| 0 | **Contract** | `contracts/C-0x_*.md` (from `contract-template.md`) | Provider + all consumers approve, status **Approved**, golden fixture exists |
| 1 | **Specify** | `spec.md` | No `[NEEDS CLARIFICATION]` left. Every FR has an AC. Reviewed by ≥ 1 consumer-module owner |
| 2 | **Plan** | `plan.md` | Constitution Check all ✅. Every FR mapped to a component. Mock and test strategy defined |
| 3 | **Tasks** | `tasks.md` | Every task ≤ ½ day, has file paths and FR/AC refs, dependencies marked |
| 4 | **Implement** | code + tests | Tests for each AC are written first or alongside. `make test` green |
| 5 | **Verify** | AC table in `spec.md` updated to ✅ | `make contract-test` green. Every AC verified |
| 6 | **Integrate** | `integration/checklists/I-xx.md` | Checklist signed by both module owners |

Status values for any document: `Draft → In Review → Approved → Implemented → Verified` (or `Superseded`).

## 3. IDs and naming

| Thing | Format | Example |
|---|---|---|
| Feature folder | `MN-Fxx-<kebab-slug>/` | `M1-F03-replay-producer/` |
| Functional requirement | `MN-FR-xxx` | `M1-FR-004` |
| Non-functional requirement | `MN-NFR-xxx` | `M3-NFR-002` |
| Acceptance criterion | `MN-Fxx-AC-xx` | `M3-F02-AC-03` |
| Task | `MN-Txxx` | `M2-T012` |
| Contract | `C-0x` (file `C-0x_<snake_name>.md`) | `C-01_network_event.md` |
| Change request | `CR-xxx` (in `contracts/changes/`) | `CR-003` |
| ADR (project / module) | `ADR-xxx` / `MN-ADR-xxx` | `ADR-001-latency-definition.md` |
| Integration | `I-xx` | `I-02-M2-M3-bundle.md` |
| Decision from the plan | `D-xx` | `D-01` |

Requirement keywords follow RFC 2119: **MUST**, **SHOULD** and **MAY**.

## 4. Templates

| Template | Use it when |
|---|---|
| [spec-template.md](templates/spec-template.md) | Starting any feature |
| [plan-template.md](templates/plan-template.md) | After the spec is approved |
| [tasks-template.md](templates/tasks-template.md) | After the plan is approved |
| [contract-template.md](templates/contract-template.md) | Defining any cross-module interface |
| [contract-change-request-template.md](templates/contract-change-request-template.md) | Changing an approved contract |
| [adr-template.md](templates/adr-template.md) | Any decision with alternatives (D-xx, tech choices) |
| [integration-checklist-template.md](templates/integration-checklist-template.md) | Connecting two or more modules |
| [module-readme-template.md](templates/module-readme-template.md) | Each module's README |
| [development-log-template.md](templates/development-log-template.md) | Your personal step-by-step log (`DEVELOPMENT_LOG.md`, PR-20) |

To start a feature:
```bash
cd ModuleN_<name>/specs
mkdir MN-Fxx-<slug> && cp ../../sdd/templates/{spec,plan,tasks}-template.md MN-Fxx-<slug>/
# then rename the files to spec.md, plan.md and tasks.md
```

## 5. Review rules

- **Spec:** reviewed by the owner plus at least one owner of a module that consumes this feature's output.
- **Contract:** provider plus **every** consumer must approve. MAJOR changes need all 4.
- **Plan/Tasks:** the owner can self-approve, but the Constitution Check must be completed honestly.
- Write review comments inline as `> **[Reviewer-Initials]:** comment`, and resolve them before approval.

## 6. Change handling

| Change | Process |
|---|---|
| Typo or clarification in your own spec | Edit it and add a change-log line |
| New requirement in your own module | Update spec → plan → tasks, then bump the spec version |
| Anything that changes a contract | CR → impact analysis → approvals → bump contract version → update fixtures → every affected module re-runs `make contract-test` |
| Disagreement | Write an ADR with options, then decide at the twice-weekly sync |

## 7. Working with an AI coding assistant (Claude Code)

Give the assistant the spec rather than a vague request:
- *"Read `CONSTITUTION.md`, `contracts/C-01_network_event.md` and `Module1_.../specs/M1-F03-replay-producer/`.
  Implement task M1-T004 only. Write the test for M1-F03-AC-02 first."*
- *"Review `spec.md` for ambiguity and list anything that should be `[NEEDS CLARIFICATION]`."*
- *"Check `plan.md` against the constitution and report any violations."*

The assistant must not change files outside the current module or under `contracts/` without
a CR. This is the same rule that applies to people.
````

## A5. `sdd/templates/spec-template.md`

````markdown
# Spec: MN-Fxx — <Feature Name>

<!--
SPEC = WHAT and WHY. No technology or implementation choices here (those go in plan.md).
Mark every unknown as [NEEDS CLARIFICATION: question]. A spec cannot be Approved while any remain.
Delete these comment blocks once filled.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Module | ModuleN_<name> |
| Owner | <name> |
| Reviewers | <consumer-module owner(s)> |
| Status | Draft / In Review / Approved / Implemented / Verified |
| Version | 0.1.0 |
| Created / Updated | YYYY-MM-DD / YYYY-MM-DD |
| Proposal trace | G?, P?, F? (see PROJECT_PLAN §1.2–1.3) |
| Contracts touched | C-0x (provides v?), C-0y (consumes v?) |
| Decisions applied | D-xx, ADR-xxx |

## 1. Summary
<!-- 2–4 sentences: what this feature delivers and for whom. -->

## 2. Context and motivation
<!-- Why this feature is needed and where it sits in the pipeline. Link to PROJECT_PLAN sections. -->

## 3. Scope
**In scope**
- …

**Out of scope** (and who handles it, if anyone)
- …

## 4. Actors and user stories
<!-- Actors can be people (operator, evaluator) or modules (M3 stream job). -->
- **US-1:** As a <actor>, I want <capability> so that <benefit>.
- **US-2:** …

## 5. Functional requirements

| ID | Requirement (MUST / SHOULD / MAY) | Priority | Story | Trace |
|---|---|---|---|---|
| MN-FR-001 | The <component> MUST … | P0 | US-1 | G? |
| MN-FR-002 | | | | |

## 6. Non-functional requirements

| ID | Category | Requirement (measurable) | Trace |
|---|---|---|---|
| MN-NFR-001 | Performance | MUST sustain ≥ X ev/s on the reference machine | P1 |
| MN-NFR-002 | Reliability | | |
| MN-NFR-003 | Resource | MUST run within N GB RAM / M CPUs | R1 |
| MN-NFR-004 | Observability | | |

## 7. Interfaces

### 7.1 Provided (this feature produces)
| Contract | Version | What exactly is provided |
|---|---|---|
| C-0x | 1.0 | |

### 7.2 Consumed (this feature depends on)
| Contract | Version | What is used | Mock used until the real one is available |
|---|---|---|---|
| C-0y | 1.0 | | `contracts/fixtures/...` or `ModuleK/mocks/...` |

## 8. Data
<!-- Inputs, outputs, volumes, retention. Reference contract fields; do not redefine them. -->

## 9. Acceptance criteria

| ID | Given / When / Then | Verifies | Test type | Status |
|---|---|---|---|---|
| MN-Fxx-AC-01 | **Given** … **When** … **Then** … | MN-FR-001 | unit / contract / integration / perf / manual | ⬜ |
| MN-Fxx-AC-02 | | | | ⬜ |

## 10. Edge cases and failure modes
| Case | Expected behaviour |
|---|---|
| Malformed input | |
| Upstream unavailable | |
| Restart / replay | |

## 11. Assumptions and dependencies
- …

## 12. Open questions
- [NEEDS CLARIFICATION: …] (owner: …, due: …)

## 13. Review checklist (complete before setting status to Approved)
- [ ] No implementation details (frameworks, code structure) in this spec
- [ ] Every FR is testable and has at least one AC
- [ ] Every NFR has a number and a unit
- [ ] Interfaces reference contracts by ID and version, with no ad-hoc formats
- [ ] Eval-only fields are not used in any scoring requirement (Constitution Art. VII)
- [ ] No open `[NEEDS CLARIFICATION]`
- [ ] At least one consumer-module owner has reviewed

## 14. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | YYYY-MM-DD | | Initial draft |
````

## A6. `sdd/templates/plan-template.md`

````markdown
# Plan: MN-Fxx — <Feature Name>

<!--
PLAN = HOW. Written only after spec.md is Approved.
Every functional requirement in the spec must map to a component below.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Spec version implemented | x.y.z |
| Owner | <name> |
| Status | Draft / Approved |
| Updated | YYYY-MM-DD |

## 1. Approach summary
<!-- One paragraph describing the technical approach. -->

## 2. Technical context
| Item | Choice | Pinned version (from `contracts/versions.md`) |
|---|---|---|
| Language | Python | |
| Key libraries | | |
| Runtime | Docker service / host process / Spark job / Colab | |
| Storage / IO | | |

## 3. Constitution check
| Article | Compliant? | Notes / justification |
|---|---|---|
| I Spec before code | ✅ / ❌ | |
| II Contracts only coupling | | |
| III Module isolation (no cross-module imports) | | |
| IV Mock-first / standalone | | |
| V Uniform Makefile targets | | |
| VI Config via env (C-06) | | |
| VII Honest ML (no hardcoded thresholds, no eval fields in scoring) | | |
| VIII Tests from AC | | |
| IX Version pins, seeds | | |
| X Measured claims | | |
| XI Ownership / CR | | |
| XII Simplicity (no new infra) | | |

## 4. Design

### 4.1 Components
<!-- A diagram (ASCII or mermaid) plus a short description of each component's responsibility. -->
```
<component A> ──► <component B> ──► <contract output>
```

### 4.2 Requirement → component mapping
| Requirement | Component / file | Notes |
|---|---|---|
| MN-FR-001 | `src/<pkg>/<file>.py` | |

### 4.3 File layout
```
ModuleN_<name>/
├── src/<pkg>/
│   ├── __init__.py
│   └── ...
├── tests/unit/test_....py
├── tests/contract/test_....py
└── mocks/...
```

### 4.4 Interface implementation
<!-- How this feature satisfies the contracts it provides or consumes: serialisation, keys, retries, idempotency. -->

## 5. Configuration
| Env var (C-06 name) | Default | Used for |
|---|---|---|
| | | |

## 6. Mock and stub strategy
| Dependency | Mock used during development | Swapped for the real one at |
|---|---|---|
| | | Integration I-xx |

## 7. Test strategy
| Level | What | Tooling | Maps to AC |
|---|---|---|---|
| Unit | | pytest | |
| Contract | Output validates against C-0x; accepts golden fixtures | pytest + `ids_contracts` | |
| Integration | | docker compose | |
| Performance | | benchmark script | |
| Manual | | screenshot / checklist | |

## 8. Risks and alternatives considered
| Option | Pros | Cons | Chosen? |
|---|---|---|---|
| | | | |
<!-- Write an ADR when the choice is significant. -->

## 9. Done means
- [ ] All tasks in `tasks.md` complete
- [ ] `make test` and `make contract-test` green
- [ ] Every AC in the spec marked ✅ with test reference
- [ ] README updated (run instructions, env vars)
````

## A7. `sdd/templates/tasks-template.md`

````markdown
# Tasks: MN-Fxx — <Feature Name>

<!--
Rules:
- Each task is ≤ ½ day, touches named files, and cites the FR/AC it serves.
- [P] = can run in parallel with other [P] tasks in the same phase (different files, no dependency).
- Write test tasks BEFORE the implementation tasks they verify.
- Tick the box and fill "Done" when a task is complete. Cite the task ID in commit messages.
-->

| Field | Value |
|---|---|
| Feature ID | MN-Fxx |
| Plan version | x.y |
| Owner | <name> |
| Target finish | YYYY-MM-DD |

## Phase 1 — Setup
- [ ] **MN-T001** Create package skeleton `src/<pkg>/…`, `Makefile` with standard targets · Files: … · Refs: Const. V · Done: _
- [ ] **MN-T002** [P] Add dependencies with pinned versions · Files: `requirements.txt` · Refs: Const. IX · Done: _

## Phase 2 — Tests first
- [ ] **MN-T010** [P] Contract test: output validates against C-0x v1.0 · Files: `tests/contract/test_….py` · Refs: AC-01 · Done: _
- [ ] **MN-T011** [P] Unit test for … · Files: `tests/unit/test_….py` · Refs: AC-02 · Done: _

## Phase 3 — Core implementation
- [ ] **MN-T020** Implement … · Files: … · Depends: T010 · Refs: FR-001 · Done: _
- [ ] **MN-T021** … · Depends: T020 · Refs: FR-002 · Done: _

## Phase 4 — Mock and integration readiness
- [ ] **MN-T030** Ship/update mock in `mocks/` for consumers · Refs: Const. IV · Done: _
- [ ] **MN-T031** Run against other modules' mocks end-to-end · Refs: AC-0x · Done: _

## Phase 5 — Polish and verify
- [ ] **MN-T040** Update module README (run steps, env vars) · Done: _
- [ ] **MN-T041** Mark AC table in spec.md ✅ with test references · Done: _

## Progress
| Phase | Total | Done | Blocked by |
|---|---|---|---|
| 1 Setup | | | |
| 2 Tests | | | |
| 3 Core | | | |
| 4 Mock / Integration | | | |
| 5 Polish | | | |

## Blockers log
| Date | Task | Blocked on (contract / module / decision) | Resolution |
|---|---|---|---|
````

## A8. `sdd/templates/contract-template.md`

````markdown
# Contract C-0x: <Contract Name>

<!--
A contract is the ONLY way two modules may depend on each other.
It must be precise enough that two people who never talk can build both sides and they still work together.
Save it as contracts/C-0x_<snake_name>.md. Machine-readable parts go in contracts/schemas/, examples in contracts/fixtures/.
-->

| Field | Value |
|---|---|
| Contract ID | C-0x |
| Version | 1.0.0 (MAJOR = breaking, MINOR = additive, PATCH = clarification) |
| Status | Draft / In Review / Approved / Superseded |
| Provider (owner) | MN — <name> |
| Consumers | MK, MJ |
| Medium | Kafka topic / Cassandra table / file bundle / CLI + env |
| Machine-readable schema | `contracts/schemas/<file>` |
| Golden fixtures | `contracts/fixtures/<file>` |
| Decisions applied | D-xx, ADR-xxx |

## 1. Purpose
<!-- What crosses this boundary and why. -->

## 2. Transport and location
<!-- e.g. Kafka topic name, key, partitioning; table name and keyspace; directory path; CLI command. Names come from C-06. -->

## 3. Schema

| Field | Type | Required | Unit / format | Constraints | Description | Example |
|---|---|---|---|---|---|---|
| | | yes/no | | | | |

## 4. Semantics
- **Keys and partitioning:**
- **Ordering guarantees:**
- **Time semantics (event time vs processing time, timezone, precision):**
- **Idempotency / duplicates:**
- **Null / missing / default handling:**
- **Eval-only fields (never used in scoring):**

## 5. Examples
```json
{ }
```

## 6. Validation
- Validator: `ids_contracts.<module>.validate_<thing>()` (in `contracts/python/`)
- Golden fixture(s) and how to use them:

## 7. Obligations
**Provider MUST**
- Emit only data that validates against §3
- …

**Consumers MUST**
- Ignore unknown fields (forward compatibility for MINOR versions)
- …

## 8. Error handling
<!-- What happens with invalid data on each side: drop, dead-letter, fail fast? -->

## 9. Contract tests
| Side | Test | Location |
|---|---|---|
| Provider | Output validates against the schema | `ModuleN/tests/contract/` |
| Consumer | Accepts golden fixture and produces the expected result | `ModuleK/tests/contract/` |

## 10. Compatibility and versioning
- MINOR: adding optional fields is allowed, and consumers must tolerate them.
- MAJOR: removing or renaming fields, or changing types or meaning, requires a CR and approval from all affected owners.

## 11. Approvals
| Role | Member | Version approved | Date |
|---|---|---|---|
| Provider | | | |
| Consumer | | | |
| Consumer | | | |

## 12. Change log
| Version | Date | CR | Change |
|---|---|---|---|
| 1.0.0 | | — | Initial approved version |
````

## A9. `sdd/templates/contract-change-request-template.md`

````markdown
# CR-xxx: <Short title>

<!-- Save as contracts/changes/CR-xxx-<slug>.md. A contract file is never edited without an approved CR (except PATCH typos). -->

| Field | Value |
|---|---|
| CR ID | CR-xxx |
| Contract | C-0x <name> |
| Version change | 1.0.0 → 1.1.0 / 2.0.0 |
| Type | PATCH (clarify) / MINOR (additive) / MAJOR (breaking) |
| Requested by | <name>, Module N |
| Date | YYYY-MM-DD |
| Status | Proposed / Approved / Rejected / Applied |

## 1. Motivation
<!-- What problem did you hit? Link to spec, task or bug. -->

## 2. Proposed change
```diff
- old field / rule
+ new field / rule
```

## 3. Impact analysis
| Module | Affected? | What must change | Effort | Owner ack |
|---|---|---|---|---|
| M1 | yes/no | | | ⬜ |
| M2 | | | | ⬜ |
| M3 | | | | ⬜ |
| M4 | | | | ⬜ |

## 4. Migration plan
<!-- Order of changes, fixture updates, whether both versions must be supported temporarily. -->

## 5. Alternatives considered
-

## 6. Decision
| Member | Approve / Reject | Date |
|---|---|---|
| | | |

Once applied: bump the version in the contract file, update the schema and fixtures, add a change-log line,
and notify everyone to re-run `make contract-test`.
````

## A10. `sdd/templates/adr-template.md`

````markdown
# ADR-xxx: <Decision title>

<!-- Project-wide: docs/adr/ADR-xxx-<slug>.md. Module-local: ModuleN/docs/adr/MN-ADR-xxx-<slug>.md -->

| Field | Value |
|---|---|
| Status | Proposed / Accepted / Superseded by ADR-yyy |
| Date | YYYY-MM-DD |
| Deciders | |
| Resolves | D-xx / issue |
| Affects | Modules, contracts |

## Context
<!-- The forces at play: requirements, constraints and facts. Be neutral. -->

## Options
| Option | Pros | Cons |
|---|---|---|
| A | | |
| B | | |

## Decision
<!-- "We will …" -->

## Consequences
- Positive:
- Negative / trade-offs:
- Follow-ups (contracts, specs or tasks to update):
````

## A11. `sdd/templates/integration-checklist-template.md`

````markdown
# Integration I-xx: <MA ↔ MB — seam name>

<!-- Save as integration/checklists/I-xx-<slug>.md. One checklist per integration event. -->

| Field | Value |
|---|---|
| Integration ID | I-xx |
| Modules | MA (<owner>) ↔ MB (<owner>) |
| Seam / contracts | C-0x v?, C-0y v? |
| Date | YYYY-MM-DD |
| Environment | Docker Compose on <machine>, `contracts/versions.md` rev ? |
| Result | ⬜ Pass / ⬜ Pass with issues / ⬜ Fail |

## 1. Module versions under test
| Module | Source (whose copy) | Spec versions | Notes |
|---|---|---|---|
| MA | owner canonical | | |
| MB | owner canonical | | |

## 2. Pre-checks (each module run alone)
- [ ] MA: `make test` green
- [ ] MA: `make contract-test` green against the contract versions above
- [ ] MB: `make test` green
- [ ] MB: `make contract-test` green
- [ ] Both sides use the same `contracts/` revision (identical files)
- [ ] Env file matches C-06 (no local overrides)

## 3. Integration steps
| # | Step | Command | Expected | Actual | ✅/❌ |
|---|---|---|---|---|---|
| 1 | Start platform | `make -C Module1_Data_Ingestion_Platform run` | all services healthy | | |
| 2 | | | | | |
| 3 | Smoke test: golden fixture end-to-end | | output equals expected fixture | | |

## 4. Acceptance checks
| Check | Evidence (log, screenshot, query output) | ✅/❌ |
|---|---|---|
| Data crosses the seam with no validation errors | | |
| Volume / rate check | | |
| Failure case (stop one side, then restart) | | |

## 5. Issues found
| # | Description | Side | Contract gap? (→ CR) | Owner | Status |
|---|---|---|---|---|---|

## 6. Sign-off
| Member | Module | Signed |
|---|---|---|
| | MA | |
| | MB | |
````

## A12. `sdd/templates/module-readme-template.md`

````markdown
# ModuleN — <Module Name>

| | |
|---|---|
| Owner | <name> |
| Python package | `<pkg>` |
| Status | Phase 0 / Building / Integrated |
| Contracts owned | C-0x |
| Contracts consumed | C-0y |

## Purpose
<!-- 2–3 sentences. -->

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| MN-F01 <name> | [specs/MN-F01-…/spec.md](specs/) | Draft |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|

## Quick start
```bash
make install
make test
make contract-test
make mock   # publish this module's mock for others
make run    # needs env from C-06
```

## Environment variables (from C-06)
| Variable | Default | Purpose |
|---|---|---|

## Layout
```
specs/   src/<pkg>/   tests/{unit,contract,integration}/   mocks/   docs/adr/
```

## Integration notes
<!-- Anything a teammate needs to know when dropping this folder into their tree. -->
````

## A13. `sdd/templates/development-log-template.md`

````markdown
# Development Log — <Name> (<Owned module>)

<!--
An append-only record of EVERY step taken, at every level of development.
- One entry per meaningful step (a document written, a decision taken, a task implemented, a test run, an integration).
- Never rewrite history. If something was wrong, add a new entry that corrects it.
- The AI assistant appends an entry at the end of every working session (PR-20).
-->

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
| L0 Project | | | |
| L1 SDD framework | | | |
| L2 Contracts | | | |
| L3 Module | | | |
| L4 Feature | | | |
| L5 Task / code | | | |
| L6 Integration | | | |
| L7 Experiments | | | |

## Step log

<!-- Copy this block for each step. IDs are sequential: S-001, S-002, … -->

### S-xxx · YYYY-MM-DD · L? <Level name> · <Procedure PR-xx>
**What:** <what was done, one or two sentences>
**Why:** <requirement, decision or gate it serves (G*, P*, F*, D-xx, FR, AC)>
**Artifacts:** <files created or changed>
**Verification:** <tests run and their result, review done, or "n/a">
**Decisions / issues:** <ADR, CR or open question raised, or "none">

## Open items

| # | Item | Level | Owner | Due | Status |
|---|---|---|---|---|---|
````

## A14. `contracts/README.md`

````markdown
# Contracts — the only shared surface between modules

Modules depend on **contracts**, never on each other's code (Constitution Art. II–III).
Each contract is written from [../sdd/templates/contract-template.md](../sdd/templates/contract-template.md)
and must be **Approved v1.0** before code is written on either side of its seam.

## Registry

| ID | File | Provider | Consumers | Medium | Status |
|---|---|---|---|---|---|
| C-01 | [`C-01_network_event.md`](C-01_network_event.md) | M1 Aswin | M3, M2 | Kafka JSON + replay Parquet | **In Review 1.0.0-rc.5** |
| C-02 | [`C-02_feature_definition.md`](C-02_feature_definition.md) | M2 Nitish | M3 | Spec + golden CSV | 🔶 **Provisional replica 0.1.1** (by M1, owner to replace) |
| C-03 | [`C-03_detection_bundle.md`](C-03_detection_bundle.md) | M2 Nitish | M3 | File bundle | 🔶 **Provisional replica 0.1.1** (by M1, owner to replace) |
| C-04 | [`C-04_anomaly_store.md`](C-04_anomaly_store.md) | M4 Vidhi | M3 (writer) | Cassandra CQL | 🔶 **Provisional replica 0.1.0** (by M1, owner to replace) |
| C-05 | [`C-05_pipeline_metrics.md`](C-05_pipeline_metrics.md) | M3 Priyanka | M4 | Cassandra CQL | 🔶 **Provisional replica 0.1.0** (by M1, owner to replace) |
| C-06 | [`C-06_runtime_config_control.md`](C-06_runtime_config_control.md) | M1 Aswin | All | Env vars, CLI, service names | **In Review 1.0.0-rc.6** |
| — | [`versions.md`](versions.md) | M1 (all approve) | All | Version pins | **In Review 1.0.0-rc.3** |

**Provisional baseline:** concrete v0.1 values for every contract (fields, formulas, DDL, env vars, pins)
are in [../SDD_PLAYBOOK.md §5](../SDD_PLAYBOOK.md). Owners start from them, and replicas build against them until v1.0 is approved.

## What each contract must settle

**C-01 Network Event**: topic name; message key = `src_ip`; fields `timestamp` (emission time,
epoch ms, D-06), `src_ip`, `dst_ip`, `dst_port`, `bytes_sent`, `syn_flag`, `ack_flag`; types and units;
the mapping from CIC-IDS2017 TrafficLabelling columns (D-03); optional `orig_ts`, `event_id`;
**eval-only** `label` and `is_injected` (D-07); the replay Parquet layout for M2.

**C-02 Feature Definition**: window 30 s, slide 10 s, watermark 1 min; grouping (`src_ip`, window);
exact formulas and zero-handling for `total_bytes`, `unique_ports`, `syn_ack_ratio`, `packet_rate` (D-08);
column order; window ground-truth rule (D-07); golden input and output fixtures.

**C-03 Detection Bundle**: directory layout (`model.joblib`, `scaler.joblib` or a single pipeline,
`manifest.json`, `rules.yaml`); the manifest fields (bundle version, feature order, sklearn version,
score semantics and sign, decision threshold, training metrics, seed); the `rules.yaml` schema;
the loading procedure; the dummy bundle.

**C-04 Anomaly Store**: keyspace, replication, table DDL, primary key (D-02); columns
`window_start`, `window_end`, `src_ip`, the 4 features, `anomaly_score`, `ml_flag`, `rule_flag`,
`is_anomaly`, `detected_at`, `max_event_ts`, eval-only `label`; upsert semantics; TTL; write consistency.

**C-05 Pipeline Metrics**: table DDL; per-micro-batch fields (`batch_id`, input rows/s,
processed rows/s, batch duration, latency p50/p95 per D-01, run_id, config tags such as partitions and executors).

**C-06 Runtime Config and Control**: env var names (for example `KAFKA_BOOTSTRAP`, `KAFKA_TOPIC`,
`CASSANDRA_HOSTS`, `CASSANDRA_KEYSPACE`, `MODEL_BUNDLE_PATH`, `DATA_DIR`, `RUN_ID`); compose service names
and ports; CLI flags for the producer (`--rate`, `--duration`, `--attack-mode`, `--attack-share`), topic admin
(`--partitions`) and stream job (`--executors`, `--trigger`); `.env.example`.

## Planned layout

```
contracts/
├── README.md                 ← this registry
├── C-01_… .. C-06_….md       ← human-readable contracts
├── versions.md               ← pinned versions (D-09)
├── changes/                  ← CR-xxx change requests
├── schemas/                  ← event.schema.json, ids_schema.cql, manifest.schema.json, rules.schema.json
├── fixtures/                 ← events_golden.jsonl, features_golden.csv, scores_golden.csv
└── python/ids_contracts/     ← constants, models, validators (no business logic)
```
````

## A15. `contracts/C-01_network_event.md`

````markdown
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
````

## A16. `contracts/C-06_runtime_config_control.md`

````markdown
# Contract C-06: Runtime Config and Control Interface

| Field | Value |
|---|---|
| Contract ID | C-06 |
| Version | 1.0.0-rc.6 |
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
| `ids_monitor.bench` | M4 | `--experiment E1\|E2\|E3`, `--dry-run`, `--duration` | `runs`, `results_dir` |

Notes:
- `--recreate` deletes and recreates the topic. It is required when *reducing* partitions, because Kafka cannot shrink a topic.
- `ids_stream.job` wraps `spark-submit` and must stop gracefully on SIGTERM, flushing the current batch.
- The producer with `--source fixture` replays `contracts/fixtures/events_golden.jsonl`, rewriting `timestamp` relative to now
  while preserving the inter-event gaps. This is the M1 mock (Constitution Art. IV).

## 6. Run IDs
Pattern: `^((E1|E2|E3)-p\d{1,2}-e\d{1,2}-r\d+-a\d{1,3}-\d{12}|DEV-[A-Za-z0-9_.-]+)$`

- Experiment runs: `E1-p4-e2-r5000-a0-202611061430` (partitions, executors, rate, attack %, `YYYYMMDDHHMM`)
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
| 1.0.0-rc.6 | 2026-10-22 | — (pre-approval) | Attack injection flags (`--seed`, `--attack-start`, `--attack-duration`) and summary fields (M1-F04) |
| 1.0.0-rc.5 | 2026-10-21 | — (pre-approval) | Producer flags `--no-loop`, `--allow-unverified` and full summary fields (M1-F03) |
| 1.0.0-rc.4 | 2026-10-21 | — (pre-approval) | Added the `ids_ingest.prepare` command (M1-F02) |
| 1.0.0-rc.3 | 2026-10-21 | — (pre-approval) | KRaft decided, so `zookeeper` is not used. Workers mount the workspace and runtime like `spark-client`. Every CLI reads `integration/.env` via `load_runtime_config` |
| 1.0.0-rc.2 | 2026-10-21 | — (pre-approval) | From the M1-F01 spec: `spark-client` service, `ids_ingest.platform` command, `SPARK_WORKERS`, `SPARK_EXECUTOR_MEMORY` default 768m |
````

## A17. `contracts/versions.md`

````markdown
# Version Pins (ADR-009)

| Field | Value |
|---|---|
| Version | 1.0.0-rc.3 |
| Status | **In Review** (all 4 approve) |
| Owner | M1 — Aswin S. |

These pins apply **everywhere**: host machines, Docker images and Google Colab. Change them only through a CR.

## Hard rules
1. **scikit-learn, numpy, pandas and pyarrow must be identical** wherever the model is trained (Colab) and wherever it is scored
   (Spark executors). A joblib pickle is not guaranteed to load across scikit-learn versions.
2. **The Spark driver and executors must have the same Python minor version.** `pandas_udf` fails otherwise.
   Therefore the stream job is submitted from a container built from the same image as the workers, not from the host.
3. Spark runs on **Java 17**. Spark 3.5 does not officially support Java 21.

## Pins

| Component | Pin | Where | Verified |
|---|---|---|---|
| Python (host tools, tests, producer, dashboard) | 3.11.x | host | ✅ 3.11.17 on M1 host (2026-10-21) |
| Python (Spark image) | the image's Python, identical on driver and workers | Docker | ✅ 3.10.12 on driver and executors (M1-F01-AC-06) |
| Java | 17 (Temurin or Homebrew `openjdk@17`) | Docker + host for local PySpark tests | ✅ 17.0.21 on M1 host (Homebrew), 17.0.14 in the Spark image |
| Apache Spark / PySpark | 3.5.5 (Scala 2.12). Image `apache/spark:3.5.5-scala2.12-java17-python3-ubuntu` | Docker + host | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Spark Kafka connector | `org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5` (+ kafka-clients 3.4.1, commons-pool2 2.11.1, token-provider 3.5.5), baked into the image | Spark | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Spark Cassandra connector | `com.datastax.spark:spark-cassandra-connector-assembly_2.12:3.5.1`, baked into the image | Spark | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Kafka | `apache/kafka:3.8.1` (KRaft) | Docker | ✅ runs in the platform (M1-F01, 2026-10-21) |
| Cassandra | `cassandra:4.1.10` | Docker | ✅ runs in the platform (M1-F01, 2026-10-21) |
| scikit-learn | 1.5.2 | Colab, Spark image, host | ✅ Spark image (driver + executors) |
| numpy | 1.26.4 | Colab, Spark image, host | ✅ Spark image |
| pandas | 2.2.3 | Colab, Spark image, host | ✅ Spark image |
| pyarrow | 17.0.0 | Colab, Spark image, host | ✅ Spark image (pandas_udf ran), ✅ host (M1-F02 writer) |
| joblib | 1.4.2 | Colab, Spark image | ✅ Spark image |
| Kafka Python client | `confluent-kafka==2.6.1` (M1-ADR-002) | M1 | ✅ host (topic_admin, perf test) |
| Container engine | Docker Desktop **or** Colima, with Compose v2. VM ≥ 6 CPU / 10 GB | host | ✅ Colima 0.10.3 + Docker CLI 29.9 + Compose 5.6 on M1 host |
| cassandra-driver | 3.29.2 | M3 (if needed), M4 | ⬜ |
| streamlit | 1.39.0 | M4 | ⬜ |
| pyyaml | 6.0.2 | M2, M3 | ✅ Spark image + host |
| pytest / jsonschema | 8.3.x / 4.23.x | all (tests only) | ⬜ |

The "Verified" column is ticked when an image or environment actually runs with the pin (for example during M1-F01).
If a pin cannot be satisfied (an image tag does not exist, or a wheel is unavailable on arm64), raise a CR that names the replacement.

## Colab cell (training must start with this)
```python
!pip install -q scikit-learn==1.5.2 numpy==1.26.4 pandas==2.2.3 pyarrow==17.0.0 joblib==1.4.2 pyyaml==6.0.2
import sklearn, numpy, pandas, pyarrow; print(sklearn.__version__, numpy.__version__, pandas.__version__, pyarrow.__version__)
# Restart the runtime after installing, then record the printed versions in the bundle manifest (C-03).
```
````

## A18. `contracts/schemas/event.schema.json`

````json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://scaling-orchestrators.local/contracts/C-01/event.schema.json",
  "title": "C-01 Network Event",
  "description": "One network event on Kafka topic network-events. Contract C-01 v1.0.0-rc.1. label and is_injected are eval-only.",
  "type": "object",
  "additionalProperties": false,
  "required": ["event_id", "timestamp", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag"],
  "properties": {
    "event_id":   {"type": "string", "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"},
    "timestamp":  {"type": "integer", "minimum": 1000000000000, "description": "Emission time, epoch milliseconds UTC"},
    "src_ip":     {"type": "string", "anyOf": [{"format": "ipv4"}, {"format": "ipv6"}]},
    "dst_ip":     {"type": "string", "anyOf": [{"format": "ipv4"}, {"format": "ipv6"}]},
    "dst_port":   {"type": "integer", "minimum": 0, "maximum": 65535},
    "bytes_sent": {"type": "integer", "minimum": 0, "maximum": 9223372036854775807},
    "syn_flag":   {"type": "integer", "minimum": 0},
    "ack_flag":   {"type": "integer", "minimum": 0},
    "orig_ts":    {"type": ["string", "null"]},
    "label": {
      "type": "string",
      "enum": [
        "BENIGN", "DDoS", "PortScan", "Bot", "Infiltration", "Heartbleed",
        "DoS Hulk", "DoS GoldenEye", "DoS slowloris", "DoS Slowhttptest",
        "FTP-Patator", "SSH-Patator",
        "Web Attack - Brute Force", "Web Attack - XSS", "Web Attack - Sql Injection",
        "INJ_DDOS", "INJ_SYNFLOOD", "INJ_PORTSCAN"
      ]
    },
    "is_injected": {"type": "boolean"}
  },
  "if": {"properties": {"is_injected": {"const": true}}, "required": ["is_injected"]},
  "then": {"required": ["label"], "properties": {"label": {"pattern": "^INJ_"}}}
}
````

## A19. `contracts/fixtures/README.md`

````markdown
# Golden fixtures

These are shared, deterministic inputs and expected outputs. Every module's contract tests use them.
Never edit them by hand. Regenerate them with the generator and bump the contract if the content changes.

| File | Contract | Owner | Produced by | Status |
|---|---|---|---|---|
| `events_golden.jsonl` | C-01 | M1 | `python contracts/fixtures/_gen/gen_events_golden.py` | ✅ v1.0.0-rc.1 |
| `features_golden.csv` | C-02 | M2 (provisional replica by M1) | `python contracts/fixtures/_gen/gen_features_golden.py` (an independent reference of the C-02 formulas) | 🔶 0.1.0-replica, 23 rows |
| `scores_golden.csv` | C-03 | M2 | `features_golden.csv` scored with `mocks/dummy_bundle/` | ⬜ pending (M2-F04 replica) |

## `events_golden.jsonl`: scenario

126 events. Base time `1767225600000` = 2026-01-01T00:00:00Z. All destinations are `192.168.10.50`.
Lines are in time order except the last one.

| Block | src_ip | Events | Time span (s from base) | Pattern | label / is_injected |
|---|---|---|---|---|---|
| A benign | `192.168.10.5` | 30 | 0, 3, …, 87 | Ports cycle 80/443/53, syn=1, ack=1, varied bytes. Includes the exact window boundaries 0, 30 and 60 s | `BENIGN` / false |
| B port scan | `172.16.0.10` | 40 | 20.0 … 39.5, every 0.5 s | 40 **distinct** ports 20–59, bytes 0, syn=1, ack=0 | `PortScan` / false |
| C SYN flood | `172.16.0.20` | 25 | 50.0 … 62.0, every 0.5 s | Port 80, 60 bytes, syn=1, ack=0 | `INJ_SYNFLOOD` / **true**, `orig_ts` null |
| D DDoS | `172.16.0.30` | 30 | 65.0 … 79.5, every 0.5 s | Port 80, 2000–2290 bytes, syn=0, ack=1 | `DDoS` / false |
| E late event | `192.168.10.5` | 1 | 40.0 (the **last line** of the file) | Port 443, 777 bytes | `BENIGN` / false |

Event E arrives 47 s behind the maximum event time seen (87 s), which is within the 60 s watermark (C-02).
**It must be included** in the windows `[20,50)`, `[30,60)` and `[40,70)` for `192.168.10.5`. It tests late-data handling.

What each consumer can check:
- **M3 parse (C-01):** 126 rows, correct types, nothing dropped.
- **M2/M3 features (C-02):** port-scan windows have high `unique_ports`; SYN-flood windows have a high `syn_ack_ratio`
  (25 SYN / (0 ACK + 1)); DDoS windows have a high `packet_rate` and `total_bytes`; benign windows are low on all features.
- **Eval-only fields:** window labels follow C-02 (any non-BENIGN event makes the window an attack window).
````

## A20. `contracts/fixtures/_gen/gen_events_golden.py`

````python
"""Deterministic generator for contracts/fixtures/events_golden.jsonl (C-01, owner M1).

Run from the workspace root:  python contracts/fixtures/_gen/gen_events_golden.py
Re-running must produce a byte-identical file (no randomness, uuid5 ids).
Scenario is documented in contracts/fixtures/README.md.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "python"))
from ids_contracts.events import check_event, encode_event  # noqa: E402

BASE_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
TARGET = "192.168.10.50"
OUT = HERE.parents[1] / "events_golden.jsonl"


def ev(seq: int, t_ms: int, src: str, dst_port: int, bytes_sent: int, syn: int, ack: int,
       label: str, injected: bool = False, orig_ts=None, dst_ip: str = TARGET) -> dict:
    return {
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"ids-golden-{seq}")),
        "timestamp": BASE_MS + t_ms,
        "src_ip": src,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "bytes_sent": bytes_sent,
        "syn_flag": syn,
        "ack_flag": ack,
        "orig_ts": orig_ts,
        "label": label,
        "is_injected": injected,
    }


def build() -> list:
    raw = []
    # A. Benign host: one flow every 3 s over 0..87 s (hits window boundaries 0/30/60 s exactly).
    for i in range(30):
        raw.append((i * 3000, "192.168.10.5", (80, 443, 53)[i % 3], 500 + (i * 137) % 1000, 1, 1, "BENIGN", False, "3/7/2017 9:00"))
    # B. Port scan: 40 flows every 0.5 s over 20..39.5 s, each to a distinct port, SYN without ACK.
    for i in range(40):
        raw.append((20_000 + i * 500, "172.16.0.10", 20 + i, 0, 1, 0, "PortScan", False, "7/7/2017 1:55"))
    # C. Injected SYN flood: 25 flows every 0.5 s over 50..62 s to port 80.
    for i in range(25):
        raw.append((50_000 + i * 500, "172.16.0.20", 80, 60, 1, 0, "INJ_SYNFLOOD", True, None))
    # D. DDoS (high rate, large bytes, ACK-heavy): 30 flows every 0.5 s over 65..79.5 s.
    for i in range(30):
        raw.append((65_000 + i * 500, "172.16.0.30", 80, 2000 + i * 10, 0, 1, "DDoS", False, "7/7/2017 3:56"))
    raw.sort(key=lambda r: r[0])
    # E. Late event: benign flow stamped at 40.0 s, appended after the 87 s event (47 s late < 60 s watermark).
    raw.append((40_000, "192.168.10.5", 443, 777, 1, 1, "BENIGN", False, "3/7/2017 9:01"))

    events = []
    for seq, (t, src, port, b, syn, ack, label, inj, orig) in enumerate(raw):
        e = ev(seq, t, src, port, b, syn, ack, label, inj, orig)
        check_event(e, strict=True)
        events.append(e)
    return events


def main() -> None:
    events = build()
    with open(OUT, "wb") as fh:
        for e in events:
            fh.write(encode_event(e) + b"\n")
    print(json.dumps({"status": "ok", "file": str(OUT), "events": len(events)}))


if __name__ == "__main__":
    main()
````

## A21. `contracts/python/pyproject.toml`

````toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "ids-contracts"
version = "1.0.0rc1"
description = "Shared contract constants, models and validators (C-01..C-06). No business logic."
requires-python = ">=3.9"
dependencies = []

[project.optional-dependencies]
test = ["pytest>=8", "jsonschema>=4.18"]

[tool.setuptools]
packages = ["ids_contracts"]

[tool.pytest.ini_options]
testpaths = ["tests"]
````

## A22. `contracts/python/ids_contracts/__init__.py`

````python
"""Shared contract package for all modules.

The only cross-module import allowed by the constitution (Art. III). Holds constants, models and
validators for contracts C-01..C-06. Never put business logic here.

Install from any module folder with:  pip install -e ../contracts/python
"""
from pathlib import Path

__version__ = "1.0.0rc1"

# Editable install keeps the package inside the workspace: contracts/python/ids_contracts/__init__.py
CONTRACTS_DIR = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"


class ContractViolation(ValueError):
    """Raised when data does not satisfy a contract."""
````

## A23. `contracts/python/ids_contracts/events.py`

````python
"""C-01 Network Event: constants, (de)serialisation and validators.

Contract: contracts/C-01_network_event.md  (owner M1)
"""
from __future__ import annotations

import ipaddress
import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Union

from . import ContractViolation

CONTRACT_ID = "C-01"
CONTRACT_VERSION = "1.0.0-rc.5"

TOPIC_DEFAULT = "network-events"
# librdkafka setting that reproduces the Java/Spark murmur2 key partitioning (C-01 §2.1)
LIBRDKAFKA_PARTITIONER = "murmur2_random"

REQUIRED_FIELDS = (
    "event_id", "timestamp", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag",
)
OPTIONAL_FIELDS = ("orig_ts",)
EVAL_ONLY_FIELDS = ("label", "is_injected")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS + EVAL_ONLY_FIELDS

# The only fields feature computation / rules / scoring may read (Constitution Art. VII).
SCORING_FIELDS = ("timestamp", "src_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag")

CIC_LABELS = frozenset({
    "BENIGN", "DDoS", "PortScan", "Bot", "Infiltration", "Heartbleed",
    "DoS Hulk", "DoS GoldenEye", "DoS slowloris", "DoS Slowhttptest",
    "FTP-Patator", "SSH-Patator",
    "Web Attack - Brute Force", "Web Attack - XSS", "Web Attack - Sql Injection",
})
INJECTED_LABELS = frozenset({"INJ_DDOS", "INJ_SYNFLOOD", "INJ_PORTSCAN"})
LABELS = CIC_LABELS | INJECTED_LABELS
BENIGN_LABEL = "BENIGN"

MIN_TIMESTAMP_MS = 1_000_000_000_000  # rejects epoch *seconds* passed by mistake
MAX_INT64 = 2**63 - 1

# CIC TrafficLabelling column (after strip()) -> event field
CIC_COLUMN_MAP = {
    "Source IP": "src_ip",
    "Destination IP": "dst_ip",
    "Destination Port": "dst_port",
    "Total Length of Fwd Packets": "bytes_sent",
    "SYN Flag Count": "syn_flag",
    "ACK Flag Count": "ack_flag",
    "Timestamp": "orig_ts",
    "Label": "label",
}

REPLAY_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
CIC_FILE_ORDER = {
    "Monday": ("Monday-WorkingHours",),
    "Tuesday": ("Tuesday-WorkingHours",),
    "Wednesday": ("Wednesday-workingHours",),
    "Thursday": ("Thursday-WorkingHours-Morning-WebAttacks",
                 "Thursday-WorkingHours-Afternoon-Infilteration"),
    "Friday": ("Friday-WorkingHours-Morning",
               "Friday-WorkingHours-Afternoon-PortScan",
               "Friday-WorkingHours-Afternoon-DDos"),
}

# Reference raw input (C-01 §3.2, verified 2026-10-21): stem -> (sha256 of the CSV, valid rows after C-01 drop rules)
CIC_REFERENCE = {
    "Monday-WorkingHours": ("96f26aea87d513073769b48ce204c2921791149e1c6225f7db65a3fed7973820", 529_918),
    "Tuesday-WorkingHours": ("ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815", 445_909),
    "Wednesday-workingHours": ("ed538e85b84181e8897dedb3d37d365982f44b27eccd67c477581a8b65f3d170", 692_703),
    "Thursday-WorkingHours-Morning-WebAttacks": ("e3deaff483d18b53b100a441dff9b8919416df8876b4edcc0f0d1e4bf48397d0", 170_366),
    "Thursday-WorkingHours-Afternoon-Infilteration": ("d74238e054023c8bd4d8056650463cadb25c100fb0e26ebd4272c07b5c022c4b", 288_602),
    "Friday-WorkingHours-Morning": ("c061cd98f39d8054aeaed6244a5129a20b3985983d0d022b860ae8aa07fe8d21", 191_033),
    "Friday-WorkingHours-Afternoon-PortScan": ("7e2ddaa80a5849ba629463296b6128436c161b4a32e8034bb5beae06b0c45e08", 286_467),
    "Friday-WorkingHours-Afternoon-DDos": ("1f779b4f0d78f9225554c4de53b5a2c07912b60dcd136ee4c5c1d0d2496b7cc4", 225_745),
}
CIC_TOTAL_VALID_ROWS = 2_830_743
CIC_FILE_SUFFIX = ".pcap_ISCX.csv"


def verify_cic_file(path: Union[str, Path]) -> List[str]:
    """Check a raw CIC CSV against CIC_REFERENCE by name and SHA-256. Empty list = identical to the reference."""
    import hashlib
    path = Path(path)
    stem = path.name[: -len(CIC_FILE_SUFFIX)] if path.name.endswith(CIC_FILE_SUFFIX) else path.stem
    if stem not in CIC_REFERENCE:
        return [f"'{path.name}' is not a C-01 source file"]
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    expected = CIC_REFERENCE[stem][0]
    return [] if digest.hexdigest() == expected else [f"{path.name}: sha256 {digest.hexdigest()} != reference {expected}"]


# Replay dataset (Parquet) column -> Arrow type name
REPLAY_COLUMNS = {
    "row_idx": "int64",
    "source_file": "string",
    "orig_ts": "string",
    "src_ip": "string",
    "dst_ip": "string",
    "dst_port": "int32",
    "bytes_sent": "int64",
    "syn_flag": "int32",
    "ack_flag": "int32",
    "label": "string",
    "day": "string",
}


def normalise_label(raw: str) -> str:
    """Normalise a raw CIC label: trim and replace the non-ASCII dash used in web-attack labels."""
    label = raw.strip()
    for bad in ("–", "—", "\x96", "�"):
        label = label.replace(bad, "-")
    return " ".join(label.split())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_ip(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def validate_event(event: Mapping[str, Any], strict: bool = False) -> List[str]:
    """Return a list of violations (empty = valid). strict=True also rejects unknown fields."""
    if not isinstance(event, Mapping):
        return ["event is not a JSON object"]
    errors: List[str] = []

    for name in REQUIRED_FIELDS:
        if name not in event or event[name] is None:
            errors.append(f"missing required field '{name}'")
    if strict:
        unknown = sorted(set(event) - set(ALL_FIELDS))
        if unknown:
            errors.append(f"unknown fields {unknown}")

    if "event_id" in event and event["event_id"] is not None:
        try:
            uuid.UUID(str(event["event_id"]))
            if not isinstance(event["event_id"], str):
                raise ValueError
        except ValueError:
            errors.append("event_id is not a UUID string")

    ts = event.get("timestamp")
    if ts is not None:
        if not _is_int(ts):
            errors.append("timestamp must be an integer (epoch ms)")
        elif ts < MIN_TIMESTAMP_MS:
            errors.append("timestamp looks like seconds, expected epoch milliseconds")

    for name in ("src_ip", "dst_ip"):
        if event.get(name) is not None and not _is_ip(event[name]):
            errors.append(f"{name} is not a valid IP address")

    port = event.get("dst_port")
    if port is not None and not (_is_int(port) and 0 <= port <= 65535):
        errors.append("dst_port must be an integer in 0..65535")

    b = event.get("bytes_sent")
    if b is not None and not (_is_int(b) and 0 <= b <= MAX_INT64):
        errors.append("bytes_sent must be a non-negative int64")

    for name in ("syn_flag", "ack_flag"):
        v = event.get(name)
        if v is not None and not (_is_int(v) and v >= 0):
            errors.append(f"{name} must be a non-negative integer")

    if "orig_ts" in event and event["orig_ts"] is not None and not isinstance(event["orig_ts"], str):
        errors.append("orig_ts must be a string or null")

    label = event.get("label")
    if label is not None and label not in LABELS:
        errors.append(f"label '{label}' is not in the C-01 label set")
    injected = event.get("is_injected")
    if injected is not None and not isinstance(injected, bool):
        errors.append("is_injected must be a boolean")
    if injected is True and not (isinstance(label, str) and label in INJECTED_LABELS):
        errors.append("is_injected=true requires an INJ_* label")
    if injected is False and isinstance(label, str) and label in INJECTED_LABELS:
        errors.append("INJ_* label requires is_injected=true")

    return errors


def check_event(event: Mapping[str, Any], strict: bool = False) -> None:
    """Raise ContractViolation if the event is invalid."""
    errors = validate_event(event, strict=strict)
    if errors:
        raise ContractViolation("; ".join(errors))


def encode_event(event: Mapping[str, Any]) -> bytes:
    """Kafka message value: compact UTF-8 JSON, fields in contract order."""
    ordered = {k: event[k] for k in ALL_FIELDS if k in event}
    return json.dumps(ordered, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def event_key(event: Mapping[str, Any]) -> bytes:
    """Kafka message key: src_ip as UTF-8."""
    return str(event["src_ip"]).encode("utf-8")


def decode_event(value: Union[bytes, str]) -> Dict[str, Any]:
    """Parse a Kafka message value. Raises ContractViolation on non-JSON or non-finite numbers."""
    try:
        text = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
        obj = json.loads(text, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContractViolation(f"not a JSON event: {exc}") from exc
    if not isinstance(obj, dict):
        raise ContractViolation("event is not a JSON object")
    return obj


def _reject_constant(name: str) -> float:
    raise ValueError(f"non-finite number {name} not allowed")


def iter_jsonl(path: Union[str, Path]) -> Iterator[Dict[str, Any]]:
    """Yield events from a JSON-lines file (blank lines skipped)."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield decode_event(line)


# Reference replay data (C-01 §2.2): per-day content_sha256 of a correctly prepared dataset (verified 2026-10-21).
# Equal hashes ⇔ identical replay rows, so every replica can prove it replays the same data.
REPLAY_CONTENT_SHA256 = {
    "Monday": "0c4e8d6c4d0396921692bdf74b2369fc6fb6973b33e0ded1fea8fb90db3c7bdd",
    "Tuesday": "83e9850002902736f7ff712e54311de90a80a3a4bdfafd48dc3ccc540289b493",
    "Wednesday": "27da03964e1505a7adab8dbbc9d344c28ab0ed1856cd7bcd19336110283a707a",
    "Thursday": "edc0c2432a87166aca81c1f6f3171061962a9feda985af94845ddf1dff7e7a95",
    "Friday": "43d3015a1c1be8fe34660233f137cf9945febf163c35ca3e1e51e6a6b260ca45",
}

REPLAY_MANIFEST_NAME = "_manifest.json"
DROP_REASONS = ("empty_row", "wrong_field_count", "missing_field", "non_numeric", "nan_or_inf",
                "negative", "bad_port", "bad_ip", "unknown_label")
MANIFEST_KEYS = ("contract", "contract_version", "tool", "tool_version", "created_at", "inputs", "days",
                 "total_rows", "labels")
MANIFEST_INPUT_KEYS = ("source_file", "day", "sha256", "verified", "data_rows", "valid_rows", "dropped")
MANIFEST_DAY_KEYS = ("rows", "files", "content_sha256", "path")


def validate_manifest(manifest: Mapping[str, Any]) -> List[str]:
    """Check a replay-dataset manifest (C-01 §2.2) for structure and internal consistency. Empty list = valid."""
    errors = [f"manifest missing '{k}'" for k in MANIFEST_KEYS if k not in manifest]
    if errors:
        return errors
    if manifest["contract"] != CONTRACT_ID:
        errors.append(f"manifest contract is {manifest['contract']!r}, expected {CONTRACT_ID!r}")
    inputs, days = manifest["inputs"], manifest["days"]
    for i, item in enumerate(inputs):
        missing = [k for k in MANIFEST_INPUT_KEYS if k not in item]
        if missing:
            errors.append(f"inputs[{i}] missing {missing}")
            continue
        unknown = sorted(set(item["dropped"]) - set(DROP_REASONS))
        if unknown:
            errors.append(f"inputs[{i}] has unknown drop reasons {unknown}")
        if item["data_rows"] != item["valid_rows"] + sum(item["dropped"].values()):
            errors.append(f"inputs[{i}] ({item['source_file']}): data_rows != valid_rows + dropped")
    for day, info in days.items():
        missing = [k for k in MANIFEST_DAY_KEYS if k not in info]
        if missing:
            errors.append(f"days[{day}] missing {missing}")
        elif day not in REPLAY_DAYS:
            errors.append(f"unknown day {day!r}")
    if errors:
        return errors
    valid_sum = sum(i["valid_rows"] for i in inputs)
    day_sum = sum(d["rows"] for d in days.values())
    if not manifest["total_rows"] == valid_sum == day_sum:
        errors.append(f"total_rows {manifest['total_rows']} != inputs valid {valid_sum} / days {day_sum}")
    if sum(manifest["labels"].values()) != manifest["total_rows"]:
        errors.append("label counts do not sum to total_rows")
    unknown_labels = sorted(set(manifest["labels"]) - LABELS)
    if unknown_labels:
        errors.append(f"unknown labels {unknown_labels}")
    return errors


def validate_replay_columns(columns: Mapping[str, str]) -> List[str]:
    """Check a replay-dataset schema given as {column: arrow_type_name}. Empty list = valid."""
    errors = []
    for name, typ in REPLAY_COLUMNS.items():
        if name not in columns:
            errors.append(f"missing column '{name}'")
        elif name != "day" and str(columns[name]) != typ:
            errors.append(f"column '{name}' has type {columns[name]}, expected {typ}")
    extra = sorted(set(columns) - set(REPLAY_COLUMNS))
    if extra:
        errors.append(f"unexpected columns {extra}")
    return errors


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
````

## A24. `contracts/python/ids_contracts/config.py`

````python
"""C-06 Runtime Config and Control: env-var spec, config loader, CLI conventions.

Contract: contracts/C-06_runtime_config_control.md  (owner M1)
Precedence: overrides (CLI flags) > environment > defaults below.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

CONTRACT_ID = "C-06"
CONTRACT_VERSION = "1.0.0-rc.6"

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

ATTACK_MODES = ("none", "ddos", "synflood", "portscan", "mixed")
RUN_ID_PATTERN = re.compile(
    r"^((E1|E2|E3)-p\d{1,2}-e\d{1,2}-r\d+-a\d{1,3}-\d{12}|DEV-[A-Za-z0-9_.-]+)$"
)
_TRIGGER_PATTERN = re.compile(r"^\d+ (second|seconds|millisecond|milliseconds)$")
_MEMORY_PATTERN = re.compile(r"^\d+[mMgG]$")
_BOOTSTRAP_PATTERN = re.compile(r"^[^,:\s]+:\d{1,5}(,[^,:\s]+:\d{1,5})*$")
_IDENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SPARK_MASTER_PATTERN = re.compile(r"^(spark://[^\s]+:\d{1,5}|local(\[(\*|\d+)\])?)$")

WORKSPACE_MARKER = "CONSTITUTION.md"


class ConfigError(ValueError):
    """Invalid configuration value (maps to exit code 2)."""


@dataclass(frozen=True)
class EnvVar:
    name: str
    kind: str          # "str" | "int" | "float" | "path"
    default: str
    check: Optional[Callable[[Any], bool]] = None
    rule: str = ""


def _range(lo: float, hi: float) -> Callable[[Any], bool]:
    return lambda v: lo <= v <= hi


ENV_SPEC: Tuple[EnvVar, ...] = (
    EnvVar("IDS_ROOT", "path", ""),
    EnvVar("KAFKA_BOOTSTRAP", "str", "localhost:9092", _BOOTSTRAP_PATTERN.match, "host:port[,host:port]"),
    EnvVar("KAFKA_TOPIC", "str", "network-events", bool, "non-empty"),
    EnvVar("KAFKA_PARTITIONS", "int", "8", _range(1, 16), "1..16"),
    EnvVar("CASSANDRA_HOSTS", "str", "localhost", bool, "non-empty"),
    EnvVar("CASSANDRA_PORT", "int", "9042", _range(1, 65535), "1..65535"),
    EnvVar("CASSANDRA_KEYSPACE", "str", "ids", _IDENT_PATTERN.match, "CQL identifier"),
    EnvVar("SPARK_MASTER_URL", "str", "spark://localhost:7077", _SPARK_MASTER_PATTERN.match, "spark://host:port or local[*]"),
    EnvVar("SPARK_WORKERS", "int", "2", _range(1, 4), "1..4"),
    EnvVar("SPARK_EXECUTORS", "int", "2", _range(1, 8), "1..8"),
    EnvVar("SPARK_EXECUTOR_CORES", "int", "1", _range(1, 8), "1..8"),
    EnvVar("SPARK_EXECUTOR_MEMORY", "str", "768m", _MEMORY_PATTERN.match, "e.g. 512m, 1g"),
    EnvVar("TRIGGER_INTERVAL", "str", "1 second", _TRIGGER_PATTERN.match, "'<n> second(s)' or '<n> millisecond(s)'"),
    EnvVar("DATA_DIR", "path", "./runtime/data"),
    EnvVar("MODEL_BUNDLE_PATH", "path", "./runtime/bundle/current"),
    EnvVar("CHECKPOINT_DIR", "path", "./runtime/checkpoints"),
    EnvVar("RESULTS_DIR", "path", "./Module4_Storage_Dashboard_Benchmarking/results"),
    EnvVar("PRODUCER_RATE", "int", "5000", _range(1, 100_000), "1..100000 events/s"),
    EnvVar("RUN_DURATION_S", "int", "600", _range(1, 86_400), "1..86400"),
    EnvVar("ATTACK_MODE", "str", "none", lambda v: v in ATTACK_MODES, "|".join(ATTACK_MODES)),
    EnvVar("ATTACK_SHARE", "float", "0.0", _range(0.0, 1.0), "0.0..1.0"),
    EnvVar("RUN_ID", "str", "DEV-local", RUN_ID_PATTERN.match, "see C-06 §6"),
)
ENV_NAMES = tuple(v.name for v in ENV_SPEC)


@dataclass(frozen=True)
class RuntimeConfig:
    workspace_root: Path
    kafka_bootstrap: str
    kafka_topic: str
    kafka_partitions: int
    cassandra_hosts: Tuple[str, ...]
    cassandra_port: int
    cassandra_keyspace: str
    spark_master_url: str
    spark_workers: int
    spark_executors: int
    spark_executor_cores: int
    spark_executor_memory: str
    trigger_interval: str
    data_dir: Path
    model_bundle_path: Path
    checkpoint_dir: Path
    results_dir: Path
    producer_rate: int
    run_duration_s: int
    attack_mode: str
    attack_share: float
    run_id: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for key, value in self.__dict__.items():
            out[key] = str(value) if isinstance(value, Path) else (list(value) if isinstance(value, tuple) else value)
        return out


def find_workspace_root(start: Optional[Path] = None) -> Path:
    """Nearest directory (start or a parent) containing CONSTITUTION.md; falls back to start."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / WORKSPACE_MARKER).is_file():
            return candidate
    return start


def _convert(var: EnvVar, raw: Any) -> Any:
    if var.kind == "int":
        try:
            if isinstance(raw, bool):
                raise ValueError
            value: Any = int(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"{var.name}={raw!r} is not an integer") from None
    elif var.kind == "float":
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"{var.name}={raw!r} is not a number") from None
    else:
        value = str(raw).strip()
    if var.check is not None and not var.check(value):
        raise ConfigError(f"{var.name}={raw!r} violates rule: {var.rule}")
    return value


def load_config(
    env: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, Any]] = None,
    cwd: Optional[Path] = None,
) -> RuntimeConfig:
    """Resolve and validate the C-06 configuration. Raises ConfigError on bad values.

    `overrides` are CLI flag values keyed by env-var name (None values are ignored).
    """
    env = os.environ if env is None else env
    overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
    unknown = sorted(set(overrides) - set(ENV_NAMES))
    if unknown:
        raise ConfigError(f"unknown config keys {unknown}")

    values: Dict[str, Any] = {}
    for var in ENV_SPEC:
        if var.name in overrides:
            raw = overrides[var.name]
        elif env.get(var.name, "") != "":
            raw = env[var.name]
        else:
            raw = var.default
        values[var.name] = _convert(var, raw) if raw != "" or var.kind != "path" else ""

    root_raw = values["IDS_ROOT"]
    root = Path(root_raw).expanduser().resolve() if root_raw else find_workspace_root(cwd)
    if not root.is_dir():
        raise ConfigError(f"IDS_ROOT={root} is not a directory")

    def path(name: str) -> Path:
        p = Path(values[name]).expanduser()
        return p if p.is_absolute() else (root / p).resolve()

    if values["ATTACK_MODE"] == "none" and values["ATTACK_SHARE"] != 0.0:
        raise ConfigError("ATTACK_SHARE must be 0 when ATTACK_MODE=none")
    if values["ATTACK_MODE"] != "none" and values["ATTACK_SHARE"] <= 0.0:
        raise ConfigError("ATTACK_SHARE must be > 0 when ATTACK_MODE is not none")

    return RuntimeConfig(
        workspace_root=root,
        kafka_bootstrap=values["KAFKA_BOOTSTRAP"],
        kafka_topic=values["KAFKA_TOPIC"],
        kafka_partitions=values["KAFKA_PARTITIONS"],
        cassandra_hosts=tuple(h.strip() for h in values["CASSANDRA_HOSTS"].split(",") if h.strip()),
        cassandra_port=values["CASSANDRA_PORT"],
        cassandra_keyspace=values["CASSANDRA_KEYSPACE"],
        spark_master_url=values["SPARK_MASTER_URL"],
        spark_workers=values["SPARK_WORKERS"],
        spark_executors=values["SPARK_EXECUTORS"],
        spark_executor_cores=values["SPARK_EXECUTOR_CORES"],
        spark_executor_memory=values["SPARK_EXECUTOR_MEMORY"],
        trigger_interval=values["TRIGGER_INTERVAL"],
        data_dir=path("DATA_DIR"),
        model_bundle_path=path("MODEL_BUNDLE_PATH"),
        checkpoint_dir=path("CHECKPOINT_DIR"),
        results_dir=path("RESULTS_DIR"),
        producer_rate=values["PRODUCER_RATE"],
        run_duration_s=values["RUN_DURATION_S"],
        attack_mode=values["ATTACK_MODE"],
        attack_share=values["ATTACK_SHARE"],
        run_id=values["RUN_ID"],
    )


ENV_FILE_RELATIVE = Path("integration") / ".env"


def load_runtime_config(
    overrides: Optional[Mapping[str, Any]] = None,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> RuntimeConfig:
    """What every module CLI calls (C-06 §2): `<root>/integration/.env` (if present) < process env < overrides."""
    env = dict(os.environ if env is None else env)
    root = Path(env["IDS_ROOT"]).expanduser().resolve() if env.get("IDS_ROOT") else find_workspace_root(cwd)
    env_file = root / ENV_FILE_RELATIVE
    merged = dict(read_env_file(env_file)) if env_file.is_file() else {}
    merged.update({k: v for k, v in env.items() if v != ""})
    return load_config(env=merged, overrides=overrides, cwd=root)


def validate_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.match(run_id))


def summary_line(command: str, run_id: str, status: str = "ok", **fields: Any) -> str:
    """The single JSON line every C-06 CLI prints last on stdout."""
    payload = {"status": status, "command": command, "run_id": run_id}
    payload.update(fields)
    return json.dumps(payload, separators=(",", ":"), default=str)


def read_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file (comments and blank lines ignored, no quoting rules)."""
    result: Dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.split(" #", 1)[0].strip()
    return result
````

## A25. `contracts/python/tests/test_events.py`

````python
"""Contract tests for C-01 Network Event."""
import copy
import json

import pytest

from ids_contracts import FIXTURES_DIR, SCHEMAS_DIR, ContractViolation
from ids_contracts import events as ev

GOLDEN = FIXTURES_DIR / "events_golden.jsonl"


@pytest.fixture(scope="module")
def golden():
    return list(ev.iter_jsonl(GOLDEN))


@pytest.fixture
def valid():
    return {
        "event_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
        "timestamp": 1767225600123,
        "src_ip": "172.16.0.1",
        "dst_ip": "192.168.10.50",
        "dst_port": 80,
        "bytes_sent": 1032,
        "syn_flag": 1,
        "ack_flag": 0,
        "orig_ts": "7/7/2017 3:56",
        "label": "DDoS",
        "is_injected": False,
    }


def test_golden_fixture_shape(golden):
    assert len(golden) == 126
    assert {e["src_ip"] for e in golden} == {"192.168.10.5", "172.16.0.10", "172.16.0.20", "172.16.0.30"}
    assert len({e["event_id"] for e in golden}) == 126


def test_golden_fixture_validates_strict(golden):
    for e in golden:
        assert ev.validate_event(e, strict=True) == [], e


def test_golden_fixture_has_late_event_within_watermark(golden):
    max_seen = max(e["timestamp"] for e in golden[:-1])
    late = golden[-1]
    assert late["timestamp"] < max_seen
    assert max_seen - late["timestamp"] < 60_000


def test_golden_fixture_is_deterministic(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen", FIXTURES_DIR / "_gen" / "gen_events_golden.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rebuilt = b"".join(ev.encode_event(e) + b"\n" for e in gen.build())
    assert rebuilt == GOLDEN.read_bytes()


def test_valid_event_passes(valid):
    assert ev.validate_event(valid, strict=True) == []
    ev.check_event(valid)


@pytest.mark.parametrize(
    "field,value,fragment",
    [
        ("timestamp", 1767225600, "seconds"),
        ("timestamp", "1767225600123", "integer"),
        ("dst_port", 70000, "dst_port"),
        ("dst_port", True, "dst_port"),
        ("bytes_sent", -1, "bytes_sent"),
        ("syn_flag", 1.0, "syn_flag"),
        ("src_ip", "999.1.1.1", "src_ip"),
        ("event_id", "not-a-uuid", "event_id"),
        ("label", "Bogus", "label"),
        ("is_injected", True, "INJ_"),
    ],
)
def test_invalid_values_rejected(valid, field, value, fragment):
    bad = copy.deepcopy(valid)
    bad[field] = value
    errors = ev.validate_event(bad)
    assert errors and any(fragment in msg for msg in errors), errors
    with pytest.raises(ContractViolation):
        ev.check_event(bad)


def test_missing_required_field(valid):
    del valid["src_ip"]
    assert any("src_ip" in m for m in ev.validate_event(valid))


def test_unknown_fields_only_rejected_in_strict_mode(valid):
    valid["future_field"] = 1
    assert ev.validate_event(valid) == []
    assert ev.validate_event(valid, strict=True)


def test_optional_and_eval_fields_may_be_absent(valid):
    for name in ("orig_ts", "label", "is_injected"):
        valid.pop(name)
    assert ev.validate_event(valid, strict=True) == []


def test_encode_decode_roundtrip(valid):
    raw = ev.encode_event(valid)
    assert b"\n" not in raw and b" " not in raw.replace(b"7/7/2017 3:56", b"")
    assert ev.decode_event(raw) == valid
    assert ev.event_key(valid) == b"172.16.0.1"


@pytest.mark.parametrize("raw", [b"not json", b"[1,2]", b'{"timestamp": NaN}', b"\xff\xfe"])
def test_decode_rejects_garbage(raw):
    with pytest.raises(ContractViolation):
        ev.decode_event(raw)


def test_scoring_fields_exclude_eval_only():
    assert not set(ev.SCORING_FIELDS) & set(ev.EVAL_ONLY_FIELDS)


@pytest.mark.parametrize(
    "raw,expected",
    [(" BENIGN ", "BENIGN"), ("Web Attack \x96 Brute Force", "Web Attack - Brute Force"),
     ("Web Attack � XSS", "Web Attack - XSS"), ("Web Attack – Sql Injection", "Web Attack - Sql Injection")],
)
def test_normalise_label(raw, expected):
    assert ev.normalise_label(raw) == expected
    assert expected in ev.LABELS


def test_cic_reference_is_consistent_with_file_order():
    stems = [s for day in ev.REPLAY_DAYS for s in ev.CIC_FILE_ORDER[day]]
    assert stems == list(ev.CIC_REFERENCE)
    assert sum(rows for _, rows in ev.CIC_REFERENCE.values()) == ev.CIC_TOTAL_VALID_ROWS == 2_830_743
    assert all(len(sha) == 64 for sha, _ in ev.CIC_REFERENCE.values())


def test_verify_cic_file(tmp_path):
    bogus = tmp_path / "Monday-WorkingHours.pcap_ISCX.csv"
    bogus.write_text("not the real file")
    assert ev.verify_cic_file(bogus) and "sha256" in ev.verify_cic_file(bogus)[0]
    other = tmp_path / "notes.csv"
    other.write_text("x")
    assert "not a C-01 source file" in ev.verify_cic_file(other)[0]


def _manifest():
    return {
        "contract": "C-01", "contract_version": ev.CONTRACT_VERSION, "tool": "ids_ingest.prepare",
        "tool_version": "0.2.0", "created_at": "2026-10-21T00:00:00Z",
        "inputs": [{"source_file": "Monday-WorkingHours", "day": "Monday", "sha256": "0" * 64, "verified": True,
                    "data_rows": 12, "valid_rows": 10, "dropped": {"empty_row": 2}}],
        "days": {"Monday": {"rows": 10, "files": ["Monday-WorkingHours"], "content_sha256": "a" * 64,
                            "path": "day=Monday/part-00000.parquet"}},
        "total_rows": 10, "labels": {"BENIGN": 10},
    }


def test_replay_reference_hashes_cover_all_days():
    assert list(ev.REPLAY_CONTENT_SHA256) == list(ev.REPLAY_DAYS)
    assert all(len(h) == 64 for h in ev.REPLAY_CONTENT_SHA256.values())


def test_valid_manifest_passes():
    assert ev.validate_manifest(_manifest()) == []


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        (lambda m: m.pop("labels"), "missing 'labels'"),
        (lambda m: m.update(total_rows=11), "total_rows"),
        (lambda m: m["inputs"][0]["dropped"].update(meteor_strike=1), "unknown drop reasons"),
        (lambda m: m["inputs"][0].update(data_rows=99), "data_rows != valid_rows"),
        (lambda m: m["labels"].update(BENIGN=9), "label counts"),
        (lambda m: m["days"].update(Sunday=m["days"]["Monday"]), "unknown day"),
        (lambda m: m.update(contract="C-02"), "expected 'C-01'"),
    ],
)
def test_invalid_manifest_detected(mutate, fragment):
    m = _manifest()
    mutate(m)
    errors = ev.validate_manifest(m)
    assert errors and any(fragment in e for e in errors), errors


def test_replay_columns_validator():
    assert ev.validate_replay_columns(dict(ev.REPLAY_COLUMNS)) == []
    cols = dict(ev.REPLAY_COLUMNS)
    cols["dst_port"] = "int64"
    del cols["label"]
    cols["extra"] = "string"
    errors = ev.validate_replay_columns(cols)
    assert len(errors) == 3


def test_json_schema_agrees_with_python_validator(golden, valid):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMAS_DIR / "event.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for e in golden + [valid]:
        assert not list(validator.iter_errors(e)), e
    assert set(schema["required"]) == set(ev.REQUIRED_FIELDS)
    assert set(schema["properties"]) == set(ev.ALL_FIELDS)
    assert set(schema["properties"]["label"]["enum"]) == set(ev.LABELS)
    bad = dict(valid, is_injected=True)
    assert list(validator.iter_errors(bad))
````

## A26. `contracts/python/tests/test_config.py`

````python
"""Contract tests for C-06 Runtime Config and Control."""
import json

import pytest

from ids_contracts import CONTRACTS_DIR
from ids_contracts import config as cfg

ROOT = CONTRACTS_DIR.parent
ENV_EXAMPLE = ROOT / "integration" / ".env.example"


def test_defaults_load_and_resolve_paths_against_workspace_root():
    c = cfg.load_config(env={}, cwd=ROOT / "Module1_Data_Ingestion_Platform")
    assert c.workspace_root == ROOT
    assert c.kafka_topic == "network-events"
    assert c.kafka_partitions == 8
    assert c.cassandra_hosts == ("localhost",)
    assert (c.spark_workers, c.spark_executor_memory) == (2, "768m")
    assert c.data_dir == ROOT / "runtime" / "data"
    assert c.results_dir == ROOT / "Module4_Storage_Dashboard_Benchmarking" / "results"
    assert c.attack_mode == "none" and c.attack_share == 0.0


def test_precedence_override_beats_env_beats_default():
    env = {"PRODUCER_RATE": "7000", "KAFKA_PARTITIONS": "4"}
    c = cfg.load_config(env=env, overrides={"PRODUCER_RATE": 9000, "KAFKA_PARTITIONS": None}, cwd=ROOT)
    assert c.producer_rate == 9000
    assert c.kafka_partitions == 4


def test_empty_env_value_falls_back_to_default():
    assert cfg.load_config(env={"KAFKA_TOPIC": ""}, cwd=ROOT).kafka_topic == "network-events"


@pytest.mark.parametrize(
    "key,value",
    [
        ("KAFKA_PARTITIONS", "0"), ("KAFKA_PARTITIONS", "17"), ("SPARK_WORKERS", "5"), ("KAFKA_PARTITIONS", "eight"),
        ("PRODUCER_RATE", "0"), ("ATTACK_MODE", "nuke"), ("ATTACK_SHARE", "1.5"),
        ("TRIGGER_INTERVAL", "1s"), ("SPARK_EXECUTOR_MEMORY", "1GB"), ("KAFKA_BOOTSTRAP", "localhost"),
        ("CASSANDRA_KEYSPACE", "ids-prod"), ("RUN_ID", "my run"), ("SPARK_MASTER_URL", "http://x:7077"),
    ],
)
def test_invalid_values_raise_config_error(key, value):
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={key: value}, cwd=ROOT)


def test_attack_mode_and_share_must_be_consistent():
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={"ATTACK_MODE": "none", "ATTACK_SHARE": "0.2"}, cwd=ROOT)
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={"ATTACK_MODE": "ddos", "ATTACK_SHARE": "0"}, cwd=ROOT)
    c = cfg.load_config(env={"ATTACK_MODE": "ddos", "ATTACK_SHARE": "0.2"}, cwd=ROOT)
    assert (c.attack_mode, c.attack_share) == ("ddos", 0.2)


def test_unknown_override_key_rejected():
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={}, overrides={"KAFKA_TOPICS": "x"}, cwd=ROOT)


@pytest.mark.parametrize(
    "run_id,ok",
    [("E1-p4-e2-r5000-a0-202611061430", True), ("E3-p8-e2-r5000-a20-202611071000", True),
     ("DEV-local", True), ("DEV-aswin_test.1", True), ("E4-p4-e2-r5000-a0-202611061430", False),
     ("E1-p4-e2-r5000-a0-2026", False), ("dev-local", False)],
)
def test_run_id_pattern(run_id, ok):
    assert cfg.validate_run_id(run_id) is ok


def test_summary_line_is_single_json_line():
    line = cfg.summary_line("producer", "DEV-local", sent=10, achieved_rate=5000.0)
    assert "\n" not in line
    data = json.loads(line)
    assert data == {"status": "ok", "command": "producer", "run_id": "DEV-local", "sent": 10, "achieved_rate": 5000.0}


def test_env_example_matches_env_spec_and_loads():
    env = cfg.read_env_file(ENV_EXAMPLE)
    assert list(env) == list(cfg.ENV_NAMES)
    for var in cfg.ENV_SPEC:
        if var.name != "IDS_ROOT":
            assert env[var.name] == var.default, var.name
    cfg.load_config(env=env, cwd=ROOT)


def test_runtime_config_layers_env_file_under_process_env(tmp_path):
    (tmp_path / "CONSTITUTION.md").write_text("x")
    (tmp_path / "integration").mkdir()
    (tmp_path / "integration" / ".env").write_text("PRODUCER_RATE=6000\nKAFKA_PARTITIONS=4\n# comment\n")
    c = cfg.load_runtime_config(env={"KAFKA_PARTITIONS": "16"}, cwd=tmp_path / "integration")
    assert c.workspace_root == tmp_path.resolve()
    assert c.producer_rate == 6000          # from .env
    assert c.kafka_partitions == 16         # process env beats .env
    c2 = cfg.load_runtime_config(env={}, overrides={"PRODUCER_RATE": 7000}, cwd=tmp_path)
    assert c2.producer_rate == 7000         # override beats .env


def test_runtime_config_without_env_file_uses_defaults(tmp_path):
    (tmp_path / "CONSTITUTION.md").write_text("x")
    assert cfg.load_runtime_config(env={}, cwd=tmp_path).kafka_partitions == 8


def test_config_as_dict_is_json_serialisable():
    json.dumps(cfg.load_config(env={}, cwd=ROOT).as_dict())
````

## A27. `integration/.env.example`

````text
# C-06 Runtime Config — copy to integration/.env (git-ignored) and adjust locally.
# Host-side defaults shown; inside the compose network use kafka:29092, cassandra, spark://spark-master:7077.
# IDS_ROOT is auto-detected (nearest parent containing CONSTITUTION.md) when left unset.
IDS_ROOT=
KAFKA_BOOTSTRAP=localhost:9092
KAFKA_TOPIC=network-events
KAFKA_PARTITIONS=8
CASSANDRA_HOSTS=localhost
CASSANDRA_PORT=9042
CASSANDRA_KEYSPACE=ids
SPARK_MASTER_URL=spark://localhost:7077
SPARK_WORKERS=2
SPARK_EXECUTORS=2
SPARK_EXECUTOR_CORES=1
SPARK_EXECUTOR_MEMORY=768m
TRIGGER_INTERVAL=1 second
DATA_DIR=./runtime/data
MODEL_BUNDLE_PATH=./runtime/bundle/current
CHECKPOINT_DIR=./runtime/checkpoints
RESULTS_DIR=./Module4_Storage_Dashboard_Benchmarking/results
PRODUCER_RATE=5000
RUN_DURATION_S=600
ATTACK_MODE=none
ATTACK_SHARE=0.0
RUN_ID=DEV-local
````

## A28. `docs/adr/ADR-003-dataset-variant.md`

````markdown
# ADR-003: Use the CIC-IDS2017 TrafficLabelling CSVs

| Field | Value |
|---|---|
| Status | **Proposed** (team accepts at the P0 sync) |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-03 |
| Affects | C-01, M1-F02, M2 |

## Context
CIC-IDS2017 is distributed in two CSV variants. **MachineLearningCVE** has 78 flow features plus the label, but **no
`Source IP`, `Destination IP` or `Timestamp`**. **TrafficLabelling** (GeneratedLabelledFlows) has the same features plus
`Flow ID`, `Source IP`, `Source Port`, `Destination IP` and `Timestamp`. The pipeline groups windows by `src_ip` (proposal §2.3),
so it needs source IPs.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. TrafficLabelling | Has `Source IP` and `Timestamp`, so it matches the proposal's event schema | Slightly larger. latin-1 encoding and some empty or garbled rows need cleaning |
| B. MachineLearningCVE | Cleaner, widely used | No source IP, so the `src_ip` grouping is impossible. Synthetic IPs would invalidate realism |

## Decision
We use **TrafficLabelling**. M1-F02 cleans it per C-01 §3.2: strip headers, read as latin-1, normalise labels, and drop invalid rows with per-reason counts in the replay manifest.

## Consequences
- Positive: the real per-host behaviour of the dataset is preserved, and the port-scan and DDoS sources are real IPs.
- Negative: M1 must handle encoding and garbage rows. File names must be confirmed on download (C-01 §3.2).
- **Verified 2026-10-21:** all 8 TrafficLabelling CSVs downloaded (1.1 GB). Every one has `Source IP`, `Destination IP` and `Timestamp`. 2,830,743 valid flows. Checksums are in C-01 §3.2.
````

## A29. `docs/adr/ADR-006-event-timestamp.md`

````markdown
# ADR-006: Event `timestamp` is producer emission time

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-06 |
| Affects | C-01, C-02, C-05, M1-F03, M3, M4-F03 |

## Context
The CIC flows carry 2017 timestamps at minute resolution. Spark windows and watermarks run on event time, and the
latency metric is `detected_at − event time` (proposal §3.1). Replaying 2017 times would make every event "late" relative to
a 2026 wall clock, and would make latency meaningless.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. `timestamp` = emission time (epoch ms). Keep the original as `orig_ts` | Watermarks work, latency is measurable end to end | Original inter-arrival timing is not reproduced (handled in ADR-011) |
| B. Original 2017 time shifted to now | Preserves original timing | Minute resolution creates bursts. Rate control conflicts with timing. Harder to benchmark at a fixed rate |
| C. Use the Kafka record timestamp only | No field needed | Ties event time to the broker. Not visible in the JSON for offline use |

## Decision
Option A. The producer stamps `timestamp` (epoch ms UTC) immediately before send. `orig_ts` is kept as text for traceability only.

## Consequences
- Latency (C-05) starts at a well-defined point. Windows contain events at the replay rate.
- Offline features must simulate emission timing. See ADR-011.
````

## A30. `docs/adr/ADR-007-eval-only-fields.md`

````markdown
# ADR-007: Eval-only ground-truth fields in the stream

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-07 |
| Affects | C-01, C-02, C-04, M1, M3, M4-F04 |

## Context
F2 (benign FPR), F3 (rule versus hybrid per attack category) and E3 (attack-injection share) are evaluated **online**, so
ground truth has to travel with the data. The proposal's event schema has no label.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Optional `label` + `is_injected` on each event, marked eval-only | Simple. The ground truth reaches the window rows | Risk of leakage into scoring |
| B. A separate ground-truth topic or side table joined later | No leakage risk | Complex join on event_id or window. More moving parts |

## Decision
Option A, with guards:
1. The fields are optional and documented as **eval-only** in C-01.
2. `ids_contracts.events.SCORING_FIELDS` lists the only fields that features and rules may read. Contract tests in M2 and M3 assert this.
3. Window ground truth (C-02) is `label_attack = any(label ≠ BENIGN)`, stored as eval-only columns in C-04.

## Consequences
- Online evaluation is possible with no joins.
- Every scoring-path spec must state that eval-only fields are excluded (spec review checklist).
````

## A31. `docs/adr/ADR-009-version-pins.md`

````markdown
# ADR-009: Pin versions identically across Colab, host and Spark images

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-09 |
| Affects | `contracts/versions.md`, C-03, M1-F01, M2-F03, M3-F03 |

## Context
The model is trained in Google Colab and scored inside Spark executors via `pandas_udf`. scikit-learn pickles are not
guaranteed to load across versions. `pandas_udf` requires the same Python minor version on the driver and workers. Spark 3.5 does not
officially support Java 21, which is what the M1 owner's host has.

## Decision
- A single pin table in `contracts/versions.md`, with scikit-learn, numpy, pandas, pyarrow and joblib identical everywhere.
- Colab training starts with the pinned `pip install` cell. The bundle manifest (C-03) records the versions it was trained with.
- The stream job is submitted from a container built from the Spark worker image, never from the host.
- Java 17 for Spark (host and image). Spark 3.5.5 (rather than 4.x) for Spark Cassandra Connector compatibility.

## Consequences
- An M3 contract test loads the bundle inside the Spark image (risk R3).
- Pins are marked "Verified" only after they actually run (for example in M1-F01). Unavailable tags or wheels go through a CR.
````

## A32. `docs/adr/ADR-011-replay-time-model.md`

````markdown
# ADR-011: Constant-rate replay with a matching offline time model

| Field | Value |
|---|---|
| Status | **Proposed** (M1 + M2 must both accept) |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-11 |
| Affects | C-01 §4.4, C-02, M1-F03, M2-F02, M2-F03, E3 |

## Context
With ADR-006, online windows contain events at the replay rate R. If M2 computed training windows from the original
2017 timing, rate-dependent features (`packet_rate`, `total_bytes`, `unique_ports` per window) would follow a different
distribution than at serving time. That is training/serving skew, and it would silently break F1 and F2.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Constant-rate replay at R. Offline simulates `ts_i = t0 + i·1000/R_ref` | Exact parity at R_ref. Simple producer rate control | Not the original traffic timing. Detection quality is only valid at R_ref |
| B. Replay preserving original inter-arrival times × speed-up | More realistic timing | Minute-resolution timestamps make the timing unknown inside a minute. Rate is hard to control for benchmarks |
| C. Rate-invariant features (normalise by window count) | Robust to rate | Changes the proposal's feature set. Weaker signal |

## Decision
Option A, with **R_ref = 5000 ev/s**. The producer emits in `row_idx` order (C-01 §4.4). M2 simulates the same timestamps when
building training windows. F1, F2, F3 and E3 are evaluated at R_ref. E1 and E2 vary throughput, and their detection numbers are not reported.

## Consequences
- The golden fixtures and parity tests guarantee identical windows offline and online.
- The report must state that detection quality is measured at the reference rate.
````

## A33. `integration/README.md`

````markdown
# Integration

This folder holds what is needed to connect the four modules. It is jointly owned.
**Integration lead (proposed): M1 owner**, because M1 owns the platform. Confirm in P0.

## Planned integrations

| ID | Seam | Modules | Contracts | Phase | Proves |
|---|---|---|---|---|---|
| I-01 | Kafka events | M1 → M3 | C-01, C-06 | P2 | Events reach Spark at the target rate with no schema errors |
| I-02 | Detection bundle and features | M2 → M3 | C-02, C-03 | P2 | Spark features equal the golden fixture, and the bundle loads and scores in the Spark image |
| I-03 | Anomaly store and metrics | M3 → M4 | C-04, C-05 | P2 | Rows and metrics written by Spark render in the dashboard |
| I-04 | Full pipeline | M1→M3→M4 + M2 | All | P3 | E2E smoke test, then E1/E2/E3 runnable from the M4 harness |

Use [../sdd/templates/integration-checklist-template.md](../sdd/templates/integration-checklist-template.md)
and save results as `checklists/I-0x-<slug>.md`.

## Swapping in a teammate's module

1. Replace the folder `ModuleN_<name>/` in your tree with the owner's copy. Do not merge the two.
2. Confirm that `contracts/` is identical on both sides (same versions).
3. Run `make contract-test` in **all four** module folders.
4. If they all pass, run the relevant integration checklist. If any fail, the failing side has a contract
   violation: fix it, or raise a CR if the contract itself is wrong.

## Planned contents (built in P2/P3)

```
integration/
├── checklists/            ← signed I-xx checklists
├── docker-compose.yml     ← overlay that runs each module's `run` on M1's platform
├── .env.example           ← generated from C-06
└── e2e/                   ← end-to-end smoke tests using the golden fixtures
```
````

## A34. `Module1_Data_Ingestion_Platform/README.md`

````markdown
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
````

## A35. `Module2_ML_Anomaly_Model/README.md`

````markdown
> **REPLICA built by Aswin S. (M1). Canonical owner: Nitish Kumar Yadav.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 2 — ML Anomaly Model

| | |
|---|---|
| Owner | **Nitish Kumar Yadav** |
| Python package | `ids_model` |
| Status | Replica: M2-F02 ✅ · M2-F03 ✅ implemented (targets: see D-14) · M2-F04 ✅ · M2-F01 (EDA) not started |
| Contracts owned | C-02 Feature Definition, C-03 Detection Bundle |
| Contracts consumed | C-01 (replay dataset format), C-06 (paths, version pins) |

## Purpose
This module trains an unsupervised Isolation Forest offline (Colab) on windowed CIC-IDS2017 features
that exactly match what Spark computes at runtime, evaluates it against F1 and F2, and packages the model
and the rule set as a self-describing detection bundle for the stream job.

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M2-F01 EDA and window labelling rule | `specs/M2-F01-eda-window-labelling/` | Not started |
| M2-F02 Reference feature builder (pandas) + golden fixture | [specs/M2-F02-reference-features/](specs/M2-F02-reference-features/spec.md) | ✅ Verified (replica, 3/3) |
| M2-F03 IF training and evaluation (precision, recall, FPR) | [specs/M2-F03-if-training-eval/](specs/M2-F03-if-training-eval/spec.md) | ✅ Implemented (replica). F1 recall 0.941 ✅ · F2 1.21 % ✅ · F1 precision 0.058 ❌ (D-14) |
| M2-F04 Detection bundle + rules + offline rule-vs-hybrid | [specs/M2-F04-detection-bundle/](specs/M2-F04-detection-bundle/spec.md) | ✅ Verified (replica, 6/6: dummy bundle + golden scores) |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Feature definition + golden fixtures | C-02 | M3 | `contracts/fixtures/features_golden.csv` |
| Detection bundle (model, scaler, manifest, rules) | C-03 | M3 | `mocks/dummy_bundle/` (ship on day 1) |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Replay dataset (Parquet) | C-01 | M1 | Raw CIC CSV sample mapped with the C-01 column table |

## Quick start
```bash
make install && make test && make contract-test
make mock              # dummy bundle → mocks/dummy_bundle + runtime/bundle/current; golden scores → contracts/fixtures/scores_golden.csv
make run               # validate the bundle at MODEL_BUNDLE_PATH
make integration-test  # the bundle loads and scores identically inside the Spark image (platform up)
python -m ids_model.train [--install]   # real training (about 5 s): bundle runtime/bundle/1.0.0-replica + docs/measurements/F03-training-<date>.{md,json}
```
```python
from ids_model.features import build_features, features_from_replay   # C-02 in pandas (golden parity)
from ids_model.bundle import Bundle                                     # C-03: Bundle.load(path).score(features_df)
```
The dummy bundle flags the golden port scan and SYN flood via `R-SYN-FLOOD` only. Its ML threshold (0.654) comes from synthetic data, so
`ml_flag` is false on all golden windows. Real training is M2-F03.
````

## A36. `Module3_Spark_Stream_Processing/README.md`

````markdown
> **REPLICA built by Aswin S. (M1). Canonical owner: Kumari Priyanka.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 3 — Spark Stream Processing

| | |
|---|---|
| Owner | **Kumari Priyanka** |
| Python package | `ids_stream` |
| Status | Replica: M3-F01 ✅ · F02 ✅ · F03 ✅ · F04 ✅ (end-to-end verified) |
| Contracts owned | C-05 Pipeline Metrics |
| Contracts consumed | C-01 (events), C-02 (features), C-03 (bundle), C-04 (store), C-06 (config) |

## Purpose
This module is the PySpark Structured Streaming job at the centre of the pipeline. It consumes events
from Kafka, computes 30 s / 10 s sliding-window features per source IP, scores them with the broadcast
Isolation Forest via `pandas_udf` alongside rule checks, and writes results and runtime metrics to Cassandra.
Checkpointing gives fast recovery.

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M3-F01 Stream ingest (Kafka source, parse, watermark, bad records) | [specs/M3-F01-stream-ingest/](specs/M3-F01-stream-ingest/spec.md) | ✅ Verified (replica) |
| M3-F02 Windowed features (C-02 parity with golden fixture) | [specs/M3-F02-windowed-features/](specs/M3-F02-windowed-features/spec.md) | ✅ Verified (replica, golden 23/23) |
| M3-F03 Hybrid scoring (broadcast bundle, `pandas_udf`, rules) | [specs/M3-F03-hybrid-scoring/](specs/M3-F03-hybrid-scoring/spec.md) | ✅ Verified (replica, golden scores) |
| M3-F04 Sink, metrics, checkpointing and recovery | [specs/M3-F04-sink-metrics-recovery/](specs/M3-F04-sink-metrics-recovery/spec.md) | ✅ Verified (replica, e2e + recovery) |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Anomaly rows | C-04 (as writer) | M4 | `mocks/fake_stream_writer.py` |
| Pipeline metrics | C-05 | M4 | `mocks/fake_stream_writer.py` |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Events | C-01 | M1 | `events_golden.jsonl` pushed by `producer --source fixture` |
| Feature spec + fixture | C-02 | M2 | `contracts/fixtures/features_golden.csv` |
| Detection bundle | C-03 | M2 | `Module2_ML_Anomaly_Model/mocks/dummy_bundle/` (copied to `MODEL_BUNDLE_PATH`) |
| Store schema | C-04 | M4 | `contracts/schemas/ids_schema.cql` |

## Quick start
```bash
make install && make test && make contract-test     # host side (no PySpark needed)
# Platform up (Module 1), topic created, bundle installed (Module 2 `make mock` → runtime/bundle/current):
python -m ids_stream.job --run-id DEV-x --starting-offsets earliest          # runs until Ctrl-C (graceful)
python -m ids_stream.job --executors 2 --trigger "1 second" --await-seconds 120 --run-id E2-...
make integration-test      # golden parity in Spark + end-to-end + worker-restart recovery (about 4 min)
```
- **Submission:** `job.py` submits `app.py` from `spark-client` (same Python as the workers), with `--py-files runtime/build/ids_stream.zip`.
- **Pipeline:** Kafka → C-01 parse/validate (malformed dropped and counted) → watermark 60 s → `window(30 s, 10 s)` per `src_ip` → `foreachBatch`:
  features → broadcast IsolationForest via `pandas_udf` + rules compiled from `rules.yaml` → upsert `ids.window_scores`.
- **Metrics:** listener progress → `ids.pipeline_metrics` (written from the main thread). One `ids.runs` row per start.
- **Checkpoint:** `runtime/checkpoints/<run_id>`.
````

## A37. `Module4_Storage_Dashboard_Benchmarking/README.md`

````markdown
> **REPLICA built by Aswin S. (M1). Canonical owner: Vidhi Kant Gupta.** Minimal but contract-conformant (playbook §8). Will be replaced at integration.

# Module 4 — Storage, Dashboard and Benchmarking

| | |
|---|---|
| Owner | **Vidhi Kant Gupta** |
| Python package | `ids_monitor` |
| Status | Replica: M4-F01 ✅ · M4-F02 ✅ · F03–F04 not started |
| Contracts owned | C-04 Anomaly Store |
| Contracts consumed | C-05 (metrics), C-06 (config + control CLI of M1/M3) |

## Purpose
This module owns the Cassandra time-series schema and its read access, the live Streamlit operations
dashboard with its drift alert, and the scripted benchmark harness that produces every number in the report
(E1, E2, E3, latency, recovery, FPR).

## Scope (features)
| Feature | Spec | Status |
|---|---|---|
| M4-F01 Store schema, init and read repository + synthetic data generator | [specs/M4-F01-store-schema-access/](specs/M4-F01-store-schema-access/spec.md) | ✅ Verified (replica, 5/5) |
| M4-F02 Streamlit dashboard (throughput, anomaly gauge, top-10 IPs, drift banner) | [specs/M4-F02-dashboard/](specs/M4-F02-dashboard/spec.md) | ✅ Verified (replica, 5/5) |
| M4-F03 Benchmark harness (E1/E2/E3, p95 latency, efficiency, recovery) | `specs/M4-F03-benchmark-harness/` | Not started |
| M4-F04 Results analysis and report figures | `specs/M4-F04-results-analysis/` | Not started |

## Provides → consumers
| What | Contract | Consumer | Mock for others |
|---|---|---|---|
| Keyspace and table DDL | C-04 | M3 | `contracts/schemas/ids_schema.cql` + `python -m ids_monitor.schema apply` |
| Dashboard, benchmark results, figures | — | Team / report | — |

## Consumes ← providers
| What | Contract | Provider | Mock I use until integration |
|---|---|---|---|
| Anomaly rows + metrics | C-04, C-05 | M3 | `mocks/synthetic_rows.py` (own) or M3's `fake_stream_writer.py` |
| Control CLI (partitions, rate, attack share, executors) | C-06 | M1, M3 | Dry-run mode that only prints commands |

## Quick start
```bash
make install
make test && make contract-test
make run                     # schema apply + check (idempotent), against Cassandra on localhost:9042
make mock                    # 10 min of synthetic windows + metrics ending now (run_id DEV-synthetic)
python mocks/synthetic_rows.py --seconds 300 --anomaly-share 0.3 --follow 600   # keep writing live windows
make integration-test        # live tests (platform must be up)
make run                     # … then serves the dashboard on http://localhost:8501 (reads C-04/C-05 from Cassandra)
make demo                    # dashboard on in-memory synthetic data, no platform needed
```
**Dashboard (M4-F02):**
- **KPI tiles:** throughput, p95 latency, anomaly rate, windows scored.
- **Drift banner:** shown when the anomaly rate exceeds 15 % over the last 300 s.
- **Charts:** throughput, anomaly rate (with the 15 % rule), p50/p95 latency (one axis, with the 500 ms rule). All have hover tooltips.
- **Top-10 table:** flagged source IPs.
- **Controls:** run selector and time span. The page refreshes every 3 s.
- **Colours:** reference-palette slots 1–2, validated in light and dark (dataviz).
- **Pin a run:** `streamlit run src/ids_monitor/dashboard.py -- --run-id ID`.
Python access (used by the dashboard and benchmarks):
```python
from ids_contracts.config import load_runtime_config
from ids_monitor.store import connect, StoreReader
r = StoreReader(connect(load_runtime_config()))
r.recent_windows(now_ms, seconds=300, run_id=None); r.drift(now_ms); r.top_flagged(now_ms, n=10); r.metrics(run_id); r.runs()
```
Host connections use a single-node address translator (Cassandra advertises its container IP, which the Mac cannot reach).
````

## A38. `.gitignore`

````text
# Data and large artifacts (scripts that produce them ARE committed)
data/
*.csv
!contracts/fixtures/*.csv
*.parquet
!Module1_Data_Ingestion_Platform/mocks/replay_sample.parquet
*.joblib
!**/mocks/dummy_bundle/*.joblib
checkpoints/
**/results/raw/

# Python
__pycache__/
*.pyc
.venv/
.ipynb_checkpoints/
.pytest_cache/

# Env / OS
.env
.DS_Store

# Local runtime (data, model bundles, checkpoints)
runtime/
*.egg-info/
````

## A39. `sdd/build_playbook.sh`

````bash
#!/usr/bin/env bash
# Regenerates SDD_PLAYBOOK.md = sdd/playbook_core.md + verbatim copies of the workspace files (Appendix).
# Run from anywhere: bash sdd/build_playbook.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/SDD_PLAYBOOK.md"

FILES=(
  README.md
  PROJECT_PLAN.md
  CONSTITUTION.md
  sdd/WORKFLOW.md
  sdd/templates/spec-template.md
  sdd/templates/plan-template.md
  sdd/templates/tasks-template.md
  sdd/templates/contract-template.md
  sdd/templates/contract-change-request-template.md
  sdd/templates/adr-template.md
  sdd/templates/integration-checklist-template.md
  sdd/templates/module-readme-template.md
  sdd/templates/development-log-template.md
  contracts/README.md
  contracts/C-01_network_event.md
  contracts/C-06_runtime_config_control.md
  contracts/versions.md
  contracts/schemas/event.schema.json
  contracts/fixtures/README.md
  contracts/fixtures/_gen/gen_events_golden.py
  contracts/python/pyproject.toml
  contracts/python/ids_contracts/__init__.py
  contracts/python/ids_contracts/events.py
  contracts/python/ids_contracts/config.py
  contracts/python/tests/test_events.py
  contracts/python/tests/test_config.py
  integration/.env.example
  docs/adr/ADR-003-dataset-variant.md
  docs/adr/ADR-006-event-timestamp.md
  docs/adr/ADR-007-eval-only-fields.md
  docs/adr/ADR-009-version-pins.md
  docs/adr/ADR-011-replay-time-model.md
  integration/README.md
  Module1_Data_Ingestion_Platform/README.md
  Module2_ML_Anomaly_Model/README.md
  Module3_Spark_Stream_Processing/README.md
  Module4_Storage_Dashboard_Benchmarking/README.md
  .gitignore
  sdd/build_playbook.sh
)

{
  cat "$ROOT/sdd/playbook_core.md"
  printf '\n---\n\n# Appendix — Workspace files (create verbatim in PR-01)\n\n'
  printf 'Each block is the **exact content** of the file at the path in its heading, relative to the workspace root.\n'
  printf 'Generated on %s. Note: `sdd/playbook_core.md` is this document minus the Appendix; recreate it by copying §0–§9.\n\n' "$(date +%Y-%m-%d)"
  i=1
  for f in "${FILES[@]}"; do
    case "$f" in
      *.md) lang=markdown ;; *.sh) lang=bash ;; *.py) lang=python ;; *.json) lang=json ;; *.toml) lang=toml ;; *) lang=text ;;
    esac
    printf '## A%d. `%s`\n\n````%s\n' "$i" "$f" "$lang"
    cat "$ROOT/$f"
    printf '````\n\n'
    i=$((i+1))
  done
} > "$OUT"

echo "Wrote $OUT ($(wc -l < "$OUT") lines)"
````

