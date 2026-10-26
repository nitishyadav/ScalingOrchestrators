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
