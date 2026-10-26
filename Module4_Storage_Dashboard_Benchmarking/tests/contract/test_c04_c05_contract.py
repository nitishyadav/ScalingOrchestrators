"""M4-T010 — M4 replica honours C-04/C-05/C-06 (M4-F01-AC-03, AC-05)."""
import subprocess
import sys

import pytest

from conftest import BASE, MODULE_DIR, ROOT
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR
from ids_monitor import store as st
from ids_monitor import synthetic as syn


def test_generated_rows_satisfy_c04_c05():
    data = syn.generate(now_ms=BASE + 7_200_000, seconds=600, n_ips=30, anomaly_share=0.2, run_id="DEV-c", seed=3)
    assert all(S.validate_row(r) == [] for r in data["windows"])
    assert all(M.validate_metrics_row(m) == [] for m in data["metrics"]) and M.validate_run_row(data["run"]) == []
    assert all(set(r) == {c for c, _ in S.COLUMNS} for r in data["windows"])


def test_reader_never_needs_allow_filtering():
    assert "ALLOW FILTERING" not in (st.WINDOWS_QUERY + st.METRICS_QUERY + st.RUNS_QUERY).upper()
    assert "WHERE date_bucket = %s AND hour = %s" in st.WINDOWS_QUERY


def cli(*args):
    return subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, cwd=MODULE_DIR,
                          env={"PATH": "/usr/bin:/bin", "IDS_ROOT": str(ROOT)}, timeout=60)


@pytest.mark.parametrize("module", ["ids_monitor.schema", "ids_monitor.synthetic"])
def test_help(module):
    assert cli(module, "--help").returncode == EXIT_OK


@pytest.mark.parametrize("args", [("ids_monitor.schema", "frobnicate"), ("ids_monitor.synthetic", "--anomaly-share", "2"),
                                  ("ids_monitor.synthetic", "--bogus")])
def test_usage_errors(args):
    assert cli(*args).returncode == EXIT_USAGE_ERROR
