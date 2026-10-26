"""M1-F01-AC-06 smoke job — runs INSIDE spark-client via spark-submit (see test_platform_live.py).

Checks: golden events readable from the mounted workspace, a sklearn pandas_udf runs on the workers,
executor/driver library versions, connector classes present locally, no runtime package download configured.
Prints one JSON line.
"""
import json
import socket
import sys

import pandas as pd
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.functions import pandas_udf

spark = (SparkSession.builder.appName("m1-f01-smoke")
         .config("spark.cores.max", "4").config("spark.executor.cores", "1").config("spark.executor.memory", "768m")
         .getOrCreate())

events = spark.read.json("/workspace/contracts/fixtures/events_golden.jsonl")


@pandas_udf("double")
def iso_score(bytes_sent: pd.Series, dst_port: pd.Series) -> pd.Series:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    x = np.column_stack([bytes_sent.to_numpy(float), dst_port.to_numpy(float)])
    if len(x) < 2:
        return pd.Series(np.zeros(len(x)))
    return pd.Series(-IsolationForest(n_estimators=10, random_state=0).fit(x).score_samples(x))


scored = events.repartition(4).withColumn("score", iso_score("bytes_sent", "dst_port"))
rows = scored.count()
scored_rows = scored.filter(F.col("score").isNotNull()).count()


def versions(_):
    import joblib, numpy, pandas, pyarrow, sklearn, yaml
    yield (socket.gethostname(), sys.version.split()[0], sklearn.__version__, numpy.__version__, pandas.__version__,
           pyarrow.__version__, joblib.__version__, yaml.__version__)


executor_versions = sorted(set(spark.sparkContext.parallelize(range(8), 8).mapPartitions(versions).collect()))


def has_class(name):
    try:
        spark._jvm.java.lang.Class.forName(name)
        return True
    except Exception:
        return False


import joblib, numpy, pyarrow, sklearn, yaml  # noqa: E402  (driver side)

print(json.dumps({
    "rows": rows,
    "scored_rows": scored_rows,
    "driver_host": socket.gethostname(),
    "driver": [sys.version.split()[0], sklearn.__version__, numpy.__version__, pd.__version__, pyarrow.__version__,
               joblib.__version__, yaml.__version__],
    "executors": [list(v) for v in executor_versions],
    "kafka_connector": has_class("org.apache.spark.sql.kafka010.KafkaSourceProvider"),
    "cassandra_connector": has_class("com.datastax.spark.connector.CassandraSparkExtensions"),
    "jars_packages": spark.conf.get("spark.jars.packages", ""),
}))
spark.stop()
