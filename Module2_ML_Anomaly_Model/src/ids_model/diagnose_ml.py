"""`python -m ids_model.diagnose_ml` — why does the ML half of the hybrid detect (almost) nothing? (M2-F03 diagnostics, REPLICA).

Research tooling, no contract change. Trains the same model as `ids_model.train` (same splits, seed, pipeline) and reports, per attack
category: ROC-AUC against benign windows, where attack scores fall on the benign-train score distribution, ML-only precision/recall at
every candidate percentile, and how far each model input moves from the benign-train mean.

Reading the result: AUC high but ML recall ~0 at the chosen threshold → a THRESHOLD problem (selection discards the signal).
AUC near 0.5 → a FEATURE/MODEL problem (attacks look benign in C-02 space). The test split is used here for diagnosis only;
nothing in this module feeds back into threshold or feature choices (spec §Data protocol).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from ids_contracts import features as F
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config, summary_line

from . import MODULE_DIR
from . import train as tr

QUANTILES = (0.05, 0.5, 0.95)


def _benign_percentile(train_scores: np.ndarray, scores: np.ndarray) -> np.ndarray:
    """Share of benign-train windows scoring at or below each score (0–100). 99.9 = more extreme than 99.9 % of benign."""
    return 100.0 * np.searchsorted(np.sort(train_scores), scores, side="right") / max(len(train_scores), 1)


def _transformed(model, frame: pd.DataFrame, features: Sequence[str]) -> np.ndarray:
    """Model inputs after log1p + scaling (what the forest actually sees)."""
    return model[:-1].transform(frame[list(features)].to_numpy(float))


def diagnose(splits: Mapping, seed: int = tr.SEED, features: Sequence[str] = tr.FEATURES) -> dict:
    model = tr.fit_model(splits["train"], seed, features)
    train_s = tr.anomaly_scores(model, splits["train"], features)
    thresholds = {p: float(np.percentile(train_s, p)) for p in tr.PERCENTILES}
    out = {"seed": seed, "features": list(features), "train_windows": int(len(train_s)),
           "train_score_percentiles": {str(p): t for p, t in thresholds.items()}, "splits": {}}
    named = {"validation": splits["validation"], "test": pd.concat(list(splits["test"].values()), ignore_index=True)}
    for name, frame in named.items():
        scores = tr.anomaly_scores(model, frame, features)
        attack = frame["label_attack"].to_numpy(bool)
        types = frame["label_type"].to_numpy()
        z = _transformed(model, frame, features)
        entry = {"windows": int(len(frame)), "attack_windows": int(attack.sum()), "categories": {}}
        # ML-only precision / recall at every candidate percentile (the curve the F1 selection collapses to one point)
        entry["ml_only_by_percentile"] = {
            str(p): {k: v for k, v in tr.binary_metrics(attack, scores >= t).items() if k in ("precision", "recall", "fpr")}
            for p, t in thresholds.items()}
        for cat in sorted(set(types[attack])):
            m = attack & (types == cat)
            if m.sum() == 0:
                continue
            pct = _benign_percentile(train_s, scores[m])
            labels = np.r_[np.ones(int(m.sum())), np.zeros(int((~attack).sum()))]
            auc = float(roc_auc_score(labels, np.r_[scores[m], scores[~attack]])) if (~attack).any() else None
            entry["categories"][cat] = {
                "windows": int(m.sum()), "auc_vs_benign": auc,
                "score_quantiles": {str(q): float(np.quantile(scores[m], q)) for q in QUANTILES},
                "benign_score_quantiles": {str(q): float(np.quantile(scores[~attack], q)) for q in QUANTILES} if (~attack).any() else None,
                "benign_percentile_quantiles": {str(q): float(np.quantile(pct, q)) for q in QUANTILES},
                "recall_at_percentile": {str(p): float((scores[m] >= t).mean()) for p, t in thresholds.items()},
                # mean shift of each model input vs the benign-train distribution, in train standard deviations
                "feature_shift_sd": {f: float(z[m][:, i].mean()) for i, f in enumerate(features)},
            }
        out["splits"][name] = entry
    out["verdict"] = verdict(out)
    return out


def verdict(res: Mapping) -> dict:
    """Plain classification of each test category: threshold problem, feature/model problem, or detected."""
    chosen = str(tr.PERCENTILES[-1])
    result = {}
    for cat, v in res["splits"]["test"]["categories"].items():
        auc, rec = v["auc_vs_benign"], v["recall_at_percentile"][chosen]
        if rec >= 0.5:
            kind = "detected at the strictest candidate threshold"
        elif auc is not None and auc >= 0.8:
            kind = "THRESHOLD problem: attacks rank high but fall under the threshold"
        elif auc is not None and auc <= 0.6:
            kind = "FEATURE/MODEL problem: attacks score like benign windows"
        else:
            kind = "partial separation: some ranking signal, threshold and features both matter"
        result[cat] = {"auc": auc, f"recall_at_p{chosen}": rec, "reading": kind}
    return result


def report_markdown(res: Mapping, date: str) -> str:
    lines = [f"# M2-F03 ML diagnosis ({date})", "",
             f"Same model as `ids_model.train` (seed {res['seed']}, inputs {', '.join(res['features'])}). Test split used for diagnosis only.", "",
             "## Verdict per test category", "", "| Category | Windows | AUC vs benign | ML recall at p99.9 | Reading |", "|---|---|---|---|---|"]
    chosen = str(tr.PERCENTILES[-1])
    for cat, v in res["verdict"].items():
        n = res["splits"]["test"]["categories"][cat]["windows"]
        auc = "n/a" if v["auc"] is None else f"{v['auc']:.3f}"
        lines.append(f"| {cat} | {n} | {auc} | {v[f'recall_at_p{chosen}']:.3f} | {v['reading']} |")
    for split in ("test", "validation"):
        sp = res["splits"][split]
        lines += ["", f"## {split.capitalize()}: attack score position ({sp['attack_windows']:,} attack of {sp['windows']:,} windows)", "",
                  "Percentile of the benign-train score distribution at which attack windows land (5 / 50 / 95 % of attack windows).", "",
                  "| Category | AUC | Benign-train percentile (q05 / median / q95) | Recall at p90 | p99 | p99.9 |", "|---|---|---|---|---|---|"]
        for cat, v in sp["categories"].items():
            b = v["benign_percentile_quantiles"]
            r = v["recall_at_percentile"]
            auc = "n/a" if v["auc_vs_benign"] is None else f"{v['auc_vs_benign']:.3f}"
            lines.append(f"| {cat} | {auc} | {b['0.05']:.1f} / {b['0.5']:.1f} / {b['0.95']:.1f} | {r['90']:.3f} | {r['99']:.3f} | {r['99.9']:.3f} |")
        lines += ["", f"ML-only {split} precision / recall / FPR by threshold percentile:", "", "| Percentile | Precision | Recall | FPR |", "|---|---|---|---|"]
        for p, m in sp["ml_only_by_percentile"].items():
            lines.append(f"| p{p} | {m['precision']:.3f} | {m['recall']:.3f} | {m['fpr']:.3%} |")
    lines += ["", "## Mean shift of each model input, test attack windows vs benign-train (after log1p + scaling, in train SD)", "",
              "| Category | " + " | ".join(res["features"]) + " |", "|---|" + "---|" * len(res["features"])]
    for cat, v in res["splits"]["test"]["categories"].items():
        lines.append(f"| {cat} | " + " | ".join(f"{v['feature_shift_sd'][f]:+.2f}" for f in res["features"]) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_model.diagnose_ml", description="Why is the ML detector's recall ~0? (M2-F03 diagnostics)")
    p.add_argument("--replay", type=Path, help="replay dataset dir (default DATA_DIR/replay)")
    p.add_argument("--report-dir", type=Path, default=MODULE_DIR / "docs" / "measurements")
    p.add_argument("--seed", type=int, default=tr.SEED)
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    replay = args.replay or cfg.data_dir / "replay"
    try:
        splits = tr.load_splits(replay)
    except OSError as exc:
        print(f"cannot read the replay dataset at {replay}: {exc} (run `python -m ids_ingest.prepare`)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    res = diagnose(splits, seed=args.seed)
    today = dt.date.today().isoformat()
    args.report_dir.mkdir(parents=True, exist_ok=True)
    stem = args.report_dir / f"D15-ml-diagnosis-{today}"
    stem.with_suffix(".json").write_text(json.dumps(res, indent=2, default=float) + "\n")
    stem.with_suffix(".md").write_text(report_markdown(res, today))
    print(summary_line("diagnose_ml", cfg.run_id, report=str(stem.with_suffix(".md")),
                       **{f"reading_{c}": v["reading"].split(":")[0] for c, v in res["verdict"].items()}))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
