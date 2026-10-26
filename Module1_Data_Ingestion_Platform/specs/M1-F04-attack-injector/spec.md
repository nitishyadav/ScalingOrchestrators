# Spec: M1-F04 — Attack Injector

| Field | Value |
|---|---|
| Feature ID | M1-F04 |
| Module | Module1_Data_Ingestion_Platform |
| Owner | Aswin S. |
| Reviewers | Vidhi Kant Gupta (M4 runs E3 and the drift demo), Nitish Kumar Yadav (M2 detection) |
| Status | **Verified** (2026-10-22, all 9 ACs ✅. Gates approved by owner 2026-10-22) |
| Version | 0.1.0 |
| Created / Updated | 2026-10-22 / 2026-10-22 |
| Proposal trace | §2.1 (attack injection flag: DDoS bursts, port-scan sequences on demand), Week 3 (toggles for DDoS, SYN Flood, Port Scan), E3 (0 / 5 / 20 % malicious share), F5 (drift banner), F3 |
| Contracts touched | C-01 1.0.0-rc.5 (provides: injected events with `INJ_*` labels, `is_injected=true`), C-06 1.0.0-rc.6 (provides: `--seed`, `--attack-start`, `--attack-duration`, summary fields) |
| Decisions applied | ADR-007 (eval-only ground truth), ADR-011 (constant rate) |

## 1. Summary
This feature adds synthetic attack traffic to the replay stream on demand. The traffic is DDoS, SYN flood, port scan, or a mix,
at an exact share of all emitted events, optionally within a time window. Every injected event is a valid C-01 event labelled
`INJ_*` with `is_injected=true`, sent from reserved documentation IP ranges so that ground truth is unambiguous. The output is
reproducible from a seed.

## 2. Context and motivation
E3 measures detection and pipeline behaviour at 0 %, 5 % and 20 % malicious traffic. F5 requires the dashboard's drift banner to fire
when injection pushes the anomaly rate above 15 %. The demo needs attacks "on demand". Recorded CIC attacks alone cannot be dialled
to an exact share or started at a chosen moment. Injection must not disturb the replay itself (order, content), so that runs stay
comparable and the eval-only rule holds (Constitution Art. VII).

Data facts (2026-10-22): the replay contains 19,129 distinct IPs and **none** in the RFC 5737 ranges. The busiest real source
(`172.16.0.1`, the CIC attack NAT) carries about 20 % of all flows, so attack signatures must show in more than raw rate. That is M2's concern, noted here for context.

## 3. Scope
**In scope:** generators for 3 attack types, `mixed` mode, exact share, a time window, seed, summary accounting, CLI wiring into the producer.
**Out of scope:** detection (M2/M3), any change to replayed CIC events (their labels are untouched), fixture-mode injection (the fixture already contains an injected SYN flood).

## 4. User stories
- **US-1:** As the M4 harness running E3, I want an exact malicious share (0/5/20 %), so that results across runs and members are comparable.
- **US-2:** As a demo operator, I want to start an attack at a chosen second (for example after 60 s of benign traffic), so that the dashboard visibly reacts.
- **US-3:** As M2/M4 evaluating detection, I want injected events to carry unambiguous ground truth and a recognisable signature per attack type.

## 5. Functional requirements

| ID | Requirement | Priority | Story | Trace |
|---|---|---|---|---|
| M1-FR-041 | `--attack-mode ddos\|synflood\|portscan\|mixed` with `--attack-share p` (0 < p ≤ 1) MUST make injected events exactly `floor(n·p)` (±1) of the first *n* events emitted while the attack is active, spread evenly (error diffusion, no randomness in *which* slots). | P0 | US-1 | E3 |
| M1-FR-042 | Generators MUST follow these signatures (C-01 fields). Victim `192.168.10.50` (CIC web server). Attackers from RFC 5737 ranges: **ddos**: 2 sources `203.0.113.10–11`, dst port 80, `bytes_sent` 1,000–3,000, `syn_flag` 0, `ack_flag` 1. **synflood**: 4 sources `198.51.100.20–23`, dst port 80, `bytes_sent` 0–60, `syn_flag` 1, `ack_flag` 0. **portscan**: 1 source `192.0.2.30`, dst ports sweeping 1, 2, …, 65535 (wrapping), `bytes_sent` 0, `syn_flag` 1, `ack_flag` 0. **mixed**: cycles ddos → synflood → portscan per injected event. | P0 | US-3 | Week 3 |
| M1-FR-043 | Injected events MUST be strict-valid C-01 with `label` `INJ_DDOS` / `INJ_SYNFLOOD` / `INJ_PORTSCAN`, `is_injected=true`, `orig_ts=null`, `timestamp` = emission time and key = `src_ip`. | P0 | US-3 | C-01 §3.1, ADR-007 |
| M1-FR-044 | `--attack-start S` (default 0) and `--attack-duration D` (default: until the end) MUST restrict injection to emission times [S, S+D) seconds from run start (event-index window `[round(S·R), round((S+D)·R))`). | P0 | US-2 | F5, demo |
| M1-FR-045 | Given the same `--seed` (default 42), mode, share, rate and window, the sequence of injected records (all fields except `event_id`/`timestamp`) and their slots MUST be identical across runs. | P1 | US-1 | Art. IX |
| M1-FR-046 | Injection MUST interleave without dropping or reordering replay events, and MUST NOT read any field of the replay records (no label-based decisions). | P0 | US-1 | Art. VII |
| M1-FR-047 | The producer summary MUST add `attack_mode`, `attack_share`, `achieved_share` (= injected / produced while active), `injected_by_type`, `seed`, `attack_window_s`. | P0 | US-1 | C-06 §5 |
| M1-FR-048 | Attack flags with `--source fixture`, `--attack-start` < 0, or `--attack-duration` ≤ 0 MUST exit 2. | P1 | — | C-06 |

