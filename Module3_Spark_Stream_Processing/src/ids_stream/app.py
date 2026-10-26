"""PySpark driver for the IDS stream job (M3-F01..F04, REPLICA built by M1; canonical owner Kumari Priyanka).

Runs ONLY inside the platform's Spark image, submitted by `python -m ids_stream.job` (ADR-009):
  Kafka (C-01) → parse + validity filter (observed) → watermark 60 s → window(30 s, 10 s) per src_ip (C-02)
  → foreachBatch: features → broadcast IsolationForest via pandas_udf + compiled rules (C-03)
  → upsert ids.window_scores (C-04) → batch stats;  StreamingQueryListener → ids.pipeline_metrics (C-05).
"""
from __future__ import annotations

import argparse
import json
import queue
import signal
import sys
import threading
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as Fn
from pyspark.sql.functions import pandas_udf
from pyspark.sql.streaming import StreamingQueryListener

from ids_contracts import features as F
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import load_runtime_config, summary_line
from ids_stream import spec

CASSANDRA = "org.apache.spark.sql.cassandra"
_SPARK_TYPE = {"text": "string", "int": "int", "bigint": "bigint", "double": "double", "timestamp": "timestamp",
               "boolean": "boolean"}


def build_spark(app_name: str) -> SparkSession:
    return (SparkSession.builder.appName(app_name)
            .config("spark.sql.session.timeZone", "UTC")
            .getOrCreate())


# ---- F01 ingest ----------------------------------------------------------------------------------
def parse_events(raw: DataFrame) -> DataFrame:
    """`raw` has a string column `value` (Kafka value or a JSON-lines text file). Invalid records are dropped and counted."""
    events = raw.select(Fn.from_json(Fn.col("value").cast("string"), spec.EVENT_DDL).alias("e")).select("e.*")
    valid = Fn.coalesce(Fn.expr(spec.VALID_EVENT_SQL), Fn.lit(False))
    observed = events.observe("ingest", Fn.count(Fn.lit(1)).alias("input"),
                              Fn.sum(Fn.when(valid, 0).otherwise(1)).alias("malformed"))
    return observed.where(valid).withColumn("event_time", Fn.expr("timestamp_millis(timestamp)"))


def kafka_source(spark: SparkSession, bootstrap: str, topic: str, starting: str) -> DataFrame:
    return (spark.readStream.format("kafka").option("kafka.bootstrap.servers", bootstrap).option("subscribe", topic)
            .option("startingOffsets", starting).option("failOnDataLoss", "false").load()
            .select(Fn.col("value").cast("string").alias("value")))


# ---- F02 windowed features -----------------------------------------------------------------------
def windowed(events: DataFrame) -> DataFrame:
    aggs = [Fn.expr(sql).alias(name) for name, sql in {**spec.FEATURE_AGG_SQL, **spec.LABEL_AGG_SQL}.items()]
    return (events.withWatermark("event_time", spec.WATERMARK)
            .groupBy(Fn.window("event_time", spec.WINDOW, spec.SLIDE), "src_ip").agg(*aggs))


def finalize(agg: DataFrame) -> DataFrame:
    """Aggregated rows → C-02 columns (+ eval-only labels), with window bounds as timestamps and epoch ms."""
    return agg.select(
        Fn.col("window.start").alias("window_start_ts"), Fn.col("window.end").alias("window_end_ts"),
        Fn.expr("unix_millis(window.start)").alias("window_start"), Fn.expr("unix_millis(window.end)").alias("window_end"),
        "src_ip",
        Fn.col("total_bytes").cast("bigint").alias("total_bytes"),
        Fn.col("unique_ports").cast("int").alias("unique_ports"),
        (Fn.col("syn_sum") / (Fn.col("ack_sum") + 1)).cast("double").alias("syn_ack_ratio"),
        (Fn.col("event_count") / Fn.lit(float(F.WINDOW_S))).cast("double").alias("packet_rate"),
        (Fn.col("total_bytes") / Fn.col("event_count")).cast("double").alias("bytes_per_flow"),     # C-02 0.2.0
        (Fn.col("unique_ports") / Fn.col("event_count")).cast("double").alias("port_ratio"),
        (Fn.col("syn_sum") / Fn.col("event_count")).cast("double").alias("syn_share"),
        Fn.col("event_count").cast("int").alias("event_count"),
        Fn.col("max_event_ts").cast("bigint").alias("max_event_ts"),
        (Fn.expr(" + ".join(spec.LABEL_AGG_SQL)) > 0).alias("label_attack"),
        Fn.expr(spec.label_type_sql()).alias("label_type"),
    )


