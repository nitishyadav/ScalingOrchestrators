"""`python -m ids_model.eda` — M2-F01 EDA and window labelling (REPLICA).

Flow level (C-01 replay rows) and window level (C-02 0.2.0 windows at R_ref, per day). Writes
docs/measurements/F01-eda-<date>.{md,json} and docs/measurements/figures/F01-*.png.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.metrics import roc_auc_score

from ids_contracts import features as F
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config, summary_line
from ids_contracts.events import BENIGN_LABEL, REPLAY_DAYS

from . import MODULE_DIR
from .features import DEFAULT_T0_MS, R_REF, features_from_replay

FLOW_COLUMNS = ["row_idx", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag", "label"]
FIGURES = ("rows-per-day", "attack-labels", "model-inputs-ecdf", "volume-ecdf")
VOLUME_FEATURES = ("packet_rate", "unique_ports")
LOG_FEATURES = {"bytes_per_flow", "syn_ack_ratio", "packet_rate", "unique_ports", "total_bytes"}

# dataviz reference palette, light mode (validated 2026-10-22): slot 1 = benign, slot 2 = attack
BENIGN_C, ATTACK_C = "#2a78d6", "#eb6834"
INK, MUTED, RULE, GRID = "#1f2328", "#59636e", "#d0d7de", "#eef1f4"


# ---- flow level (AC-01) --------------------------------------------------------------------------
def _days(values) -> List[str]:
    present = set(values)
    return [d for d in REPLAY_DAYS if d in present]


def flow_profile(flows: pd.DataFrame) -> pd.DataFrame:
    attack = flows["label"] != BENIGN_LABEL
    g = flows.assign(_attack=attack).groupby("day")
    out = pd.DataFrame({"rows": g.size(), "attack": g["_attack"].sum().astype(int), "src_ips": g["src_ip"].nunique()})
    out["benign"] = out["rows"] - out["attack"]
    out["attack_share"] = out["attack"] / out["rows"]
    out = out.reindex(_days(flows["day"]))
    return out.reset_index()[["day", "rows", "benign", "attack", "attack_share", "src_ips"]]


def label_counts(flows: pd.DataFrame) -> pd.DataFrame:
    c = flows.groupby("label").size().reset_index(name="rows")
    return c.sort_values(["rows", "label"], ascending=[False, True]).reset_index(drop=True)


def attack_concentration(flows: pd.DataFrame, top: int = 5) -> dict:
    att = flows[flows["label"] != BENIGN_LABEL]
    n = len(att)

    def ranked(col):
        g = att.groupby(col)
        rows = g.size().sort_values(ascending=False).head(top)
        return [{"ip": ip, "rows": int(r), "share": r / n, "labels": ",".join(sorted(g.get_group(ip)["label"].unique()))}
                for ip, r in rows.items()]
    return {"attack_rows": n, "src": ranked("src_ip") if n else [], "dst": ranked("dst_ip") if n else [],
            "attack_src_ips": int(att["src_ip"].nunique())}


# ---- window level (AC-02) ------------------------------------------------------------------------
def window_summary(w: pd.DataFrame) -> dict:
    per_day = {}
    for day in _days(w["day"]):
        d = w[w["day"] == day]
        per_day[day] = {"windows": len(d), "attack_windows": int(d["label_attack"].sum()),
                        "attack_share": float(d["label_attack"].mean()) if len(d) else 0.0}
    per_label = w[w["label_attack"]].groupby("label_type").size()
    return {"per_day": per_day, "per_label": {k: int(v) for k, v in per_label.sort_values(ascending=False).items()},
            "windows": len(w), "attack_windows": int(w["label_attack"].sum())}


def purity(w: pd.DataFrame) -> dict:
    a = w[w["label_attack"]]
    p = (a["attack_events"] / a["event_count"]).to_numpy(float)
    if not len(p):
        return {"attack_windows": 0}
    q = np.quantile(p, [0.05, 0.25, 0.5])
    return {"attack_windows": len(p), "p05": float(q[0]), "p25": float(q[1]), "p50": float(q[2]),
            "share_ge_0.5": float((p >= 0.5).mean()), "share_ge_0.99": float((p >= 0.99).mean())}


def separation(w: pd.DataFrame, features: Sequence[str] = F.RULE_FEATURES) -> List[dict]:
    y = w["label_attack"].to_numpy(bool)
    out = []
    for f in features:
        x = w[f].to_numpy(float)
        auc = float(roc_auc_score(y, x)) if 0 < y.sum() < len(y) else None
        row = {"feature": f, "model_input": f in F.FEATURE_ORDER,
               "auc": None if auc is None else max(auc, 1 - auc),
               "direction": None if auc is None else ("higher in attacks" if auc >= 0.5 else "lower in attacks")}
        for cls, m in (("benign", ~y), ("attack", y)):
            q = np.quantile(x[m], [0.05, 0.5, 0.95]) if m.any() else [None] * 3
            row.update({f"{cls}_p05": _num(q[0]), f"{cls}_p50": _num(q[1]), f"{cls}_p95": _num(q[2])})
        out.append(row)
    return sorted(out, key=lambda r: -(r["auc"] or 0))


def _num(v):
    return None if v is None else float(v)


# ---- data ----------------------------------------------------------------------------------------
def _windows(raw: pd.DataFrame, day: str) -> pd.DataFrame:
    return features_from_replay(raw.sort_values("row_idx"), rate=R_REF, t0_ms=DEFAULT_T0_MS, extended=True).assign(day=day)


def load_days(replay_dir: Path, days: Sequence[str] = REPLAY_DAYS) -> Tuple[pd.DataFrame, pd.DataFrame]:
    flows, wins = [], []
    for day in days:
        raw = pq.ParquetFile(Path(replay_dir) / f"day={day}" / "part-00000.parquet").read(columns=FLOW_COLUMNS).to_pandas()
        flows.append(raw[["src_ip", "dst_ip", "label"]].assign(day=day))
        wins.append(_windows(raw, day))
    return pd.concat(flows, ignore_index=True), pd.concat(wins, ignore_index=True)


def load_sample(path: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    raw = pq.ParquetFile(path).read().to_pandas()
    days = _days(raw["day"])
    return (raw[["src_ip", "dst_ip", "label", "day"]].copy(),
            pd.concat([_windows(raw[raw["day"] == d], d) for d in days], ignore_index=True))


# ---- figures -------------------------------------------------------------------------------------
def _style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"axes.edgecolor": RULE, "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED,
                         "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.axisbelow": True, "font.size": 9,
                         "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlelocation": "left",
                         "lines.linewidth": 2, "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight",
                         "figure.facecolor": "white", "axes.facecolor": "white"})
    return plt


def _ecdf(ax, values, color, label):
    x = np.sort(np.asarray(values, float))
    if not len(x):
        return
    idx = np.unique(np.linspace(0, len(x) - 1, min(len(x), 2000)).astype(int))     # ≤ 2,000 points per line
    ax.step(x[idx], (idx + 1) / len(x), where="post", color=color, label=label)


def _ecdf_grid(plt, w: pd.DataFrame, feats: Sequence[str], title: str, path: Path, cols: int = 2):
    rows = (len(feats) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(7.2, 2.6 * rows), squeeze=False)
    att = w["label_attack"].to_numpy(bool)
    for ax, f in zip(axes.flat, feats):
        _ecdf(ax, w.loc[~att, f], BENIGN_C, f"Benign windows (n={(~att).sum():,})")
        _ecdf(ax, w.loc[att, f], ATTACK_C, f"Attack windows (n={att.sum():,})")
        if f in LOG_FEATURES and w[f].max() > 50:                 # wide-range features only; small ranges stay linear
            ax.set_xscale("symlog", linthresh=1)
        ax.set_title(f)
        ax.set_ylabel("Share of windows ≤ x")
        ax.set_ylim(0, 1.02)
    for ax in list(axes.flat)[len(feats):]:
        ax.axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle(title, x=0.01, y=1.06, ha="left", fontweight="bold", fontsize=11)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def figures(prof: pd.DataFrame, labels: pd.DataFrame, w: pd.DataFrame, fig_dir: Path) -> int:
    plt = _style()
    fig_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    y = np.arange(len(prof))[::-1]
    ax.barh(y, prof["benign"], color=BENIGN_C, edgecolor="white", linewidth=2, label="Benign flows", height=0.6)
    ax.barh(y, prof["attack"], left=prof["benign"], color=ATTACK_C, edgecolor="white", linewidth=2, label="Attack flows", height=0.6)
    for yi, (_, r) in zip(y, prof.iterrows()):
        ax.text(r["rows"], yi, f"  {r['rows']:,} ({r['attack_share']:.0%} attack)", va="center", color=MUTED, fontsize=8)
    ax.set_yticks(y, prof["day"])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Flows (rows)")
    ax.set_xlim(0, prof["rows"].max() * 1.35)
    from matplotlib.ticker import EngFormatter
    ax.xaxis.set_major_formatter(EngFormatter(sep=""))
    ax.set_title("Replay dataset: flows per day", pad=22)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    fig.savefig(fig_dir / "F01-rows-per-day.png")
    plt.close(fig)

    att = labels[labels["label"] != BENIGN_LABEL].iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 0.28 * len(att) + 1.0))
    ax.barh(att["label"], att["rows"], color=ATTACK_C, height=0.6)
    for i, r in enumerate(att["rows"]):
        ax.text(r, i, f"  {r:,}", va="center", color=MUTED, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlim(right=att["rows"].max() * 4)                     # room for the value labels
    from matplotlib.ticker import EngFormatter
    ax.xaxis.set_major_formatter(EngFormatter(sep=""))
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Attack flows (log scale)")
    ax.set_title("Attack flows per CIC label")
    fig.savefig(fig_dir / "F01-attack-labels.png")
    plt.close(fig)

    _ecdf_grid(plt, w, F.FEATURE_ORDER, "Model inputs (C-02 0.2.0): benign vs attack windows", fig_dir / "F01-model-inputs-ecdf.png")
    _ecdf_grid(plt, w, VOLUME_FEATURES, "Volume features (no longer model inputs, D-14)", fig_dir / "F01-volume-ecdf.png")
    return len(FIGURES)


# ---- report --------------------------------------------------------------------------------------
def _pct(v):
    return "—" if v is None else f"{v:.1%}"


def _g(v):
    return "—" if v is None else f"{v:,.3g}"


def report_markdown(data: Mapping, date: str) -> str:
    fl, conc, ws, pur = data["flows"], data["concentration"], data["windows"], data["purity"]
    top = conc["src"][0] if conc["src"] else None
    lines = [f"# M2-F01 EDA — replay dataset ({date})", "",
             f"Source: `{data['source']}`. Windows: C-02 0.2.0 at R_ref = {R_REF:,} ev/s, each day replayed from its first row.", "",
             "## Findings", ""]
    if top:
        lines.append(f"- **Attack concentration:** {top['share']:.1%} of {conc['attack_rows']:,} attack flows come from **{top['ip']}** "
                     f"({top['labels']}). There are only {conc['attack_src_ips']} attacking source IPs in total. Per-`src_ip` windows "
                     f"therefore hold very few attack windows ({ws['attack_windows']:,} of {ws['windows']:,}), which bounds window-level precision (D-14).")
    if pur.get("attack_windows"):
        lines.append(f"- **Window label rule** (attack iff ≥ 1 non-benign event, C-02 `window_label`): the median attack window is "
                     f"{pur['p50']:.0%} attack events; {pur['share_ge_0.99']:.0%} are ≥ 99 % attack and {pur['share_ge_0.5']:.0%} are ≥ 50 %. "
                     "Attack windows are almost pure, so the ≥ 1 rule and a majority rule label nearly the same windows. **Keep the rule.**")
    sep = data["separation"]
    if sep and sep[0]["auc"] is not None:
        best = ", ".join(f"`{r['feature']}` {r['auc']:.2f}" for r in sep[:3])
        vol = ", ".join(f"`{r['feature']}` {r['auc']:.2f}" for r in sep if r["feature"] in VOLUME_FEATURES)
        lines.append(f"- **Separation** (single-feature ROC AUC, attack vs benign windows): best {best}; volume features {vol}. "
                     "This is consistent with ADR-012 (rate-invariant model inputs).")
    lines += ["", "## Flows per day", "", "| Day | Flows | Benign | Attack | Attack share | Source IPs |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['day']} | {r['rows']:,} | {r['benign']:,} | {r['attack']:,} | {_pct(r['attack_share'])} | {r['src_ips']:,} |"
              for r in fl["per_day"]]
    lines += ["", "![Flows per day](figures/F01-rows-per-day.png)", "", "## Labels", "", "| Label | Flows |", "|---|---|"]
    lines += [f"| {r['label']} | {r['rows']:,} |" for r in fl["labels"]]
    lines += ["", "![Attack flows per label](figures/F01-attack-labels.png)", "", "## Attack concentration", "",
              "| Source IP | Attack flows | Share | Labels |", "|---|---|---|---|"]
    lines += [f"| {r['ip']} | {r['rows']:,} | {_pct(r['share'])} | {r['labels']} |" for r in conc["src"]]
    lines += ["", "| Destination IP | Attack flows | Share | Labels |", "|---|---|---|---|"]
    lines += [f"| {r['ip']} | {r['rows']:,} | {_pct(r['share'])} | {r['labels']} |" for r in conc["dst"]]
    lines += ["", "## Windows (per src_ip, 30 s / 10 s)", "", "| Day | Windows | Attack windows | Share |", "|---|---|---|---|"]
    lines += [f"| {d} | {v['windows']:,} | {v['attack_windows']:,} | {_pct(v['attack_share'])} |" for d, v in ws["per_day"].items()]
    lines += ["", "| Window label | Attack windows |", "|---|---|"] + [f"| {k} | {v:,} |" for k, v in ws["per_label"].items()]
    if pur.get("attack_windows"):
        lines += ["", f"Purity of attack windows (attack events / events): p05 {pur['p05']:.2f} · p25 {pur['p25']:.2f} · p50 {pur['p50']:.2f}."]
    lines += ["", "## Feature separation", "", "| Feature | Model input | AUC | Direction | Benign p05 / p50 / p95 | Attack p05 / p50 / p95 |",
              "|---|---|---|---|---|---|"]
    lines += [f"| `{r['feature']}` | {'yes' if r['model_input'] else 'no'} | {_g(r['auc'])} | {r['direction'] or '—'} | "
              f"{_g(r['benign_p05'])} / {_g(r['benign_p50'])} / {_g(r['benign_p95'])} | {_g(r['attack_p05'])} / {_g(r['attack_p50'])} / {_g(r['attack_p95'])} |"
              for r in sep]
    lines += ["", "![Model inputs](figures/F01-model-inputs-ecdf.png)", "", "![Volume features](figures/F01-volume-ecdf.png)", ""]
    return "\n".join(lines)


def run(data: Tuple[pd.DataFrame, pd.DataFrame], out_dir: Path, date: Optional[str] = None, source: str = "") -> dict:
    flows, wins = data
    date = date or dt.date.today().isoformat()
    out_dir = Path(out_dir)
    prof, labels = flow_profile(flows), label_counts(flows)
    result = {
        "source": source, "date": date, "r_ref": R_REF,
        "flows": {"total_rows": int(len(flows)), "per_day": prof.to_dict("records"), "labels": labels.to_dict("records")},
        "concentration": attack_concentration(flows), "windows": window_summary(wins), "purity": purity(wins),
        "separation": separation(wins),
    }
    n = figures(prof, labels, wins, out_dir / "figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / f"F01-eda-{date}"
    stem.with_suffix(".json").write_text(json.dumps(result, indent=2, default=lambda v: v.item() if hasattr(v, "item") else str(v)) + "\n")
    stem.with_suffix(".md").write_text(report_markdown(result, date))
    return {"report": str(stem.with_suffix(".md")), "figures": n, "windows": result["windows"]["windows"],
            "attack_windows": result["windows"]["attack_windows"]}


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_model.eda", description="M2-F01 EDA of the replay dataset (replica).")
    p.add_argument("--replay-dir", type=Path, help="default DATA_DIR/replay")
    p.add_argument("--out-dir", type=Path, default=MODULE_DIR / "docs" / "measurements")
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    replay = args.replay_dir or cfg.data_dir / "replay"
    if not (replay / "_manifest.json").is_file():
        print(f"no replay dataset at {replay} (`python -m ids_ingest.prepare` in Module 1)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    out = run(load_days(replay), args.out_dir, source=str(replay))
    print(summary_line("eda", cfg.run_id, **out))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
