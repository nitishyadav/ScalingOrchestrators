"""M4-F03 benchmark harness: plans, maths and orchestration with fake CLIs (AC-01..AC-04)."""
import json
import signal

import pytest

from conftest import BASE, ROOT
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR, validate_run_id
from ids_monitor import bench as bn

STAMP = "202610251430"


# ---- AC-01 plans ---------------------------------------------------------------------------------
def test_plans_levels_and_run_ids():
    assert [s.level for s in bn.plan("E1")] == ["1", "4", "8", "16"]
    assert [s.level for s in bn.plan("E2")] == ["1", "2", "4"]
    assert [(s.level, s.share) for s in bn.plan("E3")] == [("0", 0.0), ("5", 0.05), ("20", 0.2), ("100", 1.0)]
    assert [s.level for s in bn.plan("LAT")] == ["1000", "500", "250"]
    assert bn.plan("E1")[0].run_id(STAMP) == "E1-p1-e2-r5000-a0-202610251430"
    assert bn.plan("LAT")[2].run_id(STAMP) == "LAT-p8-e2-r5000-a0-t250-202610251430"
    assert bn.plan("P1")[0].run_id(STAMP) == "P1-p16-e4-r12000-a0-202610251430"
    assert all(validate_run_id(s.run_id(STAMP)) for e in bn.EXPERIMENTS for s in bn.plan(e))
    assert [s.level for s in bn.plan("E1", ["16", "1"])] == ["1", "16"]          # plan order kept
    with pytest.raises(ValueError):
        bn.plan("E1", ["3"])


def test_commands_use_only_c06_clis():
    e1 = bn.plan("E1")[0]
    c = bn.commands(e1, "RID", duration=600, budget=1090, py="py")
    assert c["topic"] == ["py", "-m", "ids_ingest.topic_admin", "--partitions", "1", "--recreate"]
    assert c["job"] == ["py", "-m", "ids_stream.job", "--executors", "2", "--trigger", "1 second", "--run-id", "RID",
                        "--await-seconds", "1090", "--starting-offsets", "earliest"]
    assert c["producer"] == ["py", "-m", "ids_ingest.producer", "--days", "Monday", "--rate", "5000", "--duration", "600",
                             "--run-id", "RID"]
    assert c["restart"] is None
    e3 = bn.commands(bn.plan("E3", ["20"])[0], "RID", 600, 1090, py="py")
    assert e3["producer"][-4:] == ["--attack-mode", "mixed", "--attack-share", "0.2"]
    rec = bn.commands(bn.plan("REC")[0], "RID", 600, 1090, py="py")
    assert rec["restart"] == ["py", "-m", "ids_ingest.platform", "restart-worker", "--index", "1"]
    assert bn.commands(bn.plan("LAT", ["250"])[0], "RID", 60, 550, py="py")["job"][6] == "250 milliseconds"


def test_dry_run_prints_plan_and_runs_nothing(capsys):
    def boom(*_a, **_k):
        raise AssertionError("dry run must not touch the platform")
    code = bn.main(["--experiment", "E2", "--dry-run", "--duration", "60"], env={"IDS_ROOT": str(ROOT)}, runner_factory=boom)
    out = capsys.readouterr().out.strip().splitlines()
    summary = json.loads(out[-1])
    assert code == EXIT_OK and summary["command"] == "bench" and summary["dry_run"] is True
    assert len(summary["runs"]) == 3 and all(validate_run_id(r) for r in summary["runs"])
    assert any("ids_stream.job" in line for line in out[:-1])


def test_bad_level_is_usage_error(capsys):
    assert bn.main(["--experiment", "E1", "--levels", "3", "--dry-run"], env={"IDS_ROOT": str(ROOT)}) == EXIT_USAGE_ERROR


# ---- AC-02 metric maths --------------------------------------------------------------------------
def batches(start, end, *, every_ms=1000, rows=5000, cap=10_000.0, p95=300.0, tail_ms=0):
    out, t, i = [], start, 0
    while t <= end + tail_ms:
        out.append({"run_id": "RID", "batch_ts": t, "batch_id": i, "input_rows": rows, "input_rows_per_sec": rows * 1000 / every_ms,
                    "processed_rows_per_sec": cap, "batch_duration_ms": 400, "latency_p50_ms": p95 / 2, "latency_p95_ms": p95,
                    "latency_max_ms": p95 * 2, "windows_written": 100, "anomalies_written": 1, "kafka_partitions": 8, "executors": 2})
        t += every_ms
        i += 1
    return out


def test_summary_steady_state_capacity_and_latency():
    start, end = BASE, BASE + 600_000
    m = batches(start, end)
    for b in m[:60]:                                    # warm-up batches are slow and must not count
        b["processed_rows_per_sec"], b["latency_p95_ms"] = 100.0, 9_000.0
    m.append(dict(m[-1], batch_ts=end + 20_000, batch_id=10_000, input_rows=0, latency_p95_ms=None))   # idle batch
    s = bn.summarize_metrics(m, start, end, warmup_s=60, target_rate=5000)
    assert s["steady_batches"] == 541 and s["capacity_rows_per_s"] == 10_000.0 and s["latency_p95_ms"] == 300.0
    assert s["sustained_evs"] == pytest.approx(5000 * 601 / 600, rel=1e-3)
    assert s["backlog_s"] == 0 and s["keeping_up"] is True


