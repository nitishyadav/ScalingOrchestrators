# ScalingOrchestrators

Real-Time Network Intrusion Detection using Streaming ML on Apache Kafka and PySpark

**Team:** Scaling Orchestrators — Priyanka Kumar, Aswin S., Nitish Yadav, Vidhi Gupta
**Course:** Data Engineering at Scale (DES), Indian Institute of Science, 2026

## Problem

Modern networks generate traffic at a scale where manual inspection is impossible, and most
production intrusion detection today relies on periodic batch jobs or rule-based signature
matching — both too slow or too rigid to catch novel attacks in time. This project builds a
pipeline that ingests raw network log events, computes traffic features over short time windows,
and scores them with an unsupervised ML model (Isolation Forest), all within a few hundred
milliseconds of the original event arriving.

### Design Goals

- **Throughput:** sustain at least 10,000 events/second end-to-end.
- **Detection latency:** anomaly alerts written within 500 ms (p95) of event ingestion.
- **Genuine ML inference:** an offline-trained scikit-learn Isolation Forest, broadcast to Spark
  workers and applied via a vectorized `pandas_udf` — no hardcoded thresholds in the scoring path.
- **Hybrid detection:** a lightweight rule check for known signatures runs alongside the ML model,
  with both labels stored separately for comparison.
- **Scalability measurement:** Kafka partition count and Spark executor count are varied
  independently to characterize scaling behavior and bottlenecks.
- **Live monitoring:** a Streamlit dashboard shows throughput, anomaly rate, and a drift/retraining
  alert when more than 15% of recent windows are flagged.

## Architecture

```
Log Producer  →  Apache Kafka  →  PySpark Streaming  →  Apache Cassandra  →  Streamlit
(CIC-IDS2017     (1–16 topic       (30s windows +         (time-series        (live dashboard
replay + attack   partitions)       ML inference)          anomaly sink)       + drift monitor)
injector)
```

A Python Kafka producer replays CIC-IDS2017 flow records as JSON events at a configurable rate,
with an attack-injection flag for triggering DDoS bursts or port-scan sequences on demand. A
PySpark Structured Streaming job consumes the topic, aggregates events into 30-second sliding
windows (10-second slide) per source IP, and scores the resulting feature vectors with a broadcast
Isolation Forest model. Both the ML score and rule-based flag are written to Cassandra, which a
Streamlit dashboard polls for live charts.

## Platforms Used

- **Apache Kafka** — message broker with configurable partitioning for scalability experiments.
- **Apache Spark / PySpark** — Structured Streaming, MLlib pipeline, `pandas_udf` for vectorized ML scoring.
- **Apache Cassandra** — wide-column store with a time-series schema, written via the Spark-Cassandra-Connector.
- **Docker Compose** — runs the full local cluster (Kafka, Zookeeper, Spark, Cassandra).
- **scikit-learn (Google Colab)** — offline training of the Isolation Forest on CIC-IDS2017.

## Data

Built on the [CIC-IDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) dataset (~2 GB of
labelled network flow features covering DDoS, DoS, Port Scan, Brute Force, Web Attack, and
Infiltration traffic). Each Kafka event carries `timestamp, src_ip, dst_ip, dst_port, bytes_sent,
syn_flag, ack_flag`; Spark aggregates these into four windowed features (`total_bytes`,
`unique_ports`, `syn_ack_ratio`, `packet_rate`) that feed the Isolation Forest.

## Evaluation

Three benchmark experiments, each run for 10 minutes on a local Docker Compose cluster:

| Experiment | Varies | Values | Held Fixed |
|---|---|---|---|
| E1 – Kafka Partitions | Topic partitions | 1, 4, 8, 16 | 2 executors, 5,000 events/s |
| E2 – Spark Parallelism | Spark executors | 1, 2, 4 | 8 partitions, 5,000 events/s |
| E3 – Attack Injection | Malicious event share | 0%, 5%, 20% | 8 partitions, 2 executors |

**Success criteria** include sustaining 10,000 events/s at 16 partitions, p95 latency under 500 ms
at 5,000 events/s, a ≥1.5x throughput gain from 1→4 partitions, recovery within 30s after a
simulated worker restart, Isolation Forest precision ≥0.80 / recall ≥0.75 on held-out CIC-IDS2017
data, and a false positive rate under 5% on clean traffic.

## Timeline (8 Weeks)

| Week | Focus |
|---|---|
| 1–2 | Stand up Docker Compose cluster; explore CIC-IDS2017; agree on event schema |
| 3 | Build Kafka producer with attack injection toggles |
| 4 | Train and serialize the Isolation Forest model on Google Colab |
| 5–6 | Build the PySpark Structured Streaming job with hybrid rule + ML scoring |
| 7 | Build the Streamlit dashboard with drift alerting |
| 8 | Run benchmark experiments; write report and prepare demo |

Report due **15 Nov 2026**; live demo **29 Nov 2026**.

See [des_project_proposal.html](des_project_proposal.html) for the full project proposal.
