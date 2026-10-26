# One image for spark-master, spark-worker and spark-client (M1-F01 FR-006, ADR-009):
# identical Python on driver and executors, pinned ML stack, connector jars baked in (no downloads at job time).
FROM apache/spark:3.5.5-scala2.12-java17-python3-ubuntu

USER root

COPY requirements-spark.txt /tmp/requirements-spark.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-spark.txt \
 && python3 -c "import sklearn, numpy, pandas, pyarrow, joblib, yaml; print('stack', sklearn.__version__, numpy.__version__, pandas.__version__, pyarrow.__version__)"

COPY fetch_jars.py /tmp/fetch_jars.py
RUN python3 /tmp/fetch_jars.py /opt/spark/jars && rm /tmp/fetch_jars.py /tmp/requirements-spark.txt

# PySpark + py4j for the driver in spark-client; ids_contracts from the mounted workspace.
ENV PYSPARK_PYTHON=python3 \
    PYSPARK_DRIVER_PYTHON=python3 \
    PYTHONPATH=/opt/spark/python:/opt/spark/python/lib/py4j-0.10.9.7-src.zip:/workspace/contracts/python \
    PATH=/opt/spark/bin:$PATH

# Runs as root so containers can write to the host-mounted runtime/ directory (local development only).
WORKDIR /opt/spark
