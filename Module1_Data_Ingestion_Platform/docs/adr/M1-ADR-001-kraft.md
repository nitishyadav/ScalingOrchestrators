# M1-ADR-001: Run Kafka in KRaft mode (no ZooKeeper)

| Field | Value |
|---|---|
| Status | **Accepted** (owner, 2026-10-21, M1-F01 gate G2) |
| Deciders | Aswin S. (M1) |
| Affects | M1-F01, C-06 §4 (the `zookeeper` service is not used) |

## Context
The proposal (§2.2, Week 1–2) names "Kafka, Zookeeper, Spark, Cassandra". On a 16 GB laptop the Docker VM gets 10 GB (risk R1).
KRaft has been production-ready since Kafka 3.3, and ZooKeeper mode is removed in Kafka 4.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. KRaft single node (broker + controller) | About 0.5 GB less RAM, one fewer service, faster start, current default | Differs from the proposal wording |
| B. ZooKeeper + broker | Matches the proposal text | More memory, deprecated, an extra health dependency |

## Decision
Option A, using `apache/kafka:3.8.1` with `KAFKA_PROCESS_ROLES=broker,controller` and a fixed `CLUSTER_ID`.

## Consequences
- The memory budget (plan §4.4) fits in 10 GB. The final report states the deviation and the reason.
- Partition-scaling behaviour (E1) is unaffected. Partitions are a broker concern in both modes.
