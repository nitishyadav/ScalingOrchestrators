"""Benchmark harness (M4-T222, M4-F03). C-06 §5: `python -m ids_monitor.bench --experiment E1|E2|E3|P1|LAT|REC`.

    python -m ids_monitor.bench --experiment E1 --dry-run                     # plan + exact commands, touches nothing
    python -m ids_monitor.bench --experiment E1 --levels 1 --duration 60      # smoke (≈ 2 min)
    python -m ids_monitor.bench --experiment E2                               # 3 levels × 600 s

Drives M1/M3 only through their C-06 CLIs (subprocesses, FR-041). Reads C-05 (and C-04 for E3) through M4-F01 `Store`.
The CLI, store and clock are injected, so everything except the live smoke runs in unit tests (NFR-021).
"""
from __future__ import annotations

import argparse
import json
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import CONTRACT_VERSION as C06_VERSION
from ids_contracts.config import RuntimeConfig

from ids_monitor import bench_math as BM
from ids_monitor import bench_plan as BP
from ids_monitor import bench_report as BR
from ids_monitor import cli, db
from ids_monitor.store import Store

COMMAND = "ids_monitor.bench"
REGISTER_TIMEOUT_S, SETTLE_S = 180, 10
PRODUCER_GRACE_S = 120
DRAIN_IDLE_S, DRAIN_TIMEOUT_S = 10, 120
STOP_TIMEOUT_S, KILL_TIMEOUT_S = 120, 30
POLL_S = 2
DEFAULT_WARMUP_S = 60
LOG_NAMES = {"topic": "topic_admin", "job": "job", "producer": "producer", "restart": "restart"}


class PreflightError(RuntimeError):
    pass


class LevelFailed(RuntimeError):
    pass


# ---- adapters ------------------------------------------------------------------------------------
def last_json(text: str) -> Optional[Dict[str, Any]]:
    """C-06: the last stdout line that parses as a JSON object is the CLI summary."""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


class Handle:
    def __init__(self, proc: subprocess.Popen, log, log_path: Path):
        self._p, self._log, self._path = proc, log, log_path

    def poll(self) -> Optional[int]:
        return self._p.poll()

    def wait(self, timeout: float) -> Optional[int]:
        try:
            return self._p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None

    def interrupt(self) -> None:
        if self._p.poll() is None:
            self._p.send_signal(signal.SIGINT)                # the C-06 CLIs stop gracefully on SIGINT

    def kill(self) -> None:
        if self._p.poll() is None:
            self._p.kill()

    def summary(self) -> Optional[Dict[str, Any]]:
        self._log.flush()
        return last_json(self._path.read_text(errors="replace"))


