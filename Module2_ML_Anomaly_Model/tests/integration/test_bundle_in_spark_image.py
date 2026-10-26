"""M2-F04-AC-05 — cross-environment check (risk R3): the bundle trained on the host (Python 3.11) loads inside the
Spark image (`spark-client`, Python 3.10, same pins) and reproduces scores_golden.csv within 1e-9. Marker `docker`."""
import json
import math
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT
from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B

pytestmark = pytest.mark.docker
DOCKER = "/opt/homebrew/bin/docker" if Path("/opt/homebrew/bin/docker").exists() else "docker"

SCRIPT = r"""
import json, sys
sys.path.insert(0, "/workspace/Module2_ML_Anomaly_Model/src")
import sklearn, numpy, platform
from ids_model.bundle import Bundle, golden_score_rows
rows = golden_score_rows(Bundle.load("/workspace/Module2_ML_Anomaly_Model/mocks/dummy_bundle"))
print(json.dumps({"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": numpy.__version__, "rows": rows}))
"""


def test_bundle_scores_identically_inside_spark_client():
    if subprocess.run([DOCKER, "inspect", "ids-spark-client-1"], capture_output=True).returncode != 0:
        pytest.skip("platform not running (spark-client container missing)")
    proc = subprocess.run([DOCKER, "exec", "-i", "ids-spark-client-1", "python3", "-"], input=SCRIPT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["python"].startswith("3.10") and result["sklearn"] == "1.5.2" and result["numpy"] == "1.26.4"
    golden = B.read_scores_csv(FIXTURES_DIR / "scores_golden.csv")
    assert len(result["rows"]) == len(golden) == 23
    for a, b in zip(result["rows"], golden):
        assert math.isclose(a["anomaly_score"], b["anomaly_score"], rel_tol=0, abs_tol=B.SCORE_TOLERANCE)
        assert (a["ml_flag"], a["rule_flag"], a["rule_ids"], a["is_anomaly"]) == \
               (b["ml_flag"], b["rule_flag"], b["rule_ids"], b["is_anomaly"])
