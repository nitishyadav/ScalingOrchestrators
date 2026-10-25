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
