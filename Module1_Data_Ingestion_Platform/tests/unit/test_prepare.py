"""M1-T061 — dataset preparation on synthetic CSVs (M1-F02-AC-02, 04, 05, 06, 07, 08, 10)."""
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from csv_factory import HEADER, default_rows, make_raw, row
from ids_contracts import events as ev
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from ids_ingest import prepare as pr

DEFECTS = [
    row(),
    [""] * len(HEADER),                         # empty_row (CIC style ",,,,")
    [],                                         # empty_row (blank line)
    row()[:5],                                  # wrong_field_count
    row(src=""),                                # missing_field
    row(port="http"),                           # non_numeric
    row(nbytes="NaN"),                          # nan_or_inf
    row(port="Infinity"),                       # nan_or_inf
    row(nbytes="-5"),                           # negative
    row(port="70000"),                          # bad_port
    row(src="999.1.1.1"),                       # bad_ip
    row(label="Bogus"),                         # unknown_label
    row(label="Web Attack \x96 Brute Force"),   # valid, label normalised
    row(label="  BENIGN "),                     # valid, label trimmed
]
EXPECTED_DROPS = {"empty_row": 2, "wrong_field_count": 1, "missing_field": 1, "non_numeric": 1, "nan_or_inf": 2,
                  "negative": 1, "bad_port": 1, "bad_ip": 1, "unknown_label": 1}


def setup_raw(tmp_path, monkeypatch, rows_by_stem=None):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(ev, "CIC_REFERENCE", make_raw(data_dir, rows_by_stem))
    return data_dir


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    return setup_raw(tmp_path, monkeypatch)


def manifest(d):
    return json.loads((d / "replay" / ev.REPLAY_MANIFEST_NAME).read_text())


def day_table(d, day):
    return pq.ParquetFile(d / "replay" / f"day={day}" / "part-00000.parquet").read()   # file only, no hive "day" column


def raw_file(d, stem):
    return d / "raw" / "TrafficLabelling" / f"{stem}{ev.CIC_FILE_SUFFIX}"


# ---- AC-02 cleaning ---------------------------------------------------------------------------
def test_defect_matrix(tmp_path, monkeypatch):
    d = setup_raw(tmp_path, monkeypatch, {"Monday-WorkingHours": DEFECTS})
    pr.prepare_all(d)
    monday = next(i for i in manifest(d)["inputs"] if i["source_file"] == "Monday-WorkingHours")
    assert monday["dropped"] == EXPECTED_DROPS
    assert (monday["data_rows"], monday["valid_rows"]) == (len(DEFECTS), 3)
    labels = day_table(d, "Monday").column("label").to_pylist()
    assert labels == ["BENIGN", "Web Attack - Brute Force", "BENIGN"]


def test_schema_types_and_row_order(data_dir):
    pr.prepare_all(data_dir)
    t = day_table(data_dir, "Thursday")
    assert t.schema.equals(pr.SCHEMA, check_metadata=False)
    assert t.column("row_idx").to_pylist() == list(range(6))
    assert t.column("source_file").to_pylist() == ["Thursday-WorkingHours-Morning-WebAttacks"] * 3 + \
        ["Thursday-WorkingHours-Afternoon-Infilteration"] * 3
    first = t.slice(0, 1).to_pylist()[0]
    assert first == {"row_idx": 0, "source_file": "Thursday-WorkingHours-Morning-WebAttacks", "orig_ts": "3/7/2017 9:00",
                     "src_ip": "172.16.0.1", "dst_ip": "192.168.10.50", "dst_port": 80, "bytes_sent": 100,
                     "syn_flag": 0, "ack_flag": 1, "label": "Web Attack - XSS"}


def test_manifest_is_valid_and_complete(data_dir):
    summary = pr.prepare_all(data_dir)
    m = manifest(data_dir)
    assert ev.validate_manifest(m) == []
    assert m["contract_version"] == ev.CONTRACT_VERSION and m["tool"] == "ids_ingest.prepare"
    assert m["total_rows"] == 24 == summary["total_rows"] and summary["days"] == 5
    assert [i["source_file"] for i in m["inputs"]] == [s for day in ev.REPLAY_DAYS for s in ev.CIC_FILE_ORDER[day]]
    assert all(i["verified"] for i in m["inputs"])
    assert m["days"]["Friday"]["files"] == list(ev.CIC_FILE_ORDER["Friday"])


