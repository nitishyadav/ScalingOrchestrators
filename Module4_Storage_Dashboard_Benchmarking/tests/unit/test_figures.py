"""M4-T311: report figures — palette, one y-axis per panel, log only when needed, skip on missing data (AC-04)."""
import matplotlib.colors as mcolors
import pytest

from ids_monitor import analyze as A
from ids_monitor import figures as F

import results_fixture as RF

ALLOWED = {mcolors.to_hex(c) for c in (*F.SERIES, F.MUTED, F.TEXT, F.TEXT_2, F.GRID, F.SURFACE, "white", "black", "none")}


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    import matplotlib.pyplot as plt
    plt.close("all")


@pytest.fixture()
def built(tmp_path):
    RF.write(tmp_path)
    return F.build_all(A.latest_reports(tmp_path), tmp_path)


def colours(fig):
    out = set()
    for ax in fig.axes:
        for line in ax.get_lines():
            out.add(mcolors.to_hex(line.get_color()))
            mfc = line.get_markerfacecolor()
            if not (isinstance(mfc, str) and mfc == "none"):
                out.add(mcolors.to_hex(mfc))
        for patch in ax.patches:
            fc = patch.get_facecolor()
            if fc[3] > 0:
                out.add(mcolors.to_hex(fc[:3]))
        for coll in ax.collections:
            for fc in coll.get_facecolors():
                if fc[3] > 0:
                    out.add(mcolors.to_hex(fc[:3]))
    return out


def test_all_six_figures(built):
    figs, skipped = built
    assert sorted(figs) == ["detection", "f3", "latency", "recovery", "scaling", "timeline"] and skipped == []


def test_palette_and_one_y_axis_per_panel(built):
    figs, _ = built
    panels = {"scaling": 2, "timeline": 2, "latency": 1, "detection": 1, "f3": 1, "recovery": 1}
    for name, fig in figs.items():
        assert len(fig.axes) == panels[name], name                    # no twin axes (a twin adds an Axes)
        assert colours(fig) <= ALLOWED, (name, colours(fig) - ALLOWED)
        for ax in fig.axes:
            assert ax.get_ylabel(), name                              # every axis says what it measures


def test_legends_for_multi_series_and_value_labels_on_bars(built):
    figs, _ = built
    for name in ("latency", "detection", "f3", "scaling"):
        fig = figs[name]
        assert fig.legends or any(ax.get_legend() is not None for ax in fig.axes), name   # panel or shared legend
    f3_texts = [t.get_text() for t in figs["f3"].axes[0].texts]
    assert "94%" in f3_texts and "35%" in f3_texts                  # INJ_DDOS hybrid / rule (relief rule for aqua)


def test_lower_bounds_are_hollow(built):
    figs, _ = built
    e1 = figs["scaling"].axes[0]
    hollow = [ln for ln in e1.get_lines() if ln.get_marker() == "o" and mcolors.to_hex(ln.get_markerfacecolor()) == "#ffffff"]
    assert hollow and len(hollow[0].get_xdata()) == 2                  # levels 8 and 16 kept up with the producer


def test_log_axis_only_when_values_span_more_than_50x():
    assert F.needs_log([100, 6000]) and not F.needs_log([300, 1500]) and not F.needs_log([])
    fig = F.latency([{"level": "1000", "summary": {"p95_ms": 115_000.0, "p95_tail_ms": 144_000.0}},
                     {"level": "250", "summary": {"p95_ms": 410.0, "p95_tail_ms": 800.0}}])
    ax = fig.axes[0]
    assert ax.get_yscale() == "log" and "log" in ax.get_ylabel()


def test_missing_data_skips_figures(tmp_path):
    RF.write(tmp_path, only={"E1", "LAT"})
    figs, skipped = F.build_all(A.latest_reports(tmp_path), tmp_path)
    assert sorted(figs) == ["latency", "scaling"]
    assert {s["figure"] for s in skipped} == {"detection", "f3", "timeline", "recovery"}
    assert all(s["reason"] for s in skipped)
