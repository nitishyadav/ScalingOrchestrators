"""M1-T012 — platform CLI behaviour with a fake engine (M1-F01-AC-02, AC-08, AC-11; FR-002, FR-008..FR-010, edge cases)."""
import json

import pytest

from ids_ingest import platform as pf
from ids_ingest._compose import EngineUnavailable
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR

GIB = 1024 ** 3
SINGLE = ("kafka", "spark-master", "spark-client", "cassandra")


def container(service, index=1, state="running", health="healthy"):
    return {"Service": service, "Name": f"ids-{service}-{index}", "State": state, "Health": health}


def healthy_ps(workers=2):
    return [container(s) for s in SINGLE] + [container("spark-worker", i) for i in range(1, workers + 1)]


class FakeEngine:
    def __init__(self, ps_sequence=None, mem_gib=9.7, cpus=6, available=True):
        self.ps_sequence = list(ps_sequence or [healthy_ps()])
        self.mem_gib, self.cpus, self.available = mem_gib, cpus, available
        self.calls = []

    def engine_info(self):
        if not self.available:
            raise EngineUnavailable("Cannot connect to the Docker daemon")
        return {"MemTotal": int(self.mem_gib * GIB), "NCPU": self.cpus}

    def ps(self):
        self.calls.append(("ps",))
        return self.ps_sequence.pop(0) if len(self.ps_sequence) > 1 else self.ps_sequence[0]

    def up(self, workers):
        self.calls.append(("up", workers))

    def down(self, volumes=False):
        self.calls.append(("down", volumes))

    def restart_container(self, name):
        self.calls.append(("restart", name))


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


def run(argv, engine, capsys, ports_in_use=(), master_sequence=None, clock=None):
    clock = clock or FakeClock()
    seq = list(master_sequence or [[{"id": "worker-a", "state": "ALIVE", "cores": 2}, {"id": "worker-b", "state": "ALIVE", "cores": 2}]])
    deps = pf.Deps(
        engine=engine,
        port_in_use=lambda port: port in ports_in_use,
        master_workers=lambda: seq.pop(0) if len(seq) > 1 else seq[0],
        now=clock.now,
        sleep=clock.sleep,
    )
    code = pf.main(argv, deps=deps, env={})
    out = capsys.readouterr()
    return code, out


def summary(out):
    return json.loads(out.out.strip().splitlines()[-1])


# ---- status ---------------------------------------------------------------------------------
def test_status_ready(capsys):
    code, out = run(["status"], FakeEngine(), capsys)
    s = summary(out)
    assert code == EXIT_OK and s["status"] == "ok" and s["ready"] is True
    assert s["services"]["spark-worker"] == "healthy" and s["workers"] == 2


def test_status_not_ready_exits_1(capsys):
    ps = healthy_ps()
    ps[0] = container("kafka", state="exited", health="")
    code, out = run(["status"], FakeEngine([ps]), capsys)
    s = summary(out)
    assert code == EXIT_RUNTIME_ERROR and s["ready"] is False and s["services"]["kafka"] != "healthy"


def test_engine_unavailable_hint(capsys):
    code, out = run(["status"], FakeEngine(available=False), capsys)
    assert code == EXIT_RUNTIME_ERROR and "colima start" in out.err


# ---- up -------------------------------------------------------------------------------------
def test_up_waits_until_healthy(capsys):
    starting = [container(s, health="starting") for s in SINGLE] + [container("spark-worker", i, health="starting") for i in (1, 2)]
    engine = FakeEngine([[], starting, starting, healthy_ps()])
    code, out = run(["up"], engine, capsys)
    s = summary(out)
    assert code == EXIT_OK and s["ready"] is True and s["workers"] == 2
    assert ("up", 2) in engine.calls and "elapsed_s" in s


def test_up_workers_flag(capsys):
    engine = FakeEngine([[], healthy_ps(1)])
    code, out = run(["up", "--workers", "1"], engine, capsys,
                    master_sequence=[[{"id": "worker-a", "state": "ALIVE", "cores": 2}]])
    assert code == EXIT_OK and ("up", 1) in engine.calls