# ---- AC-04 verification of inputs -----------------------------------------------------------
def test_missing_input_fails(data_dir):
    raw_file(data_dir, "Tuesday-WorkingHours").unlink()
    with pytest.raises(pr.PrepareError, match="Tuesday-WorkingHours"):
        pr.prepare_all(data_dir)
    assert not (data_dir / "replay").exists()


def test_tampered_input_fails_unless_allowed(data_dir):
    with open(raw_file(data_dir, "Monday-WorkingHours"), "a", encoding="latin-1") as fh:
        fh.write(",".join(row(src="10.0.0.9")) + "\n")
    with pytest.raises(pr.PrepareError, match="sha256"):
        pr.prepare_all(data_dir)
    summary = pr.prepare_all(data_dir, allow_unverified=True)
    monday = next(i for i in manifest(data_dir)["inputs"] if i["source_file"] == "Monday-WorkingHours")
    assert monday["verified"] is False and summary["verified_inputs"] == 7


def test_unknown_csv_is_ignored(data_dir):
    (data_dir / "raw" / "TrafficLabelling" / "notes.csv").write_text("x\n")
    assert pr.prepare_all(data_dir)["ignored_files"] == ["notes.csv"]


# ---- AC-05 idempotence and determinism ------------------------------------------------------
def test_noop_then_force_is_deterministic(data_dir):
    assert pr.prepare_all(data_dir)["action"] == "create"
    first = {k: v["content_sha256"] for k, v in manifest(data_dir)["days"].items()}
    assert pr.prepare_all(data_dir)["action"] == "noop"
    assert pr.prepare_all(data_dir, force=True)["action"] == "rebuild"
    assert {k: v["content_sha256"] for k, v in manifest(data_dir)["days"].items()} == first


def test_stale_manifest_triggers_rebuild(data_dir):
    pr.prepare_all(data_dir)
    path = data_dir / "replay" / ev.REPLAY_MANIFEST_NAME
    m = json.loads(path.read_text())
    m["contract_version"] = "0.0.0-old"
    path.write_text(json.dumps(m))
    assert pr.prepare_all(data_dir)["action"] == "rebuild"


# ---- AC-06 atomicity -------------------------------------------------------------------------
def test_failed_run_leaves_previous_dataset_intact(data_dir, monkeypatch):
    pr.prepare_all(data_dir)
    before = (data_dir / "replay" / ev.REPLAY_MANIFEST_NAME).read_text()
    calls = {"n": 0}
    original = pr.RowCleaner.clean

    def flaky(self, cells):
        calls["n"] += 1
        if calls["n"] == 10:
            raise OSError("disk full (simulated)")
        return original(self, cells)

    monkeypatch.setattr(pr.RowCleaner, "clean", flaky)
    with pytest.raises(OSError):
        pr.prepare_all(data_dir, force=True)
    assert (data_dir / "replay" / ev.REPLAY_MANIFEST_NAME).read_text() == before
    assert not [p.name for p in data_dir.iterdir() if p.name.startswith("replay.")]
    assert pr.verify_replay(data_dir) == []


# ---- AC-07 verify-only -----------------------------------------------------------------------
def test_verify_only_passes_on_fresh_dataset(data_dir):
    pr.prepare_all(data_dir)
    assert pr.verify_replay(data_dir) == []


def test_verify_only_detects_dropped_row(data_dir):
    pr.prepare_all(data_dir)
    path = data_dir / "replay" / "day=Friday" / "part-00000.parquet"
    t = pq.ParquetFile(path).read()
    pq.write_table(t.slice(0, t.num_rows - 1), path)
    errors = pr.verify_replay(data_dir)
    assert errors and any("Friday" in e for e in errors)


def test_verify_only_detects_changed_value(data_dir):
    pr.prepare_all(data_dir)
    path = data_dir / "replay" / "day=Monday" / "part-00000.parquet"
    t = pq.ParquetFile(path).read()
    idx = t.schema.get_field_index("bytes_sent")
    t = t.set_column(idx, "bytes_sent", pa.array([999] * t.num_rows, pa.int64()))
    pq.write_table(t, path)
    errors = pr.verify_replay(data_dir)
    assert errors and any("Monday" in e and "content" in e for e in errors)


