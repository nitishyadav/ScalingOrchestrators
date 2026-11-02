"""M4-T230: C-06 §5/§9 conformance of `python -m ids_monitor.bench` (no platform needed: --dry-run)."""
import json
import subprocess
import sys

from ids_contracts.config import validate_run_id


def bench(*args):
    return subprocess.run([sys.executable, "-m", "ids_monitor.bench", *args], capture_output=True, text=True, timeout=60)


def test_help_exits_0():
    assert bench("--help").returncode == 0


def test_bad_flag_and_bad_values_exit_2():
    assert bench("--experiment", "E1", "--no-such-flag").returncode == 2
    assert bench("--experiment", "E9").returncode == 2
    p = bench("--experiment", "E1", "--levels", "3", "--dry-run")
    assert p.returncode == 2 and "unknown level" in p.stderr
    assert bench("--experiment", "E1", "--duration", "60", "--warmup", "60", "--dry-run").returncode == 2


def test_dry_run_summary_line():
    p = bench("--experiment", "E3", "--duration", "60", "--dry-run")
    assert p.returncode == 0, p.stderr
    summary = json.loads(p.stdout.strip().splitlines()[-1])
    assert summary["status"] == "ok" and summary["command"] == "ids_monitor.bench" and summary["experiment"] == "E3"
    assert len(summary["runs"]) == 4 and all(validate_run_id(r) for r in summary["runs"]) and summary["failed"] == []
    assert "python -m ids_ingest.producer" in p.stdout and "--attack-share 0.2" in p.stdout
