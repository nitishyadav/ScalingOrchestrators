"""Contract tests for the PROVISIONAL REPLICA contracts C-02..C-05 (authored by M1 in replica mode)."""
import importlib.util
import json
import re

import pytest

from ids_contracts import FIXTURES_DIR, SCHEMAS_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.events import iter_jsonl

GOLDEN_FEATURES = FIXTURES_DIR / "features_golden.csv"
BASE = 1_767_225_600_000


# ---- C-02 ------------------------------------------------------------------------------------
def test_replay_timestamp_floor():
    assert [F.replay_timestamp(i, BASE, 5000) for i in range(7)] == [BASE] * 5 + [BASE + 1] * 2


def test_window_starts_match_spark_semantics():
    assert F.window_starts(BASE) == (BASE, BASE - 10_000, BASE - 20_000)
    assert F.window_starts(BASE + 29_999) == (BASE + 20_000, BASE + 10_000, BASE)
    for t in (BASE + 12_345, BASE + 40_000):
        assert all(s <= t < s + F.WINDOW_MS for s in F.window_starts(t))


def test_formulas_and_labels():
    assert F.syn_ack_ratio(25, 0) == 25.0 and F.syn_ack_ratio(3, 2) == 1.0
    assert F.packet_rate(30) == 1.0
    assert F.window_label(["BENIGN", "BENIGN"]) == (False, "BENIGN")
    assert F.window_label(["BENIGN", "PortScan", "DDoS", "DDoS"]) == (True, "DDoS")
    assert F.window_label(["PortScan", "DDoS"]) == (True, "DDoS")            # tie → alphabetical


def test_golden_features_file():
    rows = F.read_feature_csv(GOLDEN_FEATURES)
    assert len(rows) == 23
    assert all(F.validate_feature_row(r) == [] for r in rows)
    assert rows == sorted(rows, key=lambda r: (r["window_start"], r["src_ip"]))
    by = {(r["window_start"] - BASE, r["src_ip"]): r for r in rows}
    assert max(r["unique_ports"] for r in rows if r["src_ip"] == "172.16.0.10") == 40           # port scan
    assert by[(40_000, "172.16.0.20")]["syn_ack_ratio"] == 25.0                                  # SYN flood
    for start in (20_000, 30_000, 40_000):                                                       # late event counted
        assert by[(start, "192.168.10.5")]["event_count"] == 11
    assert sum(r["event_count"] for r in rows) == 126 * 3