class SubprocessCli:
    """`python -m <module> …` from the workspace root, same interpreter and environment (each CLI reads C-06 itself)."""

    def __init__(self, workspace_root: Path, python: str = sys.executable):
        self.root, self.python = workspace_root, python

    def available(self, module: str) -> bool:
        try:
            return subprocess.run([self.python, "-m", module, "--help"], cwd=self.root, capture_output=True,
                                  timeout=60).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def run(self, argv: Sequence[str], log_path: Path, timeout: float = 300):
        try:
            p = subprocess.run([self.python, "-m", *argv], cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            log_path.write_text((exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
            return 1, None
        log_path.write_text(p.stdout)
        return p.returncode, last_json(p.stdout)

    def start(self, argv: Sequence[str], log_path: Path) -> Handle:
        log = log_path.open("w")
        # own session: a terminal Ctrl-C reaches only the harness, which then stops each child gracefully (S-053 lesson)
        proc = subprocess.Popen([self.python, "-m", *argv], cwd=self.root, stdout=log, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
        return Handle(proc, log, log_path)


class SystemClock:
    @staticmethod
    def now_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def sleep(s: float) -> None:
        time.sleep(s)


# ---- runner --------------------------------------------------------------------------------------
class Runner:
    def __init__(self, cli_adapter, store, clock, results_dir: Path, duration_s: int, warmup_s: int, log=None):
        self.cli, self.store, self.clock = cli_adapter, store, clock
        self.results = Path(results_dir)
        self.duration_s, self.warmup_s = duration_s, warmup_s
        self.log = log or (lambda msg: print(f"[bench] {msg}", file=sys.stderr, flush=True))
        self._last_stamp: Optional[str] = None

    # preflight (FR-041)
    def preflight(self, experiment: str) -> None:
        missing = [m for m in BP.modules_needed(experiment) if not self.cli.available(m)]
        if missing:
            raise PreflightError(f"C-06 CLI(s) not available: {', '.join(missing)}. Install M1/M3 into this Python "
                                 f"(`make install` in Module1_… and Module3_…) and start the platform.")

    def _new_stamp(self) -> str:
        st = BP.stamp(self.clock.now_ms())
        while st == self._last_stamp:                           # run IDs carry minutes: never reuse one
            self.clock.sleep(60 - (self.clock.now_ms() // 1000) % 60 + 0.5)
            st = BP.stamp(self.clock.now_ms())
        self._last_stamp = st
        return st

    def _elapsed_s(self, since_ms: int) -> float:
        return (self.clock.now_ms() - since_ms) / 1000

    # one experiment
    def run_experiment(self, experiment: str, levels: Optional[Sequence[str]] = None, dry_run: bool = False) -> Dict[str, Any]:
        specs = BP.plan(experiment, levels)
        if dry_run:
            return self._dry_run(experiment, specs)
        runs: List[Dict[str, Any]] = []
        interrupted = False
        first_stamp = None
        for spec in specs:
            st = self._new_stamp()
            first_stamp = first_stamp or st
            run, interrupted = self.run_level(spec, BP.run_id(spec, st))
            runs.append(run)
            if interrupted:
                break
        rep = BR.experiment_report(experiment, runs, self.duration_s, self.warmup_s, interrupted)
        name = f"{experiment}-{first_stamp}.json"
        BR.write_json(self.results / name, rep)
        (self.results / name.replace(".json", ".md")).write_text(BR.report_markdown(rep))
        self.log(f"report: {self.results / name.replace('.json', '.md')}")
        return {"experiment": experiment, "runs": runs, "failed": [r["run_id"] for r in runs if r["status"] == "failed"],
                "interrupted": interrupted, "report": name, "results_dir": str(self.results)}

    def _dry_run(self, experiment: str, specs: Sequence[BP.RunSpec]) -> Dict[str, Any]:
        st = BP.stamp(self.clock.now_ms())
        print(f"# {experiment}: {BP.EXPERIMENTS[experiment].target}")
        print(f"# {len(specs)} level(s) × ({self.duration_s} s replay + ≈ 90 s overhead); run-ID stamps are set at each start")
        runs = []
        for spec in specs:
            rid = BP.run_id(spec, st)
            print(f"\n## level {spec.level}: {rid}")
            for step, argv in BP.commands(spec, rid, self.duration_s).items():
                when = f"  (at {spec.restart_at:.0%} of the replay)" if step == "restart" else ""
                print(f"python -m {shlex.join(argv)}{when}")
            runs.append({"level": spec.level, "run_id": rid, "status": "planned", "reason": ""})
        return {"experiment": experiment, "runs": runs, "failed": [], "interrupted": False, "report": None,
                "results_dir": str(self.results)}

    # one level (FR-042, FR-050)
    def run_level(self, spec: BP.RunSpec, rid: str):
        raw = self.results / "raw" / rid
        raw.mkdir(parents=True, exist_ok=True)
        cmds = BP.commands(spec, rid, self.duration_s)
        BR.write_json(raw / "config.json", {"run_id": rid, "spec": asdict(spec), "duration_s": self.duration_s,
                                             "warmup_s": self.warmup_s, "started_ms": self.clock.now_ms(),
                                             "contracts": {"C-04": S.CONTRACT_VERSION, "C-05": M.CONTRACT_VERSION,
                                                           "C-06": C06_VERSION}})
        BR.write_json(raw / "commands.json", {k: ["python", "-m", *v] for k, v in cmds.items()})
        run: Dict[str, Any] = {"level": spec.level, "run_id": rid, "status": "ok", "reason": "", "notes": [],
                               "summary": None, "detection": None, "banner": None, "recovery": None, "raw_dir": str(raw)}
        job = producer = None
        t_start = t_end = restart_ms = None
        interrupted = False
        self.log(f"{rid}: start")
        try:
            code, summ = self.cli.run(cmds["topic"], raw / "topic_admin.log")
            BR.write_json(raw / "topic_admin.json", summ)
            if code != 0:
                raise LevelFailed(f"topic_admin exited {code}")
            job = self.cli.start(cmds["job"], raw / "job.log")
            self._await_registration(rid, job)
            self.clock.sleep(SETTLE_S)
            t_start = self.clock.now_ms()
            producer = self.cli.start(cmds["producer"], raw / "producer.log")
            restart_at = None if spec.restart_at is None else t_start + spec.restart_at * self.duration_s * 1000
            deadline = t_start + (self.duration_s + PRODUCER_GRACE_S) * 1000
            while producer.poll() is None:
                if restart_at is not None and restart_ms is None and self.clock.now_ms() >= restart_at:
                    restart_ms = self.clock.now_ms()
                    self.log(f"{rid}: restarting worker 1")
                    rc, rs = self.cli.run(cmds["restart"], raw / "restart.log")
                    BR.write_json(raw / "restart.json", rs)
                    if rc != 0:
                        run["notes"].append(f"restart-worker exited {rc}")
                if self.clock.now_ms() > deadline:
                    producer.interrupt()
                    producer.wait(30)
                    run["notes"].append("producer overran its duration and was stopped")
                    break
                self.clock.sleep(1)
            t_end = self.clock.now_ms()
            if producer.poll() not in (0, None):
                raise LevelFailed(f"producer exited {producer.poll()}")
            self._drain(rid, t_end)
        except LevelFailed as exc:
            run["status"], run["reason"] = "failed", str(exc)
        except KeyboardInterrupt:
            interrupted = True
            run["status"], run["reason"] = "interrupted", "Ctrl-C"
            self.log(f"{rid}: interrupted, stopping children")
            if producer is not None:
                producer.interrupt()
                producer.wait(30)
            t_end = t_end or self.clock.now_ms()
        finally:
            self._stop_job(job, run)
            if job is not None:
                BR.write_json(raw / "job.json", job.summary())
        self._collect(spec, rid, raw, run, producer, t_start, t_end, restart_ms)
        self.log(f"{rid}: {run['status']} {run['reason']}".rstrip())
        return run, interrupted

    def _await_registration(self, rid: str, job) -> None:
        since = self.clock.now_ms()
        while self._elapsed_s(since) < REGISTER_TIMEOUT_S:
            if any(r["run_id"] == rid for r in self.store.latest_runs(20)):
                return
            if job.poll() is not None:
                raise LevelFailed(f"stream job exited {job.poll()} before registering")
            self.clock.sleep(POLL_S)
        raise LevelFailed(f"stream job did not register in C-05 runs within {REGISTER_TIMEOUT_S} s")

    def _drain(self, rid: str, t_end: int) -> None:
        since = self.clock.now_ms()
        while self._elapsed_s(since) < DRAIN_TIMEOUT_S:
            inputs = [m["batch_ts"] for m in self.store.latest_metrics(rid, 20) if m["input_rows"] > 0]
            if self._elapsed_s(max(inputs + [t_end])) >= DRAIN_IDLE_S:
                return
            self.clock.sleep(POLL_S)

    def _stop_job(self, job, run: Dict[str, Any]) -> None:
        if job is None:
            return
        if job.poll() is None:
            job.interrupt()
            if job.wait(STOP_TIMEOUT_S) is None:
                job.interrupt()                                  # the job wrapper's second SIGINT = force
                if job.wait(KILL_TIMEOUT_S) is None:
                    job.kill()
                    run["notes"].append("stream job did not stop and was killed")
        rc = job.poll()
        if rc not in (0, None) and run["status"] == "ok":
            run["notes"].append(f"stream job exited {rc}")

    def _collect(self, spec, rid, raw: Path, run, producer, t_start, t_end, restart_ms) -> None:
        if producer is not None:
            BR.write_json(raw / "producer.json", producer.summary())
        # the job handle exists if we got past topic_admin
        metrics = self.store.latest_metrics(rid, 100_000) if t_start is not None else []
        BR.write_csv(raw / "metrics.csv", sorted(metrics, key=lambda m: m["batch_ts"]), BR.METRICS_FIELDS)
        if t_start is None:
            return
        prod = (producer.summary() if producer is not None else None) or {}
        summary = BM.summarize(metrics, t_start, t_end, self.warmup_s, spec.rate, prod.get("achieved_rate"))
        run["summary"] = summary
        BR.write_csv(raw / "samples.csv", BM.samples(metrics, t_start, t_end), BR.SAMPLE_FIELDS)
        if summary["status"] != "ok" and run["status"] == "ok":
            run["status"], run["reason"] = "failed", summary["reason"]
        if spec.experiment == "E3":
            windows = self.store.read_windows(t_start - 60_000, self.clock.now_ms(), run_id=rid).rows
            run["detection"], run["banner"] = BM.detection(windows), BM.banner(windows, t_start, t_end)
            BR.write_json(raw / "detection.json", {"detection": run["detection"], "banner": run["banner"]})
        if spec.restart_at is not None:
            if restart_ms is None:
                if run["status"] == "ok":
                    run["status"], run["reason"] = "failed", "worker restart did not happen"
            else:
                run["recovery"] = BM.recovery(metrics, restart_ms)
                BR.write_json(raw / "recovery.json", run["recovery"])
        BR.write_json(raw / "summary.json", {**summary, "run_id": rid, "status": run["status"] if run["status"] != "ok"
                                             else summary["status"], "reason": run["reason"], "notes": run["notes"]})


# ---- CLI (FR-051, C-06 §5) -----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"python -m {COMMAND}", description="M4-F03 benchmark harness (C-06 §5).")
    p.add_argument("--experiment", required=True, choices=list(BP.EXPERIMENTS))
    p.add_argument("--levels", help="comma-separated subset of the experiment's levels (smoke tests)")
    p.add_argument("--duration", type=int, help="replay seconds per level (→ RUN_DURATION_S, default 600)")
    p.add_argument("--warmup", type=int, help=f"seconds excluded from the steady state (default min({DEFAULT_WARMUP_S}, duration / 4))")
    p.add_argument("--dry-run", action="store_true", help="print the plan and the exact commands; run nothing")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)                    # argparse: bad flag → exit 2 (C-06)
    levels = [x.strip() for x in args.levels.split(",") if x.strip()] if args.levels else None

    def handler(cfg: RuntimeConfig) -> Dict[str, Any]:
        duration = cfg.run_duration_s
        warmup = min(DEFAULT_WARMUP_S, duration // 4) if args.warmup is None else args.warmup
        if not 0 <= warmup < duration:
            raise cli.UsageError(f"--warmup {warmup} must be ≥ 0 and < the duration {duration}")
        try:
            BP.plan(args.experiment, levels)
        except ValueError as exc:
            raise cli.UsageError(str(exc)) from exc
        results = Path(cfg.results_dir)
        adapter = SubprocessCli(cfg.workspace_root)
        if args.dry_run:
            res = Runner(adapter, None, SystemClock(), results, duration, warmup).run_experiment(
                args.experiment, levels, dry_run=True)
        else:
            _, session = db.connect(cfg)
            runner = Runner(adapter, Store(session, cfg.cassandra_keyspace), SystemClock(), results, duration, warmup)
            try:
                runner.preflight(args.experiment)
            except PreflightError as exc:
                raise cli.CommandFailed(str(exc), experiment=args.experiment, runs=[], failed=[]) from exc
            res = runner.run_experiment(args.experiment, levels)
        fields = {"experiment": args.experiment, "runs": [r["run_id"] for r in res["runs"]], "failed": res["failed"],
                  "results_dir": res["results_dir"], "report": res["report"], "dry_run": args.dry_run}
        if res["interrupted"]:
            return {**fields, "status": "stopped"}
        if res["failed"]:
            raise cli.CommandFailed(f"{len(res['failed'])} run(s) failed", **fields)
        return fields

    return cli.run(COMMAND, handler, overrides={"RUN_DURATION_S": args.duration} if args.duration else None)


if __name__ == "__main__":
    sys.exit(main())
