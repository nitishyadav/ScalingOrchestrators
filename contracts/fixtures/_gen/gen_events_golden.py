"""Deterministic generator for contracts/fixtures/events_golden.jsonl (C-01, owner M1).

Run from the workspace root:  python contracts/fixtures/_gen/gen_events_golden.py
Re-running must produce a byte-identical file (no randomness, uuid5 ids).
Scenario is documented in contracts/fixtures/README.md.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "python"))
from ids_contracts.events import check_event, encode_event  # noqa: E402

BASE_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
TARGET = "192.168.10.50"
OUT = HERE.parents[1] / "events_golden.jsonl"


def ev(seq: int, t_ms: int, src: str, dst_port: int, bytes_sent: int, syn: int, ack: int,
       label: str, injected: bool = False, orig_ts=None, dst_ip: str = TARGET) -> dict:
    return {
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"ids-golden-{seq}")),
        "timestamp": BASE_MS + t_ms,
        "src_ip": src,
        "dst_ip": dst_ip,
        "dst_port": dst_port,
        "bytes_sent": bytes_sent,
        "syn_flag": syn,
        "ack_flag": ack,
        "orig_ts": orig_ts,
        "label": label,
        "is_injected": injected,
    }


def build() -> list:
    raw = []
    # A. Benign host: one flow every 3 s over 0..87 s (hits window boundaries 0/30/60 s exactly).
    for i in range(30):
        raw.append((i * 3000, "192.168.10.5", (80, 443, 53)[i % 3], 500 + (i * 137) % 1000, 1, 1, "BENIGN", False, "3/7/2017 9:00"))
    # B. Port scan: 40 flows every 0.5 s over 20..39.5 s, each to a distinct port, SYN without ACK.
    for i in range(40):
        raw.append((20_000 + i * 500, "172.16.0.10", 20 + i, 0, 1, 0, "PortScan", False, "7/7/2017 1:55"))
    # C. Injected SYN flood: 25 flows every 0.5 s over 50..62 s to port 80.
    for i in range(25):
        raw.append((50_000 + i * 500, "172.16.0.20", 80, 60, 1, 0, "INJ_SYNFLOOD", True, None))
    # D. DDoS (high rate, large bytes, ACK-heavy): 30 flows every 0.5 s over 65..79.5 s.
    for i in range(30):
        raw.append((65_000 + i * 500, "172.16.0.30", 80, 2000 + i * 10, 0, 1, "DDoS", False, "7/7/2017 3:56"))
    raw.sort(key=lambda r: r[0])
    # E. Late event: benign flow stamped at 40.0 s, appended after the 87 s event (47 s late < 60 s watermark).
    raw.append((40_000, "192.168.10.5", 443, 777, 1, 1, "BENIGN", False, "3/7/2017 9:01"))

    events = []
    for seq, (t, src, port, b, syn, ack, label, inj, orig) in enumerate(raw):
        e = ev(seq, t, src, port, b, syn, ack, label, inj, orig)
        check_event(e, strict=True)
        events.append(e)
    return events


def main() -> None:
    events = build()
    with open(OUT, "wb") as fh:
        for e in events:
            fh.write(encode_event(e) + b"\n")
    print(json.dumps({"status": "ok", "file": str(OUT), "events": len(events)}))


if __name__ == "__main__":
    main()