def test_summary_detects_backlog():
    start, end = BASE, BASE + 120_000
    m = batches(start, end, rows=4000, tail_ms=40_000)    # still processing 40 s after the producer stopped
    s = bn.summarize_metrics(m, start, end, warmup_s=30, target_rate=5000)
    assert s["backlog_s"] == 40 and s["keeping_up"] is False


def test_30s_samples():
    m = batches(BASE, BASE + 89_000)
    rows = bn.samples(m, BASE)
    assert [r["t_s"] for r in rows] == [0, 30, 60] and rows[0]["batches"] == 30
    assert rows[0]["input_evs"] == pytest.approx(5000.0) and rows[1]["p95_max_ms"] == 300.0


def test_efficiency():
    e = bn.efficiency([(4, 30_000.0), (1, 10_000.0), (16, 40_000.0)])
    assert [r["n"] for r in e] == [1, 4, 16]
    assert e[0]["efficiency"] == 1.0 and e[1]["speedup"] == 3.0 and e[1]["efficiency"] == 0.75 and e[2]["efficiency"] == 0.25
    assert bn.efficiency([(1, None), (4, 1.0)])[1]["efficiency"] is None


# ---- AC-03 detection, banner, recovery -----------------------------------------------------------
def windows(start, end, *, benign_per_10s=10, benign_flag_every=50, injected_per_10s=2, injected_flagged=True):
    rows, t, k = [], start + 30_000, 0
    while t <= end:
        for i in range(benign_per_10s):
            k += 1
            rows.append({"window_end": t, "src_ip": f"10.0.0.{i}", "is_anomaly": k % benign_flag_every == 0,
                         "label_attack": False, "label_type": "BENIGN", "event_count": 50})
        for i in range(injected_per_10s):
            rows.append({"window_end": t, "src_ip": f"198.51.100.{i}", "is_anomaly": injected_flagged,
                         "label_attack": True, "label_type": "INJ_DDOS", "event_count": 500})
        t += 10_000
    return rows


def test_detection_rates_and_banner():
    start, end = BASE, BASE + 600_000
    d = bn.detection(windows(start, end), start, end)
    # 58 window ends × (10 benign + 2 injected); every 50th benign window flagged → 11 of 580
    assert d["benign"] == {"windows": 580, "flagged": 11, "fpr": pytest.approx(11 / 580)}
    assert d["injected"]["recall"] == 1.0 and d["cic_attack"]["windows"] == 0 and d["windows"] == 696
    assert d["anomalous_share"] == pytest.approx((11 + 116) / 696)
    assert d["banner"]["alert_fraction"] == 1.0 and d["banner"]["max_share"] > 0.15
    quiet = bn.detection(windows(start, end, injected_per_10s=0), start, end)
    assert quiet["banner"]["alert_fraction"] == 0.0 and quiet["injected"]["recall"] is None


def test_recovery_after_restart():
    start = BASE
    m = batches(start, start + 60_000) + batches(start + 68_000, start + 120_000)   # 8 s gap after a restart at 60.5 s
    for b in m:
        if start + 68_000 <= b["batch_ts"] < start + 80_000:
            b["latency_p95_ms"] = 6_000.0                                            # backlog being worked off
    r = bn.recovery(m, start + 60_500)
    assert r["first_batch_after_s"] == 7.5 and r["max_gap_s"] == 8.0
    assert r["pre_p95_ms"] == 300.0 and r["recovered_s"] == 19.5 and r["p5_pass"] is True


# ---- AC-04 orchestration with fake CLIs ----------------------------------------------------------
class FakeClock:
    def __init__(self):
        self.t, self.interrupt_at = BASE, None

    def now_ms(self):
        return self.t

    def sleep(self, s):
        self.t += int(s * 1000)
        if self.interrupt_at is not None and self.t >= self.interrupt_at:
            self.interrupt_at = None
            raise KeyboardInterrupt


class FakeProc:
    def __init__(self, cli, name, out, done_at):
        self.cli, self.name, self.out, self.done_at, self.rc, self.signals = cli, name, out, done_at, None, []

    def poll(self):
        if self.rc is None and self.done_at is not None and self.cli.clock.t >= self.done_at:
            self._finish()
        return self.rc

    def _finish(self):
        summary = {"status": "ok", "command": "stream job" if self.name == "job" else "producer", "run_id": "RID",
                   "sent": 300_000, "achieved_rate": 5000.0, "batches": 70, "rows_written": 1234}
        self.out.write_text("log line\n" + json.dumps(summary) + "\n")
        self.rc = 0

    def send_signal(self, sig):
        self.signals.append(sig)
        self.cli.calls.append(f"{self.name}:SIGINT")
        self._finish()

    def wait(self, timeout=None):
        if self.rc is None:
            self._finish()
        return self.rc

    def kill(self):
        self.rc = -9


