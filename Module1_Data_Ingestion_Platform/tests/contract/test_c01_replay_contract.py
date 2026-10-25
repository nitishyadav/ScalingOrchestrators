"""M1-T062 — the replay dataset and the committed mock sample satisfy C-01 (M1-F02-AC-03, AC-08)."""
import json
import time
import uuid

import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pytest

from conftest import MODULE_DIR
from csv_factory import make_raw
from ids_contracts import events as ev
from ids_ingest import prepare as pr

SAMPLE = MODULE_DIR / "mocks" / "replay_sample.parquet"
NON_EVENT_COLUMNS = {"row_idx", "source_file", "day"}


def as_event(record: dict) -> dict:
    """A replay row becomes a C-01 event once the producer adds event_id, timestamp and is_injected (C-01 §3.4)."""
    event = {k: v for k, v in record.items() if k not in NON_EVENT_COLUMNS}
    event.update(event_id=str(uuid.uuid4()), timestamp=int(time.time() * 1000), is_injected=False)
    return event


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    d = tmp_path_factory.mktemp("c01") / "data"
    mp = pytest.MonkeyPatch()
    mp.setattr(ev, "CIC_REFERENCE", make_raw(d))
    pr.prepare_all(d)
    yield d
    mp.undo()


def test_dataset_schema_matches_c01(replay):
    dataset = ds.dataset(replay / "replay", format="parquet", partitioning="hive")
    columns = {f.name: str(f.type) for f in dataset.schema}
    assert ev.validate_replay_columns(columns) == []
    assert sorted(dataset.to_table().column("day").unique().to_pylist()) == sorted(ev.REPLAY_DAYS)


def test_row_idx_contiguous_per_day(replay):
    for day in ev.REPLAY_DAYS:
        t = pq.read_table(replay / "replay" / f"day={day}")
        assert t.column("row_idx").to_pylist() == list(range(t.num_rows))


def test_every_row_becomes_a_strict_valid_event(replay):
    table = ds.dataset(replay / "replay", format="parquet", partitioning="hive").to_table()
    for record in table.to_pylist():
        assert ev.validate_event(as_event(record), strict=True) == [], record


def test_manifest_satisfies_c01(replay):
    m = json.loads((replay / "replay" / ev.REPLAY_MANIFEST_NAME).read_text())
    assert ev.validate_manifest(m) == []
    assert m["contract_version"] == ev.CONTRACT_VERSION


@pytest.mark.skipif(not SAMPLE.exists(), reason="mock sample not generated yet (M1-T081)")
def test_committed_mock_sample_satisfies_c01():
    t = pq.read_table(SAMPLE)
    assert ev.validate_replay_columns({f.name: str(f.type) for f in t.schema}) == []
    assert t.num_rows <= pr.SAMPLE_MAX and SAMPLE.stat().st_size <= 1_000_000
    assert set(t.column("label").to_pylist()) == set(ev.CIC_LABELS)   # every CIC label is in the real data
    for record in t.to_pylist():
        assert ev.validate_event(as_event(record), strict=True) == []
