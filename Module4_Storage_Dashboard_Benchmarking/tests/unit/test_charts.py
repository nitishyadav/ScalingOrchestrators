"""M4-T111: chart specs — one y-axis, tooltips, reference lines, palette (AC-03)."""
import json

from ids_contracts import store as S
from ids_monitor import charts as C

BASE = 1_767_225_600_000


def spec(chart):
    return json.loads(chart.to_json())


def walk(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            yield from walk(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, key)


THROUGHPUT = [{"batch_ts": BASE + i * 1000, "series": s, "rows_per_s": 5000.0 + i} for i in range(3)
              for s in ("input", "processed")]
LATENCY = [{"batch_ts": BASE + i * 1000, "series": s, "ms": 300.0 + i} for i in range(3) for s in ("p50", "p95")]
RATE = [{"window_end": BASE + i * 10_000, "rate": 0.1 * i, "anomalous": i, "total": 10} for i in range(3)]


def _common(d):
    assert not list(walk(d, "resolve"))                                    # never independent (dual) y-scales
    assert list(walk(d, "tooltip"))                                        # hover layer present


def test_throughput_chart():
    d = spec(C.throughput_chart(THROUGHPUT))
    _common(d)
    assert C.SERIES[:2] == ["#2a78d6", "#eb6834"]
    assert any(v == C.SERIES[:2] for v in walk(d, "range"))                # fixed slot order


def refs(d):
    """Reference-line values embedded in the spec's inline datasets."""
    return {r["ref"] for vals in walk(d, "datasets") for rows in vals.values() for r in rows if "ref" in r}


def test_latency_chart_has_500ms_rule():
    d = spec(C.latency_chart(LATENCY))
    _common(d)
    assert C.P2_TARGET_MS == 500 and refs(d) == {500}


def test_anomaly_rate_chart_has_15pct_rule():
    d = spec(C.anomaly_rate_chart(RATE))
    _common(d)
    assert refs(d) == {S.DRIFT_THRESHOLD}
    assert any(fmt == ".0%" for fmt in walk(d, "format"))


def test_reference_lines_use_muted_ink_not_status_colors():
    for chart in (C.latency_chart(LATENCY), C.anomaly_rate_chart(RATE)):
        colors = set(v for v in walk(spec(chart), "color") if isinstance(v, str))
        assert C.MUTED in colors and not colors & set(C.STATUS.values())
