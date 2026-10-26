"""M1-T131 — producer throughput (M1-F03-AC-05, NFR-021, NFR-025). Markers `docker` + `perf`.

12,000 ev/s for 60 s at 16 partitions must deliver ≥ 11,760 ev/s with no failures; the single-process ceiling
(--rate 100000 for 20 s) is measured and recorded, not asserted. Results saved to docs/measurements/.
"""
import datetime as dt
import json

import pytest

from conftest import MODULE_DIR
from test_producer_live import new_topic, run_cli

pytestmark = [pytest.mark.docker, pytest.mark.perf]


def test_ac05_producer_throughput():
    topic = new_topic(16)
    code, target, err = run_cli("ids_ingest.producer", "--rate", "12000", "--duration", "60", topic=topic, timeout=300)
    assert code == 0, err
    code, ceiling, err = run_cli("ids_ingest.producer", "--rate", "100000", "--duration", "20", topic=new_topic(16),
                                 timeout=300)
    assert code == 0, err
    result = {"test": "M1-F03-AC-05", "date": dt.datetime.now().isoformat(timespec="seconds"), "partitions": 16,
              "at_12000": {k: target[k] for k in ("sent", "failed", "achieved_rate", "rate_p05", "rate_p50", "rate_p95", "duration_s")},
              "ceiling_rate_100000": {k: ceiling[k] for k in ("sent", "failed", "achieved_rate", "rate_p05", "rate_p50", "duration_s")},
              "target": {"achieved_rate_min": 11760, "failed": 0}}
    result["pass"] = target["achieved_rate"] >= 11760 and target["failed"] == 0
    out = MODULE_DIR / "docs" / "measurements" / f"AC-05-M1-F03-{dt.date.today().isoformat()}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    assert result["pass"], result
