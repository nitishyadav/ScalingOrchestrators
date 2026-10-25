"""Item 8 — terminal Ctrl-C (SIGINT to the whole foreground process group) must stop the job gracefully:
exit 0, the driver's summary re-emitted, no driver left running. Marker `docker`."""
import json
import os
import signal
import subprocess
import sys
import time
import uuid

import pytest

from conftest import MODULE_DIR, ROOT
from ids_stream import job
from test_e2e_live import env, session, wait_for_run_row

pytestmark = pytest.mark.docker


def test_ctrl_c_on_process_group_stops_gracefully():
    run_id = f"DEV-m3-ctrlc-{uuid.uuid4().hex[:6]}"
    proc = subprocess.Popen([sys.executable, "-m", "ids_stream.job", "--run-id", run_id], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env("network-events"), cwd=MODULE_DIR,
                            start_new_session=True)                      # its own group, like a terminal job
    wait_for_run_row(session(), run_id)
    time.sleep(3)
    os.killpg(proc.pid, signal.SIGINT)                                   # what Ctrl-C does in a terminal
    out, err = proc.communicate(timeout=120)
    assert proc.returncode == 0, err[-2000:]
    summary = json.loads(out.strip().splitlines()[-1])
    assert summary["command"] == "stream job" and summary["status"] == "ok"
    d = job.Docker()
    left = subprocess.run([d.bin, "exec", d.find_spark_client(), "pgrep", "-f", "ids_stream/app.py"], capture_output=True)
    assert left.returncode != 0, "driver still running after Ctrl-C"
