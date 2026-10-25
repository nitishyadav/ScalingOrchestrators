"""integration/demo.py with fake side effects: start order, state, graceful ordered stop."""
import json
import signal
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo  # noqa: E402


class FakeOps:
    def __init__(self, fail=None, port_busy=False, job_dies=False, stubborn=()):
        self.calls, self.signals, self.t, self.next_pid = [], [], 0.0, 100
        self.fail, self.port_busy, self.job_dies, self.stubborn = fail, port_busy, job_dies, set(stubborn)
        self.live, self.names = set(), {}

    def run(self, cmd, cwd, timeout=600):
        name = " ".join(cmd[2:4])
        self.calls.append(("run", name))
        if self.fail and self.fail in name:
            return 1, "", "boom"
        out = {"bundle_version": "1.1.0-replica"} if "bundle" in name else {"ready": True}
        return 0, json.dumps({"status": "ok", **out}) + "\n", ""

    def spawn(self, cmd, cwd, log):
        name = {"ids_stream.job": "job", "ids_ingest.producer": "producer", "streamlit": "dashboard"}[cmd[2]]
        self.calls.append(("spawn", name))
        self.next_pid += 1
        self.names[self.next_pid] = name
        if not (name == "job" and self.job_dies):
            self.live.add(self.next_pid)
        self.cmd = getattr(self, "cmd", {})
        self.cmd[name] = cmd
        return self.next_pid

    def alive(self, pid):
        return pid in self.live

    def signal(self, pid, sig):
        self.signals.append((self.names.get(pid), sig))
        if self.names.get(pid) not in self.stubborn or sig == signal.SIGKILL:
            self.live.discard(pid)

    def active_apps(self):
        jobs = [p for p, n in self.names.items() if n == "job" and p in self.live]
        return [f"ids-stream-{self.cmd['job'][self.cmd['job'].index('--run-id') + 1]}"] if jobs and self.t >= 4 else []

    def port_in_use(self, port):
        return self.port_busy

    def sleep(self, s):
        self.t += s

    def now(self):
        return self.t


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "RUN_DIR", tmp_path)
    monkeypatch.setattr(demo, "STATE", tmp_path / "demo.json")


def out_json(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_up_runs_steps_in_order_and_saves_state(capsys, tmp_path):
    ops = FakeOps()
    assert demo.main(["up", "--run-id", "DEV-demo-t", "--rate", "1000", "--attack-share", "0.2"], ops) == 0
    assert ops.calls == [("run", "ids_ingest.platform up"), ("run", "ids_monitor.schema apply"),
                         ("run", "ids_model.bundle check"), ("run", "ids_ingest.topic_admin --partitions"),
                         ("spawn", "job"), ("spawn", "producer"), ("spawn", "dashboard")]
    assert ops.cmd["producer"][-4:] == ["--attack-mode", "mixed", "--attack-share", "0.2"]
    assert ops.cmd["dashboard"][-2:] == ["--run-id", "DEV-demo-t"]
    out = out_json(capsys)
    assert out["run_id"] == "DEV-demo-t" and out["bundle_version"] == "1.1.0-replica"
    state = json.loads((tmp_path / "demo.json").read_text())
    assert set(state["pids"]) == {"job", "producer", "dashboard"}


def test_up_refuses_when_already_running(capsys):
    ops = FakeOps()
    demo.main(["up", "--run-id", "DEV-demo-t"], ops)
    capsys.readouterr()
    assert demo.main(["up"], ops) == 1 and "already running" in out_json(capsys)["error"]


def test_up_reports_failed_step_and_dying_job(capsys):
    assert demo.main(["up"], FakeOps(fail="bundle")) == 1 and "bundle check" in out_json(capsys)["error"]
    assert demo.main(["up"], FakeOps(job_dies=True)) == 1 and "exited during start-up" in out_json(capsys)["error"]


def test_up_keeps_an_existing_dashboard(capsys):
    ops = FakeOps(port_busy=True)
    assert demo.main(["up", "--run-id", "DEV-demo-t"], ops) == 0
    assert ("spawn", "dashboard") not in ops.calls


def test_down_stops_in_order_gracefully(capsys, tmp_path):
    ops = FakeOps()
    demo.main(["up", "--run-id", "DEV-demo-t"], ops)
    assert demo.main(["down", "--platform"], ops) == 0
    assert ops.signals == [("producer", signal.SIGINT), ("job", signal.SIGINT), ("dashboard", signal.SIGTERM)]
    assert ops.calls[-1] == ("run", "ids_ingest.platform down")
    assert out_json(capsys)["stopped"] == {"producer": "stopped", "job": "stopped", "dashboard": "stopped", "platform": "down"}
    assert not (tmp_path / "demo.json").exists()


def test_down_forces_a_stuck_job(capsys):
    ops = FakeOps(stubborn={"job"})
    demo.main(["up", "--run-id", "DEV-demo-t"], ops)
    demo.main(["down"], ops)
    job_signals = [s for n, s in ops.signals if n == "job"]
    assert job_signals == [signal.SIGINT, signal.SIGINT, signal.SIGKILL]
    assert out_json(capsys)["stopped"]["job"] == "forced"
