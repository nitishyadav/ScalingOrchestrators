"""Golden parity in the real Spark runtime (M3-F02-AC-01, M3-F03-AC-02). Marker `docker`."""
import json
import math
import subprocess

import pytest

from conftest import DUMMY_BUNDLE, MODULE_DIR, ROOT
from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_stream import job
from ids_stream.spec import container_path

pytestmark = pytest.mark.docker


@pytest.fixture(scope="module")
def parity():
    d = job.Docker()
    container = d.find_spark_client()
    if not container:
        pytest.skip("platform not running")
    zip_path = job.build_zip(ROOT / "runtime" / "build" / "ids_stream.zip")
    cmd = [d.bin, "exec", container, "spark-submit", "--master", "spark://spark-master:7077", "--conf", "spark.cores.max=2",
           "--conf", "spark.executor.cores=1", "--conf", "spark.sql.shuffle.partitions=4",
           "--py-files", container_path(zip_path, ROOT),
           container_path(MODULE_DIR / "tests" / "spark" / "parity_app.py", ROOT), container_path(DUMMY_BUNDLE, ROOT)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, proc.stdout[-3000:] + proc.stderr[-3000:]
    return json.loads([l for l in proc.stdout.splitlines() if l.startswith("{")][-1])


def test_spark_features_equal_golden(parity):
    golden = F.read_feature_csv(FIXTURES_DIR / "features_golden.csv")
    got = parity["features"]
    assert len(got) == len(golden) == 23
    for a, b in zip(got, golden):
        assert F.rows_equal(a, b), (a, b)


def test_spark_scores_equal_golden(parity):
    golden = B.read_scores_csv(FIXTURES_DIR / "scores_golden.csv")
    got = parity["scores"]
    assert len(got) == len(golden)
    for a, b in zip(got, golden):
        assert (a["window_start"], a["src_ip"]) == (b["window_start"], b["src_ip"])
        assert math.isclose(a["anomaly_score"], b["anomaly_score"], rel_tol=0, abs_tol=B.SCORE_TOLERANCE), (a, b)
        assert (a["ml_flag"], a["rule_flag"], a["rule_ids"], a["is_anomaly"]) == \
               (b["ml_flag"], b["rule_flag"], b["rule_ids"], b["is_anomaly"])
