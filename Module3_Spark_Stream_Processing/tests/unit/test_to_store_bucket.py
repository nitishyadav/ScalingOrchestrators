"""C-04 1.0.0-rc.1: the sink's `bucket` column equals ids_contracts.store.partition_key (host PySpark, local mode)."""
import datetime as dt

import pytest

pyspark = pytest.importorskip("pyspark")

from ids_contracts import store as S                      # noqa: E402
from ids_stream import app, spec                          # noqa: E402


@pytest.fixture(scope="module")
def spark():
    s = app.build_spark("test-to-store-bucket")
    yield s
    s.stop()


def utc_ms(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_bucket_matches_contract_partition_key(spark):
    ends = [utc_ms(2026, 1, 1, 0, 0, 0), utc_ms(2026, 1, 1, 0, 4, 59), utc_ms(2026, 1, 1, 0, 5, 0), utc_ms(2026, 1, 1, 13, 37, 10),
            utc_ms(2026, 1, 1, 23, 59, 59), utc_ms(2026, 1, 2, 0, 0, 0)]
    df = spark.createDataFrame([(e,) for e in ends], "end_ms long")
    scored = df.selectExpr(
        "timestamp_millis(end_ms) as window_end_ts", "timestamp_millis(end_ms - 30000) as window_start_ts", "'1.2.3.4' as src_ip",
        "1L as total_bytes", "1 as unique_ports", "0.0 as syn_ack_ratio", "0.0 as packet_rate", "1 as event_count",
        "0.0 as anomaly_score", "false as ml_flag", "false as rule_flag", "'' as rule_ids", "false as is_anomaly",
        "end_ms as max_event_ts", "false as label_attack", "'BENIGN' as label_type")
    rows = app.to_store(scored, "DEV-t", "0.0.0", 0).orderBy("window_end").collect()
    assert [c for c in rows[0].asDict()] == list(spec.STORE_COLUMNS)
    assert [(r["date_bucket"], r["bucket"]) for r in rows] == [S.partition_key(e) for e in sorted(ends)]
    assert max(r["bucket"] for r in rows) == S.BUCKETS_PER_DAY - 1
