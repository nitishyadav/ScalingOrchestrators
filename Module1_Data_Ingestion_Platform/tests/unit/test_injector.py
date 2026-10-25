"""M1-T160 — attack injector (M1-F04-AC-01..AC-06)."""
import collections
import ipaddress
import itertools
import math

import pytest

from ids_contracts import events as ev
from ids_ingest import injector as inj
from ids_ingest.producer import make_event

BENIGN = {"orig_ts": "3/7/2017 9:00", "src_ip": "192.168.10.5", "dst_ip": "192.168.10.50", "dst_port": 443,
          "bytes_sent": 500, "syn_flag": 1, "ack_flag": 1, "label": "BENIGN"}
RFC5737 = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]


def take(src, n):
    return list(itertools.islice(iter(src), n))


def injected_idx(records):
    return [i for i, r in enumerate(records) if r.get("is_injected")]


# ---- AC-01 exact, evenly spread share -----------------------------------------------------------
@pytest.mark.parametrize("p", [0.05, 0.2, 1.0])
def test_share_is_exact_and_even(p):
    recs = take(inj.InjectingSource(itertools.repeat(BENIGN), mode="synflood", share=p, rate=1000), 10_000)
    idx = injected_idx(recs)
    assert abs(len(idx) - math.floor(10_000 * p)) <= 1
    gaps = [b - a for a, b in zip([-1] + idx, idx)]
    assert max(gaps) <= math.ceil(1 / p)


# ---- AC-02 signatures ----------------------------------------------------------------------------
def gen(mode, n, seed=42):
    g = inj.AttackGenerator(mode, seed=seed)
    return [g.next() for _ in range(n)]


@pytest.mark.parametrize("mode", ["ddos", "synflood", "portscan", "mixed"])
def test_generated_events_are_strict_c01(mode):
    for i, rec in enumerate(gen(mode, 3000)):
        e = make_event(rec, 1_800_000_000_000 + i)
        assert ev.validate_event(e, strict=True) == [], e
        assert e["is_injected"] is True and e["orig_ts"] is None and e["label"] in ev.INJECTED_LABELS
        assert any(ipaddress.ip_address(e["src_ip"]) in net for net in RFC5737)
        assert e["dst_ip"] == inj.VICTIM_IP


def test_ddos_signature():
    recs = gen("ddos", 2000)
    assert {r["src_ip"] for r in recs} == {"203.0.113.10", "203.0.113.11"}
    assert all(r["label"] == "INJ_DDOS" and r["dst_port"] == 80 and 1000 <= r["bytes_sent"] <= 3000
               and (r["syn_flag"], r["ack_flag"]) == (0, 1) for r in recs)


def test_synflood_signature():
    recs = gen("synflood", 2000)
    assert {r["src_ip"] for r in recs} == {f"198.51.100.{i}" for i in range(20, 24)}
    assert all(r["label"] == "INJ_SYNFLOOD" and r["dst_port"] == 80 and 0 <= r["bytes_sent"] <= 60
               and (r["syn_flag"], r["ack_flag"]) == (1, 0) for r in recs)


def test_portscan_signature_sweeps_and_wraps():
    recs = gen("portscan", 65_536)
    assert {r["src_ip"] for r in recs} == {"192.0.2.30"}
    assert [r["dst_port"] for r in recs[:5]] == [1, 2, 3, 4, 5]
    assert recs[65_534]["dst_port"] == 65_535 and recs[65_535]["dst_port"] == 1
    assert all(r["label"] == "INJ_PORTSCAN" and r["bytes_sent"] == 0 and (r["syn_flag"], r["ack_flag"]) == (1, 0)
               for r in recs[:1000])


def test_mixed_cycles_types():
    assert [r["label"] for r in gen("mixed", 6)] == ["INJ_DDOS", "INJ_SYNFLOOD", "INJ_PORTSCAN"] * 2


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        inj.AttackGenerator("meteor")


