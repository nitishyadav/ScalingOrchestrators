"""Attack injection for the replay producer (M1-F04).

`AttackGenerator` produces C-01 records with a fixed signature per attack type; `InjectingSource` interleaves them into any
record stream at an exact share (error diffusion) inside an optional time window. The injector never reads the base
records (Constitution Art. VII): slot choice depends only on the share, rate and window.
"""
from __future__ import annotations

import collections
import random
from typing import Iterable, Iterator, Optional

ATTACK_TYPES = ("ddos", "synflood", "portscan")
MODES = ATTACK_TYPES + ("mixed",)
VICTIM_IP = "192.168.10.50"                        # CIC-IDS2017 internal web server
# Attacker sources from RFC 5737 documentation ranges: never present in the replay data (checked 2026-10-22)
POOLS = {
    "ddos": ["203.0.113.10", "203.0.113.11"],
    "synflood": ["198.51.100.20", "198.51.100.21", "198.51.100.22", "198.51.100.23"],
    "portscan": ["192.0.2.30"],
}
LABELS = {"ddos": "INJ_DDOS", "synflood": "INJ_SYNFLOOD", "portscan": "INJ_PORTSCAN"}
_EPS = 1e-9


class AttackGenerator:
    """Deterministic (seeded) generator of injected C-01 records (FR-042, FR-043, FR-045)."""

    def __init__(self, mode: str, seed: int = 42):
        if mode not in MODES:
            raise ValueError(f"unknown attack mode {mode!r}; choose from {MODES}")
        self.mode = mode
        self.rng = random.Random(seed)
        self.counts: collections.Counter = collections.Counter()
        self._scan_port = collections.Counter()

    def next(self) -> dict:
        kind = ATTACK_TYPES[sum(self.counts.values()) % 3] if self.mode == "mixed" else self.mode
        k = self.counts[kind]
        self.counts[kind] += 1
        src = POOLS[kind][k % len(POOLS[kind])]
        if kind == "ddos":
            port, nbytes, syn, ack = 80, self.rng.randint(1000, 3000), 0, 1
        elif kind == "synflood":
            port, nbytes, syn, ack = 80, self.rng.randint(0, 60), 1, 0
        else:
            port, nbytes, syn, ack = 1 + (self._scan_port[src] % 65535), 0, 1, 0
            self._scan_port[src] += 1
        return {"orig_ts": None, "src_ip": src, "dst_ip": VICTIM_IP, "dst_port": port, "bytes_sent": nbytes,
                "syn_flag": syn, "ack_flag": ack, "label": LABELS[kind], "is_injected": True}


class InjectingSource:
    """Interleaves injected records into `base` at share p within slots [round(S·R), round((S+D)·R)) (FR-041, FR-044, FR-046)."""

    def __init__(self, base: Iterable[dict], *, mode: str, share: float, rate: int, seed: int = 42,
                 start_s: float = 0.0, duration_s: Optional[float] = None):
        if not 0 < share <= 1:
            raise ValueError("share must be in (0, 1]")
        if start_s < 0 or (duration_s is not None and duration_s <= 0):
            raise ValueError("attack window must have start ≥ 0 and duration > 0")
        self.base = base
        self.generator = AttackGenerator(mode, seed)
        self.mode, self.share, self.seed = mode, share, seed
        self.start_s, self.duration_s = float(start_s), (None if duration_s is None else float(duration_s))
        self.first_slot = round(start_s * rate)
        self.end_slot = None if duration_s is None else round((start_s + duration_s) * rate)
        self.active_slots = 0
        self.injected = 0

    @property
    def counts(self) -> collections.Counter:
        return self.generator.counts

    @property
    def loops(self) -> int:
        return getattr(self.base, "loops", 0)

    @property
    def exhausted(self) -> bool:
        return getattr(self.base, "exhausted", False)

    @property
    def achieved_share(self) -> float:
        return round(self.injected / self.active_slots, 6) if self.active_slots else 0.0

    @property
    def window(self):
        return [self.start_s, None if self.duration_s is None else self.start_s + self.duration_s]

    def __iter__(self) -> Iterator[dict]:
        base_it = iter(self.base)
        acc = 0.0
        slot = 0
        while True:
            active = slot >= self.first_slot and (self.end_slot is None or slot < self.end_slot)
            slot += 1
            if active:
                self.active_slots += 1
                acc += self.share
                if acc >= 1 - _EPS:
                    acc -= 1
                    self.injected += 1
                    yield self.generator.next()
                    continue
            try:
                yield next(base_it)
            except StopIteration:
                return