class FakeCli:
    def __init__(self, clock, fail=()):
        self.clock, self.fail, self.calls, self.procs, self.producer_start = clock, set(fail), [], {}, None

    def run(self, cmd, cwd, timeout):
        name = cmd[2].split(".")[-1]
        self.calls.append(name)
        if name in self.fail:
            return 1, "", "boom"
        return 0, json.dumps({"status": "ok", "command": name}) + "\n", ""

    def start(self, cmd, cwd, out, err):
        name = "job" if cmd[2] == "ids_stream.job" else "producer"
        self.calls.append(name)
        done = None
        if name == "producer":
            self.producer_start = self.clock.t
            done = self.clock.t + int(cmd[cmd.index("--duration") + 1]) * 1000
        p = FakeProc(self, name, out, done)
        self.procs[name] = p
        return p


class FakeStore:
    def __init__(self, cli, duration_s):
        self.cli, self.duration_s, self.reads = cli, duration_s, []

    def runs(self, limit=20):
        return [{"run_id": "any"}] + ([{"run_id": self.cli.run_id}] if "job" in self.cli.procs else [])

    def metrics(self, run_id, limit=60):
        s = self.cli.producer_start
        if s is None:
            return []
        rows = [b for b in batches(s, s + self.duration_s * 1000 + 1000) if b["batch_ts"] <= self.cli.clock.t]
        return sorted(rows, key=lambda b: -b["batch_ts"])[:limit]

    def recent_windows(self, now_ms, seconds, run_id=None):
        self.reads.append((now_ms, seconds, run_id))
        s = self.cli.producer_start
        return windows(s, s + self.duration_s * 1000)


def make_runner(tmp_path, fail=(), duration=60):
    clock = FakeClock()
    cli = FakeCli(clock, fail)
    store = FakeStore(cli, duration)
    runner = bn.Runner(cli=cli, store=store, clock=clock, results_dir=tmp_path, root=ROOT, py="py")
    orig = runner.run_one

    def run_one(spec, run_id, duration, warmup):
        cli.run_id = run_id
        return orig(spec, run_id, duration, warmup)
    runner.run_one = run_one
    return runner, cli, store, clock


def test_orchestration_order_and_raw_files(tmp_path):
    runner, cli, store, _ = make_runner(tmp_path)
    report = runner.run_experiment("E3", bn.plan("E3", ["20"]), duration=60, warmup=10)
    assert cli.calls == ["topic_admin", "job", "producer", "job:SIGINT"]
    assert cli.procs["job"].signals == [signal.SIGINT]
    (r,) = report["runs"]
    raw = tmp_path / "raw" / r["run_id"]
    assert r["status"] == "ok" and validate_run_id(r["run_id"]) and r["run_id"].startswith("E3-p8-e2-r5000-a20-")
    for f in ("config.json", "producer.json", "job.json", "metrics.csv", "samples.csv", "summary.json", "detection.json"):
        assert (raw / f).is_file(), f
    assert r["summary"]["keeping_up"] is True and r["detection"]["injected"]["recall"] == 1.0 and store.reads
    assert json.loads((raw / "producer.json").read_text())["sent"] == 300_000
    assert (tmp_path / f"{report['report_stem']}.md").is_file() and (tmp_path / f"{report['report_stem']}.json").is_file()


def test_failed_cli_is_recorded_and_experiment_continues(tmp_path):
    runner, cli, _, _ = make_runner(tmp_path, fail={"topic_admin"})
    report = runner.run_experiment("E1", bn.plan("E1", ["1", "4"]), duration=60, warmup=10)
    assert [r["status"] for r in report["runs"]] == ["failed", "failed"] and "topic_admin" in report["runs"][0]["error"]
    assert report["runs"][0]["run_id"] != report["runs"][1]["run_id"]            # distinct stamps (one minute apart)


def test_interrupt_stops_children_and_experiment(tmp_path):
    runner, cli, _, clock = make_runner(tmp_path)
    clock.interrupt_at = BASE + 40_000                     # during the producer phase
    report = runner.run_experiment("E1", bn.plan("E1", ["1", "4"]), duration=60, warmup=10)
    assert [r["status"] for r in report["runs"]] == ["interrupted"] and report["interrupted"] is True
    assert cli.procs["producer"].signals and cli.procs["job"].signals == [signal.SIGINT]


def test_recovery_run_restarts_worker(tmp_path):
    runner, cli, _, _ = make_runner(tmp_path)
    report = runner.run_experiment("REC", bn.plan("REC"), duration=60, warmup=10)
    assert cli.calls == ["topic_admin", "job", "producer", "platform", "job:SIGINT"]
    assert "recovery" in report["runs"][0] and (tmp_path / "raw" / report["runs"][0]["run_id"] / "recovery.json").is_file()
