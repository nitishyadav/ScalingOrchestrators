# Plan: M1-F04 — Attack Injector

| Field | Value |
|---|---|
| Feature ID | M1-F04 |
| Spec version | 0.1.0 |
| Owner | Aswin S. |
| Status | **Approved** (G2, 2026-10-22) |

## 1. Approach
A new module `src/ids_ingest/injector.py` provides two pieces:
- `AttackGenerator(mode, seed)` yields C-01 record dicts per the FR-042 signature table, using a private `random.Random(seed)` for the `bytes_sent` jitter only.
- `InjectingSource(base, generator, share, rate, start_s, duration_s)` wraps any record iterable. For each output slot *i* inside the active window
  `[round(S·R), round((S+D)·R))` it adds `share` to an accumulator. When the accumulator reaches 1 it emits a generated record (and subtracts 1);
  otherwise it emits the next base record. It never inspects base records. `loops`/`exhausted` are proxied from the base.

The producer's `main()` wraps `ReplaySource` when `ATTACK_MODE ≠ none`. `run()` is unchanged: `make_event` already honours the record's `is_injected`.
The summary gains the attack fields from the source.

## 2. Constitution check
| Article | ✅ | Notes |
|---|---|---|
| I, II, III | ✅ | Spec first. Emits C-01 only. No new imports beyond the stdlib |
| IV Mock-first | ✅ | Injection works on top of the fixture-free replay, and the unit tests use synthetic bases |
| VI Config | ✅ | `ATTACK_MODE`, `ATTACK_SHARE` via C-06. New flags via C-06 rc.6 |
| VII Honest ML | ✅ | Ground truth only in eval-only fields. The injector is blind to base labels (AC-06) |
| IX Reproducible | ✅ | Seeded RNG, deterministic slot choice |
| X Measured | ✅ | AC-08 saved |
| XII Simplicity | ✅ | stdlib `random`, no new dependencies |

## 3. Design details
| Item | Choice |
|---|---|
| Accumulator | `acc += p; if acc >= 1 - 1e-9: acc -= 1; inject`. For n slots the count is floor(n·p) (±1 for float error) and the gaps are ≤ ceil(1/p) |
| Source rotation | Per type, the attacker IP is `pool[k % len(pool)]`, where k is the per-type counter |
| Port scan | Per attacker, the port counter is `1 + (c % 65535)` |
| Mixed | Type is `TYPES[j % 3]`, where j is the total injected count |
| Accounting | `InjectingSource.counts` (per type) and `active_slots` (slots inside the window), used for `achieved_share` |

## 4. Tests
| Level | What | AC |
|---|---|---|
| Unit | Share exactness and spread. Signatures per mode. 30 s window feature strength (pure-Python C-02 provisional formulas over a simulated stream). Time window. Seed determinism. Base order and blindness. CLI fields and guards | AC-01..06, 09 |
| Contract | Injected events strict-valid C-01, key = `src_ip`. Extended C-06 CLI usage errors | AC-02, 09 |
| Integration (`docker`) | Live mixed 20 %: counts, labels, validity, no IP collision with the replay data | AC-07 |
| Perf (`docker and perf`) | 12k ev/s with mixed 20 % for 60 s | AC-08 |
