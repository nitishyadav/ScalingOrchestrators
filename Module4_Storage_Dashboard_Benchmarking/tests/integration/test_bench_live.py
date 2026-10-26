"""M4-F03-AC-05 — harness smoke on the live platform (E1, 1 partition, 45 s). Marker `docker`. Takes about 80 s."""
import csv
import json
import os
import subprocess
import sys

import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts import metrics as M
from ids_contracts.config import load_config, validate_run_id
from ids_monitor import store as st

pytestmark = pytest.mark.docker

try:
    st.connect(load_config(env={}, cwd=ROOT))
except st.StoreUnavailable:
    pytest.skip("Cassandra not reachable on localhost:9042 (`make run` in Module 1)", allow_module_level=True)


def test_ac05_smoke_run_writes_valid_raw_results(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "ids_monitor.bench", "--experiment", "E1", "--levels", "1",
                           "--duration", "45", "--warmup", "15"], capture_output=True, text=True, cwd=MODULE_DIR,
                          env={**os.environ, "IDS_ROOT": str(ROOT), "RESULTS_DIR": str(tmp_path)}, timeout=600)
    assert proc.returncode == 0, proc.stderr[-3000:]
    summary = json.loads(proc.stdout.strip().splitlines()[-1])
    (run_id,) = summary["runs"]
    assert summary["command"] == "bench" and summary["failed"] == [] and validate_run_id(run_id)
    raw = tmp_path / "raw" / run_id
    result = json.loads((raw / "summary.json").read_text())
    assert result["status"] == "ok" and result["job"]["input_rows"] == result["producer"]["sent"] == 45 * 5000
    s = result["summary"]
    assert s["keeping_up"] and s["capacity_rows_per_s"] > 0 and s["latency_p95_ms"] > 0
    with open(raw / "metrics.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and list(rows[0]) == [c for c, _ in M.METRICS_COLUMNS] and all(r["run_id"] == run_id for r in rows)
    assert sum(int(r["input_rows"]) for r in rows) == 45 * 5000
    assert summary["report"].startswith(str(tmp_path)) and os.path.isfile(summary["report"])
