"""`python -m ids_model.experiment_d14` — D-14 feature experiment (REPLICA research tooling, no contract change).

Compares model-input feature sets under the M2-F03 protocol (train Mon 80 % / hold-out Mon 20 % / validation Tue–Thu /
test Fri DDoS + PortScan). Reports window-level metrics, flow-level metrics (window verdict applied to its flows) and
the share of benign traffic inside flagged windows (what decides the event-weighted drift metric, D-12).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from ids_contracts.config import EXIT_OK, load_runtime_config, summary_line

from . import MODULE_DIR
from . import train as tr
from .bundle import DEFAULT_RULES

VARIANTS = {
    "V0-current": ("total_bytes", "unique_ports", "syn_ack_ratio", "packet_rate"),
    "V1-ratios": ("bytes_per_flow", "port_ratio", "syn_share", "ack_share"),
    "V2-ratios+rate": ("bytes_per_flow", "port_ratio", "syn_share", "ack_share", "packet_rate"),
    "V3-ratios+synack": ("bytes_per_flow", "port_ratio", "syn_ack_ratio", "syn_share"),
}


def derive(frame: pd.DataFrame) -> pd.DataFrame:
    """Rate-invariant per-window ratios from the extended C-02 aggregates (needs syn_sum / ack_sum)."""
    n = frame["event_count"].astype(float)
    return frame.assign(bytes_per_flow=frame["total_bytes"] / n, port_ratio=frame["unique_ports"] / n,
                        syn_share=frame["syn_sum"] / n, ack_share=frame["ack_sum"] / n)


def flow_metrics(frame: pd.DataFrame, pred) -> dict:
    """Window verdicts applied to the flows inside each window (eval-only attack_events)."""
    p = np.asarray(pred, bool)
    a = frame["attack_events"].to_numpy(float)
    b = frame["event_count"].to_numpy(float) - a
    tp, fp, fn, tn = a[p].sum(), b[p].sum(), a[~p].sum(), b[~p].sum()
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": float(precision), "recall": float(recall),
            "f1": float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
            "benign_flow_share_flagged": float(fp / (fp + tn)) if fp + tn else 0.0}


def evaluate_variant(splits: Mapping, features: Sequence[str], seed: int = tr.SEED, rules: Mapping = DEFAULT_RULES) -> dict:
    res = tr.train_and_evaluate(splits, seed=seed, rules=rules, features=features)
    thr = res["selection"]["threshold"]
    test = pd.concat(list(splits["test"].values()), ignore_index=True)
    preds = tr.predictions(res["model"], test, thr, rules, features)
    hold_preds = tr.predictions(res["model"], splits["holdout"], thr, rules, features)
    val_preds = tr.predictions(res["model"], splits["validation"], thr, rules, features)
    return {
        "features": list(features), "threshold_percentile": res["selection"]["percentile"],
        "fpr_constraint_met": res["selection"]["fpr_constraint_met"],
        "window": {k: {m: res["test"][k][m] for m in ("precision", "recall", "f1", "fpr")} for k in ("ml", "hybrid")},
        "flow": {k: flow_metrics(test, preds[k]) for k in ("ml", "hybrid")},
        "holdout_benign_flow_share_flagged": flow_metrics(splits["holdout"], hold_preds["hybrid"])["benign_flow_share_flagged"],
        "validation_benign_flow_share_flagged": flow_metrics(splits["validation"], val_preds["hybrid"])["benign_flow_share_flagged"],
        "per_category": res["per_category"],
    }


def run_experiment(splits: Mapping, variants: Mapping = VARIANTS, seed: int = tr.SEED) -> dict:
    derived = {"train": derive(splits["train"]), "holdout": derive(splits["holdout"]),
               "validation": derive(splits["validation"]), "test": {k: derive(v) for k, v in splits["test"].items()}}
    return {name: evaluate_variant(derived, feats, seed) for name, feats in variants.items()}


def report_markdown(results: Mapping, counts: Mapping) -> str:
    lines = [f"# D-14 feature experiment ({dt.date.today().isoformat()})", "",
             "Protocol as M2-F03 (no test leakage). Window = per (30 s window, src_ip). Flow level = each window's verdict applied to its flows.",
             f"Windows: train {counts['train']:,} · hold-out {counts['holdout']:,} · validation {counts['validation']:,} · test {counts['test']:,}", "",
             "| Variant | Model inputs | Window P / R (hybrid) | Flow P / R (hybrid) | Benign flows in flagged windows (test / hold-out / validation) |",
             "|---|---|---|---|---|"]
    for name, r in results.items():
        w, f = r["window"]["hybrid"], r["flow"]["hybrid"]
        lines.append(f"| {name} | {', '.join(r['features'])} | {w['precision']:.3f} / {w['recall']:.3f} | {f['precision']:.3f} / {f['recall']:.3f} | "
                     f"{f['benign_flow_share_flagged']:.1%} / {r['holdout_benign_flow_share_flagged']:.1%} / {r['validation_benign_flow_share_flagged']:.1%} |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    cfg = load_runtime_config(env=env)
    splits = tr.load_splits(cfg.data_dir / "replay", extended=True)
    counts = {"train": len(splits["train"]), "holdout": len(splits["holdout"]), "validation": len(splits["validation"]),
              "test": sum(len(v) for v in splits["test"].values())}
    results = run_experiment(splits)
    out = MODULE_DIR / "docs" / "measurements" / f"D14-experiment-{dt.date.today().isoformat()}"
    out.with_suffix(".json").write_text(json.dumps({"counts": counts, "results": results}, indent=2, default=float) + "\n")
    out.with_suffix(".md").write_text(report_markdown(results, counts))
    best = max(results, key=lambda k: results[k]["flow"]["hybrid"]["f1"])
    print(summary_line("experiment d14", cfg.run_id, variants=list(results), best_by_flow_f1=best, report=str(out.with_suffix(".md"))))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
