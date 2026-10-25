"""M2-F01 EDA (AC-01..AC-03)."""
import json

import numpy as np
import pandas as pd
import pytest

from conftest import ROOT
from ids_contracts import features as F
from ids_model import eda


def flows():
    return pd.DataFrame({
        "day": ["Monday"] * 4 + ["Friday"] * 6,
        "src_ip": ["10.0.0.1", "10.0.0.2", "10.0.0.1", "10.0.0.3"] + ["172.16.0.1"] * 4 + ["10.0.0.1", "10.0.0.9"],
        "dst_ip": ["8.8.8.8"] * 4 + ["192.168.10.50"] * 4 + ["8.8.8.8"] * 2,
        "label": ["BENIGN"] * 4 + ["DDoS", "DDoS", "DDoS", "PortScan", "BENIGN", "BENIGN"],
    })


def test_flow_profile_and_concentration():
    prof = eda.flow_profile(flows()).set_index("day")
    assert list(prof.index) == ["Monday", "Friday"]                       # C-01 day order
    assert prof.loc["Monday", ["rows", "benign", "attack", "src_ips"]].tolist() == [4, 4, 0, 3]
    assert prof.loc["Friday", "attack"] == 4 and prof.loc["Friday", "attack_share"] == pytest.approx(4 / 6)
    labels = eda.label_counts(flows())
    assert labels.iloc[0].to_dict() == {"label": "BENIGN", "rows": 6} and labels["rows"].sum() == 10
    conc = eda.attack_concentration(flows())
    assert conc["src"][0] == {"ip": "172.16.0.1", "rows": 4, "share": 1.0, "labels": "DDoS,PortScan"}
    assert conc["dst"][0]["ip"] == "192.168.10.50" and conc["attack_rows"] == 4


def windows():
    rng = np.random.default_rng(0)
    n = 200
    attack = np.arange(n) < 40
    df = pd.DataFrame({c: rng.uniform(1, 2, n) for c in F.RULE_FEATURES})
    df["port_ratio"] = np.where(attack, 1.0, 0.1)                       # separates perfectly
    df["syn_share"] = 0.5                                                 # constant: no separation
    df["event_count"] = 10
    df["attack_events"] = np.where(attack, np.where(np.arange(n) < 30, 10, 3), 0)
    df["label_attack"] = attack
    df["label_type"] = np.where(attack, np.where(np.arange(n) < 20, "DDoS", "PortScan"), "BENIGN")
    df["day"] = np.where(np.arange(n) % 2 == 0, "Friday", "Monday")
    return df


def test_window_summary_purity_and_separation():
    w = windows()
    summ = eda.window_summary(w)
    assert summ["per_day"]["Friday"]["windows"] == 100 and sum(d["attack_windows"] for d in summ["per_day"].values()) == 40
    assert summ["per_label"] == {"DDoS": 20, "PortScan": 20}
    pur = eda.purity(w)
    assert pur["attack_windows"] == 40 and pur["share_ge_0.5"] == 0.75 and pur["share_ge_0.99"] == 0.75
    sep = {r["feature"]: r for r in eda.separation(w)}
    assert set(sep) == set(F.RULE_FEATURES)
    assert sep["port_ratio"]["auc"] == 1.0 and sep["port_ratio"]["direction"] == "higher in attacks"
    assert sep["syn_share"]["auc"] == 0.5
    assert sep["port_ratio"]["attack_p50"] == 1.0 and sep["port_ratio"]["benign_p50"] == 0.1


def test_end_to_end_on_replay_sample(tmp_path):
    sample = ROOT / "Module1_Data_Ingestion_Platform" / "mocks" / "replay_sample.parquet"
    out = eda.run(eda.load_sample(sample), tmp_path, date="2026-10-25", source=str(sample))
    md = (tmp_path / "F01-eda-2026-10-25.md").read_text()
    data = json.loads((tmp_path / "F01-eda-2026-10-25.json").read_text())
    assert "Attack concentration" in md and data["flows"]["total_rows"] == 8046
    for name in eda.FIGURES:
        assert (tmp_path / "figures" / f"F01-{name}.png").stat().st_size > 5_000, name
    assert out["figures"] == len(eda.FIGURES)
