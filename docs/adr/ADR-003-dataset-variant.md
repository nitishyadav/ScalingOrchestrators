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
