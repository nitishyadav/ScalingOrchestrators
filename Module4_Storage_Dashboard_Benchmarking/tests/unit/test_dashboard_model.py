"""M4-T110: dashboard view model (AC-01, 02, 03, 04, 05, 10)."""
from ids_contracts import store as S
from ids_monitor import dashboard_model as DM

from conftest import BASE, MIN, window

NOW = BASE + 60 * MIN


def batch(ts, in_rate=5000.0, proc=6000.0, rows=40, anom=2, p50=300.0, p95=450.0, mx=600.0, input_rows=5000, run="DEV-test"):
    lat = (None, None, None) if rows == 0 else (p50, p95, mx)
    return {"run_id": run, "batch_ts": ts, "batch_id": 1, "input_rows": input_rows, "input_rows_per_sec": in_rate,
            "processed_rows_per_sec": proc, "batch_duration_ms": 800, "latency_p50_ms": lat[0],
            "latency_p95_ms": lat[1], "latency_max_ms": lat[2], "windows_written": rows,
            "anomalies_written": min(anom, rows), "kafka_partitions": 8, "executors": 2}


def view(windows=(), metrics=(), anchor=NOW, span=300, mode="now"):
    return DM.build_view(list(windows), list(metrics), anchor_ms=anchor, anchor_mode=mode, span_s=span, run_id="DEV-test")


# ---- AC-01 headline numbers ----
def test_kpis_are_medians_of_last_10_qualifying_batches():
    ms = [batch(NOW - i * 1000, in_rate=1000.0 * (i + 1), p95=100.0 * (i + 1)) for i in range(15)]
    ms += [batch(NOW - 500, in_rate=0.0, input_rows=0, rows=0)]          # idle batch: excluded from both
    k = view(metrics=ms).kpis
    assert k.throughput_evs == 5500.0                                      # median of 1000..10000
    assert k.latency_p95_ms == 550.0                                       # median of 100..1000


def test_kpis_missing_show_none():
    k = view().kpis
    assert (k.throughput_evs, k.latency_p95_ms, k.anomaly_rate, k.windows) == (None, None, None, 0)
    assert DM.fmt(None) == "—"


def test_batches_outside_span_are_ignored():
    k = view(metrics=[batch(NOW - 400_000, in_rate=9999.0), batch(NOW - 1000, in_rate=10.0)]).kpis
    assert k.throughput_evs == 10.0


# ---- AC-02 drift banner ----
def _windows(n, anomalous, end=NOW):
    return [window(end=end - (i % 30) * 10_000, ip=f"10.1.{i // 250}.{i % 250}", anomalous=i < anomalous)
            for i in range(n)]


def test_banner_alert_above_15_percent():
    v = view(windows=_windows(100, 16))
    assert v.drift.alert and v.banner.level == "critical" and v.banner.icon
    assert v.banner.text == "Drift alert: anomaly rate 16.0 % > 15 % — retraining recommended"


def test_banner_no_drift_at_15_percent_and_when_empty():
    for ws in (_windows(100, 15), []):
        v = view(windows=ws)
        assert not v.drift.alert and v.banner.level == "ok" and v.banner.text.startswith("No drift") and v.banner.icon


def test_drift_uses_last_300s_even_with_longer_span():
    old = [window(end=NOW - 600_000, ip=f"10.2.0.{i}", anomalous=True) for i in range(50)]   # outside 300 s
    v = view(windows=old + _windows(100, 5), span=900)
    assert v.kpis.anomaly_rate == 55 / 150 and not v.drift.alert and v.drift.total == 100


# ---- AC-03 chart data ----
def test_series_rows():
    ws = [window(end=NOW - 10_000, ip="a", anomalous=True), window(end=NOW - 10_000, ip="b"),
          window(end=NOW, ip="a")]
    ms = [batch(NOW - 2000), batch(NOW - 1000, rows=0)]
    v = view(windows=ws, metrics=ms)
    assert v.anomaly_rate == [
        {"window_end": NOW - 10_000, "rate": 0.5, "anomalous": 1, "total": 2},
        {"window_end": NOW, "rate": 0.0, "anomalous": 0, "total": 1}]
    assert [(r["batch_ts"], r["series"]) for r in v.throughput] == [
        (NOW - 2000, "input"), (NOW - 2000, "processed"), (NOW - 1000, "input"), (NOW - 1000, "processed")]
    assert [(r["batch_ts"], r["series"], r["ms"]) for r in v.latency] == [
        (NOW - 2000, "p50", 300.0), (NOW - 2000, "p95", 450.0)]              # batch without rows has no latency


# ---- AC-04 top IPs ----
def test_top_is_capped_at_10_in_order():
    ws = [window(end=NOW - k * 10_000, ip=f"10.3.0.{i}", anomalous=True, score=0.5 + i / 100)
          for i in range(12) for k in range(i % 3 + 1)]
    top = view(windows=ws).top
    assert len(top) == 10 and top[0].windows == 3 and top == sorted(top, key=lambda t: (-t.windows, -t.max_score))


# ---- AC-05 anchor ----
def test_anchor_live_run_is_now():
    assert DM.choose_anchor([batch(NOW - 5_000)], NOW) == (NOW, "now")


def test_anchor_finished_run_is_last_batch():
    assert DM.choose_anchor([batch(NOW - 600_000), batch(NOW - 700_000)], NOW) == (NOW - 600_000, "run_end")
    assert DM.choose_anchor([batch(NOW - 600_000)], NOW, force_now=True) == (NOW, "now")
    assert DM.choose_anchor([], NOW) == (NOW, "now")


def test_caption_names_the_anchor():
    assert "as of run end" in view(mode="run_end").caption
    assert "live" in view().caption


# ---- AC-10 eval-only columns never read ----
class _Guard(dict):
    def __getitem__(self, key):
        assert key not in S.EVAL_ONLY, key
        return super().__getitem__(key)

    def get(self, key, default=None):
        assert key not in S.EVAL_ONLY, key
        return super().get(key, default)


def test_eval_only_never_read():
    view(windows=[_Guard(w) for w in _windows(40, 10)], metrics=[batch(NOW)])