def test_golden_features_regenerate_identically():
    spec = importlib.util.spec_from_file_location("genf", FIXTURES_DIR / "_gen" / "gen_features_golden.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.render(gen.build_rows()) == GOLDEN_FEATURES.read_bytes()


def test_ratio_features_v020():
    rows = F.read_feature_csv(GOLDEN_FEATURES)
    syn = {(r["window_start"] - BASE, r["src_ip"]): r for r in rows}[(40_000, "172.16.0.20")]
    assert syn["syn_share"] == 1.0 and syn["port_ratio"] == 1 / 25 and syn["bytes_per_flow"] == 60.0
    scan = max((r for r in rows if r["src_ip"] == "172.16.0.10"), key=lambda r: r["unique_ports"])
    assert scan["port_ratio"] == 1.0                                   # one new port per flow = scan signature
    assert F.FEATURE_ORDER == ("bytes_per_flow", "port_ratio", "syn_ack_ratio", "syn_share")
    assert set(F.FEATURE_ORDER) <= set(F.RULE_FEATURES) and set(F.BASE_FEATURES) <= set(F.RULE_FEATURES)


def test_feature_row_validator_catches_errors():
    row = F.read_feature_csv(GOLDEN_FEATURES)[0]
    assert F.validate_feature_row(dict(row, window_end=row["window_end"] + 1))
    assert F.validate_feature_row(dict(row, packet_rate=9.9))
    assert F.validate_feature_row(dict(row, max_event_ts=row["window_end"]))
    assert F.validate_feature_row(dict(row, port_ratio=0.99))
    assert F.validate_feature_row(dict(row, bytes_per_flow=row["bytes_per_flow"] + 1))
    assert F.validate_feature_row({k: v for k, v in row.items() if k != "label_type"})
    assert not F.rows_equal(row, dict(row, syn_ack_ratio=row["syn_ack_ratio"] + 1e-6))
    assert F.rows_equal(row, dict(row, syn_ack_ratio=row["syn_ack_ratio"] + 1e-12))


def test_features_read_only_scoring_fields():
    from ids_contracts.events import SCORING_FIELDS
    assert set(F.FEATURE_ORDER).isdisjoint(F.EVAL_COLUMNS)
    assert {"timestamp", "src_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag"} == set(SCORING_FIELDS)


# ---- C-03 ------------------------------------------------------------------------------------
RULES = {"version": 1, "combine": "any", "rules": [
    {"id": "R-SYN-FLOOD", "all": [{"feature": "syn_ack_ratio", "op": ">=", "value": 5.0}]},
    {"id": "R-PORT-SCAN", "all": [{"feature": "unique_ports", "op": ">=", "value": 50}]},
    {"id": "R-DDOS-RATE", "all": [{"feature": "packet_rate", "op": ">=", "value": 100.0},
                                  {"feature": "unique_ports", "op": "<=", "value": 3}]},
]}
MANIFEST = {"bundle_version": "0.0.0-dummy", "created_at": "2026-10-22T00:00:00+00:00", "python_version": "3.10.12",
            "sklearn_version": "1.5.2", "numpy_version": "1.26.4", "feature_order": list(F.FEATURE_ORDER),
            "score_definition": B.SCORE_DEFINITION, "threshold": 0.55,
            "training": {"data": "synthetic", "seed": 42, "n_estimators": 100, "contamination": "auto", "R_ref": 5000},
            "metrics": {"precision": None, "recall": None, "fpr": None, "test_files": []},
            "contract_versions": {"C-02": F.CONTRACT_VERSION, "C-03": B.CONTRACT_VERSION}}


def test_manifest_and_rules_valid():
    assert B.validate_manifest(MANIFEST) == [] and B.validate_rules(RULES) == []


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(feature_order=["packet_rate"]), lambda m: m.update(threshold=float("nan")),
    lambda m: m.pop("training"), lambda m: m["metrics"].update(precision=1.5),
    lambda m: m.update(score_definition="x"), lambda m: m.update(contract_versions={}),
])
def test_manifest_errors(mutate):
    m = json.loads(json.dumps(MANIFEST))
    mutate(m)
    assert B.validate_manifest(m)


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(version=2), lambda r: r.update(combine="most"), lambda r: r.update(rules=[]),
    lambda r: r["rules"][0]["all"][0].update(feature="label"), lambda r: r["rules"][0]["all"][0].update(op="~"),
    lambda r: r["rules"].append(dict(r["rules"][0])),
])
def test_rules_errors(mutate):
    r = json.loads(json.dumps(RULES))
    mutate(r)
    assert B.validate_rules(r)


def test_reference_decision_semantics_on_golden_rows():
    rows = F.read_feature_csv(GOLDEN_FEATURES)
    by_src = {}
    for r in rows:
        hits = B.rule_hits(RULES, r)
        ml, rule, anomaly, ids = B.decide(0.1, 0.55, RULES, hits)
        assert (ml, rule == bool(hits), anomaly == (ml or rule), ids) == (False, True, True, ",".join(hits))
        by_src.setdefault(r["src_ip"], set()).update(hits)
    assert by_src["172.16.0.20"] == {"R-SYN-FLOOD"} and by_src["172.16.0.10"] >= {"R-SYN-FLOOD"}
    assert by_src["192.168.10.5"] == set()
    assert B.decide(0.9, 0.55, RULES, [])[:3] == (True, False, True)
    assert B.decide(0.1, 0.55, dict(RULES, combine="all"), ["R-SYN-FLOOD"])[1] is False


def test_json_schemas_agree():
    jsonschema = pytest.importorskip("jsonschema")
    for name, good in (("manifest.schema.json", MANIFEST), ("rules.schema.json", RULES)):
        v = jsonschema.Draft202012Validator(json.loads((SCHEMAS_DIR / name).read_text()))
        assert not list(v.iter_errors(good)), name
    bad = json.loads(json.dumps(RULES))
    bad["rules"][0]["all"][0]["op"] = "~"
    assert list(jsonschema.Draft202012Validator(json.loads((SCHEMAS_DIR / "rules.schema.json").read_text())).iter_errors(bad))


