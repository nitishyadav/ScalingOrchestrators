"""M3 replica honours C-01 (input), C-03 (rules), C-04/C-05 (output), C-06 (CLI)."""
import re
import subprocess
import sys

import pytest

from conftest import DUMMY_BUNDLE, MODULE_DIR, ROOT
from ids_contracts import events as ev
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR
from ids_stream import spec


def test_event_ddl_matches_c01():
    fields = [tuple(f.strip().split(" ")) for f in spec.EVENT_DDL.split(",")]
    assert tuple(n for n, _ in fields) == ev.ALL_FIELDS
    types = dict(fields)
    assert types["timestamp"] == types["bytes_sent"] == "BIGINT" and types["is_injected"] == "BOOLEAN"
    assert all(types[f] == "INT" for f in ("dst_port", "syn_flag", "ack_flag"))


def test_validity_filter_covers_c01_rules():
    sql = spec.VALID_EVENT_SQL
    for frag in ("event_id IS NOT NULL", f"timestamp >= {ev.MIN_TIMESTAMP_MS}", "dst_port BETWEEN 0 AND 65535",
                 "bytes_sent >= 0", "syn_flag >= 0", "ack_flag >= 0", "src_ip RLIKE", "dst_ip RLIKE"):
        assert frag in sql, frag


def test_features_never_read_eval_only_fields():
    assert "label" not in spec.FEATURE_AGG_SQL and "is_injected" not in spec.FEATURE_AGG_SQL


def test_output_columns_equal_c04_c05():
    assert spec.STORE_COLUMNS == tuple(c for c, _ in S.COLUMNS)
    assert spec.METRICS_COLUMNS == tuple(c for c, _ in M.METRICS_COLUMNS)
    assert spec.RUN_COLUMNS == tuple(c for c, _ in M.RUNS_COLUMNS)


def test_committed_dummy_rules_compile():
    _, rules = spec.read_bundle_meta(DUMMY_BUNDLE)
    flag, ids = spec.rules_sql(rules)
    assert all(f"'{r['id']}'" in ids for r in rules["rules"])
    assert all(c["feature"] in flag for r in rules["rules"] for c in r["all"]) and "label" not in flag


def cli(*args):
    return subprocess.run([sys.executable, "-m", "ids_stream.job", *args], capture_output=True, text=True,
                          cwd=MODULE_DIR, env={"PATH": "/usr/bin:/bin", "IDS_ROOT": str(ROOT)}, timeout=60)


def test_cli_help_and_usage_errors():
    assert cli("--help").returncode == EXIT_OK
    assert cli("--bogus").returncode == EXIT_USAGE_ERROR
    assert cli("--executors", "0").returncode == EXIT_USAGE_ERROR
