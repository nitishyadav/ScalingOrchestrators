"""M1-T014 — live platform tests (marker `docker`). Runs in file order against a real engine.

Covers M1-F01-AC-01..AC-08 (AC-09 static and AC-11 contract live elsewhere; AC-10 in test_broker_perf.py).
Run with:  make integration-test     (leaves the platform running)
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import pytest

from conftest import MODULE_DIR, ROOT, SPARK_DIR

pytestmark = pytest.mark.docker
DOCKER = "/opt/homebrew/bin/docker" if Path("/opt/homebrew/bin/docker").exists() else "docker"
COMPOSE = [DOCKER, "compose", "-p", "ids", "-f", str(MODULE_DIR / "platform" / "docker-compose.yml")]
COMPOSE_ENV = {**os.environ, "IDS_HOST_ROOT": str(ROOT)}


def engine_up() -> bool:
    return subprocess.run([DOCKER, "info"], capture_output=True).returncode == 0


if not engine_up():
    pytest.skip("Docker engine not running", allow_module_level=True)


def cli(module, *args, env_extra=None, timeout=600):
    env = {**os.environ, "IDS_ROOT": str(ROOT), **(env_extra or {})}
    proc = subprocess.run([sys.executable, "-m", module, *args], capture_output=True, text=True, env=env,
                          cwd=MODULE_DIR, timeout=timeout)
    lines = proc.stdout.strip().splitlines()
    summary = json.loads(lines[-1]) if lines and lines[-1].startswith("{") else None
    return proc.returncode, summary, proc.stderr


def compose(*args, timeout=300, check=True):
    return subprocess.run([*COMPOSE, *args], capture_output=True, text=True, env=COMPOSE_ENV, timeout=timeout, check=check)


def master_json():
    with urllib.request.urlopen("http://localhost:8080/json/", timeout=5) as r:
        return json.load(r)


def wait_ready(limit_s=120):
    deadline = time.monotonic() + limit_s
    while time.monotonic() < deadline:
        code, s, _ = cli("ids_ingest.platform", "status")
        if code == 0:
            return s
        time.sleep(3)
    raise AssertionError("platform did not become ready")


@pytest.fixture(scope="module")
def started():
    """AC-01 precondition: a stopped platform (volumes kept), then `make run` equivalent."""
    cli("ids_ingest.platform", "down")
    return cli("ids_ingest.platform", "up")


def test_ac01_up_from_stopped_within_180s(started):
    code, s, err = started
    assert code == 0, err
    assert s["ready"] is True and s["elapsed_s"] <= 180
    assert set(s["services"]) == {"kafka", "spark-master", "spark-worker", "spark-client", "cassandra"}
    for port in (9092, 7077, 8080, 9042):
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            pass


def test_ac02_status_ready_then_detects_stopped_service():
    code, s, _ = cli("ids_ingest.platform", "status")
    assert code == 0 and s["ready"] is True
    subprocess.run([DOCKER, "stop", "ids-spark-client-1"], check=True, capture_output=True)
    try:
        code, s, _ = cli("ids_ingest.platform", "status")
        assert code == 1 and s["ready"] is False and s["services"]["spark-client"] != "healthy"
    finally:
        subprocess.run([DOCKER, "start", "ids-spark-client-1"], check=True, capture_output=True)
    wait_ready()


def test_ac04_workers_offer_four_executor_slots():
    m = master_json()
    alive = [w for w in m["workers"] if w["state"] == "ALIVE"]
    assert len(alive) >= 2
    assert sum(w["cores"] for w in alive) >= 4
    assert sum(w["memory"] for w in alive) >= 4 * 768


def _describe(topic):
    from confluent_kafka.admin import AdminClient, ConfigResource
    admin = AdminClient({"bootstrap.servers": "localhost:9092"})
    md = admin.list_topics(topic=topic, timeout=10).topics[topic]
    res = ConfigResource("topic", topic)
    cfg = admin.describe_configs([res])[res].result(timeout=10)
    return len(md.partitions), {k: v.value for k, v in cfg.items()}


def test_ac05_topic_admin_live():
    topic = f"m1-it-{uuid.uuid4().hex[:6]}"
    env = {"KAFKA_TOPIC": topic}
    code, s, err = cli("ids_ingest.topic_admin", "--partitions", "4", env_extra=env)
    assert code == 0 and s["action"] == "create", err
    parts, cfg = _describe(topic)
    assert parts == 4 and cfg["retention.ms"] == "1800000"
    assert cli("ids_ingest.topic_admin", "--partitions", "4", env_extra=env)[1]["action"] == "noop"
    assert cli("ids_ingest.topic_admin", "--partitions", "8", env_extra=env)[1]["action"] == "increase"
    assert _describe(topic)[0] == 8
    code, _, err = cli("ids_ingest.topic_admin", "--partitions", "1", env_extra=env)
    assert code == 2 and "--recreate" in err
    code, s, err = cli("ids_ingest.topic_admin", "--partitions", "1", "--recreate", env_extra=env)
    assert code == 0 and s["action"] == "recreate", err
    assert _describe(topic)[0] == 1


def test_ac03_dual_listeners_host_and_in_network():
    from confluent_kafka import Consumer, Producer
    topic = f"m1-listeners-{uuid.uuid4().hex[:6]}"
    assert cli("ids_ingest.topic_admin", "--partitions", "1", env_extra={"KAFKA_TOPIC": topic})[0] == 0
    one_off = [DOCKER, "run", "--rm", "-i", "--network", "ids-net", "apache/kafka:3.8.1"]

    # host (localhost:9092) -> in-network consumer (kafka:29092) in a separate container
    p = Producer({"bootstrap.servers": "localhost:9092"})
    p.produce(topic, key=b"k", value=b"from-host")
    assert p.flush(15) == 0
    out = subprocess.run([*one_off, "/opt/kafka/bin/kafka-console-consumer.sh", "--bootstrap-server", "kafka:29092",
                          "--topic", topic, "--from-beginning", "--max-messages", "1", "--timeout-ms", "30000"],
                         capture_output=True, text=True, timeout=90)
    assert "from-host" in out.stdout, out.stderr[-500:]

    # in-network producer (kafka:29092) -> host consumer (localhost:9092)
    subprocess.run([*one_off, "/opt/kafka/bin/kafka-console-producer.sh", "--bootstrap-server", "kafka:29092",
                    "--topic", topic], input="from-network\n", capture_output=True, text=True, timeout=90, check=True)
    c = Consumer({"bootstrap.servers": "localhost:9092", "group.id": f"g-{uuid.uuid4().hex}", "auto.offset.reset": "earliest"})
    c.subscribe([topic])
    seen, deadline = set(), time.monotonic() + 30
    while "from-network" not in seen and time.monotonic() < deadline:
        msg = c.poll(1.0)
        if msg is not None and not msg.error():
            seen.add(msg.value().decode())
    c.close()
    assert "from-network" in seen


def _pins():
    return dict(line.split("==") for line in (SPARK_DIR / "requirements-spark.txt").read_text().splitlines()
                if "==" in line and not line.startswith("#"))


def test_ac06_pandas_udf_job_from_client_with_pinned_stack():
    proc = compose("exec", "-T", "spark-client", "spark-submit",
                   "/workspace/Module1_Data_Ingestion_Platform/tests/integration/smoke_job.py", timeout=600, check=False)
    assert proc.returncode == 0, proc.stderr[-2000:]
    result = json.loads([l for l in proc.stdout.splitlines() if l.startswith("{")][-1])
    pins = _pins()
    want = [pins["scikit-learn"], pins["numpy"], pins["pandas"], pins["pyarrow"], pins["joblib"], pins["pyyaml"]]
    assert result["rows"] == 126 and result["scored_rows"] == 126
    assert result["driver"][1:] == want
    assert result["executors"], "no executor reported versions"
    for host, py, *libs in result["executors"]:
        assert host != result["driver_host"], "work ran on the driver, not on a worker"
        assert py == result["driver"][0], "driver/executor Python mismatch"
        assert libs == want
    assert result["kafka_connector"] and result["cassandra_connector"]
    assert result["jars_packages"] == ""     # nothing downloaded at job time (FR-006)


def test_ac07_restart_worker_reregisters_within_30s():
    code, s, err = cli("ids_ingest.platform", "restart-worker", "--index", "1")
    assert code == 0, err
    assert s["reregistered_s"] <= 30
    wait_ready()


def test_ac08_down_up_keeps_data_and_clean_needs_yes():
    topic = f"m1-persist-{uuid.uuid4().hex[:6]}"
    assert cli("ids_ingest.topic_admin", "--partitions", "2", env_extra={"KAFKA_TOPIC": topic})[0] == 0
    assert cli("ids_ingest.platform", "down")[0] == 0
    code, s, err = cli("ids_ingest.platform", "up")
    assert code == 0, err
    assert _describe(topic)[0] == 2
    code, _, err = cli("ids_ingest.platform", "clean")
    assert code == 2 and "--yes" in err
    assert cli("ids_ingest.platform", "status")[0] == 0
