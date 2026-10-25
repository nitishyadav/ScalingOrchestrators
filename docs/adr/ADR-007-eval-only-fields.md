# ADR-007: Eval-only ground-truth fields in the stream

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date | 2026-10-21 |
| Deciders | All 4 (drafted by Aswin, M1) |
| Resolves | D-07 |
| Affects | C-01, C-02, C-04, M1, M3, M4-F04 |

## Context
F2 (benign FPR), F3 (rule versus hybrid per attack category) and E3 (attack-injection share) are evaluated **online**, so
ground truth has to travel with the data. The proposal's event schema has no label.

## Options
| Option | Pros | Cons |
|---|---|---|
| A. Optional `label` + `is_injected` on each event, marked eval-only | Simple. The ground truth reaches the window rows | Risk of leakage into scoring |
| B. A separate ground-truth topic or side table joined later | No leakage risk | Complex join on event_id or window. More moving parts |

## Decision
Option A, with guards:
1. The fields are optional and documented as **eval-only** in C-01.
2. `ids_contracts.events.SCORING_FIELDS` lists the only fields that features and rules may read. Contract tests in M2 and M3 assert this.
3. Window ground truth (C-02) is `label_attack = any(label ≠ BENIGN)`, stored as eval-only columns in C-04.

## Consequences
- Online evaluation is possible with no joins.
- Every scoring-path spec must state that eval-only fields are excluded (spec review checklist).
