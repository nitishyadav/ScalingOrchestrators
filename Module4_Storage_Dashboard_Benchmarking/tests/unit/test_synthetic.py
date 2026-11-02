"""M4-T013: synthetic generator (AC-09, AC-10 logic)."""
import pytest

from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_monitor.synthetic import generate_run, next_window_ends

from conftest import BASE, MIN


def test_deterministic_for_seed_and_end():
    a = generate_run(end_ms=BASE + 10 * MIN, seed=7, n_ips=20, n_windows=12, anomaly_share=0.2, run_id="DEV-syn")
    b = generate_run(end_ms=BASE + 10 * MIN, seed=7, n_ips=20, n_windows=12, anomaly_share=0.2, run_id="DEV-syn")
    c = generate_run(end_ms=BASE + 10 * MIN, seed=8, n_ips=20, n_windows=12, anomaly_share=0.2, run_id="DEV-syn")
    assert a == b and a.windows != c.windows


def test_shape_and_alignment():
    r = generate_run(end_ms=BASE + 10 * MIN + 7_123, seed=1, n_ips=10, n_windows=30, anomaly_share=0.1, run_id="DEV-syn")
    ends = sorted({w["window_end"] for w in r.windows})
    assert len(r.windows) == 300 and len(ends) == 30
    assert ends[-1] == BASE + 10 * MIN and all(e % S.SLIDE_MS == 0 for e in ends)   # last full slide ≤ end
    assert all(b - a == S.SLIDE_MS for a, b in zip(ends, ends[1:]))
    assert len({(w["window_end"], w["src_ip"]) for w in r.windows}) == 300        # one row per key


@pytest.mark.parametrize("share", [0.0, 0.05, 0.2, 0.5, 1.0])
def test_anomaly_share(share):
    r = generate_run(end_ms=BASE + 10 * MIN, seed=3, n_ips=50, n_windows=30, anomaly_share=share, run_id="DEV-syn")
    got = sum(w["is_anomaly"] for w in r.windows) / len(r.windows)
    assert abs(got - share) <= 0.05


def test_rows_valid_and_metrics_consistent():
    r = generate_run(end_ms=BASE + 10 * MIN, seed=5, n_ips=30, n_windows=30, anomaly_share=0.2, run_id="DEV-syn")
    assert all(S.validate_row(w) == [] for w in r.windows)
    assert all(M.validate_metrics_row(m) == [] for m in r.metrics)
    assert M.validate_run_row(r.run) == []
    assert sum(m["windows_written"] for m in r.metrics) == len(r.windows)
    assert sum(m["anomalies_written"] for m in r.metrics) == sum(w["is_anomaly"] for w in r.windows)
    assert all(w["run_id"] == "DEV-syn" == r.run["run_id"] for w in r.windows)


def test_bad_arguments():
    with pytest.raises(ValueError):
        generate_run(end_ms=BASE, seed=1, n_ips=0, n_windows=1, anomaly_share=0.1, run_id="DEV-syn")
    with pytest.raises(ValueError):
        generate_run(end_ms=BASE, seed=1, n_ips=1, n_windows=1, anomaly_share=1.5, run_id="DEV-syn")
    with pytest.raises(ValueError):
        generate_run(end_ms=BASE, seed=1, n_ips=1, n_windows=1, anomaly_share=0.1, run_id="not a run id")


def test_next_window_ends_for_follow_mode():
    assert next_window_ends(last_end=BASE + 30_000, now_ms=BASE + 30_000) == []
    assert next_window_ends(last_end=BASE + 30_000, now_ms=BASE + 59_999) == [BASE + 40_000, BASE + 50_000]
