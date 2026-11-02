"""M4-T012: drift summary and top flagged IPs (AC-05, AC-06)."""
import time

from ids_contracts import store as S
from ids_monitor.view import drift_summary, top_flagged

from conftest import BASE, window


def _windows(total, anomalous):
    return [window(end=BASE + 30_000 + i * 10_000, ip=f"10.0.{i // 250}.{i % 250}", anomalous=i < anomalous)
            for i in range(total)]


def test_drift_above_threshold():
    d = drift_summary(_windows(100, 16))
    assert (d.total, d.anomalous, d.alert) == (100, 16, True) and abs(d.rate - 0.16) < 1e-12
    assert d.threshold == S.DRIFT_THRESHOLD


def test_drift_at_threshold_is_not_an_alert():
    assert drift_summary(_windows(100, 15)).alert is False


def test_drift_empty():
    d = drift_summary([])
    assert (d.total, d.anomalous, d.rate, d.alert) == (0, 0, 0.0, False)


def test_top_flagged_order_and_fields():
    ws = [window(end=BASE + 30_000, ip="a", anomalous=True, score=0.7),
          window(end=BASE + 40_000, ip="a", rule_ids="R-PORT-SCAN", score=0.2),
          window(end=BASE + 50_000, ip="b", anomalous=True, score=0.9),
          window(end=BASE + 60_000, ip="b", rule_ids="R-SYN-FLOOD,R-PORT-SCAN", score=0.3),
          window(end=BASE + 70_000, ip="c", anomalous=True, score=0.95),
          window(end=BASE + 80_000, ip="d", anomalous=False, score=0.99)]       # not flagged: excluded
    top = top_flagged(ws, n=10)
    assert [t.src_ip for t in top] == ["b", "a", "c"]                        # count desc, then max score desc
    b = top[0]
    assert (b.windows, b.max_score, b.last_seen) == (2, 0.9, BASE + 60_000)
    assert b.rule_ids == ("R-PORT-SCAN", "R-SYN-FLOOD")
    assert top_flagged(ws, n=1)[0].src_ip == "b"


class _Guard(dict):
    def __getitem__(self, key):
        assert key not in S.EVAL_ONLY, f"eval-only column {key} read"
        return super().__getitem__(key)

    def get(self, key, default=None):
        assert key not in S.EVAL_ONLY, f"eval-only column {key} read"
        return super().get(key, default)


def test_eval_only_columns_are_never_read():
    ws = [_Guard(w) for w in _windows(50, 10)]
    drift_summary(ws)
    top_flagged(ws)


def test_performance_100k_windows():
    ws = _windows(100_000, 12_000)
    t0 = time.perf_counter()
    drift_summary(ws)
    top_flagged(ws, n=10)
    assert time.perf_counter() - t0 <= 0.5                                   # NFR-002
