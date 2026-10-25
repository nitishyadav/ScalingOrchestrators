# ADR-012: Rate-invariant model inputs (C-02 0.2.0)

| Field | Value |
|---|---|
| Status | **Proposed (replica)**. The owner, M2 (Nitish), accepts or replaces it |
| Date | 2026-10-25 |
| Deciders | M2 owner, with M3 and M4 (drafted by Aswin, M1, in replica mode) |
| Resolves | D-14 |
| Affects | C-02, C-03, M2-F02/F03/F04, M3-F02/F03 |

## Context
With the 4 volume features (`total_bytes`, `unique_ports`, `syn_ack_ratio`, `packet_rate`) at R_ref = 5,000 ev/s, busy benign
hosts look like floods. Window precision was 0.058, and 87 % of benign flows sat in flagged windows (M2-F03, 2026-10-22).

## Options (measured offline, `ids_model.experiment_d14`, same M2-F03 protocol)
| Variant | Model inputs | Flow P / R (hybrid) | Benign flows in flagged windows |
|---|---|---|---|
| V0 (old) | total_bytes, unique_ports, syn_ack_ratio, packet_rate | 0.595 / 1.000 | 86.7 % |
| V1 | bytes_per_flow, port_ratio, syn_share, ack_share | 0.814 / 1.000 | 29.1 % |
| V2 | V1 + packet_rate | 0.588 / 1.000 | 89.2 % |
| **V3** | **bytes_per_flow, port_ratio, syn_ack_ratio, syn_share** | **0.846 / 1.000** | **23.2 %** (ML-only: 0 %) |

Full results: `Module2_ML_Anomaly_Model/docs/measurements/D14-experiment-2026-10-25.md`.

## Decision
Adopt **V3** as the model inputs. Add the 3 ratio columns to C-02 (0.2.0). Keep the 4 base features stored in C-04 and
usable by rules (`RULE_FEATURES`). The rules stay placeholders: the remaining 23 % benign comes entirely from `R-PORT-SCAN`
(`unique_ports ≥ 50`), and a tuned variant (also requiring `port_ratio ≥ 0.5`) missed the CIC PortScan. Rule tuning belongs to the M2 owner.

## Consequences
- Bundle `1.1.0-replica`: window P/R 0.112 / 0.941, hold-out FPR 1.0 %. F1 (window precision ≥ 0.80) is still not met. The
  report states window- and flow-level metrics, and explains that all CIC attacks come from one IP (172.16.0.1).
- Breaking change: bundles with the old `feature_order` are refused by the C-03 validator (M2 loader and M3 driver).
- The golden fixtures were regenerated, and M2/M3 golden parity, the bundle-in-image check and M3 end-to-end were re-proved on 2026-10-25.
