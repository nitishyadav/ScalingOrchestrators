"""M2 replica honours C-02 and C-03 (M2-F02-AC-01, M2-F04-AC-01, AC-04)."""
import json
import math
import re

import pandas as pd
import yaml

from conftest import DUMMY, ROOT
from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_contracts.events import iter_jsonl
from ids_model import bundle as mb
from ids_model import features as mf


def test_golden_feature_parity():
    out = mf.to_records(mf.build_features(pd.DataFrame(list(iter_jsonl(FIXTURES_DIR / "events_golden.jsonl")))))
    golden = F.read_feature_csv(FIXTURES_DIR / "features_golden.csv")
    assert len(out) == len(golden) == 23
    assert all(F.rows_equal(a, b) for a, b in zip(out, golden))


def test_committed_dummy_bundle_is_valid_c03():
    assert all((DUMMY / f).exists() for f in B.BUNDLE_FILES)
    manifest = json.loads((DUMMY / "manifest.json").read_text())
    rules = yaml.safe_load((DUMMY / "rules.yaml").read_text())
    assert B.validate_manifest(manifest) == [] and B.validate_rules(rules) == []
    assert manifest["bundle_version"] == "0.0.0-dummy" and tuple(manifest["feature_order"]) == F.FEATURE_ORDER
    pins = (ROOT / "contracts" / "versions.md").read_text()
    for lib in ("scikit-learn", "numpy"):
        pin = re.search(rf"^\| {lib} \| ([\d.]+) \|", pins, re.M).group(1)
        assert manifest[f"{'sklearn' if lib == 'scikit-learn' else lib}_version"] == pin


def test_scores_golden_regenerates_and_matches_features():
    golden = B.read_scores_csv(FIXTURES_DIR / "scores_golden.csv")
    feats = F.read_feature_csv(FIXTURES_DIR / "features_golden.csv")
    assert [(g["window_start"], g["src_ip"]) for g in golden] == [(f["window_start"], f["src_ip"]) for f in feats]
    fresh = mb.golden_score_rows(mb.Bundle.load(DUMMY))
    for a, b in zip(fresh, golden):
        assert math.isclose(a["anomaly_score"], b["anomaly_score"], rel_tol=0, abs_tol=B.SCORE_TOLERANCE)
        assert {k: a[k] for k in ("ml_flag", "rule_flag", "rule_ids", "is_anomaly")} == \
               {k: b[k] for k in ("ml_flag", "rule_flag", "rule_ids", "is_anomaly")}
