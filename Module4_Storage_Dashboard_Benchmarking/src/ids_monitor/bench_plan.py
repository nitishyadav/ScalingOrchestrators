"""Benchmark plans, run IDs and commands (M4-T220, M4-F03 spec §5, FR-040, FR-041). Pure.

Commands are C-06 §5 CLIs with C-06 flags only; the runner prefixes `python -m`.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

SATURATING_RATE = 15_000          # E1/E2 (M4-ADR-002): above single-node capacity, so throughput is what Spark sustains
BASE_RATE = 5_000                 # P2 and the proposal's operating point
REPLAY_DAYS = "Monday"            # benign background: E3's attack share is exactly the injected share
SEED = 42
JOB_EXTRA_S = 600                 # --await-seconds = duration + this; the runner stops the job itself


@dataclass(frozen=True)
class RunSpec:
    experiment: str
    level: str
    partitions: int
    executors: int
    rate: int
    attack_share: float = 0.0
    trigger_ms: int = 1000
    restart_at: Optional[float] = None        # fraction of the producer run (REC)


@dataclass(frozen=True)
class Experiment:
    name: str
    target: str
    levels: tuple


def _e(exp, level, p, e, r, **kw):
    return RunSpec(exp, level, p, e, r, **kw)


EXPERIMENTS: Dict[str, Experiment] = {
    "E1": Experiment("E1", "P3: efficiency 1 → 4 partitions ≥ 0.5 (minimum speedup 1.5×, D-05)",
                     tuple(_e("E1", str(p), p, 4, SATURATING_RATE) for p in (1, 4, 8, 16))),
    "E2": Experiment("E2", "P4: efficiency 1 → 4 executors ≥ 0.5 (minimum speedup 1.5×, D-05)",
                     tuple(_e("E2", str(x), 8, x, SATURATING_RATE) for x in (1, 2, 4))),
    "E3": Experiment("E3", "F2: benign-only window FPR < 5 %; F5: drift banner above 15 % (ADR-013)",
                     tuple(_e("E3", str(a), 8, 2, BASE_RATE, attack_share=a / 100) for a in (0, 5, 20, 100))),
    "P1": Experiment("P1", "P1: sustained ≥ 10,000 ev/s at 16 partitions × 4 executors",
                     (_e("P1", "16x4", 16, 4, 12_000),)),
    "LAT": Experiment("LAT", "P2: p95 latency < 500 ms at 5,000 ev/s (D-01, D-13)",
                      tuple(_e("LAT", str(t), 8, 2, BASE_RATE, trigger_ms=t) for t in (1000, 500, 250))),
    "REC": Experiment("REC", "P5: recovery after a Spark worker restart < 30 s",
                      (_e("REC", "8x2", 8, 2, BASE_RATE, restart_at=0.5),)),
}


def plan(experiment: str, levels: Optional[Sequence[str]] = None) -> List[RunSpec]:
    if experiment not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {experiment!r} (one of {', '.join(EXPERIMENTS)})")
    specs = list(EXPERIMENTS[experiment].levels)
    if levels:
        known = [s.level for s in specs]
        bad = [lv for lv in levels if lv not in known]
        if bad:
            raise ValueError(f"unknown level(s) {', '.join(bad)} for {experiment} (one of {', '.join(known)})")
        specs = [s for s in specs if s.level in levels]
    return specs


def stamp(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y%m%d%H%M")


def attack_pct(spec: RunSpec) -> int:
    return round(spec.attack_share * 100)


def run_id(spec: RunSpec, when: str) -> str:
    t = f"-t{spec.trigger_ms}" if spec.experiment == "LAT" else ""
    return (f"{spec.experiment}-p{spec.partitions}-e{spec.executors}-r{spec.rate}-a{attack_pct(spec)}{t}-{when}")


def trigger_text(ms: int) -> str:
    """C-06 TRIGGER_INTERVAL syntax: whole seconds as 'N second(s)', otherwise milliseconds."""
    if ms % 1000 == 0:
        n = ms // 1000
        return f"{n} second" if n == 1 else f"{n} seconds"
    return f"{ms} milliseconds"


def commands(spec: RunSpec, rid: str, duration_s: int) -> Dict[str, List[str]]:
    producer = ["ids_ingest.producer", "--source", "replay", "--days", REPLAY_DAYS, "--rate", str(spec.rate),
                "--duration", str(duration_s), "--run-id", rid, "--seed", str(SEED)]
    if spec.attack_share > 0:                                    # C-06: share 0 ⇔ mode none
        producer += ["--attack-mode", "mixed", "--attack-share", f"{spec.attack_share:g}"]
    out = {
        "topic": ["ids_ingest.topic_admin", "--partitions", str(spec.partitions), "--recreate"],
        "job": ["ids_stream.job", "--executors", str(spec.executors), "--trigger", trigger_text(spec.trigger_ms),
                "--run-id", rid, "--await-seconds", str(duration_s + JOB_EXTRA_S)],
        "producer": producer,
    }
    if spec.restart_at is not None:
        out["restart"] = ["ids_ingest.platform", "restart-worker", "--index", "1"]
    return out


def modules_needed(experiment: str) -> List[str]:
    mods = ["ids_ingest.topic_admin", "ids_stream.job", "ids_ingest.producer"]
    if any(s.restart_at is not None for s in EXPERIMENTS[experiment].levels):
        mods.append("ids_ingest.platform")
    return mods
