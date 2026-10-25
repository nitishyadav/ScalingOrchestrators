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
