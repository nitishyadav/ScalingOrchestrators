"""Build-time download of Spark connector jars with SHA-1 verification (M1-F01 FR-006: no downloads at job time).

Usage (inside the Dockerfile): python3 fetch_jars.py /opt/spark/jars
Dependency versions are taken from the spark-parent 3.5.5 POM (kafka.version=3.4.1, commons-pool2.version=2.11.1).
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

MAVEN = "https://repo1.maven.org/maven2"
JARS = [
    "org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.5/spark-sql-kafka-0-10_2.12-3.5.5.jar",
    "org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.5/spark-token-provider-kafka-0-10_2.12-3.5.5.jar",
    "org/apache/kafka/kafka-clients/3.4.1/kafka-clients-3.4.1.jar",
    "org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar",
    "com/datastax/spark/spark-cassandra-connector-assembly_2.12/3.5.1/spark-cassandra-connector-assembly_2.12-3.5.1.jar",
]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read()


def main(dest: str) -> None:
    out = Path(dest)
    out.mkdir(parents=True, exist_ok=True)
    for path in JARS:
        data = fetch(f"{MAVEN}/{path}")
        expected = fetch(f"{MAVEN}/{path}.sha1").decode().split()[0].strip()
        actual = hashlib.sha1(data).hexdigest()
        if actual != expected:
            raise SystemExit(f"SHA-1 mismatch for {path}: {actual} != {expected}")
        (out / Path(path).name).write_bytes(data)
        print(f"ok {Path(path).name} {len(data)} bytes sha1={actual}")


if __name__ == "__main__":
    main(sys.argv[1])
