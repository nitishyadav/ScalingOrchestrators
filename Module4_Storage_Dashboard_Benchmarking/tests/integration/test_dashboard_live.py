"""M4-T040 — dashboard against the live Cassandra, and the real server (M4-F02-AC-04). Marker `docker`."""
import os
import subprocess
import sys
import time
import urllib.request
import uuid

import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts.config import load_config
from ids_monitor import store as st
from ids_monitor import synthetic as syn

pytestmark = pytest.mark.docker
APP = str(MODULE_DIR / "src" / "ids_monitor" / "dashboard.py")

try:
    SESSION = st.connect(load_config(env={}, cwd=ROOT))
except st.StoreUnavailable:
    pytest.skip("Cassandra not reachable", allow_module_level=True)


def test_ac04_live_page_shows_a_fresh_run(monkeypatch):
    from streamlit.testing.v1 import AppTest
    run_id = f"DEV-dash-{uuid.uuid4().hex[:6]}"
    data = syn.generate(now_ms=int(time.time() * 1000), seconds=300, n_ips=20, anomaly_share=0.25, run_id=run_id, seed=9)
    w = st.StoreWriter(SESSION)
    w.write_run(data["run"])
    w.write_windows(data["windows"])
    w.write_metrics(data["metrics"])
    try:
        monkeypatch.setattr(sys, "argv", ["dashboard.py", "--run-id", run_id])
        at = AppTest.from_file(APP, default_timeout=60)
        at.run()
        assert not at.exception, at.exception
        assert any("Drift alert" in e.value for e in at.error)
        assert any(run_id in c.value for c in at.caption)
        assert at.metric[3].value != "—"
    finally:
        st.delete_run(SESSION, data)


def test_ac04_server_health():
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", APP, "--server.port", "8599",
                             "--server.headless", "true", "--", "--demo"],
                            cwd=MODULE_DIR, env={**os.environ, "IDS_ROOT": str(ROOT)},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline, body = time.time() + 40, ""
        while time.time() < deadline:
            try:
                body = urllib.request.urlopen("http://localhost:8599/_stcore/health", timeout=2).read().decode()
                if body == "ok":
                    break
            except OSError:
                time.sleep(1)
        assert body == "ok"
        assert urllib.request.urlopen("http://localhost:8599/", timeout=5).status == 200
    finally:
        proc.terminate()
        proc.wait(timeout=20)
