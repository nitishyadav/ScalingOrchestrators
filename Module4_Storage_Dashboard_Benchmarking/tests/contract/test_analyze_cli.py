"""M4-T322: C-06 conventions for `python -m ids_monitor.analyze` (help 0, bad flag 2, summary line, empty dir ok)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
import results_fixture as RF  # noqa: E402


def analyze(*args, results=None):
    env = {**os.environ, **({"RESULTS_DIR": str(results)} if results else {})}
    return subprocess.run([sys.executable, "-m", "ids_monitor.analyze", *args], capture_output=True, text=True,
                          timeout=120, env=env)


def test_help_and_bad_flag():
    assert analyze("--help").returncode == 0
    assert analyze("--nope").returncode == 2


def test_summary_line_on_empty_and_full_results(tmp_path):
    empty = analyze(results=tmp_path / "empty")
    s = json.loads(empty.stdout.strip().splitlines()[-1])
    assert empty.returncode == 0 and s["status"] == "ok" and set(s["verdicts"].values()) == {"NOT RUN"}
    RF.write(tmp_path / "full")
    full = analyze(results=tmp_path / "full")
    s = json.loads(full.stdout.strip().splitlines()[-1])
    assert full.returncode == 0 and s["command"] == "ids_monitor.analyze" and len(s["figures"]) == 6
    assert s["verdicts"]["P3"] == "PASS" and s["verdicts"]["P4"] == "FAIL" and Path(s["results_md"]).exists()
