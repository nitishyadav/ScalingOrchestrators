"""C-03 Detection Bundle: layout, manifest/rules validators and the reference decision semantics.

Contract: contracts/C-03_detection_bundle.md (owner M2 — PROVISIONAL REPLICA authored by M1, to be replaced at v1.0)
Loading model.joblib needs scikit-learn (consumer side); this module stays dependency-free and works on parsed
manifest.json / rules.yaml dicts.
"""
from __future__ import annotations

import math
import operator
from typing import Any, List, Mapping, Sequence, Tuple

from .features import FEATURE_ORDER, KEY_COLUMNS, RULE_FEATURES

CONTRACT_ID = "C-03"
CONTRACT_VERSION = "0.2.0-replica"

BUNDLE_FILES = ("model.joblib", "manifest.json", "rules.yaml")
SCORE_DEFINITION = "anomaly_score = -model.score_samples(X); higher = more anomalous"
MANIFEST_KEYS = ("bundle_version", "created_at", "python_version", "sklearn_version", "numpy_version", "feature_order",
                 "score_definition", "threshold", "training", "metrics", "contract_versions")
TRAINING_KEYS = ("data", "seed", "n_estimators", "contamination", "R_ref")
METRICS_KEYS = ("precision", "recall", "fpr", "test_files")
OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt, "==": operator.eq}
COMBINE = ("any", "all")
DUMMY_PREFIX = "0.0.0-dummy"
SCORE_COLUMNS = KEY_COLUMNS + ("anomaly_score", "ml_flag", "rule_flag", "rule_ids", "is_anomaly")   # scores_golden.csv
SCORE_TOLERANCE = 1e-9


def read_scores_csv(path) -> List[dict]:
    """Read scores_golden.csv (header = SCORE_COLUMNS) into typed dicts."""
    import csv
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != SCORE_COLUMNS:
            raise ValueError(f"columns {reader.fieldnames} != {list(SCORE_COLUMNS)}")
        out = []
        for r in reader:
            out.append({"window_start": int(r["window_start"]), "window_end": int(r["window_end"]), "src_ip": r["src_ip"],
                        "anomaly_score": float(r["anomaly_score"]), "ml_flag": r["ml_flag"] == "true",
                        "rule_flag": r["rule_flag"] == "true", "rule_ids": r["rule_ids"], "is_anomaly": r["is_anomaly"] == "true"})
        return out


def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_manifest(m: Mapping) -> List[str]:
    errors = [f"manifest missing '{k}'" for k in MANIFEST_KEYS if k not in m]
    if errors:
        return errors
    if tuple(m["feature_order"]) != FEATURE_ORDER:
        errors.append(f"feature_order {m['feature_order']} != C-02 {list(FEATURE_ORDER)}")
    if m["score_definition"] != SCORE_DEFINITION:
        errors.append("score_definition differs from C-03")
    if not _num(m["threshold"]):
        errors.append("threshold must be a finite number")
    errors += [f"training missing '{k}'" for k in TRAINING_KEYS if k not in m["training"]]
    errors += [f"metrics missing '{k}'" for k in METRICS_KEYS if k not in m["metrics"]]
    for k in ("precision", "recall", "fpr"):
        v = m["metrics"].get(k)
        if v is not None and not (_num(v) and 0 <= v <= 1):
            errors.append(f"metrics.{k} must be null or in [0, 1]")
    for c in ("C-02", "C-03"):
        if c not in m["contract_versions"]:
            errors.append(f"contract_versions missing {c}")
    return errors


def validate_rules(r: Mapping) -> List[str]:
    errors = []
    if r.get("version") != 1:
        errors.append("rules.version must be 1")
    if r.get("combine") not in COMBINE:
        errors.append(f"rules.combine must be one of {COMBINE}")
    rules = r.get("rules")
    if not isinstance(rules, list) or not rules:
        return errors + ["rules.rules must be a non-empty list"]
    seen = set()
    for i, rule in enumerate(rules):
        rid = rule.get("id") if isinstance(rule, Mapping) else None
        if not isinstance(rid, str) or not rid:
            errors.append(f"rules[{i}].id missing")
        elif rid in seen:
            errors.append(f"duplicate rule id {rid}")
        seen.add(rid)
        conds = rule.get("all") if isinstance(rule, Mapping) else None
        if not isinstance(conds, list) or not conds:
            errors.append(f"rules[{i}].all must be a non-empty list")
            continue
        for j, c in enumerate(conds):
            if not isinstance(c, Mapping) or c.get("feature") not in RULE_FEATURES:
                errors.append(f"rules[{i}].all[{j}].feature must be one of {list(RULE_FEATURES)}")
            elif c.get("op") not in OPS:
                errors.append(f"rules[{i}].all[{j}].op must be one of {list(OPS)}")
            elif not _num(c.get("value")):
                errors.append(f"rules[{i}].all[{j}].value must be a finite number")
    return errors


def rule_hits(rules: Mapping, features: Mapping[str, float]) -> List[str]:
    """Reference semantics: a rule fires if ALL its conditions hold; returns fired ids in rules order."""
    return [rule["id"] for rule in rules["rules"]
            if all(OPS[c["op"]](features[c["feature"]], c["value"]) for c in rule["all"])]


def decide(anomaly_score: float, threshold: float, rules: Mapping, hits: Sequence[str]) -> Tuple[bool, bool, bool, str]:
    """(ml_flag, rule_flag, is_anomaly, rule_ids). is_anomaly = ml_flag OR rule_flag (C-03 §4)."""
    ml_flag = anomaly_score >= threshold
    rule_flag = (len(hits) == len(rules["rules"])) if rules["combine"] == "all" else bool(hits)
    return ml_flag, rule_flag, ml_flag or rule_flag, ",".join(hits)
