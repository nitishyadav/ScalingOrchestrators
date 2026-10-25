"""M1-T063 — preparation on the real CIC-IDS2017 files (M1-F02-AC-01, 05, 07, 08, 09). Marker `data`.

Run with:  make data-test     (rebuilds runtime/data/replay twice, about 1–2 min)
"""
import datetime as dt
import json
import os
import subprocess
import sys

import pyarrow.parquet as pq
import pytest

from conftest import MODULE_DIR, ROOT
from ids_contracts import events as ev

pytestmark = pytest.mark.data
RAW = ROOT / "runtime" / "data" / "raw" / "TrafficLabelling"
REPLAY = ROOT / "runtime" / "data" / "replay"
SAMPLE = MODULE_DIR / "mocks" / "replay_sample.parquet"

if not all((RAW / f"{s}{ev.CIC_FILE_SUFFIX}").exists() for s in ev.CIC_REFERENCE):
    pytest.skip("real raw CSVs not present in runtime/data/raw/TrafficLabelling", allow_module_level=True)

# Label totals measured on 2026-10-21 (C-01 §3.2 reference table)
EXPECTED_LABELS = {
    "BENIGN": 2_273_097, "DoS Hulk": 231_073, "PortScan": 158_930, "DDoS": 128_027, "DoS GoldenEye": 10_293,
    "FTP-Patator": 7_938, "SSH-Patator": 5_897, "DoS slowloris": 5_796, "DoS Slowhttptest": 5_499, "Bot": 1_966,
    "Web Attack - Brute Force": 1_507, "Web Attack - XSS": 652, "Infiltration": 36, "Web Attack - Sql Injection": 21,
    "Heartbleed": 11,
}


def prepare(*args):
    proc = subprocess.run([sys.executable, "-m", "ids_ingest.prepare", *args], capture_output=True, text=True,
                          cwd=MODULE_DIR, env={**os.environ, "IDS_ROOT": str(ROOT)}, timeout=900)
    summary = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None
    return proc.returncode, summary, proc.stderr


def manifest():
    return json.loads((REPLAY / ev.REPLAY_MANIFEST_NAME).read_text())


@pytest.fixture(scope="module")
def first_run():
    return prepare("--force")


def test_ac01_full_dataset(first_run):
    code, s, err = first_run
    assert code == 0, err
    assert s["total_rows"] == ev.CIC_TOTAL_VALID_ROWS == 2_830_743 and s["days"] == 5
    assert s["dropped"] == {"empty_row": 288_602}
    m = manifest()
    for item in m["inputs"]:
        assert item["verified"] is True
        assert item["valid_rows"] == ev.CIC_REFERENCE[item["source_file"]][1], item["source_file"]
    assert m["labels"] == EXPECTED_LABELS
    assert {d: v["content_sha256"] for d, v in m["days"].items()} == ev.REPLAY_CONTENT_SHA256   # C-01 §2.2 reference


def test_ac07_verify_only_on_real_data(first_run):
    code, s, err = prepare("--verify-only")
    assert code == 0 and s["action"] == "verify", err


def test_ac05_rerun_is_noop_and_force_is_deterministic(first_run):
    hashes = {d: v["content_sha256"] for d, v in manifest()["days"].items()}
    assert prepare()[1]["action"] == "noop"
    code, s, err = prepare("--force")
    assert code == 0 and s["action"] == "rebuild", err
    assert {d: v["content_sha256"] for d, v in manifest()["days"].items()} == hashes


def test_ac08_mock_sample(first_run):
    code, s, err = prepare("--sample")
    assert code == 0, err
    t = pq.read_table(SAMPLE)
    assert t.num_rows == s["sample_rows"] <= 10_000
    assert set(t.column("label").to_pylist()) == set(EXPECTED_LABELS)
    assert SAMPLE.stat().st_size <= 1_000_000
    first = SAMPLE.read_bytes()
    prepare("--sample")
    assert SAMPLE.read_bytes() == first


def test_ac09_performance_measured(first_run):
    code, s, _ = first_run
    size_mb = sum(p.stat().st_size for p in REPLAY.rglob("*.parquet")) / 1e6
    result = {"test": "M1-F02-AC-09", "date": dt.datetime.now().isoformat(timespec="seconds"),
              "rows": s["total_rows"], "elapsed_s": s["elapsed_s"], "peak_rss_mb": s["peak_rss_mb"],
              "replay_size_mb": round(size_mb, 1), "targets": {"elapsed_s": 300, "peak_rss_mb": 2048, "replay_size_mb": 300}}
    result["pass"] = s["elapsed_s"] <= 300 and s["peak_rss_mb"] <= 2048 and size_mb <= 300
    out = MODULE_DIR / "docs" / "measurements" / f"AC-09-M1-F02-{dt.date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    assert result["pass"], result
