"""M1-T112 — producer against the live platform (M1-F03-AC-01, 02, 04, 07, 08). Marker `docker`.

Needs the platform up (`make run`) and the real replay dataset (`python -m ids_ingest.prepare`).
"""
import json
import os
import signal
import subprocess
import sys
import time
import uuid

import pyarrow.parquet as pq
import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts import FIXTURES_DIR
from ids_contracts import events as ev

pytestmark = pytest.mark.docker
REPLAY = ROOT / "runtime" / "data" / "replay"
FIELDS = ("orig_ts", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag", "label")


def _platform_ready() -> bool:
    proc = subprocess.run([sys.executable, "-m", "ids_ingest.platform", "status"], capture_output=True,
                          cwd=MODULE_DIR, env={**os.environ, "IDS_ROOT": str(ROOT),
                                               "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")})
    return proc.returncode == 0


if not _platform_ready():
    pytest.skip("platform not running (`make run`)", allow_module_level=True)
if not (REPLAY / ev.REPLAY_MANIFEST_NAME).exists():
    pytest.skip("replay dataset missing (`python -m ids_ingest.prepare`)", allow_module_level=True)


def env_for(topic, **extra):
    return {**os.environ, "IDS_ROOT": str(ROOT), "KAFKA_TOPIC": topic, **extra}


def run_cli(module, *args, topic, timeout=300, **extra):
    proc = subprocess.run([sys.executable, "-m", module, *args], capture_output=True, text=True, cwd=MODULE_DIR,
                          env=env_for(topic, **extra), timeout=timeout)
    lines = proc.stdout.strip().splitlines()
    return proc.returncode, (json.loads(lines[-1]) if lines else None), proc.stderr


def new_topic(partitions):
    topic = f"m1-prod-{uuid.uuid4().hex[:8]}"
    code, _, err = run_cli("ids_ingest.topic_admin", "--partitions", str(partitions), topic=topic)
    assert code == 0, err
    return topic


def consume_all(topic, expected, timeout_s=60):
    from confluent_kafka import Consumer
    c = Consumer({"bootstrap.servers": "localhost:9092", "group.id": f"t-{uuid.uuid4().hex}",
                  "auto.offset.reset": "earliest", "broker.address.family": "v4", "enable.auto.commit": False})
    c.subscribe([topic])
    out, deadline, idle_since = [], time.monotonic() + timeout_s, None
    while time.monotonic() < deadline:
        batch = c.consume(num_messages=10_000, timeout=1.0)
        msgs = [m for m in batch if m.error() is None]
        out.extend((m.key(), m.value(), m.partition()) for m in msgs)
        if len(out) >= expected:
            idle_since = idle_since or time.monotonic()
            if time.monotonic() - idle_since > 2:          # wait briefly for unexpected extras
                break
    c.close()
    return out


def replay_rows(day, n):
    t = pq.ParquetFile(REPLAY / f"day={day}" / "part-00000.parquet").read(columns=list(FIELDS))
    return [dict(zip(FIELDS, r)) for r in zip(*[t.column(f).slice(0, n).to_pylist() for f in FIELDS])]


def test_ac01_rate_accounting_and_validity():
    topic = new_topic(4)
    t0 = time.time() * 1000
    code, s, err = run_cli("ids_ingest.producer", "--days", "Monday", "--rate", "5000", "--duration", "20", topic=topic)
    t1 = time.time() * 1000
    assert code == 0, err
    assert s["status"] == "ok" and s["failed"] == 0 and s["invalid"] == 0 and s["partitions"] == 4
    assert abs(s["achieved_rate"] - 5000) / 5000 <= 0.02, s
    assert s["rate_p05"] >= 4500, s
    msgs = consume_all(topic, s["sent"])
    assert len(msgs) == s["sent"]
    for key, value, _ in msgs[::100]:
        e = ev.decode_event(value)
        assert ev.validate_event(e, strict=True) == []
        assert key == e["src_ip"].encode() and t0 - 1000 <= e["timestamp"] <= t1 + 1000 and e["is_injected"] is False


def test_ac02_single_partition_preserves_replay_order():
    topic = new_topic(1)
    code, s, err = run_cli("ids_ingest.producer", "--days", "Monday", "--rate", "2000", "--duration", "3", topic=topic)
    assert code == 0, err
    msgs = consume_all(topic, s["sent"])
    got = [{k: ev.decode_event(v)[k] for k in FIELDS} for _, v, _ in msgs]
    assert got == replay_rows("Monday", s["sent"])


def test_ac04_fixture_gaps_live():
    topic = new_topic(1)
    code, s, err = run_cli("ids_ingest.producer", "--source", "fixture", topic=topic, timeout=200)
    assert code == 0 and s["sent"] == 126 and s["injected"] == 25, err
    got = [ev.decode_event(v) for _, v, _ in consume_all(topic, 126)]
    golden = list(ev.iter_jsonl(FIXTURES_DIR / "events_golden.jsonl"))
    assert [e["timestamp"] - got[0]["timestamp"] for e in got] == [g["timestamp"] - golden[0]["timestamp"] for g in golden]


def test_ac07_sigterm_stops_gracefully():
    topic = new_topic(4)
    proc = subprocess.Popen([sys.executable, "-m", "ids_ingest.producer", "--days", "Monday", "--rate", "2000",
                             "--duration", "120"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            cwd=MODULE_DIR, env=env_for(topic))
    time.sleep(6)
    proc.send_signal(signal.SIGTERM)
    out, err = proc.communicate(timeout=60)
    assert proc.returncode == 0, err
    s = json.loads(out.strip().splitlines()[-1])
    assert s["status"] == "stopped" and s["failed"] == 0 and s["duration_s"] < 30
    assert len(consume_all(topic, s["sent"])) == s["sent"]


def test_ac08_missing_topic_and_unreachable_broker():
    code, _, err = run_cli("ids_ingest.producer", "--source", "fixture", topic=f"m1-missing-{uuid.uuid4().hex[:6]}")
    assert code == 1 and "topic_admin" in err
    t = time.monotonic()
    code, _, err = run_cli("ids_ingest.producer", "--source", "fixture", topic="any", KAFKA_BOOTSTRAP="localhost:9")
    assert code == 1 and "cannot reach Kafka" in err and time.monotonic() - t < 20
