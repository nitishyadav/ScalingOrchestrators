"""M4-T010: schema parse / diff / apply (AC-02, AC-03)."""
import pytest

from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_monitor import schema as SC

from conftest import FakeSession


def expected():
    return SC.parse_ddl(SC.ddl_text("ids"))


def system_rows(spec, keyspace="ids"):
    """system_schema.columns rows describing `spec` (as a live Cassandra would)."""
    rows = []
    for table, t in spec.items():
        clustering = dict(t.clustering)
        for name, typ in t.columns:
            if name in t.partition:
                kind, pos, order = "partition_key", t.partition.index(name), "none"
            elif name in clustering:
                kind, pos, order = "clustering", [c for c, _ in t.clustering].index(name), clustering[name].lower()
            else:
                kind, pos, order = "regular", -1, "none"
            rows.append({"keyspace_name": keyspace, "table_name": table, "column_name": name, "type": typ,
                         "kind": kind, "position": pos, "clustering_order": order})
    return rows


def test_parse_ddl_matches_contract_constants():
    spec = expected()
    assert set(spec) == {"window_scores", "pipeline_metrics", "runs"}
    ws = spec["window_scores"]
    assert ws.columns == S.COLUMNS and ws.partition == S.PARTITION_KEY and ws.clustering == S.CLUSTERING
    assert spec["pipeline_metrics"].columns == M.METRICS_COLUMNS and spec["runs"].columns == M.RUNS_COLUMNS


def test_ddl_keyspace_is_configurable():
    text = SC.ddl_text("ids_test")
    assert "ids_test.window_scores" in text and "CREATE KEYSPACE IF NOT EXISTS ids_test" in text
    assert " ids." not in text


def test_no_drift_when_live_equals_contract():
    exp = expected()
    assert SC.diff_schema(exp, SC.schema_from_rows(system_rows(exp))) == []


def test_drift_is_reported_per_difference():
    exp = expected()
    rows = [r for r in system_rows(exp) if not (r["table_name"] == "window_scores" and r["column_name"] == "run_id")]
    for r in rows:
        if r["table_name"] == "window_scores" and r["column_name"] == "event_count":
            r["type"] = "bigint"
    rows = [r for r in rows if r["table_name"] != "runs"]
    diffs = SC.diff_schema(exp, SC.schema_from_rows(rows))
    assert any("window_scores" in d and "missing column run_id" in d for d in diffs)
    assert any("event_count" in d and "bigint" in d for d in diffs)
    assert any("runs" in d and "missing table" in d for d in diffs)
    assert len(diffs) == 3


def test_old_key_is_detected():
    old = SC.parse_ddl(SC.ddl_text("ids").replace("bucket         int", "hour           int")
                       .replace("(date_bucket, bucket)", "(date_bucket, hour)"))
    diffs = SC.diff_schema(expected(), SC.schema_from_rows(system_rows(old)))
    assert any("primary key is ((date_bucket, hour)" in d for d in diffs)


def _session_with(live_spec):
    rows = system_rows(live_spec) if live_spec else []
    return FakeSession(lambda q, p: rows if "system_schema.columns" in q else [])


def test_apply_on_empty_creates_everything():
    s = _session_with(None)
    result = SC.apply_schema(s, "ids")
    creates = [q for q, _ in s.queries("CREATE")]
    assert len(creates) == 4 and result["recreated"] == [] and not s.queries("DROP")


def test_apply_refuses_old_key_without_recreate():
    old = SC.parse_ddl(SC.ddl_text("ids").replace("bucket         int", "hour           int")
                       .replace("(date_bucket, bucket)", "(date_bucket, hour)"))
    s = _session_with(old)
    with pytest.raises(SC.SchemaMigrationRequired, match="--recreate"):
        SC.apply_schema(s, "ids")
    assert not s.queries("CREATE TABLE") and not s.queries("DROP")


def test_apply_recreate_drops_only_mismatched_table():
    old = SC.parse_ddl(SC.ddl_text("ids").replace("bucket         int", "hour           int")
                       .replace("(date_bucket, bucket)", "(date_bucket, hour)"))
    s = _session_with(old)
    result = SC.apply_schema(s, "ids", recreate=True)
    drops = [q for q, _ in s.queries("DROP")]
    assert drops == ["DROP TABLE IF EXISTS ids.window_scores"] and result["recreated"] == ["window_scores"]