# ---- F03 hybrid scoring --------------------------------------------------------------------------
def make_scorer(spark: SparkSession, bundle_path: str):
    """Load + validate the C-03 bundle, broadcast the model, return (score_fn, manifest)."""
    import sklearn
    manifest, rules = spec.read_bundle_meta(bundle_path)
    mismatch = [k for k, v in (("sklearn_version", sklearn.__version__), ("numpy_version", np.__version__)) if manifest[k] != v]
    if mismatch:
        raise RuntimeError(f"bundle library versions {[(k, manifest[k]) for k in mismatch]} differ from the image (ADR-009)")
    model_bc = spark.sparkContext.broadcast(joblib.load(Path(bundle_path) / "model.joblib"))
    flag_sql, ids_sql = spec.rules_sql(rules)
    threshold = float(manifest["threshold"])

    if len(F.FEATURE_ORDER) != 4:
        raise RuntimeError("anomaly_score UDF takes exactly 4 model inputs (C-02 FEATURE_ORDER)")

    @pandas_udf("double")
    def anomaly_score(f1: pd.Series, f2: pd.Series, f3: pd.Series, f4: pd.Series) -> pd.Series:   # FEATURE_ORDER
        X = np.column_stack([s.to_numpy(dtype=float) for s in (f1, f2, f3, f4)])
        return pd.Series(-model_bc.value.score_samples(X)) if len(X) else pd.Series([], dtype=float)

    def score(features: DataFrame) -> DataFrame:
        s = features.withColumn("anomaly_score", anomaly_score(*[Fn.col(c) for c in F.FEATURE_ORDER]))
        s = (s.withColumn("ml_flag", Fn.col("anomaly_score") >= Fn.lit(threshold))
             .withColumn("rule_flag", Fn.expr(flag_sql)).withColumn("rule_ids", Fn.expr(ids_sql)))
        return s.withColumn("is_anomaly", Fn.col("ml_flag") | Fn.col("rule_flag"))

    return score, manifest


# ---- F04 sink + metrics --------------------------------------------------------------------------
def to_store(scored: DataFrame, run_id: str, bundle_version: str, detected_ms: int) -> DataFrame:
    cols = {
        "date_bucket": Fn.date_format("window_end_ts", "yyyy-MM-dd"), "hour": Fn.hour("window_end_ts"),
        "window_end": Fn.col("window_end_ts"), "src_ip": Fn.col("src_ip"), "window_start": Fn.col("window_start_ts"),
        "total_bytes": Fn.col("total_bytes"), "unique_ports": Fn.col("unique_ports"), "syn_ack_ratio": Fn.col("syn_ack_ratio"),
        "packet_rate": Fn.col("packet_rate"), "event_count": Fn.col("event_count"), "anomaly_score": Fn.col("anomaly_score"),
        "ml_flag": Fn.col("ml_flag"), "rule_flag": Fn.col("rule_flag"), "rule_ids": Fn.col("rule_ids"),
        "is_anomaly": Fn.col("is_anomaly"), "max_event_ts": Fn.expr("timestamp_millis(max_event_ts)"),
        "detected_at": Fn.expr(f"timestamp_millis({int(detected_ms)})"), "bundle_version": Fn.lit(bundle_version),
        "run_id": Fn.lit(run_id), "label_attack": Fn.col("label_attack"), "label_type": Fn.col("label_type"),
    }
    return scored.select(*[cols[c].alias(c) for c in spec.STORE_COLUMNS])


def _ddl(columns) -> str:
    return ", ".join(f"{c} {_SPARK_TYPE[t]}" for c, t in columns)


def _ts(ms):
    import datetime as dt
    return None if ms is None else dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)


def write_rows(spark: SparkSession, table: str, columns, rows) -> None:
    ts_cols = {c for c, t in columns if t == "timestamp"}
    data = [tuple(_ts(r[c]) if c in ts_cols else r[c] for c, _ in columns) for r in rows]
    (spark.createDataFrame(data, _ddl(columns)).write.format(CASSANDRA)
     .options(keyspace=S.KEYSPACE, table=table).mode("append").save())


