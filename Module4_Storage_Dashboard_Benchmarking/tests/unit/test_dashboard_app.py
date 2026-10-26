"""M4-T040 — the Streamlit page renders in --demo mode without Cassandra (M4-F02-AC-03)."""
import sys

import pytest

from conftest import MODULE_DIR

APP = str(MODULE_DIR / "src" / "ids_monitor" / "dashboard.py")


@pytest.fixture
def app(monkeypatch):
    from streamlit.testing.v1 import AppTest

    def make(*args):
        monkeypatch.setattr(sys, "argv", ["dashboard.py", *args])
        at = AppTest.from_file(APP, default_timeout=60)
        at.run()
        return at
    return make


def test_demo_page_renders_kpis_banner_and_table(app):
    at = app("--demo", "--demo-share", "0.2")
    assert not at.exception, at.exception
    assert [m.label for m in at.metric] == ["Throughput", "p95 latency", "Anomaly rate", "Windows scored"]
    assert any("Drift alert" in e.value for e in at.error)
    assert len(at.dataframe) == 1
    assert any("DEMO" in c.value for c in at.caption)


def test_demo_page_without_drift(app):
    at = app("--demo", "--demo-share", "0.05")
    assert not at.exception and not at.error
    assert any("No drift" in s.value for s in at.success)
