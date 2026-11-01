"""Dashboard / harness views over C-04 rows (M4-T023, M4-FR-006/007/013).

Pure functions. They never read eval-only columns (ADR-007, Const. VII); a unit test enforces it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Tuple

from ids_contracts import store as S


@dataclass(frozen=True)
class Drift:
    total: int
    anomalous: int
    rate: float
    alert: bool
    threshold: float = S.DRIFT_THRESHOLD


@dataclass(frozen=True)
class FlaggedIp:
    src_ip: str
    windows: int                                           # anomalous windows
    max_score: float
    last_seen: int                                         # latest anomalous window_end, epoch ms
    rule_ids: Tuple[str, ...]                              # sorted union of rules that fired


def drift_summary(rows: Iterable[Mapping]) -> Drift:
    total = anomalous = 0
    for r in rows:
        total += 1
        anomalous += bool(r["is_anomaly"])
    return Drift(total, anomalous, anomalous / total if total else 0.0, S.drift_alert(anomalous, total))


def top_flagged(rows: Iterable[Mapping], n: int = 10) -> List[FlaggedIp]:
    acc: Dict[str, list] = {}
    for r in rows:
        if not r["is_anomaly"]:
            continue
        a = acc.get(r["src_ip"])
        if a is None:
            a = acc[r["src_ip"]] = [0, float("-inf"), 0, set()]
        a[0] += 1
        a[1] = max(a[1], r["anomaly_score"])
        a[2] = max(a[2], r["window_end"])
        if r["rule_ids"]:
            a[3].update(r["rule_ids"].split(","))
    out = [FlaggedIp(ip, c, s, last, tuple(sorted(rules))) for ip, (c, s, last, rules) in acc.items()]
    out.sort(key=lambda f: (-f.windows, -f.max_score, f.src_ip))
    return out[:n]