def test_verify_only_detects_missing_day_file(data_dir):
    pr.prepare_all(data_dir)
    (data_dir / "replay" / "day=Tuesday" / "part-00000.parquet").unlink()
    assert any("Tuesday" in e for e in pr.verify_replay(data_dir))


def test_verify_only_without_dataset(tmp_path):
    assert pr.verify_replay(tmp_path / "nothing")


# ---- AC-08 sample ----------------------------------------------------------------------------
def test_sample_covers_every_label_and_is_byte_identical(data_dir, tmp_path):
    pr.prepare_all(data_dir)
    out = tmp_path / "sample.parquet"
    info = pr.make_sample(data_dir, out)
    t = pq.read_table(out)
    assert set(t.column("label").to_pylist()) == set(manifest(data_dir)["labels"])
    assert t.num_rows == info["sample_rows"] <= pr.SAMPLE_MAX
    assert ev.validate_replay_columns({f.name: str(f.type) for f in t.schema}) == []
    keys = list(zip([ev.REPLAY_DAYS.index(d) for d in t.column("day").to_pylist()], t.column("row_idx").to_pylist()))
    assert keys == sorted(keys)
    first = out.read_bytes()
    pr.make_sample(data_dir, out)
    assert out.read_bytes() == first


def test_sample_respects_per_label_quota(tmp_path, monkeypatch):
    many = [row(src=f"10.0.{i // 250}.{i % 250 + 1}", label="BENIGN") for i in range(60)]
    d = setup_raw(tmp_path, monkeypatch, {"Monday-WorkingHours": many})
    pr.prepare_all(d)
    n_labels = len(manifest(d)["labels"])
    t = pq.read_table(pr.make_sample(d, tmp_path / "s.parquet", max_rows=20)["sample_path"])
    counts = {}
    for lab in t.column("label").to_pylist():
        counts[lab] = counts.get(lab, 0) + 1
    assert t.num_rows <= 20 and max(counts.values()) <= 20 // n_labels and set(counts) == set(manifest(d)["labels"])


# ---- AC-10 CLI ---------------------------------------------------------------------------------
def cli(argv, d, tmp_path, capsys, **kw):
    code = pr.main(argv, env={"IDS_ROOT": str(tmp_path), "DATA_DIR": str(d)}, **kw)
    return code, capsys.readouterr()


def last_json(out):
    return json.loads(out.out.strip().splitlines()[-1])


def test_cli_prepare_verify_sample(data_dir, tmp_path, capsys):
    code, out = cli([], data_dir, tmp_path, capsys)
    s = last_json(out)
    assert code == EXIT_OK and s["command"] == "prepare" and s["action"] == "create"
    assert s["total_rows"] == 24 and s["days"] == 5 and "elapsed_s" in s and "peak_rss_mb" in s and s["dropped"] == {}
    code, out = cli(["--verify-only"], data_dir, tmp_path, capsys)
    assert code == EXIT_OK and last_json(out)["action"] == "verify"
    code, out = cli(["--sample"], data_dir, tmp_path, capsys, sample_out=tmp_path / "m.parquet")
    s = last_json(out)
    assert code == EXIT_OK and s["action"] == "noop" and s["sample_rows"] == 24


def test_cli_verify_failure_exit_1(data_dir, tmp_path, capsys):
    pr.prepare_all(data_dir)
    (data_dir / "replay" / "day=Monday" / "part-00000.parquet").unlink()
    code, out = cli(["--verify-only"], data_dir, tmp_path, capsys)
    assert code == EXIT_RUNTIME_ERROR and "Monday" in out.err


def test_cli_missing_input_exit_1(data_dir, tmp_path, capsys):
    raw_file(data_dir, "Monday-WorkingHours").unlink()
    code, out = cli([], data_dir, tmp_path, capsys)
    assert code == EXIT_RUNTIME_ERROR and "Monday-WorkingHours" in out.err


@pytest.mark.parametrize("argv", [["--bogus"], ["--verify-only", "--force"], ["--verify-only", "--sample"]])
def test_cli_usage_errors_exit_2(argv, data_dir, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli(argv, data_dir, tmp_path, capsys)
    assert exc.value.code == EXIT_USAGE_ERROR


def test_default_rows_helper_is_valid():
    assert all(len(r) == len(HEADER) for r in default_rows("Monday-WorkingHours"))
