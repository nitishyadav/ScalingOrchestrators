"""`python -m ids_stream.job` — submit the stream job from `spark-client` (C-06 §5; ADR-009). Host side, no PySpark.

    python -m ids_stream.job [--executors N] [--trigger "1 second"] [--run-id ID] [--await-seconds S]
                             [--starting-offsets latest|earliest]
SIGINT/SIGTERM → the driver is asked to stop gracefully (it flushes metrics and prints its summary).
"""
from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence

from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

from . import PACKAGE_DIR
from .spec import BundleMetaError, container_path, read_bundle_meta

_FALLBACK_DOCKER = ("/opt/homebrew/bin/docker", "/usr/local/bin/docker")


class Docker:
    """Minimal docker CLI access: find the compose `spark-client` container of project `ids`, exec, signal."""

    def __init__(self):
        self.bin = shutil.which("docker") or next((p for p in _FALLBACK_DOCKER if Path(p).exists()), "docker")

    def find_spark_client(self) -> Optional[str]:
        try:
            out = subprocess.run([self.bin, "ps", "-q", "-f", "label=com.docker.compose.project=ids",
                                  "-f", "label=com.docker.compose.service=spark-client"], capture_output=True, text=True)
        except FileNotFoundError:
            return None
        return out.stdout.split()[0] if out.returncode == 0 and out.stdout.split() else None

    def exec_stream(self, container: str, cmd: List[str], on_line: Callable[[str], None]) -> int:
        # own session: a terminal Ctrl-C (SIGINT to the foreground process group) must not kill the docker client,
        # otherwise the driver's output and summary are lost while it is still shutting down gracefully
        proc = subprocess.Popen([self.bin, "exec", container, *cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
        for line in proc.stdout:
            on_line(line.rstrip("\n"))
        return proc.wait()

    def signal_driver(self, container: str, force: bool = False) -> None:
        subprocess.run([self.bin, "exec", container, "pkill", "-KILL" if force else "-TERM", "-f",
                        "^python3 .*ids_stream/app.py"], capture_output=True, start_new_session=True)


def build_zip(dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PACKAGE_DIR.glob("*.py")):
            z.write(f, f"ids_stream/{f.name}")
    return dest


def build_command(cfg, args, root: Path, zip_path: Path, shuffle: int) -> List[str]:
    cpath = lambda p: container_path(p, root)
    return [
        "spark-submit", "--master", "spark://spark-master:7077",
        "--conf", f"spark.cores.max={cfg.spark_executors * cfg.spark_executor_cores}",
        "--conf", f"spark.executor.cores={cfg.spark_executor_cores}",
        "--conf", f"spark.executor.memory={cfg.spark_executor_memory}",
        "--conf", f"spark.sql.shuffle.partitions={shuffle}",
        "--conf", "spark.cassandra.connection.host=cassandra",
        "--conf", "spark.sql.streaming.forceDeleteTempCheckpointLocation=true",
        "--py-files", cpath(zip_path),
        cpath(PACKAGE_DIR / "app.py"),
        "--run-id", cfg.run_id, "--topic", cfg.kafka_topic, "--trigger", cfg.trigger_interval,
        "--executors", str(cfg.spark_executors), "--bundle", cpath(cfg.model_bundle_path),
        "--checkpoint", cpath(cfg.checkpoint_dir / cfg.run_id), "--starting-offsets", args.starting_offsets,
        "--await-seconds", str(args.await_seconds),
    ]


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None, docker=None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_stream.job", description="Run the M3 stream job on the platform (C-06 §5).")
    p.add_argument("--executors", type=int, help="→ SPARK_EXECUTORS (1..8)")
    p.add_argument("--trigger", help='→ TRIGGER_INTERVAL, e.g. "1 second"')
    p.add_argument("--run-id", help="→ RUN_ID")
    p.add_argument("--await-seconds", type=int, default=0, help="stop after N seconds (0 = until stopped)")
    p.add_argument("--starting-offsets", choices=("latest", "earliest"), default="latest")
    p.add_argument("--shuffle-partitions", type=int, help="default: executors × cores × 2")
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env, overrides={"SPARK_EXECUTORS": args.executors, "TRIGGER_INTERVAL": args.trigger,
                                                      "RUN_ID": args.run_id})
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    root = cfg.workspace_root
    try:
        manifest, _ = read_bundle_meta(cfg.model_bundle_path)
        container_path(cfg.model_bundle_path, root)
    except (BundleMetaError, ValueError) as exc:
        print(f"no usable C-03 bundle at MODEL_BUNDLE_PATH ({cfg.model_bundle_path}): {exc}\n"
              f"(replica: `make mock` in Module2_ML_Anomaly_Model installs the dummy bundle)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    docker = docker or Docker()
    container = docker.find_spark_client()
    if not container:
        print("spark-client container not found; start the platform (`python -m ids_ingest.platform up`)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    zip_path = build_zip(root / "runtime" / "build" / "ids_stream.zip")
    shuffle = args.shuffle_partitions or cfg.spark_executors * cfg.spark_executor_cores * 2
    cmd = build_command(cfg, args, root, zip_path, shuffle)
    app_summary = {}

    def on_line(line: str) -> None:
        if line.startswith("{"):
            try:
                parsed = json.loads(line)
            except ValueError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("command") == "stream app":
                app_summary.update(parsed)
                return
        print(line, file=sys.stderr)

    stops = {"n": 0}

    def _stop(signum, _frame):
        stops["n"] += 1
        if stops["n"] == 1:
            print("stop requested: the driver finishes its batch and flushes metrics (Ctrl-C again to force)",
                  file=sys.stderr)
            docker.signal_driver(container)
        else:
            print("forcing the driver to stop now", file=sys.stderr)
            docker.signal_driver(container, force=True)

    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.signal(sig, _stop)
        except ValueError:
            pass
    try:
        rc = docker.exec_stream(container, cmd, on_line)
    finally:
        for sig, h in previous.items():
            signal.signal(sig, h)
    if rc != 0 or app_summary.get("status") != "ok":
        print(f"stream job failed (exit {rc}); see the Spark log above", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    print(summary_line("stream job", cfg.run_id, **{k: v for k, v in app_summary.items()
                                                    if k not in ("status", "command", "run_id")}))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
