"""End-to-end on the live platform (M3-F01-AC-03, M3-F04-AC-02, AC-03). Marker `docker`.

Producer (M1, via its C-06 CLI) → Kafka → this stream job → Cassandra (C-04/C-05), checked with cassandra-driver.
"""
import calendar
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_stream import job

pytestmark = pytest.mark.docker
M1 = ROOT / "Module1_Data_Ingestion_Platform"
DOCKER = job.Docker().bin

if not job.Docker().find_spark_client():
    pytest.skip("platform not running", allow_module_level=True)


def session():
    from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
    from cassandra.policies import AddressTranslator, RoundRobinPolicy
    from cassandra.query import dict_factory

    class ToLocal(AddressTranslator):
        def translate(self, addr):
            return "127.0.0.1"

    profile = ExecutionProfile(load_balancing_policy=RoundRobinPolicy(), row_factory=dict_factory, request_timeout=20)
    return Cluster(["127.0.0.1"], port=9042, protocol_version=5, address_translator=ToLocal(),
                   execution_profiles={EXEC_PROFILE_DEFAULT: profile}).connect()


def ms(d):
    return calendar.timegm(d.utctimetuple()) * 1000 + d.microsecond // 1000


def as_ms_row(r):
    return {k: ms(v) if hasattr(v, "utctimetuple") else v for k, v in r.items()}


def env(topic):
    return {**os.environ, "IDS_ROOT": str(ROOT), "KAFKA_TOPIC": topic, "PATH": "/opt/homebrew/bin:" + os.environ["PATH"]}


def cli(module, *args, topic, cwd, timeout=300):
    p = subprocess.run([sys.executable, "-m", module, *args], capture_output=True, text=True, env=env(topic), cwd=cwd, timeout=timeout)
    return p.returncode, (json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None), p.stderr


def start_job(run_id, topic, seconds):
    return subprocess.Popen([sys.executable, "-m", "ids_stream.job", "--run-id", run_id, "--await-seconds", str(seconds),
                             "--starting-offsets", "earliest"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            env=env(topic), cwd=MODULE_DIR)


def wait_for_run_row(s, run_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(r["run_id"] == run_id for r in s.execute("SELECT run_id FROM ids.runs WHERE bucket = 'all' LIMIT 50")):
            return
        time.sleep(2)
    raise AssertionError("stream job did not register its run")


def windows_for(s, run_id, start_ms, end_ms):
    rows, h = [], (start_ms // 3_600_000) * 3_600_000
    while h <= end_ms:
        db, hr = S.partition_key(h)
        rows += [as_ms_row(r) for r in s.execute("SELECT * FROM ids.window_scores WHERE date_bucket = %s AND hour = %s",
                                                 (db, hr)) if r["run_id"] == run_id]
        h += 3_600_000
    return rows


def test_end_to_end_with_injection_and_malformed_input():
    from confluent_kafka import Producer
    tag = uuid.uuid4().hex[:6]
    run_id, topic = f"DEV-m3-e2e-{tag}", f"m3-e2e-{tag}"
    assert cli("ids_ingest.topic_admin", "--partitions", "4", topic=topic, cwd=M1)[0] == 0
    s = session()
    t0 = int(time.time() * 1000)
    proc = start_job(run_id, topic, 100)
    wait_for_run_row(s, run_id)
    bad = Producer({"bootstrap.servers": "localhost:9092", "broker.address.family": "v4"})
    for v in (b"not json", b'{"timestamp": 5}', b'{"event_id":"x","timestamp":1767225600000,"src_ip":"1.2.3.4"}',
              b"[1,2,3]", b'{"dst_port": "eighty"}'):
        bad.produce(topic, value=v)
    bad.flush(10)
    code, prod, err = cli("ids_ingest.producer", "--days", "Monday", "--rate", "2000", "--duration", "30",
                          "--attack-mode", "mixed", "--attack-share", "0.2", topic=topic, cwd=M1)
    assert code == 0 and prod["sent"] == 60_000 and prod["injected"] == 12_000, err
    out, err = proc.communicate(timeout=300)
    assert proc.returncode == 0, err[-3000:]
    summary = json.loads(out.strip().splitlines()[-1])
    assert summary["command"] == "stream job" and summary["rows_written"] > 0 and summary["malformed"] >= 5
    assert summary["input_rows"] == 60_005

    rows = windows_for(s, run_id, t0 - 60_000, int(time.time() * 1000))
    assert rows and all(S.validate_row(r) == [] for r in rows)
    flagged = {r["src_ip"] for r in rows if r["is_anomaly"]}
    assert {"198.51.100.20", "198.51.100.21", "198.51.100.22", "198.51.100.23", "192.0.2.30"} <= flagged
    syn = [r for r in rows if r["src_ip"] == "198.51.100.20"]
    assert max(r["syn_ack_ratio"] for r in syn) > 5 and all("R-SYN-FLOOD" in r["rule_ids"] for r in syn if r["is_anomaly"])
    assert all(r["label_type"].startswith("INJ_") for r in rows if r["src_ip"].startswith(("198.51.100.", "192.0.2.", "203.0.113.")))

    metrics = [as_ms_row(r) for r in s.execute("SELECT * FROM ids.pipeline_metrics WHERE run_id = %s", (run_id,))]
    assert len(metrics) >= 3 and all(M.validate_metrics_row(m) == [] for m in metrics)
    p95 = sorted(m["latency_p95_ms"] for m in metrics if m["latency_p95_ms"] is not None)
    assert p95 and sum(m["input_rows"] for m in metrics) == 60_005 and max(m["kafka_partitions"] for m in metrics) == 4
    print(json.dumps({"run_id": run_id, "windows": len(rows), "anomalous": sum(r["is_anomaly"] for r in rows),
                      "batches": len(metrics), "median_batch_p95_ms": p95[len(p95) // 2], "max_p95_ms": p95[-1]}))


def test_recovery_after_worker_restart():
    tag = uuid.uuid4().hex[:6]
    run_id, topic = f"DEV-m3-rec-{tag}", f"m3-rec-{tag}"
    assert cli("ids_ingest.topic_admin", "--partitions", "4", topic=topic, cwd=M1)[0] == 0
    s = session()
    proc = start_job(run_id, topic, 110)
    wait_for_run_row(s, run_id)
    producer = subprocess.Popen([sys.executable, "-m", "ids_ingest.producer", "--days", "Monday", "--rate", "1000",
                                 "--duration", "80"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=env(topic), cwd=M1)
    time.sleep(25)
    subprocess.run([DOCKER, "restart", "ids-spark-worker-1"], check=True, capture_output=True, timeout=120)
    restarted = int(time.time() * 1000)
    producer.communicate(timeout=200)
    out, err = proc.communicate(timeout=300)
    assert proc.returncode == 0, err[-3000:]
    after = sorted(m["batch_ts"] for m in (as_ms_row(r) for r in
                   s.execute("SELECT batch_ts, input_rows FROM ids.pipeline_metrics WHERE run_id = %s", (run_id,)))
                   if m["batch_ts"] > restarted and m["input_rows"] > 0)
    assert after, "no batches processed after the worker restart"
    gap_s = (after[0] - restarted) / 1000
    print(json.dumps({"run_id": run_id, "first_batch_after_restart_s": gap_s, "batches_after": len(after)}))
    assert gap_s <= 30
