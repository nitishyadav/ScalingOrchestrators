"""M1-T162 — attack injection against the live platform (M1-F04-AC-07, AC-08). Marker `docker` (+ `perf`)."""
import datetime as dt
import json

import pyarrow.compute as pc
import pyarrow.dataset as ds
import pytest

from conftest import MODULE_DIR
from ids_contracts import events as ev
from ids_ingest import injector as inj
from test_producer_live import REPLAY, consume_all, new_topic, run_cli

pytestmark = pytest.mark.docker


def test_ac07_mixed_injection_live():
    topic = new_topic(4)
    code, s, err = run_cli("ids_ingest.producer", "--rate", "5000", "--duration", "20", "--attack-mode", "mixed",
                           "--attack-share", "0.2", topic=topic)
    assert code == 0, err
    assert s["failed"] == 0 and s["invalid"] == 0 and s["attack_mode"] == "mixed"
    assert abs(s["achieved_share"] - 0.2) < 0.001 and sum(s["injected_by_type"].values()) == s["injected"]
    msgs = consume_all(topic, s["sent"])
    assert len(msgs) == s["sent"]
    events = [ev.decode_event(v) for _, v, _ in msgs]
    injected = [e for e in events if e["is_injected"]]
    assert len(injected) == s["injected"]
    assert all((e["label"] in ev.INJECTED_LABELS) == e["is_injected"] for e in events)
    assert all(ev.validate_event(e, strict=True) == [] for e in events[::50] + injected[::50])
    attacker_ips = {ip for pool in inj.POOLS.values() for ip in pool}
    assert {e["src_ip"] for e in injected} == attacker_ips
    replay_ips = set(pc.unique(ds.dataset(REPLAY, format="parquet", partitioning="hive")
                               .to_table(columns=["src_ip"])["src_ip"]).to_pylist())
    assert not attacker_ips & replay_ips                     # ground truth is unambiguous


@pytest.mark.perf
def test_ac08_throughput_with_injection():
    code, s, err = run_cli("ids_ingest.producer", "--rate", "12000", "--duration", "60", "--attack-mode", "mixed",
                           "--attack-share", "0.2", topic=new_topic(16), timeout=300)
    assert code == 0, err
    result = {"test": "M1-F04-AC-08", "date": dt.datetime.now().isoformat(timespec="seconds"), "partitions": 16,
              "attack": {"mode": "mixed", "share": 0.2},
              "measured": {k: s[k] for k in ("sent", "failed", "injected", "achieved_share", "achieved_rate",
                                             "rate_p05", "rate_p50", "duration_s")},
              "target": {"achieved_rate_min": 11760, "failed": 0}}
    result["pass"] = s["achieved_rate"] >= 11760 and s["failed"] == 0
    (MODULE_DIR / "docs" / "measurements" / f"AC-08-M1-F04-{dt.date.today().isoformat()}.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    assert result["pass"], result
