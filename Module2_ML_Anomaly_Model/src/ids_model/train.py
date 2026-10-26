"""`python -m ids_model.train` — Isolation Forest training + evaluation on CIC-IDS2017 (M2-F03, REPLICA).

Protocol (no leakage, spec §Data protocol): train = Monday first 80 % (benign); benign hold-out = Monday last 20 % (F2);
validation = Tue/Wed/Thu (threshold choice only); test = Friday DDoS + PortScan files (reported F1/F3, never used for choices).
Every split is replayed at R_ref = 5000 ev/s so offline windows equal online windows (ADR-011).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from ids_contracts import features as F
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config, summary_line

from . import MODULE_DIR
from .bundle import DEFAULT_RULES, BundleError, install, rule_flags, write_bundle
from .features import DEFAULT_T0_MS, R_REF, features_from_replay

VERSION = "1.1.0-replica"                      # 1.1.0: C-02 0.2.0 model inputs (D-14 V3)
SEED = 42
N_ESTIMATORS = 200
PERCENTILES = (90, 95, 97, 98, 99, 99.5, 99.9)
FPR_LIMIT = 0.05
TRAIN_FRACTION = 0.8
VALIDATION_DAYS = ("Tuesday", "Wednesday", "Thursday")
TEST_FILES = ("Friday-WorkingHours-Afternoon-DDos", "Friday-WorkingHours-Afternoon-PortScan")
TARGETS = {"precision": 0.80, "recall": 0.75, "fpr": 0.05}
_COLUMNS = ["row_idx", "source_file", "orig_ts", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag", "label"]
FEATURES = list(F.FEATURE_ORDER)


# ---- metrics -------------------------------------------------------------------------------------
def binary_metrics(y_true, y_pred) -> dict:
    y, p = np.asarray(y_true, bool), np.asarray(y_pred, bool)
    tp, fp = int((y & p).sum()), int((~y & p).sum())
    tn, fn = int((~y & ~p).sum()), int((y & ~p).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "fpr": fp / (fp + tn) if fp + tn else 0.0}


def per_category(frame: pd.DataFrame, preds: Mapping[str, np.ndarray]) -> dict:
    out = {}
    attack = frame["label_attack"].to_numpy(bool)
    types = frame["label_type"].to_numpy()
    for cat in sorted(set(types[attack])):
        m = attack & (types == cat)
        out[cat] = {"windows": int(m.sum()), **{k: float(np.asarray(v, bool)[m].mean()) for k, v in preds.items()}}
    return out


# ---- model ---------------------------------------------------------------------------------------
def fit_model(X: pd.DataFrame, seed: int = SEED, features: Sequence[str] = FEATURES) -> Pipeline:
    return Pipeline([("log1p", FunctionTransformer(np.log1p)), ("scaler", StandardScaler()),
                     ("iforest", IsolationForest(n_estimators=N_ESTIMATORS, contamination="auto", random_state=seed,
                                                 n_jobs=-1))]).fit(X[list(features)].to_numpy(float))


def anomaly_scores(model, frame: pd.DataFrame, features: Sequence[str] = FEATURES) -> np.ndarray:
    return -model.score_samples(frame[list(features)].to_numpy(float)) if len(frame) else np.empty(0)


def predictions(model, frame: pd.DataFrame, threshold: float, rules: Mapping,
                features: Sequence[str] = FEATURES) -> Dict[str, np.ndarray]:
    ml = anomaly_scores(model, frame, features) >= threshold
    rule = rule_flags(frame, rules)[0]
    return {"rule": rule, "ml": ml, "hybrid": ml | rule}


def select_threshold(model, splits: Mapping, rules: Mapping, features: Sequence[str] = FEATURES) -> dict:
    """Uses ONLY train (percentiles), validation (F1) and the benign hold-out (FPR constraint). Never the test split."""
    train_s = anomaly_scores(model, splits["train"], features)
    val, hold = splits["validation"], splits["holdout"]
    val_s, hold_s = anomaly_scores(model, val, features), anomaly_scores(model, hold, features)
    val_rule, hold_rule = rule_flags(val, rules)[0], rule_flags(hold, rules)[0]
    y_val, y_hold = val["label_attack"].to_numpy(bool), hold["label_attack"].to_numpy(bool)
    candidates = []
    for p in PERCENTILES:
        thr = float(np.percentile(train_s, p))
        vm = binary_metrics(y_val, (val_s >= thr) | val_rule)
        hm = binary_metrics(y_hold, (hold_s >= thr) | hold_rule)
        candidates.append({"percentile": p, "threshold": thr, "val_f1": vm["f1"], "val_precision": vm["precision"],
                           "val_recall": vm["recall"], "holdout_fpr": hm["fpr"]})
    ok = [c for c in candidates if c["holdout_fpr"] < FPR_LIMIT]
    best = (max(ok, key=lambda c: (c["val_f1"], -c["holdout_fpr"])) if ok
            else min(candidates, key=lambda c: (c["holdout_fpr"], -c["val_f1"])))
    return {**best, "fpr_constraint_met": bool(ok), "candidates": candidates}


def train_and_evaluate(splits: Mapping, seed: int = SEED, rules: Mapping = DEFAULT_RULES,
                       features: Sequence[str] = FEATURES) -> dict:
    model = fit_model(splits["train"], seed, features)
    sel = select_threshold(model, splits, rules, features)
    thr = sel["threshold"]
    test = pd.concat(list(splits["test"].values()), ignore_index=True)
    preds = predictions(model, test, thr, rules, features)
    y = test["label_attack"].to_numpy(bool)
    hold_preds = predictions(model, splits["holdout"], thr, rules, features)
    y_hold = splits["holdout"]["label_attack"].to_numpy(bool)
    return {
        "model": model, "seed": seed, "rules": rules, "selection": sel, "features": list(features),
        "test": {k: binary_metrics(y, v) for k, v in preds.items()},
        "test_per_file": {name: {k: binary_metrics(f["label_attack"].to_numpy(bool), v)
                                 for k, v in predictions(model, f, thr, rules, features).items()} for name, f in splits["test"].items()},
        "per_category": per_category(test, preds),
        "holdout": {k: binary_metrics(y_hold, v) for k, v in hold_preds.items()},
        "counts": {"train": len(splits["train"]), "holdout": len(splits["holdout"]), "validation": len(splits["validation"]),
                   "test": len(test), "test_attack": int(y.sum())},
    }


# ---- outputs -------------------------------------------------------------------------------------
def write_trained_bundle(res: Mapping, out_dir: Path, version: str = VERSION) -> dict:
    sel = res["selection"]
    training = {"data": "CIC-IDS2017 Monday (first 80 % of rows, benign) replayed at R_ref; C-02 windows",
                "seed": res["seed"], "n_estimators": N_ESTIMATORS, "contamination": "auto", "R_ref": R_REF,
                "pipeline": "log1p → StandardScaler → IsolationForest", "train_windows": res["counts"]["train"],
                "threshold_rule": f"percentile {sel['percentile']} of train anomaly_score; chosen on validation (Tue–Thu) "
                                  f"hybrid F1 subject to benign hold-out FPR < {FPR_LIMIT:.0%}",
                "fpr_constraint_met": sel["fpr_constraint_met"]}
    metrics = {"precision": res["test"]["hybrid"]["precision"], "recall": res["test"]["hybrid"]["recall"],
               "fpr": res["holdout"]["hybrid"]["fpr"], "test_files": list(TEST_FILES)}
    return write_bundle(out_dir, res["model"], sel["threshold"], version, training, metrics, res["rules"])


def report_dict(res: Mapping, version: str = VERSION) -> dict:
    h, f2 = res["test"]["hybrid"], res["holdout"]["hybrid"]["fpr"]
    return {
        "feature": "M2-F03 (replica)", "bundle_version": version, "date": dt.datetime.now().isoformat(timespec="seconds"),
        "protocol": {"train": "Monday rows < 80 %", "holdout": "Monday rows ≥ 80 %", "validation": list(VALIDATION_DAYS),
                     "test": list(TEST_FILES), "R_ref": R_REF, "seed": res["seed"]},
        "counts": res["counts"], "selection": res["selection"], "test": res["test"], "test_per_file": res["test_per_file"],
        "per_category": res["per_category"], "holdout": res["holdout"],
        "targets": {"F1_precision": {"target": TARGETS["precision"], "value": h["precision"], "pass": h["precision"] >= TARGETS["precision"]},
                    "F1_recall": {"target": TARGETS["recall"], "value": h["recall"], "pass": h["recall"] >= TARGETS["recall"]},
                    "F2_fpr": {"target": TARGETS["fpr"], "value": f2, "pass": f2 < TARGETS["fpr"]}},
    }


def report_markdown(rep: Mapping) -> str:
    t = rep["targets"]
    pf = lambda ok: "PASS" if ok else "FAIL"
    lines = [f"# M2-F03 training report ({rep['bundle_version']}, {rep['date']})", "",
             f"Windows: train {rep['counts']['train']:,} · hold-out {rep['counts']['holdout']:,} · validation {rep['counts']['validation']:,} "
             f"· test {rep['counts']['test']:,} ({rep['counts']['test_attack']:,} attack)", "",
             f"Threshold: percentile {rep['selection']['percentile']} of train scores = {rep['selection']['threshold']:.4f} "
             f"(validation F1 {rep['selection']['val_f1']:.3f}, hold-out FPR {rep['selection']['holdout_fpr']:.3%}, "
             f"constraint met: {rep['selection']['fpr_constraint_met']})", "",
             "| Target | Goal | Measured (hybrid) | Result |", "|---|---|---|---|",
             f"| F1 precision (Fri DDoS + PortScan) | ≥ {t['F1_precision']['target']:.2f} | {t['F1_precision']['value']:.3f} | {pf(t['F1_precision']['pass'])} |",
             f"| F1 recall | ≥ {t['F1_recall']['target']:.2f} | {t['F1_recall']['value']:.3f} | {pf(t['F1_recall']['pass'])} |",
             f"| F2 benign FPR (Monday hold-out) | < {t['F2_fpr']['target']:.0%} | {t['F2_fpr']['value']:.3%} | {pf(t['F2_fpr']['pass'])} |", "",
             "## Detectors on the test set", "", "| Detector | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|"]
    for k in ("rule", "ml", "hybrid"):
        m = rep["test"][k]
        lines.append(f"| {k} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['fpr']:.3%} |")
    lines += ["", "## F3: recall per attack category (test)", "", "| Category | Windows | Rule-only | ML-only | Hybrid |", "|---|---|---|---|---|"]
    for cat, v in rep["per_category"].items():
        lines.append(f"| {cat} | {v['windows']:,} | {v['rule']:.3f} | {v['ml']:.3f} | {v['hybrid']:.3f} |")
    return "\n".join(lines) + "\n"


# ---- real data -----------------------------------------------------------------------------------
def _day(replay_dir: Path, day: str) -> pd.DataFrame:
    return pq.ParquetFile(Path(replay_dir) / f"day={day}" / "part-00000.parquet").read(columns=_COLUMNS).to_pandas()


def _features(raw: pd.DataFrame, extended: bool = False) -> pd.DataFrame:
    return features_from_replay(raw.sort_values("row_idx"), rate=R_REF, t0_ms=DEFAULT_T0_MS, extended=extended)


def load_splits(replay_dir: Path, extended: bool = False) -> dict:
    mon = _day(replay_dir, "Monday").sort_values("row_idx")
    cut = int(len(mon) * TRAIN_FRACTION)
    fri = _day(replay_dir, "Friday")
    fx = lambda raw: _features(raw, extended)
    return {"train": fx(mon.iloc[:cut]), "holdout": fx(mon.iloc[cut:]),
            "validation": pd.concat([fx(_day(replay_dir, d)) for d in VALIDATION_DAYS], ignore_index=True),
            "test": {name: fx(fri[fri["source_file"] == name]) for name in TEST_FILES}}


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_model.train", description="Train + evaluate the C-03 bundle (M2-F03 replica).")
    p.add_argument("--replay", type=Path, help="replay dataset dir (default DATA_DIR/replay)")
    p.add_argument("--out", type=Path, help=f"bundle dir (default runtime/bundle/{VERSION})")
    p.add_argument("--install", action="store_true", help="also copy the bundle to MODEL_BUNDLE_PATH")
    p.add_argument("--report-dir", type=Path, default=MODULE_DIR / "docs" / "measurements")
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    replay = args.replay or cfg.data_dir / "replay"
    out = args.out or cfg.workspace_root / "runtime" / "bundle" / VERSION
    t0 = time.monotonic()
    try:
        splits = load_splits(replay)
    except OSError as exc:
        print(f"cannot read the replay dataset at {replay}: {exc} (run `python -m ids_ingest.prepare`)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    t_features = time.monotonic() - t0
    res = train_and_evaluate(splits, seed=args.seed)
    try:
        write_trained_bundle(res, out)
    except BundleError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    if args.install:
        install(out, cfg.model_bundle_path)
    rep = report_dict(res)
    rep["timing_s"] = {"features": round(t_features, 1), "total": round(time.monotonic() - t0, 1)}
    args.report_dir.mkdir(parents=True, exist_ok=True)
    stem = args.report_dir / f"F03-training-{dt.date.today().isoformat()}"
    stem.with_suffix(".json").write_text(json.dumps(rep, indent=2, default=float) + "\n")
    stem.with_suffix(".md").write_text(report_markdown(rep))
    t = rep["targets"]
    print(summary_line("train", cfg.run_id, bundle=str(out), installed=bool(args.install), threshold=res["selection"]["threshold"],
                       percentile=res["selection"]["percentile"], precision=t["F1_precision"]["value"], recall=t["F1_recall"]["value"],
                       holdout_fpr=t["F2_fpr"]["value"], f1_pass=t["F1_precision"]["pass"] and t["F1_recall"]["pass"],
                       f2_pass=t["F2_fpr"]["pass"], seconds=rep["timing_s"]["total"], report=str(stem.with_suffix(".md"))))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
