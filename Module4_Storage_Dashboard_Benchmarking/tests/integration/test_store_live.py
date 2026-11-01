"""M4-T031: live tests against Cassandra (`make integration-test`, marker `docker`).

They use a throwaway keyspace (`ids_m4_test`) so the shared `ids` keyspace is never touched.
AC-01, AC-03, AC-04, AC-07, AC-10, AC-11, AC-12.
"""
import json
import os
import subprocess
import sys
import time

import pytest

from ids_contracts import store as S
from ids_contracts.config import load_runtime_config
from ids_monitor import db
from ids_monitor import schema as SC
from ids_monitor.store import Store, current_ms
from ids_monitor.synthetic import generate_batch, generate_run
from ids_monitor.view import drift_summary, top_flagged

pytestmark = pytest.mark.docker
KS = "ids_m4_test"
MIN = 60_000


@pytest.fixture(scope="module")
def session():
    cfg = load_runtime_config(overrides={"CASSANDRA_KEYSPACE": KS})
    try:
        cluster, s = db.connect(cfg)
    except db.StoreUnavailable as exc:
        pytest.skip(str(exc))
    s.execute(f"DROP KEYSPACE IF EXISTS {KS}")
    yield s
    s.execute(f"DROP KEYSPACE IF EXISTS {KS}")
    db.close(cluster)


def cli(module, *args, env_extra=None):
    env = dict(os.environ, CASSANDRA_KEYSPACE=KS, **(env_extra or {}))
    p = subprocess.run([sys.executable, "-m", module, *args], capture_output=True, text=True, env=env, timeout=120)
    lines = p.stdout.strip().splitlines()
    return p.returncode, (json.loads(lines[-1]) if lines else None), p.stderr


def test_ac01_apply_twice_then_check_clean(session):
    code1, s1, err1 = cli("ids_monitor.schema", "apply")
    code2, s2, _ = cli("ids_monitor.schema", "apply")
    code3, s3, _ = cli("ids_monitor.schema", "check")
    assert (code1, code2, code3) == (0, 0, 0), err1
    assert s1["status"] == "ok" and s1["drift"] == [] and s3["drift"] == []
    assert set(s1["created"]) == {"window_scores", "pipeline_metrics", "runs"} and s2["created"] == []


def test_ac03_old_key_refused_then_recreated(session):
    old = SC.ddl_text(KS).replace("bucket         int", "hour           int").replace("(date_bucket, bucket)",
                                                                                  "(date_bucket, hour)")
    session.execute(f"DROP TABLE IF EXISTS {KS}.window_scores")
    session.execute([s for s in SC.statements(old) if f"{KS}.window_scores" in s][0])
    code, _, err = cli("ids_monitor.schema", "apply")
    assert code == 1 and "--recreate" in err
    code, summary, err = cli("ids_monitor.schema", "apply", "--recreate")
    assert code == 0, err
    assert summary["recreated"] == ["window_scores"] and summary["drift"] == []
    assert SC.live_schema(session, KS)["window_scores"].partition == ("date_bucket", "bucket")


def test_ac04_ac07_roundtrip(session):
    SC.apply_schema(session, KS)
    st = Store(session, KS)
    end = (current_ms() // MIN) * MIN - 2 * MIN
    a = generate_run(end, seed=1, n_ips=20, n_windows=40, anomaly_share=0.2, run_id="DEV-live-a")   # 400 s: 2–3 buckets
    b = generate_run(end, seed=2, n_ips=5, n_windows=10, anomaly_share=0.0, run_id="DEV-live-b")
    for w in b.windows:                      # own IPs: the key is (window, src_ip), so shared IPs would upsert over run a
        w["src_ip"] = w["src_ip"].replace("10.0.", "10.9.", 1)
    for r in (a, b):
        st.write_run(r.run)
        st.write_windows(r.windows)
        st.write_metrics(r.metrics)
    start = a.windows[0]["window_end"]
    res = st.read_windows(start, end, run_id="DEV-live-a")
    assert res.invalid == 0 and res.partitions == len(S.partition_keys(start, end)) >= 2
    key = lambda r: (r["window_end"], r["src_ip"])
    assert sorted(res.rows, key=key) == sorted(a.windows, key=key)               # exact round trip, epoch ms
    assert len(st.read_windows(start, end).rows) == len(a.windows) + len(b.windows)
    m = st.latest_metrics("DEV-live-a", limit=5)
    assert [x["batch_ts"] for x in m] == sorted((x["batch_ts"] for x in a.metrics), reverse=True)[:5]
    assert {r["run_id"] for r in st.latest_runs(10)} >= {"DEV-live-a", "DEV-live-b"}
    st.write_windows(a.windows[:20])                                               # upsert: no duplicates
    assert len(st.read_windows(start, end, run_id="DEV-live-a").rows) == len(a.windows)


def test_ac10_follow_mode_writes_new_windows(session):
    SC.apply_schema(session, KS)
    t0 = current_ms()
    code, summary, err = cli("ids_monitor.synthetic", "--n-ips", "3", "--windows", "1", "--follow", "21",
                             "--run-id", "DEV-live-follow")
    assert code == 0, err
    assert summary["last_window_end"] > summary["first_window_end"] and summary["windows"] >= 3 * 3
    rows = Store(session, KS).read_windows(t0 - 20_000, current_ms(), run_id="DEV-live-follow").rows
    ends = sorted({r["window_end"] for r in rows})
    assert len(ends) >= 3 and all(e % S.SLIDE_MS == 0 for e in ends)


def test_ac11_unreachable_cassandra_exits_1_quickly():
    t = time.monotonic()
    code, _, err = cli("ids_monitor.schema", "check", env_extra={"CASSANDRA_PORT": "9"})
    assert code == 1 and "cannot reach Cassandra" in err and time.monotonic() - t < 15


def test_ac12_read_last_300s_at_full_rate(session, record_property):
    """≈ 2.5k IPs × 30 window_ends ≈ 75k rows in the last 300 s; read ≤ 3 s (NFR-001)."""
    SC.apply_schema(session, KS)
    st = Store(session, KS)
    from cassandra.concurrent import execute_concurrent_with_args
    end = (current_ms() // S.SLIDE_MS) * S.SLIDE_MS
    names = [c for c, _ in S.COLUMNS]
    ins = session.prepare(f"INSERT INTO {KS}.window_scores ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})")
    for k in range(30):
        rows, _ = generate_batch(end - k * S.SLIDE_MS, 7, 2_500, 0.1, "DEV-live-perf")
        execute_concurrent_with_args(session, ins, [tuple(r[c] for c in names) for r in rows], concurrency=200)
    t = time.perf_counter()
    res = st.read_recent(300, now_ms=end, run_id="DEV-live-perf")
    read_s = time.perf_counter() - t
    t = time.perf_counter()
    d, top = drift_summary(res.rows), top_flagged(res.rows)
    view_s = time.perf_counter() - t
    record_property("read_s", round(read_s, 3))
    print(f"\nAC-12: read {len(res.rows)} rows from {res.partitions} partitions in {read_s:.3f} s; "
          f"drift+top in {view_s:.3f} s; rate={d.rate:.3f}")
    assert len(res.rows) >= 30 * 2_500 and read_s <= 3.0 and view_s <= 0.5 and top
