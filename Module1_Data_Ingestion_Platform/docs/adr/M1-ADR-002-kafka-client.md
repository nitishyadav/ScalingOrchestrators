# M1-ADR-002: `confluent-kafka` as the Python Kafka client

| Field | Value |
|---|---|
| Status | **Accepted** (owner, 2026-10-21) |
| Deciders | Aswin S. (M1) |
| Affects | M1-F01 (topic_admin), M1-F03 (producer), `contracts/versions.md` |

## Context
M1-F03 must emit at least 12k ev/s from Python so that the producer is never the bottleneck (G1). topic_admin needs create, increase,
delete and config operations.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. `confluent-kafka` 2.6.1 (librdkafka) | 10× or more the throughput of pure Python, a complete AdminClient, arm64 macOS wheel available | Native library inside the wheel |
| B. `kafka-python` | Pure Python | Much lower producer throughput. Admin API less complete |

## Decision
Option A, pinned `confluent-kafka==2.6.1` (arm64 cp311 wheel verified on 2026-10-21).

## Consequences
- The host producer and the admin share one client library.
- The Spark side does not use it. Spark uses its own Kafka connector jars inside the image.
