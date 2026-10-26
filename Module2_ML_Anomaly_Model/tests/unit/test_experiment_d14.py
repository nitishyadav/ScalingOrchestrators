"""D-14 experiment helpers: derived ratios, flow-level metrics, extended feature output."""
import pandas as pd
import pytest

from ids_contracts import FIXTURES_DIR
from ids_contracts import features as F
from ids_contracts.events import iter_jsonl
from ids_model import experiment_d14 as ex
from ids_model.features import EXTENDED_COLUMNS, build_features


def test_extended_output_keeps_golden_columns_and_counts_attacks():
    events = pd.DataFrame(list(iter_jsonl(FIXTURES_DIR / "events_golden.jsonl")))
    plain, ext = build_features(events), build_features(events, extended=True)
    assert tuple(ext.columns) == F.GOLDEN_COLUMNS + EXTENDED_COLUMNS
    assert ext[list(F.GOLDEN_COLUMNS)].equals(plain)
    assert (ext.loc[~ext["label_attack"], "attack_events"] == 0).all() and (ext.loc[ext["label_attack"], "attack_events"] > 0).all()
    assert (ext["syn_ack_ratio"] - ext["syn_sum"] / (ext["ack_sum"] + 1)).abs().max() < 1e-12


def test_derive_ratios():
    d = ex.derive(pd.DataFrame({"total_bytes": [100], "unique_ports": [5], "event_count": [10], "syn_sum": [10], "ack_sum": [0]}))
    assert d.iloc[0][["bytes_per_flow", "port_ratio", "syn_share", "ack_share"]].tolist() == [10.0, 0.5, 1.0, 0.0]


def test_flow_metrics():
    f = pd.DataFrame({"attack_events": [90, 0, 10], "event_count": [100, 50, 10]})
    m = ex.flow_metrics(f, [True, False, False])
    assert m["precision"] == pytest.approx(0.9) and m["recall"] == pytest.approx(0.9)
    assert m["benign_flow_share_flagged"] == pytest.approx(10 / 60)