def test_up_times_out(capsys):
    starting = [container(s, health="starting") for s in SINGLE] + [container("spark-worker", i, health="starting") for i in (1, 2)]
    code, out = run(["up", "--timeout", "30"], FakeEngine([[], starting]), capsys)
    assert code == EXIT_RUNTIME_ERROR and "timeout" in out.err.lower()


def test_up_refuses_when_port_taken_and_platform_not_running(capsys):
    engine = FakeEngine([[]])
    code, out = run(["up"], engine, capsys, ports_in_use={9042})
    assert code == EXIT_RUNTIME_ERROR and "9042" in out.err
    assert not any(c[0] == "up" for c in engine.calls)


def test_up_ignores_ports_held_by_own_running_platform(capsys):
    engine = FakeEngine([healthy_ps(), healthy_ps()])
    code, _ = run(["up"], engine, capsys, ports_in_use={9092, 9042, 7077, 8080})
    assert code == EXIT_OK


def test_up_refuses_small_engine(capsys):
    engine = FakeEngine([[]], mem_gib=6.0)
    code, out = run(["up"], engine, capsys)
    assert code == EXIT_RUNTIME_ERROR and "memory" in out.err.lower()
    assert not any(c[0] == "up" for c in engine.calls)


@pytest.mark.parametrize("argv", [["up", "--workers", "5"], ["up", "--workers", "0"], ["up", "--bogus"], ["fly"]])
def test_up_usage_errors_exit_2(argv, capsys):
    try:
        code, _ = run(argv, FakeEngine(), capsys)
    except SystemExit as exc:      # argparse errors
        code = exc.code
    assert code == EXIT_USAGE_ERROR


# ---- down / clean -----------------------------------------------------------------------------
def test_down_keeps_volumes(capsys):
    engine = FakeEngine()
    code, out = run(["down"], engine, capsys)
    assert code == EXIT_OK and ("down", False) in engine.calls and summary(out)["command"] == "platform down"


def test_clean_requires_yes(capsys):
    engine = FakeEngine()
    code, out = run(["clean"], engine, capsys)
    assert code == EXIT_USAGE_ERROR and not any(c[0] == "down" for c in engine.calls) and "--yes" in out.err


def test_clean_with_yes_removes_volumes(capsys):
    engine = FakeEngine()
    code, _ = run(["clean", "--yes"], engine, capsys)
    assert code == EXIT_OK and ("down", True) in engine.calls


# ---- restart-worker ---------------------------------------------------------------------------
def test_restart_worker_waits_for_reregistration(capsys):
    before = [{"id": "worker-a", "state": "ALIVE", "cores": 2}, {"id": "worker-b", "state": "ALIVE", "cores": 2}]
    after = before + [{"id": "worker-c", "state": "ALIVE", "cores": 2}]
    engine = FakeEngine()
    code, out = run(["restart-worker", "--index", "1"], engine, capsys, master_sequence=[before, before, after])
    s = summary(out)
    assert code == EXIT_OK and ("restart", "ids-spark-worker-1") in engine.calls
    assert s["reregistered_s"] <= 30


@pytest.mark.parametrize("index", ["0", "3"])
def test_restart_worker_bad_index_exit_2(index, capsys):
    engine = FakeEngine()
    code, out = run(["restart-worker", "--index", index], engine, capsys)
    assert code == EXIT_USAGE_ERROR and not any(c[0] == "restart" for c in engine.calls)


def test_restart_worker_reregistration_timeout(capsys):
    same = [{"id": "worker-a", "state": "ALIVE", "cores": 2}, {"id": "worker-b", "state": "ALIVE", "cores": 2}]
    code, out = run(["restart-worker", "--index", "2", "--timeout", "10"], FakeEngine(), capsys, master_sequence=[same])
    assert code == EXIT_RUNTIME_ERROR
