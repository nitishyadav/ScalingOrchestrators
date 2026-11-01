"""M4-T131: dashboard against live Cassandra (AC-07, AC-08, AC-09). Keyspace `ids_m4_dash` (throwaway)."""
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ids_contracts import store as S
from ids_contracts.config import load_runtime_config
from ids_monitor import charts, dashboard, db
from ids_monitor import schema as SC
from ids_monitor.store import Store, current_ms
from ids_monitor.synthetic import generate_batch, generate_run

pytestmark = pytest.mark.docker
KS = "ids_m4_dash"
APP = str(Path(dashboard.__file__).with_name("dashboard_app.py"))


@pytest.fixture(scope="module")
def store():
    cfg = load_runtime_config(overrides={"CASSANDRA_KEYSPACE": KS})
    try:
        cluster, session = db.connect(cfg)
    except db.StoreUnavailable as exc:
        pytest.skip(str(exc))
    session.execute(f"DROP KEYSPACE IF EXISTS {KS}")
    SC.apply_schema(session, KS)
    yield Store(session, KS)
    session.execute(f"DROP KEYSPACE IF EXISTS {KS}")
    db.close(cluster)


def _write(store, run):
    store.write_run(run.run)
    store.write_windows(run.windows)
    store.write_metrics(run.metrics)


def test_ac07_page_renders_on_synthetic_data(store, monkeypatch):
    _write(store, generate_run(current_ms(), seed=11, n_ips=40, n_windows=20, anomaly_share=0.25, run_id="DEV-dash-a"))
    # 20 windows = 200 s of a 300 s span: AppTest start-up time cannot push the oldest one out (was flaky at 30)
    monkeypatch.setattr(dashboard, "open_store", lambda: store)
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    page = " | ".join(m.value for m in at.markdown)
    assert not at.error and page.count('role="alert"') == 1 and "Drift alert" in page  # 25 % > 15 %
    assert '<div class="t-value ids-num">800</div>' in page                            # windows scored
    assert '<div class="t-value ids-num">25.0<span class="t-unit">%</span>' in page   # anomaly rate
    assert page.count('<div class="t-value ids-num">—') == 0                           # every tile has a value
    assert len(at.get("arrow_vega_lite_chart")) == 3 and len(at.dataframe) >= 4       # 3 charts, top + data tables
    assert "DEV-dash-a" in page and "LIVE" in page


def test_ac08_write_to_visible_within_5s(store):
    run_id = "DEV-dash-f4"
    _write(store, generate_run(current_ms() - 60_000, seed=12, n_ips=20, n_windows=5, anomaly_share=0.0, run_id=run_id))
    before = dashboard.load_view(store, run_id, 300, False)
    assert not before.drift.alert
    end = current_ms() // S.SLIDE_MS * S.SLIDE_MS
    rows, m = generate_batch(end, 13, 200, 1.0, run_id)                             # a burst of anomalous windows
    t_write = time.perf_counter()
    store.write_windows(rows)
    store.write_metrics([m])
    t0 = time.perf_counter()
    after = dashboard.load_view(store, run_id, 300, False)
    cycle = time.perf_counter() - t0
    worst = dashboard.REFRESH_S + cycle + (t0 - t_write)                              # wait for next tick + one cycle
    print(f"\nAC-08: refresh {dashboard.REFRESH_S} s + cycle {cycle:.3f} s → worst case {worst:.2f} s")
    assert after.drift.alert and after.top[0].windows >= 1 and worst <= 5.0


def test_ac09_cycle_at_full_rate(store, monkeypatch):
    from cassandra.concurrent import execute_concurrent_with_args
    run_id = "DEV-dash-perf"
    end = current_ms() // S.SLIDE_MS * S.SLIDE_MS
    names = [c for c, _ in S.COLUMNS]
    ins = store._session.prepare(f"INSERT INTO {KS}.window_scores ({', '.join(names)}) "
                                 f"VALUES ({', '.join('?' * len(names))})")
    metrics = []
    for k in range(30):
        rows, m = generate_batch(end - k * S.SLIDE_MS, 21, 2_500, 0.1, run_id, batch_id=k)
        execute_concurrent_with_args(store._session, ins, [tuple(r[c] for c in names) for r in rows], concurrency=200)
        metrics.append(m)
    store.write_metrics(metrics)
    store.write_run({"bucket": "all", "started_at": end - 400_000, "run_id": run_id, "config_json": "{}"})
    monkeypatch.setattr(dashboard, "current_ms", lambda: end)   # writing 75k rows takes ~10 s; pin 'now' to the data
    t = time.perf_counter()
    v = dashboard.load_view(store, run_id, 300, True)
    for fn, rows in ((charts.throughput_chart, v.throughput), (charts.latency_chart, v.latency),
                     (charts.anomaly_rate_chart, v.anomaly_rate)):
        fn(rows).to_dict()
    cycle = time.perf_counter() - t
    print(f"\nAC-09: {v.kpis.windows:,} windows → view + 3 chart specs in {cycle:.3f} s")
    assert v.kpis.windows == 75_000 and cycle <= 2.0
