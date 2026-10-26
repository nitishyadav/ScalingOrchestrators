"""M4-T010 — schema and access against the live Cassandra (M4-F01-AC-01, AC-04). Marker `docker`."""
import json
import os
import subprocess
import sys
import time
import uuid

import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts.config import load_config
from ids_monitor import store as st
from ids_monitor import synthetic as syn

pytestmark = pytest.mark.docker

try:
    SESSION = st.connect(load_config(env={}, cwd=ROOT))
except st.StoreUnavailable:
    pytest.skip("Cassandra not reachable on localhost:9042 (`make run` in Module 1)", allow_module_level=True)


def cli(*args):
    proc = subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, cwd=MODULE_DIR,
                          env={**os.environ, "IDS_ROOT": str(ROOT)}, timeout=120)
    return proc.returncode, json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None, proc.stderr


def test_ac01_apply_twice_and_check():
    for _ in range(2):
        code, s, err = cli("ids_monitor.schema", "apply")
        assert code == 0 and s["statements"] == 5, err
    code, s, err = cli("ids_monitor.schema", "check")
    assert code == 0 and s["tables"] == 3, err


def test_ac04_write_and_read_back_a_synthetic_run():
    run_id = f"DEV-it-{uuid.uuid4().hex[:8]}"
    now = int(time.time() * 1000)
    data = syn.generate(now_ms=now, seconds=120, n_ips=20, anomaly_share=0.2, run_id=run_id, seed=11)
    writer, reader = st.StoreWriter(SESSION), st.StoreReader(SESSION)
    writer.write_windows(data["windows"])
    writer.write_metrics(data["metrics"])
    writer.write_run(data["run"])
    try:
        got = reader.recent_windows(now, seconds=120, run_id=run_id)
        key = lambda r: (r["window_end"], r["src_ip"])
        assert sorted(map(key, got)) == sorted(map(key, data["windows"]))
        sample = {key(r): r for r in data["windows"]}
        for r in got[:50]:
            assert r == sample[key(r)]                           # every column round-trips (timestamps as ms)
        d = reader.drift(now, seconds=120, run_id=run_id)
        assert d["total"] == len(data["windows"]) and abs(d["rate"] - 0.2) < 1e-9 and d["alert"] is True
        top = reader.top_flagged(now, seconds=120, n=10, run_id=run_id)
        assert len(top) == 10 and all(a["anomalous_windows"] >= b["anomalous_windows"] for a, b in zip(top, top[1:]))
        metrics = reader.metrics(run_id, limit=5)
        assert len(metrics) == 5 and metrics[0]["batch_ts"] > metrics[-1]["batch_ts"]       # newest first
        assert any(r["run_id"] == run_id for r in reader.runs(limit=20))
    finally:
        st.delete_run(SESSION, data)
    assert reader.recent_windows(now, seconds=120, run_id=run_id) == []


def test_ac05_unreachable_store_is_reported():
    with pytest.raises(st.StoreUnavailable):
        st.connect(load_config(env={"CASSANDRA_PORT": "9"}, cwd=ROOT))
