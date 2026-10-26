"""M4-T040 — dashboard view model (M4-F02-AC-01, AC-02)."""
from conftest import BASE
from ids_contracts import store as S
from ids_monitor import synthetic as syn
from ids_monitor.view import DemoReader, build_view

NOW = BASE + 7_200_000 + 2_500


def test_view_from_synthetic_data():
    reader = DemoReader(share=0.2, n_ips=20, seed=5, clock=lambda: NOW)
    v = build_view(reader, NOW, seconds=300)
    assert v["run_id"] == "DEMO-synthetic" and v["has_data"]
    metrics = reader.metrics("DEMO-synthetic", limit=60)
    from ids_monitor.view import _median
    assert v["kpis"]["throughput"] == _median([m["input_rows_per_sec"] for m in metrics[:10]])     # last 10 with data
    assert v["kpis"]["latency_p95_ms"] == _median([m["latency_p95_ms"] for m in metrics[:10]])
    assert v["kpis"]["windows"] == 30 * 20 and abs(v["kpis"]["anomaly_rate"] - 0.2) < 1e-9
    assert v["drift"]["alert"] is True and v["drift"] == {**v["drift"], "rate": v["kpis"]["anomaly_rate"]}
    assert len(v["rate_series"]) == 30 and all(abs(p["rate"] - 0.2) < 1e-9 for p in v["rate_series"])
    assert [p["window_end"] for p in v["rate_series"]] == sorted(p["window_end"] for p in v["rate_series"])
    ts = [p["batch_ts"] for p in v["latency"]]
    assert ts == sorted(ts) and all(p["p50"] <= p["p95"] for p in v["latency"])
    assert len(v["throughput"]) == len(v["latency"]) == 60
    assert 0 < len(v["top"]) <= 10


def test_view_below_threshold_has_no_alert():
    v = build_view(DemoReader(share=0.1, n_ips=20, seed=5, clock=lambda: NOW), NOW)
    assert v["drift"]["alert"] is False and abs(v["kpis"]["anomaly_rate"] - 0.1) < 1e-9


class EmptyReader:
    def runs(self, limit=20):
        return []

    def recent_windows(self, now_ms, seconds=300, run_id=None):
        return []

    def metrics(self, run_id, limit=60):
        return []


def test_empty_store_renders_waiting_state():
    v = build_view(EmptyReader(), NOW)
    assert v["run_id"] is None and not v["has_data"]
    assert v["kpis"] == {"throughput": None, "latency_p95_ms": None, "anomaly_rate": None, "windows": 0, "anomalous": 0}
    assert v["throughput"] == v["latency"] == v["rate_series"] == v["top"] == []


def test_explicit_run_and_stale_rows():
    class OneRun(EmptyReader):
        def runs(self, limit=20):
            return [{"run_id": "R1", "started_at": BASE}]

        def metrics(self, run_id, limit=60):
            assert run_id == "R2"
            return []

    v = build_view(OneRun(), NOW, run_id="R2")
    assert v["run_id"] == "R2" and v["kpis"]["anomaly_rate"] is None and v["runs"] == ["R1"]


def test_demo_rows_are_contract_valid():
    rows = DemoReader(share=0.2, clock=lambda: NOW).recent_windows(NOW, 120)
    assert rows and all(S.validate_row(r) == [] for r in rows)
    assert syn.THRESHOLD == 0.55


# ---- M4-FR-018 finished runs (AC-06) ---------------------------------------------------------------
def test_finished_run_is_anchored_at_its_end():
    ended = NOW - 3_600_000                                   # run ended an hour before "now"
    reader = DemoReader(share=0.2, n_ips=20, seed=5, clock=lambda: ended)
    auto = build_view(reader, NOW, seconds=300)
    assert auto["has_data"] and auto["live"] is False
    assert auto["as_of_ms"] == reader.metrics("DEMO-synthetic", limit=1)[0]["batch_ts"]
    assert auto["kpis"]["windows"] == 30 * 20
    now_view = build_view(reader, NOW, seconds=300, anchor="now")
    assert now_view["kpis"]["windows"] == 0 and now_view["as_of_ms"] == NOW


def test_live_run_is_anchored_at_now():
    v = build_view(DemoReader(share=0.2, n_ips=20, seed=5, clock=lambda: NOW), NOW + 2_000)
    assert v["live"] is True and v["as_of_ms"] == NOW + 2_000


def test_kpis_skip_idle_trailing_batches():
    class Idle(EmptyReader):
        def runs(self, limit=20):
            return [{"run_id": "R", "started_at": BASE}]

        def metrics(self, run_id, limit=60):
            busy = {"batch_ts": NOW - 5_000, "input_rows": 2000, "input_rows_per_sec": 2000.0, "latency_p50_ms": 400.0,
                    "latency_p95_ms": 900.0}
            idle = {"batch_ts": NOW - 1_000, "input_rows": 0, "input_rows_per_sec": 0.0, "latency_p50_ms": None,
                    "latency_p95_ms": None}
            return [idle, busy]                       # newest first, as C-05 reads return

    v = build_view(Idle(), NOW)
    assert v["kpis"]["throughput"] == 2000.0 and v["kpis"]["latency_p95_ms"] == 900.0
