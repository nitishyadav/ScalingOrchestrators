"""Deterministic generator for contracts/fixtures/features_golden.csv (C-02).

A deliberately small, independent reference implementation of the C-02 formulas over events_golden.jsonl.
M2 (pandas, offline) and M3 (Spark, online) must both reproduce this file (floats within 1e-9).
Run from the workspace root:  python contracts/fixtures/_gen/gen_features_golden.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "python"))
from ids_contracts import features as F  # noqa: E402
from ids_contracts.events import iter_jsonl  # noqa: E402

FIXTURES = HERE.parents[1]
OUT = FIXTURES / "features_golden.csv"


def build_rows():
    groups = defaultdict(list)
    for e in iter_jsonl(FIXTURES / "events_golden.jsonl"):          # all events are within the 60 s watermark
        for start in F.window_starts(e["timestamp"]):
            groups[(start, e["src_ip"])].append(e)
    rows = []
    for (start, src), evs in sorted(groups.items()):
        attack, kind = F.window_label(e["label"] for e in evs)
        n, total, ports = len(evs), sum(e["bytes_sent"] for e in evs), len({e["dst_port"] for e in evs})
        rows.append({
            "window_start": start, "window_end": start + F.WINDOW_MS, "src_ip": src,
            "total_bytes": sum(e["bytes_sent"] for e in evs),
            "unique_ports": len({e["dst_port"] for e in evs}),
            "syn_ack_ratio": F.syn_ack_ratio(sum(e["syn_flag"] for e in evs), sum(e["ack_flag"] for e in evs)),
            "packet_rate": F.packet_rate(n),
            "bytes_per_flow": F.bytes_per_flow(total, n), "port_ratio": F.port_ratio(ports, n),
            "syn_share": F.syn_share(sum(e["syn_flag"] for e in evs), n),
            "event_count": len(evs), "max_event_ts": max(e["timestamp"] for e in evs),
            "label_attack": attack, "label_type": kind,
        })
    return rows


def render(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(F.GOLDEN_COLUMNS)
    for r in rows:
        w.writerow([("true" if r[c] else "false") if isinstance(r[c], bool) else repr(r[c]) if isinstance(r[c], float)
                    else r[c] for c in F.GOLDEN_COLUMNS])
    return buf.getvalue().encode("utf-8")


def main() -> None:
    rows = build_rows()
    OUT.write_bytes(render(rows))
    print(json.dumps({"status": "ok", "file": str(OUT), "rows": len(rows)}))


if __name__ == "__main__":
    main()
