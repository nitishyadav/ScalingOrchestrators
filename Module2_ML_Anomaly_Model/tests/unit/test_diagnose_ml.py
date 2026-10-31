"""M2-F03 ML diagnosis on synthetic splits: a separable attack and a hidden (benign-like) attack must be told apart."""
import numpy as np
import pandas as pd
import pytest

from ids_model import diagnose_ml as dm
from ids_model import train as tr


def benign(n, rng):
    ports = rng.integers(1, 5, n)
    events = rng.integers(5, 400, n)
    return pd.DataFrame({"bytes_per_flow": rng.uniform(200, 2000, n), "port_ratio": ports / events,
                         "syn_ack_ratio": rng.uniform(0, 1.5, n), "syn_share": rng.uniform(0, 0.8, n)})


def split(n, seed, hidden=0, loud=0):
    rng = np.random.default_rng(seed)
    parts = [benign(n, rng).assign(label_attack=False, label_type="BENIGN"),
             benign(hidden, rng).assign(label_attack=True, label_type="Hidden")]
    loud_df = benign(loud, rng).assign(bytes_per_flow=rng.uniform(50_000, 90_000, loud), port_ratio=1.0,
                                       label_attack=True, label_type="Loud")
    return pd.concat(parts + [loud_df], ignore_index=True)


@pytest.fixture(scope="module")
def res():
    splits = {"train": split(3000, 1), "holdout": split(800, 2), "validation": split(2000, 3, hidden=40, loud=40),
              "test": {"T": split(2000, 4, hidden=60, loud=60)}}
    return dm.diagnose(splits)


def test_separable_attack_has_high_auc_and_hidden_attack_does_not(res):
    cats = res["splits"]["test"]["categories"]
    assert cats["Loud"]["auc_vs_benign"] > 0.95
    assert 0.35 < cats["Hidden"]["auc_vs_benign"] < 0.65


def test_verdict_separates_feature_problem_from_threshold_problem(res):
    assert res["verdict"]["Hidden"]["reading"].startswith("FEATURE/MODEL")
    assert res["verdict"]["Loud"]["reading"].startswith("THRESHOLD")


def test_isolation_forest_scores_saturate_for_out_of_range_attacks(res):
    """A 50x out-of-range attack is caught at p99 but mostly missed at p99.9: scores plateau near the training extremes."""
    r = res["splits"]["test"]["categories"]["Loud"]["recall_at_percentile"]
    assert r["99"] >= 0.9 and r["99.9"] < 0.5
    q = res["splits"]["test"]["categories"]["Loud"]["score_quantiles"]
    assert q["0.95"] - q["0.05"] < 0.1          # attack scores are bunched at the ceiling, not spread out


def test_detected_reading():
    r = {"splits": {"test": {"categories": {"X": {"auc_vs_benign": 0.99, "recall_at_percentile": {"99.9": 0.8}}}}}}
    assert dm.verdict(r)["X"]["reading"].startswith("detected")


def test_recall_by_percentile_is_monotone_and_percentile_positions_ordered(res):
    for v in res["splits"]["test"]["categories"].values():
        r = [v["recall_at_percentile"][str(p)] for p in tr.PERCENTILES]
        assert r == sorted(r, reverse=True)
        b = v["benign_percentile_quantiles"]
        assert b["0.05"] <= b["0.5"] <= b["0.95"]


def test_threshold_problem_is_named():
    # attack ranks above benign (AUC high) but under the strictest threshold → threshold problem
    r = {"splits": {"test": {"categories": {"X": {"auc_vs_benign": 0.9, "recall_at_percentile": {"99.9": 0.0}}}}}}
    assert dm.verdict(r)["X"]["reading"].startswith("THRESHOLD")


def test_report_markdown_mentions_every_category(res):
    md = dm.report_markdown(res, "2026-11-01")
    assert "Hidden" in md and "Loud" in md and "AUC" in md
