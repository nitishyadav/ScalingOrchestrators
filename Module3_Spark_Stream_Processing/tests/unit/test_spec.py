"""M3 pure logic (M3-F01-AC-01, M3-F03-AC-01, M3-F04-AC-01)."""
import json

import pytest

from conftest import DUMMY_BUNDLE, ROOT
from ids_contracts import metrics as M
from ids_contracts.events import LABELS
from ids_stream import spec


def test_label_count_columns_cover_attack_labels():
    assert set(spec.ATTACK_LABELS) == LABELS - {"BENIGN"} and len(spec.ATTACK_LABELS) == 17
    cols = [spec.label_count_column(l) for l in spec.ATTACK_LABELS]
    assert len(set(cols)) == 17 and all(c.replace("_", "").isalnum() for c in cols)
    sql = spec.label_type_sql()
    assert "array_sort" in sql and "'BENIGN'" in sql and all(c in sql for c in cols)


RULES = {"version": 1, "combine": "any", "rules": [
    {"id": "R-A", "all": [{"feature": "syn_ack_ratio", "op": ">=", "value": 5.0}]},
    {"id": "R-B", "all": [{"feature": "packet_rate", "op": ">", "value": 100}, {"feature": "unique_ports", "op": "<=", "value": 3}]},
    {"id": "R-C", "all": [{"feature": "total_bytes", "op": "==", "value": 0}, {"feature": "unique_ports", "op": "<", "value": 2}]},
]}


def test_rule_compilation():
    assert spec.rule_condition_sql(RULES["rules"][0]) == "(syn_ack_ratio >= 5.0)"
    assert spec.rule_condition_sql(RULES["rules"][1]) == "(packet_rate > 100 AND unique_ports <= 3)"
    assert spec.rule_condition_sql(RULES["rules"][2]) == "(total_bytes = 0 AND unique_ports < 2)"
    flag, ids = spec.rules_sql(RULES)
    assert flag == "((syn_ack_ratio >= 5.0) OR (packet_rate > 100 AND unique_ports <= 3) OR (total_bytes = 0 AND unique_ports < 2))"
    assert ids == ("concat_ws(',', CASE WHEN (syn_ack_ratio >= 5.0) THEN 'R-A' END, "
                   "CASE WHEN (packet_rate > 100 AND unique_ports <= 3) THEN 'R-B' END, "
                   "CASE WHEN (total_bytes = 0 AND unique_ports < 2) THEN 'R-C' END)")
    assert spec.rules_sql(dict(RULES, combine="all"))[0] == (
        "((syn_ack_ratio >= 5.0) AND (packet_rate > 100 AND unique_ports <= 3) AND (total_bytes = 0 AND unique_ports < 2))")


def test_rule_compilation_rejects_injection():
    ratio = {"id": "R-R", "all": [{"feature": "port_ratio", "op": ">=", "value": 0.5}]}    # C-03 0.2.0: any RULE_FEATURE
    assert spec.rule_condition_sql(ratio) == "(port_ratio >= 0.5)"
    bad = {"version": 1, "combine": "any", "rules": [{"id": "x'; DROP", "all": [{"feature": "packet_rate", "op": ">=", "value": 1}]}]}
    with pytest.raises(ValueError):
        spec.rules_sql(bad)
    with pytest.raises(ValueError):
        spec.rule_condition_sql({"id": "R", "all": [{"feature": "label", "op": ">=", "value": 1}]})


def test_batch_stats_and_metrics_row():
    stats = spec.batch_stats([300, 100, 200, 400], anomalies=1)
    assert stats == {"latency_p50_ms": 200.0, "latency_p95_ms": 400.0, "latency_max_ms": 400.0,
                     "windows_written": 4, "anomalies_written": 1}
    assert spec.batch_stats([], 0)["latency_p95_ms"] is None
    progress = {"batchId": 7, "timestamp": "2026-01-01T00:00:30.250Z", "numInputRows": 5000,
                "inputRowsPerSecond": 4990.5, "processedRowsPerSecond": float("nan"),
                "durationMs": {"triggerExecution": 812},
                "sources": [{"endOffset": json.dumps({"network-events": {"0": 10, "1": 12, "2": 9, "3": 4}})}]}
    row = spec.metrics_row("DEV-x", progress, stats, executors=2)
    assert tuple(row) == tuple(c for c, _ in M.METRICS_COLUMNS)
    assert row["batch_ts"] == 1_767_225_630_250 and row["kafka_partitions"] == 4 and row["processed_rows_per_sec"] == 0.0
    assert M.validate_metrics_row(row) == []
    empty = spec.metrics_row("DEV-x", {**progress, "sources": []}, None, executors=1)
    assert empty["windows_written"] == 0 and empty["latency_p95_ms"] is None and empty["kafka_partitions"] == 0
    assert M.validate_metrics_row(empty) == []


def test_bundle_meta_reader():
    manifest, rules = spec.read_bundle_meta(DUMMY_BUNDLE)
    assert manifest["bundle_version"] == "0.0.0-dummy" and rules["version"] == 1
    with pytest.raises(spec.BundleMetaError):
        spec.read_bundle_meta(ROOT / "nope")


def test_container_path():
    assert spec.container_path(ROOT / "runtime" / "bundle" / "current", ROOT) == "/workspace/runtime/bundle/current"
    with pytest.raises(ValueError):
        spec.container_path("/tmp/elsewhere", ROOT)
