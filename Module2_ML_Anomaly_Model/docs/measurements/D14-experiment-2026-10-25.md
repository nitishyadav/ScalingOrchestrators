# D-14 feature experiment (2026-10-25)

Protocol as M2-F03 (no test leakage). Window = per (30 s window, src_ip). Flow level = each window's verdict applied to its flows.
Windows: train 37,939 · hold-out 17,845 · validation 119,536 · test 21,279

| Variant | Model inputs | Window P / R (hybrid) | Flow P / R (hybrid) | Benign flows in flagged windows (test / hold-out / validation) |
|---|---|---|---|---|
| V0-current | total_bytes, unique_ports, syn_ack_ratio, packet_rate | 0.058 / 0.941 | 0.595 / 1.000 | 86.7% / 80.0% / 87.9% |
| V1-ratios | bytes_per_flow, port_ratio, syn_share, ack_share | 0.101 / 0.941 | 0.814 / 1.000 | 29.1% / 24.1% / 41.7% |
| V2-ratios+rate | bytes_per_flow, port_ratio, syn_share, ack_share, packet_rate | 0.049 / 1.000 | 0.588 / 1.000 | 89.2% / 81.3% / 88.5% |
| V3-ratios+synack | bytes_per_flow, port_ratio, syn_ack_ratio, syn_share | 0.112 / 0.941 | 0.846 / 1.000 | 23.2% / 24.1% / 43.8% |

## Follow-up analysis (same day)
**Who flags benign traffic (V3, placeholder rules).** ML-only flags 0.0 % of hold-out benign flows (0.9 % on test). **All** of the remaining 24 % comes from
`R-PORT-SCAN` (`unique_ports ≥ 50`): at 270× replay compression, busy internal hosts (for example 192.168.10.12, 30k flows, 140 ports) exceed 50 ports per window.
`R-SYN-FLOOD` and `R-DDOS-RATE` flag 0 % benign.

**Rule tuning tried:** `unique_ports ≥ 50 AND port_ratio ≥ 0.5` cuts hold-out benign traffic 24.1 % → 6.5 %. The remainder is external servers (CDNs such as
72.21.91.29) whose response flows target client ephemeral ports (a CIC flow-direction artefact that mimics a scan). But it **misses the CIC PortScan** at a
strict ML threshold (recall 0.0), and with window-F1 threshold selection it pushes the ML threshold down (benign traffic 81–89 %). A 5 % benign-traffic
constraint is unreachable (floor about 6.5 %). With a 10 % constraint: flow P/R 0.767 / 0.446 (worse). **Rules are left as placeholders** (M2 owner to tune with more features).

**Decision (replica, provisional):** adopt **V3** (`bytes_per_flow, port_ratio, syn_ack_ratio, syn_share`) as the model inputs (C-02 0.2.0-replica) with placeholder rules:
flow-level P/R **0.846 / 1.000** (meets F1 at flow level), window FPR 0.60 % (was 1.22 %), window precision 0.112 (structural cap, 17 attack windows).
**D-12 consequence:** event-weighting is not viable (about 23 % benign traffic sits in rule-flagged windows even with no attack). Keep the window-share metric. The banner is
validated on an all-attack load (the proposal's Week 7 milestone), which the benchmark harness runs.
