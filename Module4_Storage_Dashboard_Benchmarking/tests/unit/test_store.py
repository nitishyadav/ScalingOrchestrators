"""M4-T011: Store reads and writes against a fake session (AC-04, AC-07, AC-08)."""
import datetime as dt

import pytest

from ids_contracts import store as S
from ids_monitor.store import Store, to_ms

from conftest import BASE, MIN, FakeSession, as_driver_row, window


def store_with(rows):
    """Session that serves `rows` (epoch-ms dicts) per (date_bucket, bucket, start, end) like Cassandra would."""
    def responder(query, params):
        if "window_scores" in query and query.startswith("SELECT"):
            db, b, lo, hi = params
            return [as_driver_row(r) for r in rows
                    if (r["date_bucket"], r["bucket"]) == (db, b) and lo <= r["window_end"] <= hi]
        return []
    s = FakeSession(responder)
    return Store(s, "ids"), s


def test_to_ms_roundtrip():
    assert to_ms(dt.datetime(2026, 1, 1)) == BASE
    assert to_ms(dt.datetime(2026, 1, 1, 0, 0, 0, 123_000)) == BASE + 123
    assert to_ms(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)) == BASE
    assert to_ms(None) is None and to_ms(BASE) == BASE


def test_read_windows_one_query_per_bucket_and_run_filter():
    rows = [window(end=BASE + 4 * MIN + 50_000, run_id="DEV-a"),            # bucket 0
            window(end=BASE + 5 * MIN, run_id="DEV-a"),                      # bucket 1
            window(end=BASE + 5 * MIN, ip="10.0.0.2", run_id="DEV-b"),
            window(end=BASE + 20 * MIN, run_id="DEV-a")]                     # outside span
    st, s = store_with(rows)
    res = st.read_windows(BASE + 4 * MIN, BASE + 6 * MIN, run_id="DEV-a")
    assert sorted(r["window_end"] for r in res.rows) == [BASE + 4 * MIN + 50_000, BASE + 5 * MIN]
    assert all(r["run_id"] == "DEV-a" for r in res.rows) and res.invalid == 0
    selects = s.queries("SELECT")
    assert [p[:2] for _, p in selects] == [("2026-01-01", 1), ("2026-01-01", 0)]
    assert all("ALLOW FILTERING" not in q and "date_bucket = ? AND bucket = ?" in q for q, _ in selects)
    assert all(isinstance(r["window_end"], int) for r in res.rows)
    assert all(S.validate_row(r) == [] for r in res.rows)


def test_read_windows_without_filter_returns_all_runs_newest_first():
    rows = [window(end=BASE + 30_000), window(end=BASE + 40_000, run_id="DEV-b"), window(end=BASE + 50_000)]
    st, _ = store_with(rows)
    got = st.read_windows(BASE, BASE + MIN).rows
    assert [r["window_end"] for r in got] == [BASE + 50_000, BASE + 40_000, BASE + 30_000]


def test_read_windows_empty_span_makes_no_query():
    st, s = store_with([])
    assert st.read_windows(BASE + 1, BASE).rows == [] and s.calls == []


def test_invalid_live_rows_are_skipped_and_counted():
    bad = window(end=BASE + 30_000)
    bad["is_anomaly"] = True                                   # contradicts ml_flag/rule_flag
    st, _ = store_with([bad, window(end=BASE + 40_000)])
    res = st.read_windows(BASE, BASE + MIN)
    assert len(res.rows) == 1 and res.invalid == 1


def test_read_recent_uses_last_n_seconds():
    now = BASE + 12 * MIN
    rows = [window(end=now - 10_000), window(end=now - 300_000), window(end=now - 310_000)]
    st, _ = store_with(rows)
    got = st.read_recent(300, now_ms=now).rows
    assert sorted(r["window_end"] for r in got) == [now - 300_000, now - 10_000]


def test_write_windows_validates_before_sending():
    st, s = store_with([])
    bad = window()
    bad["bucket"] = 99
    with pytest.raises(ValueError, match="date_bucket/bucket"):
        st.write_windows([window(end=BASE + 40_000), bad])
    assert not s.queries("INSERT")                             # nothing sent when any row is invalid


def test_write_windows_upserts_at_local_one():
    from cassandra import ConsistencyLevel
    st, s = store_with([])
    assert st.write_windows([window(), window(ip="10.0.0.2")]) == 2
    inserts = [c for c in s.calls if c[0].startswith("INSERT")]
    assert len(inserts) == 2 and all(cl == ConsistencyLevel.LOCAL_ONE for _, _, cl in inserts)
    q, params, _ = inserts[0]
    assert "ids.window_scores" in q and len(params) == len(S.COLUMNS)


def _metrics(ts, run_id="DEV-test"):
    return {"run_id": run_id, "batch_ts": ts, "batch_id": 1, "input_rows": 5000, "input_rows_per_sec": 5000.0,
            "processed_rows_per_sec": 6000.0, "batch_duration_ms": 800, "latency_p50_ms": 300.0,
            "latency_p95_ms": 450.0, "latency_max_ms": 600.0, "windows_written": 40, "anomalies_written": 3,
            "kafka_partitions": 8, "executors": 2}


def test_metrics_and_runs_reads():
    rows = {"pipeline_metrics": [_metrics(BASE + 2000), _metrics(BASE + 1000)],
            "runs": [{"bucket": "all", "started_at": BASE, "run_id": "DEV-test", "config_json": "{}"}]}

    def responder(query, params):
        for table, rs in rows.items():
            if f"ids.{table}" in query:
                return [{k: (dt.datetime.utcfromtimestamp(v / 1000) if k in ("batch_ts", "started_at") else v)
                         for k, v in r.items()} for r in rs]
        return []
    s = FakeSession(responder)
    st = Store(s, "ids")
    m = st.latest_metrics("DEV-test", limit=2)
    assert [r["batch_ts"] for r in m] == [BASE + 2000, BASE + 1000]
    q, p = s.queries("pipeline_metrics")[0]
    assert "WHERE run_id = ?" in q and "LIMIT ?" in q and p == ("DEV-test", 2)
    runs = st.latest_runs(limit=5)
    assert runs[0]["started_at"] == BASE and s.queries("ids.runs")[0][1] == ("all", 5)


def test_write_metrics_and_run_validate():
    st, s = store_with([])
    assert st.write_metrics([_metrics(BASE)]) == 1
    with pytest.raises(ValueError):
        st.write_metrics([dict(_metrics(BASE), anomalies_written=99)])
    st.write_run({"bucket": "all", "started_at": BASE, "run_id": "DEV-test", "config_json": "{}"})
    with pytest.raises(ValueError):
        st.write_run({"bucket": "x", "started_at": BASE, "run_id": "DEV-test", "config_json": "{}"})
    assert len(s.queries("INSERT")) == 2