## 6. Non-functional requirements

| ID | Category | Requirement | Trace |
|---|---|---|---|
| M1-NFR-041 | Throughput | `--rate 12000 --attack-mode mixed --attack-share 0.2` for 60 s achieves ≥ 11,760 ev/s with 0 failed | G1 |
| M1-NFR-042 | Signature strength | At R = 5,000 and p = 0.05 (single-type modes), within any full 30 s window (C-02 provisional formulas, playbook §5.3), **every** attacker source shows: synflood `syn_ack_ratio` ≥ 100; portscan `unique_ports` ≥ 1,000; ddos `packet_rate` ≥ 100 and `unique_ports` = 1. These exceed the playbook §5.4 placeholder rule thresholds | US-3, F3 |

## 7. Interfaces
| Contract | Version | Provided / consumed |
|---|---|---|
| C-01 | rc.5 | Provided: injected events (labels already in the C-01 label set) |
| C-06 | rc.6 | Provided: producer flags `--seed`, `--attack-start`, `--attack-duration` and summary fields. Consumed: `ATTACK_MODE`, `ATTACK_SHARE` |

## 8. Acceptance criteria

| ID | Given / When / Then | Verifies | Type | Status |
|---|---|---|---|---|
| M1-F04-AC-01 | p ∈ {0.05, 0.2, 1.0}, n = 10,000 → injected = floor(n·p) ± 1, and the largest gap between injected slots ≤ ceil(1/p) | FR-041 | unit | ✅ `test_share_is_exact_and_even` |
| M1-F04-AC-02 | Each mode's generated events are strict-valid and match the FR-042 signature table. `mixed` cycles in order | FR-042, FR-043 | unit | ✅ `test_generated_events_are_strict_c01`, `test_*_signature*`, `test_mixed_cycles_types` |
| M1-F04-AC-03 | Simulated 30 s at R = 5,000, p = 0.05 per single-type mode → every attacker meets the NFR-042 thresholds | NFR-042 | unit | ✅ `test_signature_strength_in_30s_window` |
| M1-F04-AC-04 | start = 10 s, duration = 5 s, R = 1,000 → injected only in slots [10,000, 15,000), with the exact share inside | FR-044 | unit | ✅ `test_attack_window`, `test_window_beyond_run_injects_nothing` |
| M1-F04-AC-05 | Same seed → identical injected records and slots. Different seed → different `bytes_sent` jitter | FR-045 | unit | ✅ `test_same_seed_same_stream_different_seed_differs` |
| M1-F04-AC-06 | With injection, the replay records appear in exactly the original order and content. Changing replay labels does not change the injected slots | FR-046 | unit | ✅ `test_base_order_and_content_preserved`, `test_injection_ignores_replay_labels` |
| M1-F04-AC-07 | Live: 5,000 ev/s × 20 s, mixed 20 % → every message consumed. Injected = summary `injected` (≈ 20 %). Only injected messages carry `INJ_*` / `is_injected=true`. All strict-valid. No attacker IP occurs in the replay data | FR-041..043, FR-047 | integration | ✅ `test_ac07_mixed_injection_live` |
| M1-F04-AC-08 | Perf: NFR-041 measured and saved | NFR-041 | perf | ✅ `test_ac08_throughput_with_injection`: 11,999.6 ev/s, 144,000 injected, 0 failed (`docs/measurements/AC-08-M1-F04-2026-10-22.json`) |
| M1-F04-AC-09 | CLI: summary has the FR-047 fields. Fixture + attack → 2. Negative start / zero duration → 2. Mode none with share > 0 → 2 | FR-047, FR-048 | unit + contract | ✅ `test_cli_replay_with_injection`, `test_cli_usage_errors_exit_2`, C-06 CLI contract, `test_injected_events_are_c01` |

## 9. Edge cases
| Case | Behaviour |
|---|---|
| p = 1.0 | Every active slot is injected. The replay pauses (not consumed) during the window |
| Window beyond the run's duration | No injection. `achieved_share` is 0 |
| Replay with `--no-loop` exhausted while an attack is active | The run ends (injection never extends a run) |

## 10. Review checklist
- [x] Every FR has an AC. NFRs measurable. Contracts versioned. No open questions
- [x] Eval-only: the injector never reads replay labels (FR-046, AC-06)
- [ ] Consumer review (M4, M2)

## 11. Change log
| Version | Date | Author | Change |
|---|---|---|---|
| 0.1.0 | 2026-10-22 | Aswin S. (with AI) | Initial version (gates approved by owner) |
| 0.1.0 | 2026-10-22 | Aswin S. (with AI) | Implemented and verified |