class _ProgressListener(StreamingQueryListener):
    """Only enqueues progress; the main thread writes C-05 rows (no Spark jobs inside listener callbacks)."""

    def __init__(self, sink: "queue.Queue"):
        self.sink = sink

    def onQueryStarted(self, event):
        pass

    def onQueryProgress(self, event):
        self.sink.put(json.loads(event.progress.json))

    def onQueryIdle(self, event):
        pass

    def onQueryTerminated(self, event):
        pass


def run(args) -> dict:
    cfg = load_runtime_config()                                    # in-container env: kafka:29092, cassandra
    spark = build_spark(f"ids-stream-{args.run_id}")
    spark.sparkContext.setLogLevel("WARN")
    score, manifest = make_scorer(spark, args.bundle)
    totals = {"batches": 0, "rows_written": 0, "anomalies_written": 0, "metrics_rows": 0, "malformed": 0, "input_rows": 0}
    stash: dict = {}
    progress_q: "queue.Queue" = queue.Queue()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    write_rows(spark, M.RUNS_TABLE, M.RUNS_COLUMNS, [{
        "bucket": M.RUNS_BUCKET, "started_at": int(time.time() * 1000), "run_id": args.run_id,
        "config_json": json.dumps({"topic": args.topic, "trigger": args.trigger, "executors": args.executors,
                                   "starting_offsets": args.starting_offsets, "bundle_version": manifest["bundle_version"],
                                   "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions")})}])

    def process(batch_df: DataFrame, batch_id: int) -> None:
        detected_ms = int(time.time() * 1000)
        out = to_store(score(finalize(batch_df)), args.run_id, manifest["bundle_version"], detected_ms).cache()
        try:
            stats_pdf = out.select(Fn.expr("unix_millis(max_event_ts)").alias("m"), "is_anomaly").toPandas()
            if len(stats_pdf):
                out.write.format(CASSANDRA).options(keyspace=S.KEYSPACE, table=S.TABLE).mode("append").save()
            lat = (detected_ms - stats_pdf["m"]).tolist()
            stash[batch_id] = spec.batch_stats(lat, int(stats_pdf["is_anomaly"].sum()))
            totals["batches"] += 1
            totals["rows_written"] += len(stats_pdf)
            totals["anomalies_written"] += int(stats_pdf["is_anomaly"].sum())
        finally:
            out.unpersist()

    def flush_metrics() -> None:
        rows = []
        while True:
            try:
                p = progress_q.get_nowait()
            except queue.Empty:
                break
            ingest = (p.get("observedMetrics") or {}).get("ingest") or {}
            totals["malformed"] += int(ingest.get("malformed") or 0)
            totals["input_rows"] += int(p.get("numInputRows") or 0)
            rows.append(spec.metrics_row(args.run_id, p, stash.pop(int(p["batchId"]), None), args.executors))
        if rows:
            write_rows(spark, M.METRICS_TABLE, M.METRICS_COLUMNS, rows)
            totals["metrics_rows"] += len(rows)

    spark.streams.addListener(_ProgressListener(progress_q))
    agg = windowed(parse_events(kafka_source(spark, cfg.kafka_bootstrap, args.topic, args.starting_offsets)))
    query = (agg.writeStream.outputMode("update").foreachBatch(process)
             .option("checkpointLocation", args.checkpoint).trigger(processingTime=args.trigger)
             .queryName(f"ids_{args.run_id.replace('-', '_').replace('.', '_')}").start())
    deadline = time.time() + args.await_seconds if args.await_seconds > 0 else None
    while query.isActive and not stop.is_set() and (deadline is None or time.time() < deadline):
        query.awaitTermination(1)
        flush_metrics()
    if query.isActive:
        for _ in range(100):                                        # let the running batch finish (≤ 10 s)
            if not query.status.get("isTriggerActive"):
                break
            time.sleep(0.1)
        query.stop()
    exc = query.exception()
    time.sleep(0.5)
    flush_metrics()
    spark.stop()
    if exc is not None:
        raise RuntimeError(f"streaming query failed: {exc}")
    return {**totals, "bundle_version": manifest["bundle_version"]}


def parse_args(argv):
    p = argparse.ArgumentParser(prog="ids_stream/app.py")
    p.add_argument("--run-id", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--trigger", default="1 second")
    p.add_argument("--executors", type=int, default=2)
    p.add_argument("--bundle", required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--starting-offsets", choices=("latest", "earliest"), default="latest")
    p.add_argument("--await-seconds", type=int, default=0)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = run(args)
    print(summary_line("stream app", args.run_id, **result), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
