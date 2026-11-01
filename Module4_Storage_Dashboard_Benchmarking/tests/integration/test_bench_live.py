"""M4-T231 (AC-08): live smoke of the harness on the platform: E1 level 1, 60 s replay.

Needs `ids_ingest.platform up` and M1/M3 installed in this Python. Skips otherwise. Writes to a temporary RESULTS_DIR.
"""
import json
import subprocess
import sys

import pytest

from ids_contracts.config import load_runtime_config, validate_run_id
from ids_monitor import bench, bench_plan

pytestmark = pytest.mark.docker


def test_ac08_smoke_e1_level1(tmp_path):
    cfg = load_runtime_config()
    adapter = bench.SubprocessCli(cfg.workspace_root)
    missing = [m for m in bench_plan.modules_needed("E1") if not adapter.available(m)]
    if missing:
        pytest.skip(f"C-06 CLIs not installed: {', '.join(missing)}")
    status = subprocess.run([sys.executable, "-m", "ids_ingest.platform", "status"], capture_output=True, text=True,
                            cwd=cfg.workspace_root, timeout=120)
    if status.returncode != 0 or not json.loads(status.stdout.strip().splitlines()[-1]).get("ready"):
        pytest.skip("platform is not up (python -m ids_ingest.platform up)")
    p = subprocess.run([sys.executable, "-m", "ids_monitor.bench", "--experiment", "E1", "--levels", "1", "--duration", "60"],
                       capture_output=True, text=True, timeout=900, env={**__import__("os").environ, "RESULTS_DIR": str(tmp_path)})
    summary = json.loads(p.stdout.strip().splitlines()[-1])
    assert p.returncode == 0, p.stderr[-3000:]
    (rid,) = summary["runs"]
    assert validate_run_id(rid) and summary["failed"] == []
    raw = tmp_path / "raw" / rid
    s = json.loads((raw / "summary.json").read_text())
    assert s["status"] == "ok" and s["steady_batches"] > 0 and s["sustained_evs"] > 0
    assert (tmp_path / summary["report"]).exists()
