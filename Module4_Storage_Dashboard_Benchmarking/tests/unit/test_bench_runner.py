"""M4-T212: orchestration with fake CLI, store and clock (AC-06, AC-07)."""
import csv
import json

import pytest

from ids_contracts.config import validate_run_id
from ids_monitor import bench
from ids_monitor.store import ReadResult

T0 = 1_793_975_400_000


class FakeClock:
    def __init__(self, interrupt_at_s=None):
        self.ms = T0
        self.interrupt_at = None if interrupt_at_s is None else T0 + interrupt_at_s * 1000

    def now_ms(self):
        return self.ms

    def sleep(self, s):
        self.ms += int(s * 1000)
        if self.interrupt_at is not None and self.ms >= self.interrupt_at:
            self.interrupt_at = None
            raise KeyboardInterrupt


class FakeStore:
    def __init__(self, clock):
        self.clock, self.runs, self.metrics, self.windows = clock, [], {}, []

    def latest_runs(self, limit=20):                    # a runs row becomes visible at its started_at
        return sorted((r for r in self.runs if r["started_at"] <= self.clock.ms), key=lambda r: -r["started_at"])[:limit]

    def latest_metrics(self, run_id, limit=60):
        return sorted(self.metrics.get(run_id, []), key=lambda m: -m["batch_ts"])[:limit]

    def read_windows(self, start_ms, end_ms, run_id=None):
        return ReadResult([w for w in self.windows if start_ms <= w["window_end"] <= end_ms and w["run_id"] == run_id], 0, 1)


class FakeProc:
    def __init__(self, cli, name, argv, done_at=None, code=0, summary=None):
        self.cli, self.name, self.argv, self.done_at, self.code, self._summary = cli, name, argv, done_at, code, summary
        self.signals = []

    def poll(self):
        if self.done_at is not None and self.cli.clock.ms >= self.done_at:
            return self.code
        return None

    def wait(self, timeout):
        end = self.cli.clock.ms + timeout * 1000
        while self.poll() is None and self.cli.clock.ms < end:
            self.cli.clock.ms += 1000
        return self.poll()

    def interrupt(self):
        self.signals.append("INT")
        self.cli.calls.append((self.cli.clock.ms, "interrupt", self.name))
        if self.name == "job" and not self.cli.job_ignores_sigint:
            self.done_at = self.cli.clock.ms + 2000
        if self.name == "producer":
            self.done_at = self.cli.clock.ms

    def kill(self):
        self.signals.append("KILL")
        self.done_at, self.code = self.cli.clock.ms, -9

    def summary(self):
        return self._summary


