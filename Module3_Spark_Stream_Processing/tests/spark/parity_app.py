"""Golden parity driver (M3-F02-AC-01, M3-F03-AC-01) — runs INSIDE spark-client via spark-submit.

Streams contracts/fixtures/events_golden.jsonl through the job's own transforms (file source, availableNow, update mode),
scores with the given bundle, and prints one JSON line {"features": [...], "scores": [...]} for host-side asserts.
"""
import json
import os
import shutil
import sys
from pathlib import Path

from ids_contracts import FIXTURES_DIR
from ids_contracts import bundle as B
from ids_contracts import features as F
from ids_stream import app

bundle = sys.argv[1]
work = Path(f"/workspace/runtime/tmp/m3-parity-{os.getpid()}")
(work / "in").mkdir(parents=True, exist_ok=True)
shutil.copy(FIXTURES_DIR / "events_golden.jsonl", work / "in" / "events.jsonl")

spark = app.build_spark("m3-parity")
spark.sparkContext.setLogLevel("WARN")
score, _ = app.make_scorer(spark, bundle)
rows = []


def collect(batch_df, batch_id):
    scored = score(app.finalize(batch_df))
    rows.extend(scored.drop("window_start_ts", "window_end_ts").toPandas().to_dict("records"))


agg = app.windowed(app.parse_events(spark.readStream.text(str(work / "in"))))
q = (agg.writeStream.outputMode("update").foreachBatch(collect).option("checkpointLocation", str(work / "ckpt"))
     .trigger(availableNow=True).start())
q.awaitTermination()
spark.stop()
shutil.rmtree(work, ignore_errors=True)


def plain(v):
    return v.item() if hasattr(v, "item") else v


rows = sorted(({k: plain(v) for k, v in r.items()} for r in rows), key=lambda r: (r["window_start"], r["src_ip"]))
print(json.dumps({"features": [{c: r[c] for c in F.GOLDEN_COLUMNS} for r in rows],
                  "scores": [{c: r[c] for c in B.SCORE_COLUMNS} for r in rows]}))
