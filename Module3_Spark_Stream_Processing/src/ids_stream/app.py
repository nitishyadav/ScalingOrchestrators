"""PySpark driver for the IDS stream job (M3-F01..F04). Owner: Kumari Priyanka.

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


# ---- F01 ingest (M3-FR-001, M3-FR-002, M3-FR-003) -----------------------------------------------

def kafka_source(spark: SparkSession, bootstrap: str, topic: str, starting: str) -> DataFrame:
    """Open a Kafka readStream for the C-01 topic and return the raw value column as a string."""
    return (
        spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", bootstrap)
            .option("subscribe", topic)
            .option("startingOffsets", starting)   # "latest" (live) or "earliest" (replay / tests)
            .option("failOnDataLoss", "false")      # C-01 §4: at-least-once; gaps must not crash the job
            .load()
            .select(Fn.col("value").cast("string").alias("value"))
    )


def parse_events(raw: DataFrame) -> DataFrame:
    """Parse C-01 JSON events, count malformed records, filter valid rows, add event_time for windowing.

    `raw` must have a string column `value` (Kafka message value or a JSON-lines text file for tests).
    Invalid records are dropped silently and counted via the 'ingest' observe() metric (M3-FR-002).
    The 'event_time' column is a Spark TimestampType derived from the C-01 `timestamp` (epoch ms),
    used by the C-02 watermark and window grouping in F02 (M3-FR-003).
    """
    # Step 1: parse the JSON value into a struct using the C-01 DDL, then flatten into columns.
    # from_json returns null for the whole struct when the value is not valid JSON — those rows
    # pass through with all-null fields and are caught by the validity filter below.
    events = (
        raw
        .select(Fn.from_json(Fn.col("value"), spec.EVENT_DDL).alias("e"))
        .select("e.*")
    )

    # Step 2: build the validity expression (null-safe: coalesce handles all-null rows from failed parses).
    valid = Fn.coalesce(Fn.expr(spec.VALID_EVENT_SQL), Fn.lit(False))

    # Step 3: observe input and malformed counts BEFORE filtering so the metrics capture every record.
    observed = events.observe(
        "ingest",
        Fn.count(Fn.lit(1)).alias("input"),
        Fn.sum(Fn.when(valid, 0).otherwise(1)).alias("malformed"),
    )

    # Step 4: drop invalid rows and convert timestamp (epoch ms) → Spark TimestampType for windowing.
    return (
        observed
        .where(valid)
        .withColumn("event_time", Fn.expr("timestamp_millis(timestamp)"))
    )


# ---- F02 windowed features (M3-FR-011, M3-FR-012, M3-FR-013) ------------------------------------

def windowed(events: DataFrame) -> DataFrame:
    """Apply 60 s watermark, group by sliding window (30 s / 10 s) and src_ip, run all C-02 aggregations.

    withWatermark must come before groupBy so Spark registers the watermark on the stream before
    creating the stateful aggregation.  The 60 s watermark keeps the 47 s late event in the golden
    fixture (events_golden.jsonl) inside its window — tightening it would break golden parity.
    """
    aggs = [
        Fn.expr(sql).alias(name)
        for name, sql in {**spec.FEATURE_AGG_SQL, **spec.LABEL_AGG_SQL}.items()
    ]
    return (
        events
        .withWatermark("event_time", spec.WATERMARK)
        .groupBy(Fn.window("event_time", spec.WINDOW, spec.SLIDE), "src_ip")
        .agg(*aggs)
    )


def finalize(agg: DataFrame) -> DataFrame:
    """Convert raw aggregates into the full C-02 feature row (GOLDEN_COLUMNS order).

    The groupBy(window(...)) produces a struct column `window` with fields .start and .end
    (both Spark TimestampType).  We expose them in two forms:
      - window_start_ts / window_end_ts  → Spark Timestamp, needed by the Cassandra sink (F04)
      - window_start / window_end        → epoch milliseconds (BIGINT), stored in C-04 and in the golden fixture

    Derived features (C-02 §3):
      syn_ack_ratio  = syn_sum  / (ack_sum + 1)          avoids div-by-zero; high value → SYN flood
      packet_rate    = event_count / WINDOW_S (30)        flows per second in the window
      bytes_per_flow = total_bytes / event_count          rate-invariant (ADR-012)
      port_ratio     = unique_ports / event_count         1.0 = every flow hits a new port → port scan
      syn_share      = syn_sum / event_count              fraction of flows that sent a SYN

    label_attack and label_type are eval-only (ADR-007) and must never feed into scoring (Art. VII).
    """
    # label_attack: True if any attack-label counter in this window is > 0
    any_attack = Fn.expr(" + ".join(spec.LABEL_AGG_SQL)) > 0

    return agg.select(
        # Window bounds — both as Spark Timestamp (for Cassandra) and epoch ms (for golden / C-04)
        Fn.col("window.start").alias("window_start_ts"),
        Fn.col("window.end").alias("window_end_ts"),
        Fn.expr("unix_millis(window.start)").alias("window_start"),
        Fn.expr("unix_millis(window.end)").alias("window_end"),

        # Group key
        Fn.col("src_ip"),

        # BASE_FEATURES (C-02 §3, stored in C-04)
        Fn.col("total_bytes").cast("bigint"),
        Fn.col("unique_ports").cast("int"),
        (Fn.col("syn_sum") / (Fn.col("ack_sum") + 1)).cast("double").alias("syn_ack_ratio"),
        (Fn.col("event_count") / Fn.lit(float(F.WINDOW_S))).cast("double").alias("packet_rate"),

        # RATIO_FEATURES (C-02 0.2.0 / ADR-012 — rate-invariant, used as model inputs)
        (Fn.col("total_bytes") / Fn.col("event_count")).cast("double").alias("bytes_per_flow"),
        (Fn.col("unique_ports") / Fn.col("event_count")).cast("double").alias("port_ratio"),
        (Fn.col("syn_sum") / Fn.col("event_count")).cast("double").alias("syn_share"),

        # AUX columns
        Fn.col("event_count").cast("int"),
        Fn.col("max_event_ts").cast("bigint"),

        # EVAL-ONLY columns (Art. VII — never read by scoring path)
        any_attack.alias("label_attack"),
        Fn.expr(spec.label_type_sql()).alias("label_type"),
    )


# ---- F03 hybrid scoring (M3-FR-021, M3-FR-022, M3-FR-023) ---------------------------------------

def make_scorer(spark: SparkSession, bundle_path: str):
    """Load the C-03 bundle, broadcast the Isolation Forest, return (score_fn, manifest).

    Steps (C-03 §5 decision semantics):
      1. Read and validate manifest.json + rules.yaml from bundle_path.
      2. Guard that sklearn and numpy versions match the bundle (ADR-009) — a version mismatch
         means the pickled model may behave differently or fail to load on workers.
      3. Broadcast model.joblib to all Spark executors once (avoids re-serialising per task).
      4. Compile rules.yaml → Spark SQL expressions (rule_flag_sql, rule_ids_sql).
      5. Define a vectorised pandas_udf that scores a whole partition at once using numpy arrays.
      6. Return a score() closure that adds anomaly_score, ml_flag, rule_flag, rule_ids, is_anomaly.
    """
    import sklearn

    # Step 1: load and validate the bundle from disk (raises BundleMetaError if anything is wrong).
    manifest, rules = spec.read_bundle_meta(bundle_path)

    # Step 2: version guard (ADR-009). The model is pickled, so sklearn/numpy must be identical
    # between training (M2, Colab) and scoring (M3, Spark image).
    version_checks = [
        ("sklearn_version", sklearn.__version__),
        ("numpy_version",   np.__version__),
    ]
    mismatch = [key for key, installed in version_checks if manifest[key] != installed]
    if mismatch:
        raise RuntimeError(
            f"bundle library versions {[(k, manifest[k]) for k in mismatch]} "
            f"differ from the Spark image (ADR-009) — retrain or rebuild the image"
        )

    # Step 3: broadcast the model. The driver loads model.joblib once, serialises it once,
    # and sends it to each executor where it is cached in memory for all tasks in the job.
    model_bc = spark.sparkContext.broadcast(joblib.load(Path(bundle_path) / "model.joblib"))

    # Step 4: compile rules.yaml to SQL. Thresholds and conditions live only in the bundle (Art. VII).
    flag_sql, ids_sql = spec.rules_sql(rules)
    threshold = float(manifest["threshold"])

    # Sanity check: the UDF is hard-coded for 4 inputs matching C-02 FEATURE_ORDER.
    if len(F.FEATURE_ORDER) != 4:
        raise RuntimeError(
            f"FEATURE_ORDER has {len(F.FEATURE_ORDER)} features but the UDF expects exactly 4 (C-02)"
        )

    # Step 5: vectorised pandas_udf for anomaly scoring.
    # Each argument is a pd.Series for one feature column (in FEATURE_ORDER).
    # np.column_stack assembles them into an (n_rows, 4) matrix and score_samples scores all rows
    # in one call — much faster than a row-by-row Python UDF.
    # sklearn's score_samples returns negative scores (more negative = more anomalous); C-03 flips
    # this so that higher anomaly_score = more suspicious.
    @pandas_udf("double")
    def _anomaly_score_udf(
        f1: pd.Series, f2: pd.Series, f3: pd.Series, f4: pd.Series
    ) -> pd.Series:
        # FEATURE_ORDER: bytes_per_flow, port_ratio, syn_ack_ratio, syn_share
        X = np.column_stack([s.to_numpy(dtype=float) for s in (f1, f2, f3, f4)])
        if len(X) == 0:
            return pd.Series([], dtype=float)
        return pd.Series(-model_bc.value.score_samples(X))

    # Step 6: score() applies the UDF and rule SQL to a feature DataFrame and returns it enriched
    # with the 5 output columns defined in C-03 §5.
    def score(features: DataFrame) -> DataFrame:
        # anomaly_score via broadcast model (ML path)
        scored = features.withColumn(
            "anomaly_score",
            _anomaly_score_udf(*[Fn.col(c) for c in F.FEATURE_ORDER]),
        )
        # ml_flag: anomaly_score >= threshold (threshold comes from the bundle manifest only)
        scored = scored.withColumn("ml_flag", Fn.col("anomaly_score") >= Fn.lit(threshold))
        # rule_flag and rule_ids: pure SQL compiled from rules.yaml (rule path)
        scored = scored.withColumn("rule_flag", Fn.expr(flag_sql))
        scored = scored.withColumn("rule_ids",  Fn.expr(ids_sql))
        # is_anomaly: True if either flag is True (hybrid = union of both detectors)
        scored = scored.withColumn("is_anomaly", Fn.col("ml_flag") | Fn.col("rule_flag"))
        return scored

    return score, manifest


# ---- F04 sink, metrics and recovery (M3-FR-031, M3-FR-032, M3-FR-033, M3-FR-034) ---------------

def to_store(scored: DataFrame, run_id: str, bundle_version: str, detected_ms: int) -> DataFrame:
    """Select and derive every C-04 column from the scored feature DataFrame.

    C-04 1.0.0-rc.1 partition key is (date_bucket, bucket) where:
      bucket = floor((hour * 60 + minute) / 5)   → 5-minute index 0..287 (M4-ADR-001)
    spark.sql.session.timeZone=UTC ensures date_format and hour/minute extract in UTC.

    detected_ms is captured at the start of process() before the Cassandra write so that
    latency = detected_at − max_event_ts measures end-to-end processing time (D-01).
    """
    cols = {
        # Partition key (C-04 §4, M4-ADR-001)
        "date_bucket":    Fn.date_format("window_end_ts", "yyyy-MM-dd"),
        "bucket":         Fn.floor(
                              (Fn.hour("window_end_ts") * 60 + Fn.minute("window_end_ts")) / 5
                          ).cast("int"),

        # Clustering key
        "window_end":     Fn.col("window_end_ts"),
        "src_ip":         Fn.col("src_ip"),

        # Window bounds and base features (C-02 BASE_FEATURES stored in C-04; ratio features are not stored)
        "window_start":   Fn.col("window_start_ts"),
        "total_bytes":    Fn.col("total_bytes"),
        "unique_ports":   Fn.col("unique_ports"),
        "syn_ack_ratio":  Fn.col("syn_ack_ratio"),
        "packet_rate":    Fn.col("packet_rate"),
        "event_count":    Fn.col("event_count"),

        # Scoring output (C-03 §5)
        "anomaly_score":  Fn.col("anomaly_score"),
        "ml_flag":        Fn.col("ml_flag"),
        "rule_flag":      Fn.col("rule_flag"),
        "rule_ids":       Fn.col("rule_ids"),
        "is_anomaly":     Fn.col("is_anomaly"),

        # Timing columns
        "max_event_ts":   Fn.expr("timestamp_millis(max_event_ts)"),    # epoch ms → Timestamp
        "detected_at":    Fn.expr(f"timestamp_millis({int(detected_ms)})"),

        # Provenance
        "bundle_version": Fn.lit(bundle_version),
        "run_id":         Fn.lit(run_id),

        # Eval-only (ADR-007) — stored for offline evaluation (F2, F3, E3) only
        "label_attack":   Fn.col("label_attack"),
        "label_type":     Fn.col("label_type"),
    }
    return scored.select(*[cols[c].alias(c) for c in spec.STORE_COLUMNS])


def _ddl(columns) -> str:
    """Build a Spark schema DDL string from a C-04/C-05 columns tuple."""
    return ", ".join(f"{c} {_SPARK_TYPE[t]}" for c, t in columns)


def _ts(ms):
    """Convert epoch ms (int) to a timezone-aware datetime for Spark/Cassandra timestamp columns."""
    import datetime as dt
    return None if ms is None else dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)


def write_rows(spark: SparkSession, table: str, columns, rows) -> None:
    """Write a list of plain Python dicts to a Cassandra table via a small Spark DataFrame.

    Used for metrics and runs rows, which are built on the driver (not in foreachBatch).
    Timestamp columns (epoch ms ints) are converted to datetime objects because the
    Cassandra connector requires Python datetime, not raw integers.
    """
    ts_cols = {c for c, t in columns if t == "timestamp"}
    data = [
        tuple(_ts(r[c]) if c in ts_cols else r[c] for c, _ in columns)
        for r in rows
    ]
    (spark.createDataFrame(data, _ddl(columns))
     .write.format(CASSANDRA)
     .options(keyspace=S.KEYSPACE, table=table)
     .mode("append")
     .save())


class _ProgressListener(StreamingQueryListener):
    """Capture Spark StreamingQueryProgress events and hand them to the main thread via a queue.

    Spark calls listener callbacks from a background thread. Starting a Spark job (e.g. writing
    a DataFrame) inside a callback deadlocks. This listener only enqueues the progress JSON;
    the main thread drains the queue in flush_metrics() and does the actual Cassandra write.
    """

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
    """Entry point for the stream job inside the Spark image (called by app.py main).

    Wires F01–F04 together:
      kafka_source → parse_events → windowed
          → writeStream(outputMode=update, foreachBatch=process, checkpoint=...)
    Metrics are written after each batch via flush_metrics() in the main loop.
    Stops gracefully on SIGTERM / SIGINT / --await-seconds expiry (M3-FR-034).
    Checkpointing at CHECKPOINT_DIR/<run_id> enables worker-restart recovery (M3-FR-033).
    """
    cfg   = load_runtime_config()          # reads C-06 env vars: KAFKA_BOOTSTRAP_SERVERS, CASSANDRA_HOST, etc.
    spark = build_spark(f"ids-stream-{args.run_id}")
    spark.sparkContext.setLogLevel("WARN")

    score, manifest = make_scorer(spark, args.bundle)

    # Running totals returned in the summary line at exit.
    totals = {
        "batches": 0, "rows_written": 0, "anomalies_written": 0,
        "metrics_rows": 0, "malformed": 0, "input_rows": 0,
    }

    # stash[batch_id] = batch_stats dict; populated in process(), consumed in flush_metrics().
    # The listener fires after process() returns, so this dict bridges the two callbacks.
    stash: dict = {}
    progress_q: queue.Queue = queue.Queue()
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    # One ids.runs row at job start — lets M4 know which run is live and what its config is.
    write_rows(spark, M.RUNS_TABLE, M.RUNS_COLUMNS, [{
        "bucket":      M.RUNS_BUCKET,
        "started_at":  int(time.time() * 1000),
        "run_id":      args.run_id,
        "config_json": json.dumps({
            "topic":              args.topic,
            "trigger":            args.trigger,
            "executors":          args.executors,
            "starting_offsets":   args.starting_offsets,
            "bundle_version":     manifest["bundle_version"],
            "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
        }),
    }])

    def process(batch_df: DataFrame, batch_id: int) -> None:
        """foreachBatch callback: finalize → score → shape → cache → write → record latency stats.

        detected_ms is captured before any computation so that latency includes the full
        processing cost of this batch, not just the Cassandra write time (D-01).
        cache() + unpersist() avoids recomputing the F01→F03 chain twice (once for
        toPandas stats, once for the Cassandra write). unpersist() is in finally so it
        always runs even if the write fails.
        """
        detected_ms = int(time.time() * 1000)   # capture before compute — D-01 latency start

        # Apply F02 finalize + F03 scoring + F04 C-04 column shaping, then cache.
        out = to_store(
            score(finalize(batch_df)),
            args.run_id, manifest["bundle_version"], detected_ms,
        ).cache()

        try:
            # Pull max_event_ts and is_anomaly to the driver for latency and anomaly counting.
            stats_pdf = out.select(
                Fn.expr("unix_millis(max_event_ts)").alias("m"),
                "is_anomaly",
            ).toPandas()

            if len(stats_pdf):
                # Upsert: update mode re-emits windows as they change; the latest write wins.
                out.write.format(CASSANDRA).options(
                    keyspace=S.KEYSPACE, table=S.TABLE
                ).mode("append").save()

            # Latency = detected_at − max_event_ts for each row written (C-05 §3, D-01).
            latencies = (detected_ms - stats_pdf["m"]).tolist()
            stash[batch_id] = spec.batch_stats(latencies, int(stats_pdf["is_anomaly"].sum()))

            totals["batches"]          += 1
            totals["rows_written"]     += len(stats_pdf)
            totals["anomalies_written"] += int(stats_pdf["is_anomaly"].sum())

        finally:
            out.unpersist()   # release cached data even if the write failed

    def flush_metrics() -> None:
        """Drain the listener queue and write one C-05 pipeline_metrics row per batch.

        Correlates each Spark progress event with its batch_stats from stash (keyed by batch_id).
        Also accumulates malformed event counts from the 'ingest' observe() metric (F01).
        """
        rows = []
        while True:
            try:
                p = progress_q.get_nowait()
            except queue.Empty:
                break
            ingest = (p.get("observedMetrics") or {}).get("ingest") or {}
            totals["malformed"]   += int(ingest.get("malformed") or 0)
            totals["input_rows"]  += int(p.get("numInputRows") or 0)
            rows.append(
                spec.metrics_row(args.run_id, p, stash.pop(int(p["batchId"]), None), args.executors)
            )
        if rows:
            write_rows(spark, M.METRICS_TABLE, M.METRICS_COLUMNS, rows)
            totals["metrics_rows"] += len(rows)

    # Register listener before starting the query so no progress events are missed.
    spark.streams.addListener(_ProgressListener(progress_q))

    # Build the full pipeline: F01 → F02 → writeStream(F03+F04 in foreachBatch).
    agg = windowed(parse_events(
        kafka_source(spark, cfg.kafka_bootstrap, args.topic, args.starting_offsets)
    ))
    query = (
        agg.writeStream
           .outputMode("update")                              # D-01: re-emit windows as they change
           .foreachBatch(process)
           .option("checkpointLocation", args.checkpoint)    # enables recovery after worker restart
           .trigger(processingTime=args.trigger)
           .queryName(f"ids_{args.run_id.replace('-', '_').replace('.', '_')}")
           .start()
    )

    # Main loop: check for stop signal or timeout every second, flush metrics each iteration.
    deadline = time.time() + args.await_seconds if args.await_seconds > 0 else None
    while query.isActive and not stop.is_set() and (deadline is None or time.time() < deadline):
        query.awaitTermination(1)
        flush_metrics()

    # Graceful stop: wait up to 10 s for the running batch to finish, then stop the query.
    if query.isActive:
        for _ in range(100):
            if not query.status.get("isTriggerActive"):
                break
            time.sleep(0.1)
        query.stop()

    exc = query.exception()
    time.sleep(0.5)      # brief pause for the listener to receive the final onQueryProgress event
    flush_metrics()      # flush any remaining metrics before shutting down Spark
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
