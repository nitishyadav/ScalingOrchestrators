"""Unit-test fakes (M4-T002): a recording Cassandra session and C-04 row builders."""
import datetime as dt

import pytest

from ids_contracts import store as S

BASE = 1_767_225_600_000              # 2026-01-01T00:00:00Z
MIN = 60_000


class FakePrepared:
    def __init__(self, query):
        self.query_string = query
        self.consistency_level = None


class FakeSession:
    """Records every statement. `responder(query, params)` returns the rows for a query (default: none)."""

    def __init__(self, responder=None):
        self.calls = []
        self.prepared = []
        self.responder = responder or (lambda query, params: [])

    def prepare(self, query):
        p = FakePrepared(query)
        self.prepared.append(p)
        return p

    def execute(self, statement, params=None, timeout=None):
        query = getattr(statement, "query_string", statement)
        self.calls.append((query, params, getattr(statement, "consistency_level", None)))
        return list(self.responder(query, params))

    def queries(self, contains=""):
        return [(q, p) for q, p, _ in self.calls if contains in q]


@pytest.fixture
def session():
    return FakeSession()


def window(end=BASE + 30_000, ip="10.0.0.1", anomalous=False, score=0.1, rule_ids="", run_id="DEV-test", **over):
    db, b = S.partition_key(end)
    rule_flag = bool(rule_ids)
    row = {"date_bucket": db, "bucket": b, "window_end": end, "src_ip": ip, "window_start": end - 30_000,
           "total_bytes": 100, "unique_ports": 2, "syn_ack_ratio": 0.5, "packet_rate": 0.1, "event_count": 3,
           "anomaly_score": score, "ml_flag": anomalous and not rule_flag, "rule_flag": rule_flag, "rule_ids": rule_ids,
           "is_anomaly": anomalous or rule_flag, "max_event_ts": end - 1_000, "detected_at": end - 400,
           "bundle_version": "0.0.0-dummy", "run_id": run_id, "label_attack": False, "label_type": "BENIGN"}
    row.update(over)
    return row


def as_driver_row(row):
    """What cassandra-driver returns with dict_factory: timestamps as naive UTC datetimes."""
    out = dict(row)
    for c, t in S.COLUMNS:
        if t == "timestamp" and out.get(c) is not None:
            out[c] = dt.datetime.fromtimestamp(out[c] / 1000, tz=dt.timezone.utc).replace(tzinfo=None)
    return out
