"""Dashboard presentation builders (ui.py): status is never colour-only, HTML is Markdown-safe, input is escaped."""
from ids_monitor import dashboard_model as DM
from ids_monitor import ui

from conftest import BASE, window

NOW = BASE + 3_600_000


def _view(anomalous, total=100, mode="now", run="DEV-test"):
    ws = [window(end=NOW - (i % 30) * 10_000, ip=f"10.4.0.{i}", anomalous=i < anomalous) for i in range(total)]
    return DM.build_view(ws, [], NOW, mode, 300, run)


def test_builders_return_single_line_html():
    v = _view(30)
    for markup in (ui.header_html(v), ui.drift_html(v), ui.tiles_html(v), ui.card_title("a", "b"), ui.empty_html("x")):
        assert "\n" not in markup


def test_header_live_vs_ended_and_escaping():
    assert "LIVE" in ui.header_html(_view(0)) and "ENDED" not in ui.header_html(_view(0))
    ended = ui.header_html(_view(0, mode="run_end", run="<b>x</b>"))
    assert "ENDED" in ended and "As of run end" in ended and "&lt;b&gt;x&lt;/b&gt;" in ended


def test_drift_strip_alert_has_icon_text_and_role():
    crit = ui.drift_html(_view(30))
    assert 'role="alert"' in crit and "🚨" in crit and "Drift alert" in crit and "30 of 100 windows" in crit
    ok = ui.drift_html(_view(10))
    assert 'role="status"' in ok and "No drift" in ok and "✅" in ok


def test_tile_status_has_a_text_label():
    for status, label in (("good", "On target"), ("warning", "Near limit"), ("critical", "Over limit")):
        t = ui.tile_html("p95 latency", "450", "ms", status)
        assert label in t and f'ids-tile {status}' in t
    assert "On target" not in ui.tile_html("Windows", "1", status="neutral")
    assert 't-unit' not in ui.tile_html("p95 latency", "—", "ms")                 # no unit next to a missing value


def test_sparkline_and_delta():
    assert ui.sparkline_svg([]) == "" and ui.sparkline_svg([1.0]) == ""
    assert "<polyline" in ui.sparkline_svg([1.0, 1.0, 1.0])                        # flat series does not divide by 0
    assert ui.delta_text(110.0, 100.0, "prev") == "▲ 10.0 % vs prev"
    assert ui.delta_text(90.0, 100.0, "prev").startswith("▼")
    assert ui.delta_text(None, 100.0, "prev") == "" and ui.delta_text(1.0, 0.0, "prev") == ""
