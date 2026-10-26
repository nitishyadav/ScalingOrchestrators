"""M2-F03 training/evaluation logic on small synthetic splits (AC-01, AC-02, AC-03)."""
import json

import numpy as np
import pandas as pd
import pytest

from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_model import bundle as mb
from ids_model import train as tr


# ---- AC-01 metric maths --------------------------------------------------------------------------
def test_binary_metrics():
    y = np.array([1, 1, 1, 1, 0, 0, 0, 0], bool)
    p = np.array([1, 1, 0, 0, 1, 0, 0, 0], bool)
    m = tr.binary_metrics(y, p)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (2, 1, 3, 2)
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == 0.5 and m["fpr"] == 0.25
    assert m["f1"] == pytest.approx(2 * (2 / 3) * 0.5 / (2 / 3 + 0.5))


def test_binary_metrics_zero_division():
    m = tr.binary_metrics(np.array([1, 0], bool), np.array([0, 0], bool))
    assert m["precision"] == 0.0 and m["recall"] == 0.0 and m["f1"] == 0.0 and m["fpr"] == 0.0
    assert tr.binary_metrics(np.array([1], bool), np.array([1], bool))["fpr"] == 0.0


def test_per_category_recall():
    df = pd.DataFrame({"label_type": ["DDoS", "DDoS", "PortScan", "BENIGN"], "label_attack": [True, True, True, False]})
    preds = {"rule": np.array([0, 0, 1, 0], bool), "ml": np.array([1, 0, 0, 1], bool), "hybrid": np.array([1, 0, 1, 1], bool)}
    out = tr.per_category(df, preds)
    assert out == {"DDoS": {"windows": 2, "rule": 0.0, "ml": 0.5, "hybrid": 0.5},
                   "PortScan": {"windows": 1, "rule": 1.0, "ml": 0.0, "hybrid": 1.0}}


# ---- synthetic splits ----------------------------------------------------------------------------
def frame(n, attack_share, seed, label="DDoS"):
    rng = np.random.default_rng(seed)
    attack = rng.random(n) < attack_share
    df = pd.DataFrame({
        "total_bytes": np.where(attack, rng.integers(500_000, 2_000_000, n), rng.integers(100, 20_000, n)),
        "unique_ports": np.where(attack, 1, rng.integers(1, 5, n)),
        "syn_ack_ratio": np.where(attack, rng.uniform(0, 0.5, n), rng.uniform(0, 1.5, n)),
        "packet_rate": np.where(attack, rng.uniform(40, 90, n), rng.uniform(0.03, 3, n)),
        "syn_share": np.where(attack, rng.uniform(0.9, 1.0, n), rng.uniform(0, 0.8, n)),
    })
    events = np.maximum(1, (df["packet_rate"] * 30).round())
    df["bytes_per_flow"], df["port_ratio"] = df["total_bytes"] / events, df["unique_ports"] / events
    df["label_attack"] = attack
    df["label_type"] = np.where(attack, label, "BENIGN")
    return df


@pytest.fixture(scope="module")
def splits():
    return {"train": frame(3000, 0.0, 1), "holdout": frame(800, 0.0, 2),
            "validation": frame(2000, 0.1, 3), "test": {"DDos": frame(1500, 0.3, 4)}}


# ---- AC-02 selection without leakage -------------------------------------------------------------
def test_threshold_selection_respects_fpr_constraint(splits):
    model = tr.fit_model(splits["train"][list(F.FEATURE_ORDER)], seed=42)
    sel = tr.select_threshold(model, splits, mb.DEFAULT_RULES)
    assert sel["fpr_constraint_met"] is True and sel["holdout_fpr"] < 0.05
    ok = [c for c in sel["candidates"] if c["holdout_fpr"] < 0.05]
    assert sel["val_f1"] == max(c["val_f1"] for c in ok)
    assert sel["percentile"] in tr.PERCENTILES


def test_no_qualifying_threshold_is_flagged(splits):
    model = tr.fit_model(splits["train"][list(F.FEATURE_ORDER)], seed=42)
    # benign-labelled rows that trip R-SYN-FLOOD fire at EVERY threshold (IF itself cannot be relied on for
    # out-of-range points: its splits never extrapolate beyond the training range)
    holdout = frame(800, 0.0, 9)
    holdout.loc[holdout.index[:480], "syn_ack_ratio"] = 10.0
    noisy = dict(splits, holdout=holdout)
    sel = tr.select_threshold(model, noisy, mb.DEFAULT_RULES)
    assert sel["fpr_constraint_met"] is False
    assert sel["holdout_fpr"] == min(c["holdout_fpr"] for c in sel["candidates"])


def test_test_labels_never_influence_choices(splits):
    a = tr.train_and_evaluate(splits, seed=42)
    flipped = dict(splits, test={"DDos": splits["test"]["DDos"].assign(label_attack=lambda d: ~d["label_attack"])})
    b = tr.train_and_evaluate(flipped, seed=42)
    assert a["selection"]["threshold"] == b["selection"]["threshold"]
    assert a["test"]["hybrid"] != b["test"]["hybrid"]                   # only the reported test numbers change


# ---- AC-03 determinism + bundle --------------------------------------------------------------------
def test_deterministic_and_bundle_valid(splits, tmp_path):
    a = tr.train_and_evaluate(splits, seed=42)
    b = tr.train_and_evaluate(splits, seed=42)
    assert a["selection"]["threshold"] == b["selection"]["threshold"] and a["test"] == b["test"]
    tr.write_trained_bundle(a, tmp_path / "bundle", version="1.0.0-replica")
    bundle = mb.Bundle.load(tmp_path / "bundle")
    m = json.loads((tmp_path / "bundle" / "manifest.json").read_text())
    assert B.validate_manifest(m) == [] and m["bundle_version"] == "1.0.0-replica"
    assert m["threshold"] == a["selection"]["threshold"] and m["metrics"]["precision"] == a["test"]["hybrid"]["precision"]
    scores = bundle.score(splits["test"]["DDos"])
    assert np.allclose(scores["anomaly_score"], -a["model"].score_samples(splits["test"]["DDos"][list(F.FEATURE_ORDER)].to_numpy(float)))


def test_report_markdown_has_pass_fail(splits):
    res = tr.train_and_evaluate(splits, seed=42)
    md = tr.report_markdown(tr.report_dict(res, version="1.0.0-replica"))
    assert "F1 precision" in md and "F2 benign FPR" in md and ("PASS" in md or "FAIL" in md)
