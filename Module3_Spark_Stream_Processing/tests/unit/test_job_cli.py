"""M3 host-side job CLI with a fake docker (M3-F01-AC-02)."""
import json
import zipfile

import pytest

from conftest import ROOT
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from ids_stream import job


class FakeDocker:
    def __init__(self, container="abc123", lines=None, rc=0):
        self.container, self.rc, self.calls = container, rc, []
        self.lines = lines if lines is not None else [
            "some spark log line",
            json.dumps({"status": "ok", "command": "stream app", "run_id": "DEV-t", "batches": 12, "rows_written": 340,
                        "anomalies_written": 20, "metrics_rows": 12, "bundle_version": "0.0.0-dummy"})]

    def find_spark_client(self):
        return self.container

    def exec_stream(self, container, cmd, on_line):
        self.calls.append((container, cmd))
        for line in self.lines:
            on_line(line)
        return self.rc

    def signal_driver(self, container, force=False):
        self.calls.append((container, "KILL" if force else "TERM"))


def run(argv, capsys, docker=None, env=None):
    code = job.main(argv, env={"IDS_ROOT": str(ROOT), **(env or {})}, docker=docker or FakeDocker())
    return code, capsys.readouterr()


def test_builds_spark_submit_and_reemits_summary(capsys):
    d = FakeDocker()
    code, out = run(["--executors", "2", "--run-id", "DEV-t", "--await-seconds", "30", "--starting-offsets", "earliest"], capsys, d)
    assert code == EXIT_OK
    container, cmd = d.calls[0]
    assert container == "abc123" and cmd[0] == "spark-submit"
    s = " ".join(cmd)
    for frag in ("--conf spark.cores.max=2", "--conf spark.executor.cores=1", "--conf spark.executor.memory=768m",
                 "--conf spark.sql.shuffle.partitions=4", "--conf spark.cassandra.connection.host=cassandra",
                 "--py-files /workspace/runtime/build/ids_stream.zip",
                 "/workspace/Module3_Spark_Stream_Processing/src/ids_stream/app.py",
                 "--run-id DEV-t", "--await-seconds 30", "--starting-offsets earliest", "--topic network-events",
                 "--bundle /workspace/runtime/bundle/current", "--checkpoint /workspace/runtime/checkpoints/DEV-t",
                 "--trigger 1 second", "--executors 2"):
        assert frag in s, frag
    summary = json.loads(out.out.strip().splitlines()[-1])
    assert summary["command"] == "stream job" and summary["batches"] == 12 and summary["rows_written"] == 340
    with zipfile.ZipFile(ROOT / "runtime" / "build" / "ids_stream.zip") as z:
        assert "ids_stream/app.py" in z.namelist() and "ids_stream/spec.py" in z.namelist()


def test_missing_bundle_exit_1(capsys, tmp_path):
    code, out = run([], capsys, env={"MODEL_BUNDLE_PATH": str(tmp_path / "none")})
    assert code == EXIT_RUNTIME_ERROR and "bundle" in out.err


def test_no_container_exit_1(capsys):
    code, out = run([], capsys, FakeDocker(container=None))
    assert code == EXIT_RUNTIME_ERROR and "spark-client" in out.err


def test_app_failure_exit_1(capsys):
    code, out = run([], capsys, FakeDocker(lines=["Traceback ..."], rc=1))
    assert code == EXIT_RUNTIME_ERROR


@pytest.mark.parametrize("argv", [["--executors", "9"], ["--trigger", "soon"], ["--starting-offsets", "middle"]])
def test_usage_errors(argv, capsys):
    try:
        code, _ = run(argv, capsys)
    except SystemExit as exc:
        code = exc.code
    assert code == EXIT_USAGE_ERROR


def test_signal_handler_terms_then_kills(capsys):
    import signal as sig

    class Interrupting(FakeDocker):
        def exec_stream(self, container, cmd, on_line):
            self.calls.append((container, cmd))
            sig.raise_signal(sig.SIGINT)                       # first Ctrl-C → graceful
            sig.raise_signal(sig.SIGINT)                       # second Ctrl-C → force
            for line in self.lines:
                on_line(line)
            return 0

    d = Interrupting()
    code, out = run([], capsys, d)
    assert code == EXIT_OK and [c[1] for c in d.calls[1:]] == ["TERM", "KILL"]
    assert "Ctrl-C again to force" in out.err