# ---- C-04 / C-05: python constants equal the DDL ------------------------------------------------
def cql_tables(path):
    text = re.sub(r"--[^\n]*", "", path.read_text())
    tables = {}
    for name, body, opts in re.findall(r"CREATE TABLE IF NOT EXISTS ids\.(\w+) \((.*?)\)\s*(WITH[^;]*);", text, re.S):
        cols = re.findall(r"^\s*(\w+)\s+(\w+),\s*$", body, re.M)
        pk = re.search(r"PRIMARY KEY \(\((.*?)\),\s*(.*?)\)\s*$", body.strip(), re.S)
        tables[name] = {"columns": tuple(cols), "partition": tuple(c.strip() for c in pk.group(1).split(",")),
                        "clustering": tuple(c.strip() for c in pk.group(2).split(",")), "options": opts}
    return tables


def test_store_constants_match_ddl():
    t = cql_tables(SCHEMAS_DIR / "ids_schema.cql")["window_scores"]
    assert t["columns"] == S.COLUMNS
    assert t["partition"] == S.PARTITION_KEY and t["clustering"] == tuple(c for c, _ in S.CLUSTERING)
    assert "window_end DESC, src_ip ASC" in t["options"] and f"default_time_to_live = {S.TTL_S}" in t["options"]


def test_metrics_constants_match_ddl():
    t = cql_tables(SCHEMAS_DIR / "metrics_schema.cql")
    assert t["pipeline_metrics"]["columns"] == M.METRICS_COLUMNS and t["runs"]["columns"] == M.RUNS_COLUMNS
    assert t["pipeline_metrics"]["partition"] == ("run_id",) and t["runs"]["partition"] == ("bucket",)


def _row():
    end = BASE + 30_000
    db, hr = S.partition_key(end)
    return {"date_bucket": db, "hour": hr, "window_end": end, "src_ip": "10.0.0.1", "window_start": BASE,
            "total_bytes": 10, "unique_ports": 1, "syn_ack_ratio": 0.5, "packet_rate": 0.1, "event_count": 3,
            "anomaly_score": 0.4, "ml_flag": False, "rule_flag": True, "rule_ids": "R-SYN-FLOOD", "is_anomaly": True,
            "max_event_ts": BASE + 29_000, "detected_at": BASE + 29_400, "bundle_version": "0.0.0-dummy",
            "run_id": "DEV-local", "label_attack": False, "label_type": "BENIGN"}


def test_store_row_validation():
    assert S.partition_key(BASE + 30_000) == ("2026-01-01", 0)
    assert S.validate_row(_row()) == []
    assert S.validate_row(dict(_row(), hour=5))
    assert S.validate_row(dict(_row(), is_anomaly=False))
    assert S.validate_row(dict(_row(), rule_ids=""))
    assert S.validate_row(dict(_row(), src_ip=None))
    assert S.drift_alert(16, 100) and not S.drift_alert(15, 100) and not S.drift_alert(0, 0)


def test_metrics_rows_and_percentile():
    assert M.percentile([], 95) is None
    assert M.percentile(list(range(1, 101)), 95) == 95 and M.percentile([7], 50) == 7
    assert M.percentile([1, 2, 3, 4], 50) == 2
    row = {"run_id": "DEV-local", "batch_ts": BASE, "batch_id": 1, "input_rows": 5000, "input_rows_per_sec": 5000.0,
           "processed_rows_per_sec": 6000.0, "batch_duration_ms": 800, "latency_p50_ms": 300.0, "latency_p95_ms": 450.0,
           "latency_max_ms": 600.0, "windows_written": 40, "anomalies_written": 3, "kafka_partitions": 8, "executors": 2}
    assert M.validate_metrics_row(row) == []
    assert M.validate_metrics_row(dict(row, latency_p95_ms=700.0))
    assert M.validate_metrics_row(dict(row, windows_written=0))
    assert M.validate_metrics_row(dict(row, windows_written=0, anomalies_written=0, latency_p50_ms=None,
                                       latency_p95_ms=None, latency_max_ms=None)) == []
    assert M.validate_run_row({"bucket": "all", "started_at": BASE, "run_id": "DEV-local", "config_json": "{}"}) == []
    assert M.validate_run_row({"bucket": "x", "started_at": BASE, "run_id": "DEV-local", "config_json": "{}"})
