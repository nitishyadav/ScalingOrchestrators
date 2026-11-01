"""M4-T112: headless page tests with a fake store (AC-02, AC-04, AC-06)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ids_monitor import dashboard, db
from ids_monitor.store import ReadResult

from conftest import window

APP = str(Path(dashboard.__file__).with_name("dashboard_app.py"))


class FakeStore:
    def __init__(self, windows=(), metrics=(), runs=()):
        self.windows, self.metrics, self.runs = list(windows), list(metrics), list(runs)

    def latest_runs(self, limit=20):
        return self.runs[:limit]

    def latest_metrics(self, run_id, limit=60):
        return [m for m in self.metrics if m["run_id"] == run_id][:limit]

    def read_windows(self, start_ms, end_ms, run_id=None):
        rows = [w for w in self.windows if start_ms <= w["window_end"] <= end_ms and (run_id is None or w["run_id"] == run_id)]
        return ReadResult(rows, 0, 2)


def run_app(monkeypatch, store_or_exc):
    def opener():
        if isinstance(store_or_exc, Exception):
            raise store_or_exc
        return store_or_exc
    monkeypatch.setattr(dashboard, "open_store", opener)
    at = AppTest.from_file(APP, default_timeout=20)
    at.run()
    assert not at.exception, at.exception
    return at


def texts(at):
    out = []
    for kind in ("error", "success", "info", "warning", "caption", "markdown", "title", "subheader"):
        out += [e.value for e in getattr(at, kind)]
    return " | ".join(str(t) for t in out)


def _live(anomalous, total=100, run="DEV-test"):
    from ids_monitor.store import current_ms
    now = current_ms() // 10_000 * 10_000
    ws = [window(end=now - (i % 30) * 10_000, ip=f"10.4.{i // 250}.{i % 250}", anomalous=i < anomalous, run_id=run)
          for i in range(total)]
    ms = [{"run_id": run, "batch_ts": now - i * 1000, "batch_id": i, "input_rows": 5000, "input_rows_per_sec": 5000.0,
           "processed_rows_per_sec": 6000.0, "batch_duration_ms": 800, "latency_p50_ms": 300.0,
           "latency_p95_ms": 450.0, "latency_max_ms": 600.0, "windows_written": 40, "anomalies_written": 2,
           "kafka_partitions": 8, "executors": 2} for i in range(20)]
    runs = [{"bucket": "all", "started_at": now - 600_000, "run_id": run, "config_json": "{}"}]
    return FakeStore(ws, ms, runs)


def test_alert_banner_and_top_table(monkeypatch):
    at = run_app(monkeypatch, _live(anomalous=30))
    assert len(at.error) == 1 and "Drift alert: anomaly rate 30.0 % > 15 %" in at.error[0].value
    assert at.error[0].icon
    assert [m.label for m in at.metric][:3] == ["Input throughput (ev/s)", "p95 latency (ms, target < 500)",
                                                "Anomaly rate (span)"]
    top = [d for d in at.dataframe if "src_ip" in d.value.columns]
    assert top and len(top[0].value) == 10


def test_no_drift_banner(monkeypatch):
    at = run_app(monkeypatch, _live(anomalous=10))
    assert not at.error and any("No drift" in s.value for s in at.success)


def test_empty_store_waits_for_data(monkeypatch):
    at = run_app(monkeypatch, FakeStore())
    assert "Waiting for data" in texts(at) and not at.error


def test_store_down_single_error(monkeypatch):
    at = run_app(monkeypatch, db.StoreUnavailable("cannot reach Cassandra at localhost:9042"))
    assert len(at.error) == 1 and "localhost:9042" in at.error[0].value
