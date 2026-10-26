"""M2-F03-AC-04 — training + evaluation on the real CIC-IDS2017 replay dataset (marker `data`, about 10 s)."""
import json

import pytest

from conftest import ROOT
from ids_contracts import bundle as B
from ids_model import train as tr
from ids_model.bundle import Bundle

pytestmark = pytest.mark.data
REPLAY = ROOT / "runtime" / "data" / "replay"
if not (REPLAY / "_manifest.json").exists():
    pytest.skip("replay dataset missing", allow_module_level=True)


def test_training_on_real_data(tmp_path):
    out = tmp_path / "bundle"
    assert tr.main(["--out", str(out), "--report-dir", str(tmp_path)], env={"IDS_ROOT": str(ROOT)}) == 0
    rep = json.loads(next(tmp_path.glob("F03-training-*.json")).read_text())
    assert rep["counts"]["train"] > 10_000 and rep["counts"]["test_attack"] > 0
    assert rep["selection"]["fpr_constraint_met"] is True and rep["targets"]["F2_fpr"]["pass"] is True
    assert set(rep["per_category"]) == {"DDoS", "PortScan"}
    m = json.loads((out / "manifest.json").read_text())
    assert B.validate_manifest(m) == [] and m["bundle_version"] == tr.VERSION
    Bundle.load(out)
