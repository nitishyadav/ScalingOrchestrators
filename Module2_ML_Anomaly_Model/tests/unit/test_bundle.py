"""M2-F04 detection bundle (AC-02, AC-03, AC-06)."""
import json

import numpy as np
import pandas as pd
import pytest

from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_model import bundle as mb


@pytest.fixture(scope="module")
def dummy(tmp_path_factory):
    out = tmp_path_factory.mktemp("bundle")
    mb.make_dummy(out)
    return out


def golden_features():
    return pd.DataFrame(F.read_feature_csv(FIXTURES_DIR / "features_golden.csv"))


def test_same_seed_same_scores(dummy, tmp_path):
    again = tmp_path / "again"
    mb.make_dummy(again)
    a = mb.Bundle.load(dummy).score(golden_features())
    b = mb.Bundle.load(again).score(golden_features())
    assert np.allclose(a["anomaly_score"], b["anomaly_score"], atol=0, rtol=0)


def test_vectorised_score_equals_reference(dummy):
    bundle = mb.Bundle.load(dummy)
    rng = np.random.default_rng(0)
    rand = pd.DataFrame({"total_bytes": rng.integers(0, 10_000_000, 1000), "unique_ports": rng.integers(1, 2000, 1000),
                         "syn_ack_ratio": rng.uniform(0, 400, 1000), "packet_rate": rng.uniform(0, 300, 1000),
                         "bytes_per_flow": rng.lognormal(6, 3, 1000), "port_ratio": rng.uniform(0, 1, 1000),
                         "syn_share": rng.uniform(0, 3, 1000)})
    for frame in (golden_features(), rand):
        got = bundle.score(frame)
        for (_, row), (_, s) in zip(frame.iterrows(), got.iterrows()):
            feats = {f: row[f] for f in F.RULE_FEATURES}
            hits = B.rule_hits(bundle.rules, feats)
            ml, rule, anomaly, ids = B.decide(s["anomaly_score"], bundle.threshold, bundle.rules, hits)
            assert (s["ml_flag"], s["rule_flag"], s["is_anomaly"], s["rule_ids"]) == (ml, rule, anomaly, ids)
    golden = bundle.score(golden_features())                      # the golden rows exercise both outcomes
    assert golden["rule_flag"].any() and (~golden["is_anomaly"]).any()


def test_threshold_only_from_manifest(dummy):
    bundle = mb.Bundle.load(dummy)
    m = json.loads((dummy / "manifest.json").read_text())
    assert bundle.threshold == m["threshold"]
    scores = bundle.score(golden_features())
    assert (scores["ml_flag"] == (scores["anomaly_score"] >= m["threshold"])).all()


def test_version_mismatch_refused(dummy, tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    for name in B.BUNDLE_FILES:
        (bad / name).write_bytes((dummy / name).read_bytes())
    m = json.loads((bad / "manifest.json").read_text())
    m["sklearn_version"] = "0.24.2"
    (bad / "manifest.json").write_text(json.dumps(m))
    with pytest.raises(mb.BundleError, match="sklearn"):
        mb.Bundle.load(bad)


def test_invalid_manifest_or_missing_file_refused(dummy, tmp_path):
    bad = tmp_path / "bad2"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({"bundle_version": "x"}))
    with pytest.raises(mb.BundleError):
        mb.Bundle.load(bad)
    with pytest.raises(mb.BundleError):
        mb.Bundle.load(tmp_path / "nothing")