class FakeCli:
    """Simulates M1/M3: the job registers 5 s after start; the producer writes one C-05 batch per second."""

    def __init__(self, clock, store, fail=None, register=True, job_ignores_sigint=False, rows_per_batch=5000):
        self.clock, self.store, self.fail, self.register = clock, store, fail or set(), register
        self.job_ignores_sigint, self.rows = job_ignores_sigint, rows_per_batch
        self.calls, self.procs = [], {}

    @staticmethod
    def _name(argv):
        return {"ids_ingest.topic_admin": "topic", "ids_stream.job": "job", "ids_ingest.producer": "producer",
                "ids_ingest.platform": "restart"}[argv[0]]

    def available(self, module):
        return True

    def run(self, argv, log_path):
        name = self._name(argv)
        self.calls.append((self.clock.ms, "run", name))
        log_path.write_text(f"{name} log\n")
        if name in self.fail:
            return 1, None
        return 0, {"status": "ok", "command": name}

    def start(self, argv, log_path):
        name = self._name(argv)
        self.calls.append((self.clock.ms, "start", name))
        log_path.write_text(f"{name} log\n")
        rid = argv[argv.index("--run-id") + 1]
        if name == "job":
            if self.register:
                self.store.runs.append({"bucket": "all", "started_at": self.clock.ms + 5000, "run_id": rid, "config_json": "{}"})
            proc = FakeProc(self, name, argv, code=0, summary={"status": "ok", "batches": 1})
            if name in self.fail:
                proc.done_at, proc.code, proc._summary = self.clock.ms + 1000, 1, None
        else:
            dur = int(argv[argv.index("--duration") + 1])
            rate = int(argv[argv.index("--rate") + 1])
            start = self.clock.ms
            self.store.metrics[rid] = [_batch(rid, start + i * 1000, self.rows) for i in range(1, dur + 3)]  # +2 drain
            self.store.windows += [{"window_end": start + i * 10_000, "run_id": rid, "is_anomaly": i % 4 == 0,
                                    "label_attack": i % 4 == 0, "label_type": "INJ_DDOS" if i % 4 == 0 else "BENIGN"}
                                   for i in range(1, dur // 10 + 1)]
            code = 1 if name in self.fail else 0
            proc = FakeProc(self, name, argv, done_at=start + dur * 1000, code=code,
                            summary=None if code else {"status": "ok", "achieved_rate": float(rate), "sent": rate * dur})
        self.procs[name] = proc
        return proc


def _batch(rid, ts, rows):
    return {"run_id": rid, "batch_ts": ts, "batch_id": 0, "input_rows": rows, "input_rows_per_sec": float(rows),
            "processed_rows_per_sec": 9000.0, "batch_duration_ms": 700, "latency_p50_ms": 200.0, "latency_p95_ms": 400.0,
            "latency_max_ms": 500.0, "windows_written": 40, "anomalies_written": 1, "kafka_partitions": 8, "executors": 2}


def runner(tmp_path, **cli_kw):
    clock = FakeClock(cli_kw.pop("interrupt_at_s", None))
    store = FakeStore(clock)
    cli = FakeCli(clock, store, **cli_kw)
    return bench.Runner(cli, store, clock, tmp_path, duration_s=120, warmup_s=30), cli, store, clock


# ---- AC-06 ----
def test_call_order_raw_files_and_report(tmp_path):
    r, cli, store, _ = runner(tmp_path)
    res = r.run_experiment("E1", ["1", "4"])
    assert [c[1:] for c in cli.calls if c[2] != "restart"][:5] == [
        ("run", "topic"), ("start", "job"), ("start", "producer"), ("interrupt", "job"), ("run", "topic")]
    t = {name: ms for ms, kind, name in cli.calls[:3]}
    assert t["producer"] - t["job"] >= 15_000                       # registered (5 s) + 10 s settle
    assert t["job"] < t["producer"] < t["producer"] + 120_000 <= [c[0] for c in cli.calls if c[1] == "interrupt"][0]
    assert res["failed"] == [] and len(res["runs"]) == 2 and not res["interrupted"]
    rid = res["runs"][0]["run_id"]
    assert validate_run_id(rid) and rid.startswith("E1-p1-e4-r15000-a0-")
    assert res["runs"][0]["run_id"] != res["runs"][1]["run_id"]     # never the same minute stamp
    raw = tmp_path / "raw" / rid
    for f in ("config.json", "commands.json", "topic_admin.json", "job.json", "producer.json", "metrics.csv",
              "samples.csv", "summary.json", "topic_admin.log", "job.log", "producer.log"):
        assert (raw / f).exists(), f
    summary = json.loads((raw / "summary.json").read_text())
    assert summary["sustained_evs"] == 5000.0 and summary["p95_ms"] == 400.0 and summary["status"] == "ok"
    assert summary["producer_bound"] is False                        # 5,000 of 15,000 ev/s: saturated
    assert len(list(csv.DictReader((raw / "metrics.csv").open()))) == 122
    report = json.loads((tmp_path / res["report"]).read_text())
    assert report["experiment"] == "E1" and [x["level"] for x in report["runs"]] == ["1", "4"]
    assert report["efficiency"][1]["speedup"] == 1.0                # same fake throughput at both levels
    assert (tmp_path / res["report"].replace(".json", ".md")).read_text().startswith("# E1")


def test_e3_writes_detection_and_rec_restarts_worker(tmp_path):
    r, cli, *_ = runner(tmp_path)
    e3 = r.run_experiment("E3", ["20"])
    det = json.loads((tmp_path / "raw" / e3["runs"][0]["run_id"] / "detection.json").read_text())
    assert det["detection"]["recall_injected"] == 1.0 and "banner" in det
    r2, cli2, *_ = runner(tmp_path)
    rec = r2.run_experiment("REC")
    restarts = [c for c in cli2.calls if c[2] == "restart"]
    prod = [c[0] for c in cli2.calls if c[2] == "producer"][0]
    assert len(restarts) == 1 and abs(restarts[0][0] - (prod + 60_000)) <= 1000   # at 50 % of 120 s
    assert (tmp_path / "raw" / rec["runs"][0]["run_id"] / "recovery.json").exists()


def test_dry_run_prints_plan_and_calls_nothing(tmp_path, capsys):
    r, cli, *_ = runner(tmp_path)
    res = r.run_experiment("LAT", dry_run=True)
    out = capsys.readouterr().out
    assert cli.calls == [] and not (tmp_path / "raw").exists()
    assert "ids_stream.job --executors 2 --trigger '250 milliseconds'" in out and len(res["runs"]) == 3


# ---- AC-07 ----
def test_failed_cli_is_recorded_and_experiment_continues(tmp_path):
    r, cli, *_ = runner(tmp_path, fail={"topic"})
    res = r.run_experiment("E2", ["1", "2"])
    assert len(res["failed"]) == 2 and all("topic_admin exited 1" in x["reason"] for x in res["runs"])
    assert not any(c[2] == "job" for c in cli.calls)


def test_job_never_registers(tmp_path):
    r, cli, *_ = runner(tmp_path, register=False)
    res = r.run_experiment("E1", ["1"])
    assert res["runs"][0]["status"] == "failed" and "did not register" in res["runs"][0]["reason"]
    assert cli.procs["job"].signals and not any(c[2] == "producer" for c in cli.calls)


def test_job_ignoring_sigint_is_killed(tmp_path):
    r, cli, *_ = runner(tmp_path, job_ignores_sigint=True)
    r.run_experiment("E1", ["1"])
    assert cli.procs["job"].signals == ["INT", "INT", "KILL"]


def test_interrupt_stops_children_and_experiment(tmp_path):
    r, cli, *_ = runner(tmp_path, interrupt_at_s=60)                  # during the first producer run
    res = r.run_experiment("E1", ["1", "4"])
    assert res["interrupted"] and len(res["runs"]) == 1 and res["runs"][0]["status"] == "interrupted"
    assert cli.procs["producer"].signals == ["INT"] and cli.procs["job"].signals[0] == "INT"
    assert (tmp_path / "raw" / res["runs"][0]["run_id"] / "metrics.csv").exists()   # what was collected is kept


def test_preflight_names_missing_clis(tmp_path):
    r, cli, *_ = runner(tmp_path)
    cli.available = lambda module: module != "ids_stream.job"
    with pytest.raises(bench.PreflightError, match="ids_stream.job"):
        r.preflight("E1")