# ---- AC-03 signature strength in a 30 s window (C-02 provisional formulas, playbook §5.3) --------
@pytest.mark.parametrize("mode", ["ddos", "synflood", "portscan"])
def test_signature_strength_in_30s_window(mode):
    rate, p = 5000, 0.05
    recs = take(inj.InjectingSource(itertools.repeat(BENIGN), mode=mode, share=p, rate=rate), 30 * rate)
    per_src = collections.defaultdict(lambda: {"n": 0, "ports": set(), "syn": 0, "ack": 0})
    for r in recs:
        if r.get("is_injected"):
            f = per_src[r["src_ip"]]
            f["n"] += 1
            f["ports"].add(r["dst_port"])
            f["syn"] += r["syn_flag"]
            f["ack"] += r["ack_flag"]
    assert per_src and set(per_src) == set(inj.POOLS[mode])
    for src, f in per_src.items():
        syn_ack_ratio, unique_ports, packet_rate = f["syn"] / (f["ack"] + 1), len(f["ports"]), f["n"] / 30.0
        if mode == "synflood":
            assert syn_ack_ratio >= 100, (src, syn_ack_ratio)
        elif mode == "portscan":
            assert unique_ports >= 1000, (src, unique_ports)
        else:
            assert packet_rate >= 100 and unique_ports == 1, (src, packet_rate, unique_ports)


# ---- AC-04 time window -------------------------------------------------------------------------
def test_attack_window():
    src = inj.InjectingSource(itertools.repeat(BENIGN), mode="ddos", share=0.2, rate=1000, start_s=10, duration_s=5)
    recs = take(src, 20_000)
    idx = injected_idx(recs)
    assert idx and min(idx) >= 10_000 and max(idx) < 15_000
    assert abs(len(idx) - 1000) <= 1 and src.active_slots == 5000


def test_window_beyond_run_injects_nothing():
    src = inj.InjectingSource(itertools.repeat(BENIGN), mode="ddos", share=0.2, rate=1000, start_s=100)
    assert injected_idx(take(src, 5000)) == [] and src.achieved_share == 0.0


# ---- AC-05 determinism -------------------------------------------------------------------------
def test_same_seed_same_stream_different_seed_differs():
    a = take(inj.InjectingSource(itertools.repeat(BENIGN), mode="mixed", share=0.2, rate=1000, seed=7), 5000)
    b = take(inj.InjectingSource(itertools.repeat(BENIGN), mode="mixed", share=0.2, rate=1000, seed=7), 5000)
    c = take(inj.InjectingSource(itertools.repeat(BENIGN), mode="mixed", share=0.2, rate=1000, seed=8), 5000)
    assert a == b
    assert injected_idx(a) == injected_idx(c)                       # slots never depend on the seed
    assert [r["bytes_sent"] for r in a if r.get("is_injected")] != [r["bytes_sent"] for r in c if r.get("is_injected")]


# ---- AC-06 replay untouched, injector blind to replay content ----------------------------------
def test_base_order_and_content_preserved():
    base = [dict(BENIGN, bytes_sent=i) for i in range(4000)]
    out = take(inj.InjectingSource(iter(base), mode="synflood", share=0.2, rate=1000), 5000)
    assert [r for r in out if not r.get("is_injected")] == base


def test_injection_ignores_replay_labels():
    benign = [dict(BENIGN) for _ in range(3000)]
    attacks = [dict(BENIGN, label="DDoS") for _ in range(3000)]
    a = take(inj.InjectingSource(iter(benign), mode="portscan", share=0.05, rate=1000), 3000)
    b = take(inj.InjectingSource(iter(attacks), mode="portscan", share=0.05, rate=1000), 3000)
    assert injected_idx(a) == injected_idx(b)


def test_counts_and_proxying():
    class Base:
        loops, exhausted = 3, False

        def __iter__(self):
            return itertools.repeat(BENIGN)

    src = inj.InjectingSource(Base(), mode="mixed", share=0.3, rate=1000)
    take(src, 1000)
    assert sum(src.counts.values()) == src.injected == 300
    assert set(src.counts) == {"ddos", "synflood", "portscan"} and src.loops == 3
