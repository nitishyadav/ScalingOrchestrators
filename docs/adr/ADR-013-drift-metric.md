# ADR-013: Drift banner keeps the anomalous-window share

| Field | Value |
|---|---|
| Status | **Proposed (replica)**. The owner, M4 (Vidhi), accepts or replaces it |
| Date | 2026-10-25 |
| Deciders | M4 owner, with M1 and M3 (drafted by Aswin, M1, in replica mode) |
| Resolves | D-12 |
| Affects | C-04 §4, M4-F02, M4-F03 (E3/F5), M1-F04 |

## Context
The drift banner (F5) fires when the share of anomalous windows exceeds 15 %. With per-`src_ip` windows, 20 % injected events
from 7 attacker IPs among hundreds of benign IPs give only about 2 % anomalous windows.

## Options
| Option | Finding |
|---|---|
| (a) Event-weighted share (Σ events in anomalous windows / Σ events) | Measured on real runs: **87–94 %** at 20 % injection under V0, because busy benign hosts sit in flagged windows. It overstates the attack share, and the banner would fire on normal traffic |
| (b) More attacker IPs in the injector | Changes M1-F04 and makes the attack less like CIC. Not needed for F5 |
| (c) Lower the 15 % threshold | Brings the banner close to benign noise (window FPR about 1 %) |
| **(d) Keep the window share; validate F5 with an all-attack load** | Matches the proposal's Week 7 milestone ("drift alarm on an all-attack load") |

## Decision
Option (d). `drift()` stays the anomalous-window share. F5 is validated by the benchmark harness (M4-F03 E3) with a
**100 % injection** phase. The E3 20 % level reports the share honestly, and is not expected to trigger the banner.

## Consequences
- No contract change.
- E3 adds a 100 % level. The report explains why 20 % does not trigger the banner.
