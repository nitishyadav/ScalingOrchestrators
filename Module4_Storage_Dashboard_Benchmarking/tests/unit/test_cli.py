"""M4-T014: C-06 CLI behaviour — exit codes and the JSON summary line (AC-11)."""
import json

import pytest

from ids_monitor import cli, db
from ids_monitor import schema as SC
from ids_monitor import synthetic as SY

from conftest import FakeSession


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for k in ("CASSANDRA_HOSTS", "CASSANDRA_PORT", "CASSANDRA_KEYSPACE", "RUN_ID"):
        monkeypatch.delenv(k, raising=False)


def last_json(capsys):
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


def test_ok_prints_summary_last(capsys):
    code = cli.run("demo", lambda cfg: {"rows": 3})
    s = last_json(capsys)
    assert code == 0 and s["status"] == "ok" and s["command"] == "demo" and s["rows"] == 3 and "run_id" in s


def test_runtime_error_exits_1(capsys):
    def boom(cfg):
        raise db.StoreUnavailable("cannot reach Cassandra at localhost:9042")
    assert cli.run("demo", boom) == 1
    err = capsys.readouterr().err
    assert "localhost:9042" in err and "Traceback" not in err


def test_usage_error_exits_2(capsys):
    def bad(cfg):
        raise cli.UsageError("--n-ips must be ≥ 1")
    assert cli.run("demo", bad) == 2


def test_config_error_exits_2(monkeypatch, capsys):
    monkeypatch.setenv("CASSANDRA_PORT", "not-a-port")
    assert cli.run("demo", lambda cfg: {}) == 2


def test_connection_settings_come_from_c06(monkeypatch):
    monkeypatch.setenv("CASSANDRA_HOSTS", "h1,h2")
    monkeypatch.setenv("CASSANDRA_PORT", "9043")
    seen = {}
    cli.run("demo", lambda cfg: seen.update(hosts=cfg.cassandra_hosts, port=cfg.cassandra_port) or {})
    assert seen == {"hosts": ("h1", "h2"), "port": 9043}


def test_schema_cli_check_reports_drift_exit_1(monkeypatch, capsys):
    s = FakeSession()                                           # empty keyspace: every table missing
    monkeypatch.setattr(db, "connect", lambda cfg: (None, s))
    assert SC.main(["check"]) == 1
    out = capsys.readouterr()
    assert "missing table" in out.err


def test_schema_cli_bad_usage_exit_2(capsys):
    assert SC.main(["frobnicate"]) == 2


def test_synthetic_cli_writes_and_summarises(monkeypatch, capsys):
    s = FakeSession()
    monkeypatch.setattr(db, "connect", lambda cfg: (None, s))
    assert SY.main(["--n-ips", "5", "--windows", "3", "--seed", "9", "--run-id", "DEV-cli"]) == 0
    summary = last_json(capsys)
    assert summary["windows"] == 15 and summary["seed"] == 9 and summary["run_id"] == "DEV-cli"
    assert len(s.queries("INSERT INTO ids.window_scores")) == 15


def test_synthetic_cli_bad_share_exit_2(monkeypatch, capsys):
    monkeypatch.setattr(db, "connect", lambda cfg: (None, FakeSession()))
    assert SY.main(["--anomaly-share", "2"]) == 2
