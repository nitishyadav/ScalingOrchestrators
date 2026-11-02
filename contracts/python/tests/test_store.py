"""C-04 Anomaly Store contract tests (owner M4). Key design per M4-ADR-001."""
import re

import pytest

from ids_contracts import SCHEMAS_DIR
from ids_contracts import store as S

BASE = 1_767_225_600_000              # 2026-01-01T00:00:00Z
MIN = 60_000


def _ddl():
    text = re.sub(r"--[^\n]*", "", (SCHEMAS_DIR / "ids_schema.cql").read_text())
    body, opts = re.search(r"CREATE TABLE IF NOT EXISTS ids\.window_scores \((.*?)\)\s*(WITH[^;]*);", text, re.S).groups()
    pk = re.search(r"PRIMARY KEY \(\((.*?)\),\s*(.*?)\)\s*$", body.strip(), re.S)
    return {"columns": tuple(re.findall(r"^\s*(\w+)\s+(\w+),\s*$", body, re.M)),
            "partition": tuple(c.strip() for c in pk.group(1).split(",")),
            "clustering": tuple(c.strip() for c in pk.group(2).split(",")), "options": opts, "text": text}


def _row(end=BASE + 30_000, **over):
    db, b = S.partition_key(end)
    row = {"date_bucket": db, "bucket": b, "window_end": end, "src_ip": "10.0.0.1", "window_start": end - 30_000,
           "total_bytes": 10, "unique_ports": 1, "syn_ack_ratio": 0.5, "packet_rate": 0.1, "event_count": 3,
           "anomaly_score": 0.4, "ml_flag": False, "rule_flag": True, "rule_ids": "R-SYN-FLOOD", "is_anomaly": True,
           "max_event_ts": end - 1_000, "detected_at": end - 600, "bundle_version": "0.0.0-dummy",
           "run_id": "DEV-local", "label_attack": False, "label_type": "BENIGN"}
    row.update(over)
    return row


# ---- DDL <-> python constants ------------------------------------------------------------------
def test_constants_match_ddl():
    t = _ddl()
    assert t["columns"] == S.COLUMNS
    assert t["partition"] == S.PARTITION_KEY == ("date_bucket", "bucket")
    assert t["clustering"] == tuple(c for c, _ in S.CLUSTERING)
    assert "window_end DESC, src_ip ASC" in t["options"]
    assert f"default_time_to_live = {S.TTL_S}" in t["options"]
    assert "'replication_factor': 1" in t["text"] and "SimpleStrategy" in t["text"]


def test_key_and_eval_only_columns_exist():
    names = {c for c, _ in S.COLUMNS}
    assert set(S.KEY_COLUMNS) <= names and set(S.EVAL_ONLY) <= names and set(S.NULLABLE) == set(S.EVAL_ONLY)
    assert "hour" not in names                            # 0.1.0-replica key column is gone


# ---- key derivation (M4-ADR-001) ---------------------------------------------------------------
@pytest.mark.parametrize("offset_ms, expected", [
    (0, ("2026-01-01", 0)),                               # midnight opens bucket 0
    (5 * MIN - 10_000, ("2026-01-01", 0)),                # 00:04:50, last window_end in bucket 0
    (5 * MIN, ("2026-01-01", 1)),                         # boundary instant opens the next bucket
    (12 * 60 * MIN + 5 * MIN, ("2026-01-01", 145)),       # 12:05:00
    (24 * 60 * MIN - 10_000, ("2026-01-01", 287)),        # 23:59:50, last bucket of the day
    (24 * 60 * MIN, ("2026-01-02", 0)),                   # next UTC day
])
def test_partition_key(offset_ms, expected):
    assert S.partition_key(BASE + offset_ms) == expected


def test_every_bucket_holds_30_window_ends():
    ends = range(BASE, BASE + 24 * 60 * MIN, S.SLIDE_MS)
    counts = {}
    for e in ends:
        counts[S.partition_key(e)] = counts.get(S.partition_key(e), 0) + 1
    assert len(counts) == S.BUCKETS_PER_DAY == 288 and set(counts.values()) == {30}


def test_partition_keys_range():
    now = BASE + 12 * 60 * MIN + 7 * MIN                  # 12:07:00
    keys = S.partition_keys(now - S.DRIFT_WINDOW_S * 1000, now)
    assert keys == [("2026-01-01", 145), ("2026-01-01", 144)]   # newest first; drift read touches <= 2 partitions
    assert S.partition_keys(BASE, BASE) == [("2026-01-01", 0)]
    assert S.partition_keys(BASE + 1, BASE) == []
    across_midnight = S.partition_keys(BASE - 2 * MIN, BASE + 1 * MIN)
    assert across_midnight == [("2026-01-01", 0), ("2025-12-31", 287)]
    run = S.partition_keys(BASE + 2 * MIN, BASE + 12 * MIN)    # a 10-minute run touches <= 3 partitions
    assert len(run) == 3


@pytest.mark.parametrize("width_ms", [0, 10_000, 299_999, 300_000, 600_000, 3_600_000])
def test_partition_keys_cover_every_window_end(width_ms):
    start = BASE + 123 * S.SLIDE_MS
    keys = set(S.partition_keys(start, start + width_ms))
    ends = range(start, start + width_ms + 1, S.SLIDE_MS)
    assert {S.partition_key(e) for e in ends} == keys


# ---- row validation ----------------------------------------------------------------------------
def test_valid_row():
    assert S.validate_row(_row()) == []
    assert S.validate_row(_row(rule_flag=False, rule_ids="", ml_flag=True)) == []
    assert S.validate_row(_row(label_attack=None, label_type=None)) == []       # eval-only may be null


@pytest.mark.parametrize("bad", [
    {"bucket": 5},                                         # wrong partition
    {"date_bucket": "2026-01-02"},
    {"window_start": BASE + 10_000},                       # 20 s, not 30 s long
    {"window_start": BASE + 5_000, "window_end": BASE + 35_000},   # not slide-aligned (key recomputed below)
    {"is_anomaly": False},
    {"rule_ids": ""},                                      # rule_flag true with no ids
    {"src_ip": None},
    {"anomaly_score": None},                               # non-eval columns are required
    {"total_bytes": 1.5},
    {"ml_flag": 0},
])
def test_invalid_rows(bad):
    row = _row(**bad)
    if "window_end" in bad:
        row["date_bucket"], row["bucket"] = S.partition_key(row["window_end"])
    assert S.validate_row(row)


def test_missing_column():
    row = _row()
    del row["run_id"]
    assert S.validate_row(row) == ["missing 'run_id'"]


def test_drift_alert():
    assert S.drift_alert(16, 100) and not S.drift_alert(15, 100) and not S.drift_alert(0, 0)
