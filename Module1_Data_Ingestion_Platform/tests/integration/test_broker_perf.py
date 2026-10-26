"""M1-T032 — broker throughput headroom (M1-F01-AC-10, NFR-003): ≥ 15,000 msg/s, 300-byte messages,
one host producer, 16 partitions, 60 s. Result saved to docs/measurements/ (Constitution Art. X).

Run with:  ../.venv/bin/python -m pytest tests/integration/test_broker_perf.py -m perf -q
"""
import datetime as dt
import json
import os
import platform as host_platform
import subprocess
import sys
import time
import uuid

import pytest

from conftest import MODULE_DIR, ROOT

pytestmark = [pytest.mark.docker, pytest.mark.perf]
DURATION_S = int(os.environ.get("M1_PERF_DURATION_S", "60"))
RECORD_BYTES, PARTITIONS, TARGET = 300, 16, 15_000


def test_ac10_broker_accepts_15k_msgs_per_second():
    from confluent_kafka import Producer
    topic = f"m1-perf-{uuid.uuid4().hex[:6]}"
    env = {**os.environ, "IDS_ROOT": str(ROOT), "KAFKA_TOPIC": topic}
    subprocess.run([sys.executable, "-m", "ids_ingest.topic_admin", "--partitions", str(PARTITIONS)],
                   check=True, capture_output=True, env=env, cwd=MODULE_DIR)

    delivered = {"ok": 0, "err": 0}

    def on_delivery(err, _msg):
        delivered["err" if err else "ok"] += 1

    producer = Producer({"bootstrap.servers": "localhost:9092", "linger.ms": 5, "batch.size": 262144,
                         "compression.type": "none", "acks": "1", "queue.buffering.max.messages": 500000})
    payload = os.urandom(RECORD_BYTES // 2).hex().encode()[:RECORD_BYTES]
    start = time.monotonic()
    i = 0
    while time.monotonic() - start < DURATION_S:
        try:
            producer.produce(topic, key=str(i % 1000).encode(), value=payload, on_delivery=on_delivery)
            i += 1
        except BufferError:
            producer.poll(0.01)
        if i % 1000 == 0:
            producer.poll(0)
    producer.flush(60)
    elapsed = time.monotonic() - start
    rate = delivered["ok"] / elapsed

    result = {"test": "M1-F01-AC-10", "date": dt.datetime.now().isoformat(timespec="seconds"),
              "host": host_platform.platform(), "partitions": PARTITIONS, "record_bytes": RECORD_BYTES,
              "compression": "none (identical payloads would otherwise compress away and inflate the rate)",
              "duration_s": round(elapsed, 1), "delivered": delivered["ok"], "errors": delivered["err"],
              "rate_msgs_per_s": round(rate), "target": TARGET, "pass": rate >= TARGET}
    out_dir = MODULE_DIR / "docs" / "measurements"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"AC-10-{dt.date.today().isoformat()}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    assert delivered["err"] == 0
    assert rate >= TARGET, result
