"""C-03 detection bundle tooling (M2-F04, REPLICA): dummy bundle, loader with version guard, vectorised scoring,
golden scores. Usage:
    python -m ids_model.bundle make-dummy [--out DIR] [--install]     # mocks/dummy_bundle (+ MODEL_BUNDLE_PATH)
    python -m ids_model.bundle golden-scores [--bundle DIR]           # contracts/fixtures/scores_golden.csv
    python -m ids_model.bundle check [--bundle DIR]                   # validate a bundle (default MODEL_BUNDLE_PATH)
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

from . import MODULE_DIR

DUMMY_DIR = MODULE_DIR / "mocks" / "dummy_bundle"
SCORES_GOLDEN = FIXTURES_DIR / "scores_golden.csv"
SEED = 42
DEFAULT_RULES = {"version": 1, "combine": "any", "rules": [
    {"id": "R-SYN-FLOOD", "all": [{"feature": "syn_ack_ratio", "op": ">=", "value": 5.0}]},
    {"id": "R-PORT-SCAN", "all": [{"feature": "unique_ports", "op": ">=", "value": 50}]},
    {"id": "R-DDOS-RATE", "all": [{"feature": "packet_rate", "op": ">=", "value": 100.0},
                                  {"feature": "unique_ports", "op": "<=", "value": 3}]},
]}


class BundleError(RuntimeError):
    """Invalid, incomplete or incompatible bundle (exit code 1)."""


def synthetic_features(n: int = 5000, seed: int = SEED) -> np.ndarray:
    """Seeded benign-looking C-02 feature rows (order = FEATURE_ORDER, 0.2.0) for the dummy model."""
    rng = np.random.default_rng(seed)
    events = rng.integers(2, 40, n)
    syn, ack = rng.binomial(events, 0.97), rng.binomial(events, 0.97)
    return np.column_stack([
        rng.lognormal(6.9, 0.5, n),                          # bytes_per_flow (~1 kB, like the golden benign host)
        np.minimum(events, rng.integers(1, 6, n)) / events,  # port_ratio
        syn / (ack + 1),                                     # syn_ack_ratio
        syn / events,                                        # syn_share
    ]).astype(float)


def write_bundle(out_dir: Path, model, threshold: float, version: str, training: Mapping, metrics: Mapping,
                 rules: Mapping = DEFAULT_RULES) -> dict:
    """Write a C-03 bundle (model.joblib, manifest.json, rules.yaml); validates before writing."""
    manifest = {
        "bundle_version": version, "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(), "sklearn_version": sklearn.__version__, "numpy_version": np.__version__,
        "feature_order": list(F.FEATURE_ORDER), "score_definition": B.SCORE_DEFINITION, "threshold": float(threshold),
        "training": dict(training), "metrics": dict(metrics),
        "contract_versions": {"C-02": F.CONTRACT_VERSION, "C-03": B.CONTRACT_VERSION},
    }
    errors = B.validate_manifest(manifest) + B.validate_rules(rules)
    if errors:
        raise BundleError(f"bundle would violate C-03: {errors}")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "model.joblib")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "rules.yaml").write_text("# C-03 §4 rules (placeholders; M2 tunes them)\n" + yaml.safe_dump(dict(rules), sort_keys=False))
    return manifest


def make_dummy(out_dir: Path, seed: int = SEED) -> dict:
    X = synthetic_features(seed=seed)
    model = Pipeline([("scaler", StandardScaler()),
                      ("iforest", IsolationForest(n_estimators=100, contamination="auto", random_state=seed))]).fit(X)
    threshold = float(np.quantile(-model.score_samples(X), 0.99))
    return write_bundle(out_dir, model, threshold, B.DUMMY_PREFIX,
                        {"data": f"synthetic benign-like C-02 features, n={len(X)}", "seed": seed, "n_estimators": 100,
                         "contamination": "auto", "R_ref": 5000, "threshold_rule": "99th percentile of training anomaly_score"},
                        {"precision": None, "recall": None, "fpr": None, "test_files": []})


def rule_flags(features: pd.DataFrame, rules: Mapping):
    """(rule_flag bool array, rule_ids list) per C-03 §5, vectorised over a frame with the C-02 feature columns."""
    n = len(features)
    ids = [r["id"] for r in rules["rules"]]
    masks = np.array([np.logical_and.reduce([B.OPS[c["op"]](features[c["feature"]].to_numpy(dtype=float), c["value"])
                                             for c in r["all"]]) for r in rules["rules"]]).reshape(len(ids), n)
    flag = masks.all(axis=0) if rules["combine"] == "all" else masks.any(axis=0)
    return flag, [",".join(i for i, m in zip(ids, col) if m) for col in masks.T]


class Bundle:
    def __init__(self, path: Path, manifest: dict, rules: dict, model):
        self.path, self.manifest, self.rules, self.model = path, manifest, rules, model

    @classmethod
    def load(cls, path, check_versions: bool = True) -> "Bundle":
        path = Path(path)
        missing = [f for f in B.BUNDLE_FILES if not (path / f).is_file()]
        if missing:
            raise BundleError(f"bundle at {path} is missing {missing}")
        try:
            manifest = json.loads((path / "manifest.json").read_text())
            rules = yaml.safe_load((path / "rules.yaml").read_text())
        except (ValueError, yaml.YAMLError) as exc:
            raise BundleError(f"cannot parse bundle metadata: {exc}") from None
        errors = B.validate_manifest(manifest) + B.validate_rules(rules or {})
        if errors:
            raise BundleError(f"bundle at {path} violates C-03: {errors}")
        if check_versions:
            mismatch = [f"{k}: bundle {manifest[k]} != running {v}" for k, v in
                        (("sklearn_version", sklearn.__version__), ("numpy_version", np.__version__)) if manifest[k] != v]
            if mismatch:
                raise BundleError(f"library versions differ from the bundle (ADR-009): {mismatch}")
        return cls(path, manifest, rules, joblib.load(path / "model.joblib"))

    @property
    def threshold(self) -> float:
        return self.manifest["threshold"]

    @property
    def version(self) -> str:
        return self.manifest["bundle_version"]

    def score(self, features: pd.DataFrame) -> pd.DataFrame:
        """C-03 §5, vectorised. Input: any frame with the C-02 FEATURE_ORDER columns."""
        X = features[list(F.FEATURE_ORDER)].to_numpy(dtype=float)
        score = -self.model.score_samples(X) if len(X) else np.empty(0)
        rule_flag, rule_ids = rule_flags(features, self.rules)
        ml_flag = score >= self.threshold
        return pd.DataFrame({"anomaly_score": score, "ml_flag": ml_flag, "rule_flag": rule_flag, "rule_ids": rule_ids,
                             "is_anomaly": ml_flag | rule_flag}, index=features.index)


def golden_score_rows(bundle: Bundle) -> List[dict]:
    feats = pd.DataFrame(F.read_feature_csv(FIXTURES_DIR / "features_golden.csv"))
    scored = pd.concat([feats[list(F.KEY_COLUMNS)], bundle.score(feats)], axis=1)
    return [{"window_start": int(r.window_start), "window_end": int(r.window_end), "src_ip": str(r.src_ip),
             "anomaly_score": float(r.anomaly_score), "ml_flag": bool(r.ml_flag), "rule_flag": bool(r.rule_flag),
             "rule_ids": str(r.rule_ids), "is_anomaly": bool(r.is_anomaly)} for r in scored.itertuples(index=False)]


def write_golden_scores(bundle: Bundle, path: Path = SCORES_GOLDEN) -> int:
    rows = golden_score_rows(bundle)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(B.SCORE_COLUMNS)
        for r in rows:
            w.writerow([("true" if r[c] else "false") if isinstance(r[c], bool) else repr(r[c]) if isinstance(r[c], float)
                        else r[c] for c in B.SCORE_COLUMNS])
    return len(rows)


def install(src: Path, dest: Path) -> None:
    dest = Path(dest)
    if dest.exists() or dest.is_symlink():
        shutil.rmtree(dest) if dest.is_dir() and not dest.is_symlink() else dest.unlink()
    shutil.copytree(src, dest)


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_model.bundle", description="C-03 detection bundle tooling (M2 replica).")
    sub = p.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make-dummy")
    mk.add_argument("--out", type=Path, default=DUMMY_DIR)
    mk.add_argument("--install", action="store_true", help="also copy to MODEL_BUNDLE_PATH")
    gs = sub.add_parser("golden-scores")
    gs.add_argument("--bundle", type=Path, default=DUMMY_DIR)
    gs.add_argument("--out", type=Path, default=SCORES_GOLDEN)
    ck = sub.add_parser("check")
    ck.add_argument("--bundle", type=Path)
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    try:
        if args.cmd == "make-dummy":
            m = make_dummy(args.out)
            if args.install:
                install(args.out, cfg.model_bundle_path)
            print(summary_line("bundle make-dummy", cfg.run_id, bundle_version=m["bundle_version"], threshold=m["threshold"],
                               out=str(args.out), installed=str(cfg.model_bundle_path) if args.install else None))
        elif args.cmd == "golden-scores":
            n = write_golden_scores(Bundle.load(args.bundle), args.out)
            print(summary_line("bundle golden-scores", cfg.run_id, rows=n, out=str(args.out)))
        else:
            b = Bundle.load(args.bundle or cfg.model_bundle_path)
            print(summary_line("bundle check", cfg.run_id, bundle=str(b.path), bundle_version=b.version, threshold=b.threshold))
    except BundleError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
