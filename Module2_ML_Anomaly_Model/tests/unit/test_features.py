"""M2-F02 reference feature builder (AC-02, AC-03)."""
import pandas as pd

from conftest import ROOT
from ids_contracts import FIXTURES_DIR
from ids_contracts import features as F
from ids_contracts.events import iter_jsonl
from ids_model import features as mf

SAMPLE = ROOT / "Module1_Data_Ingestion_Platform" / "mocks" / "replay_sample.parquet"


def golden_events():
    return pd.DataFrame(list(iter_jsonl(FIXTURES_DIR / "events_golden.jsonl")))


def test_labels_never_change_features():
    df = golden_events()
    a = mf.build_features(df)
    b = mf.build_features(df.assign(label="DDoS"))
    assert a[list(F.KEY_COLUMNS + F.FEATURE_ORDER + F.AUX_COLUMNS)].equals(b[list(F.KEY_COLUMNS + F.FEATURE_ORDER + F.AUX_COLUMNS)])
    assert not b["label_attack"].eq(a["label_attack"]).all()


def test_empty_input():
    out = mf.build_features(pd.DataFrame(columns=["timestamp", "src_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag", "label"]))
    assert out.empty and tuple(out.columns) == F.GOLDEN_COLUMNS


def test_without_labels_eval_columns_default_benign():
    out = mf.build_features(golden_events().drop(columns=["label"]))
    assert not out["label_attack"].any() and set(out["label_type"]) == {"BENIGN"}


def test_replay_timestamps():
    ts = mf.replay_timestamps(12, 1_767_225_600_000, 5000)
    assert list(ts[:6]) == [1_767_225_600_000] * 5 + [1_767_225_600_001]
    assert all(b >= a for a, b in zip(ts, ts[1:]))
    assert list(ts) == [F.replay_timestamp(i, 1_767_225_600_000, 5000) for i in range(12)]


def test_features_from_replay_sample_are_valid():
    df = pd.read_parquet(SAMPLE)
    out = mf.features_from_replay(df, rate=5000, t0_ms=1_767_225_600_000)
    assert len(out) > 0
    rows = mf.to_records(out)
    assert all(F.validate_feature_row(r) == [] for r in rows)
    assert sum(r["event_count"] for r in rows) == 3 * len(df)
