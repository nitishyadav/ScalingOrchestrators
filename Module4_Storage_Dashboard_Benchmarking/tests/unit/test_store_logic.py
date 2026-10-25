"""M4-T010 — pure access-layer logic and the schema CLI with a fake session (M4-F01-AC-02, AC-05)."""
import datetime as dt
import json

import pytest

from conftest import BASE
from ids_contracts import SCHEMAS_DIR
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from ids_monitor import schema as cli
from ids_monitor import store as st

HOUR = 3_600_000


def test_split_statements():
    assert len(st.split_statements((SCHEMAS_DIR / "ids_schema.cql").read_text())) == 2
    stmts = st.split_statements((SCHEMAS_DIR / "metrics_schema.cql").read_text())
    assert len(stmts) == 3 and all(s.startswith("CREATE") and "--" not in s for s in stmts)


def test_partitions_between():
    assert st.partitions_between(BASE + 60_000, BASE + 360_000) == [("2026-01-01", 0)]
    end = BASE + 24 * HOUR + 4 * 60_000                       # 2026-01-02 00:04
    assert st.partitions_between(end - 300_000, end) == [("2026-01-01", 23), ("2026-01-02", 0)]
    assert len(st.partitions_between(BASE, BASE + 3 * HOUR)) == 4


def test_ms_datetime_roundtrip_incl_naive_driver_values():
    t = BASE + 123_456
    assert st.dt_to_ms(st.ms_to_dt(t)) == t
    naive = dt.datetime(2026, 1, 1, 0, 2, 3, 456000)          # what the driver returns (UTC, naive)
    assert st.dt_to_ms(naive) == BASE + 123_456


def test_row_to_dict_converts_timestamps():
    row = {"window_end": dt.datetime(2026, 1, 1, 0, 0, 30), "src_ip": "10.0.0.1", "total_bytes": 5}
    assert st.row_to_dict(row) == {"window_end": BASE + 30_000, "src_ip": "10.0.0.1", "total_bytes": 5}


def rows(spec):
    """spec: list of (src_ip, window_end_offset_s, is_anomaly, score, rule_ids)."""
    return [{"src_ip": ip, "window_end": BASE + off * 1000, "is_anomaly": a, "anomaly_score": sc, "rule_ids": r}
            for ip, off, a, sc, r in spec]


def test_drift_summary():
    r = rows([("a", 10, True, 0.7, ""), ("b", 10, False, 0.3, ""), ("c", 20, False, 0.2, ""), ("d", 20, False, 0.2, "")])
    assert st.drift_summary(r) == {"total": 4, "anomalous": 1, "rate": 0.25, "alert": True}
    assert st.drift_summary([]) == {"total": 0, "anomalous": 0, "rate": 0.0, "alert": False}
    assert st.drift_summary(rows([("a", 1, True, 1, "")] + [("b", 1, False, 0, "")] * 6))["alert"] is False   # 1/7 ≤ 0.15


def test_aggregate_top():
    r = rows([("x", 10, True, 0.6, "R-SYN-FLOOD"), ("x", 20, True, 0.9, ""), ("y", 30, True, 0.95, "R-PORT-SCAN"),
              ("z", 30, False, 0.1, ""), ("w", 40, True, 0.6, "R-SYN-FLOOD,R-PORT-SCAN"), ("w", 50, True, 0.6, "")])
    top = st.aggregate_top(r, 2)
    assert [t["src_ip"] for t in top] == ["x", "w"]              # 2 windows each; x has the higher max score
    assert top[0] == {"src_ip": "x", "anomalous_windows": 2, "max_score": 0.9, "last_seen": BASE + 20_000,
                      "rule_ids": "R-SYN-FLOOD"}
    assert top[1]["rule_ids"] == "R-PORT-SCAN,R-SYN-FLOOD"
    assert [t["src_ip"] for t in st.aggregate_top(r, 10)] == ["x", "w", "y"]


def test_writer_statements_cover_contract_columns():
    assert st.WINDOW_INSERT_COLUMNS == tuple(c for c, _ in S.COLUMNS)
    assert st.METRICS_INSERT_COLUMNS == tuple(c for c, _ in M.METRICS_COLUMNS)
    assert st.RUN_INSERT_COLUMNS == tuple(c for c, _ in M.RUNS_COLUMNS)


# ---- schema CLI with a fake session ----------------------------------------------------------
class FakeSession:
    def __init__(self, columns=None):
        self.executed = []
        self.columns = columns if columns is not None else [
            {"table_name": t, "column_name": c, "type": typ}
            for t, cols in (("window_scores", S.COLUMNS), ("pipeline_metrics", M.METRICS_COLUMNS), ("runs", M.RUNS_COLUMNS))
            for c, typ in cols]

    def execute(self, statement, params=None):
        self.executed.append((statement, params))
        return self.columns if "system_schema.columns" in str(statement) else []


def run(argv, capsys, session=None, fail=None):
    def factory(cfg):
        if fail:
            raise st.StoreUnavailable(fail)
        return session or FakeSession()
    code = cli.main(argv, env={}, session_factory=factory)
    return code, capsys.readouterr()


def test_schema_apply(capsys):
    s = FakeSession()
    code, out = run(["apply"], capsys, s)
    assert code == EXIT_OK and len(s.executed) == 5
    assert json.loads(out.out.strip().splitlines()[-1])["statements"] == 5


def test_schema_check_ok_and_drift(capsys):
    code, out = run(["check"], capsys)
    assert code == EXIT_OK and json.loads(out.out.strip().splitlines()[-1])["tables"] == 3
    broken = FakeSession()
    broken.columns = [c for c in broken.columns if c["column_name"] != "rule_ids"] + \
        [{"table_name": "runs", "column_name": "extra", "type": "int"}]
    code, out = run(["check"], capsys, broken)
    assert code == EXIT_RUNTIME_ERROR and "rule_ids" in out.err and "extra" in out.err


def test_schema_store_unavailable(capsys):
    code, out = run(["check"], capsys, fail="NoHostAvailable")
    assert code == EXIT_RUNTIME_ERROR and "platform" in out.err


def test_schema_bad_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        run(["frobnicate"], capsys)
    assert exc.value.code == EXIT_USAGE_ERROR
