"""One-command demo of the whole pipeline (I-04), using only the modules' C-06 CLIs.

    .venv/bin/python integration/demo.py up       # platform → schema → bundle check → topic → stream job → producer → dashboard
    .venv/bin/python integration/demo.py status
    .venv/bin/python integration/demo.py down     # graceful, in order: producer → stream job → dashboard
    .venv/bin/python integration/demo.py down --platform     # … then the containers too (volumes kept)

State: runtime/run/demo.json (run id, pids); logs: runtime/run/logs/. Colima itself is left running (`colima stop` after `down --platform`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import List, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runtime" / "run"
STATE = RUN_DIR / "demo.json"
M1, M2 = ROOT / "Module1_Data_Ingestion_Platform", ROOT / "Module2_ML_Anomaly_Model"
M3, M4 = ROOT / "Module3_Spark_Stream_Processing", ROOT / "Module4_Storage_Dashboard_Benchmarking"
MASTER_JSON = "http://localhost:8080/json/"
DASHBOARD_PORT = 8501
STOP_ORDER = ("producer", "job", "dashboard")          # upstream first, so nothing is left half-written
STOP_TIMEOUT_S = {"producer": 30, "job": 150, "dashboard": 15}
PY = sys.executable


class DemoError(RuntimeError):
    pass


class Ops:
    """Side effects, injectable for tests."""

    def run(self, cmd: Sequence[str], cwd: Path, timeout: int = 600):
        p = subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "IDS_ROOT": str(ROOT)})
        return p.returncode, p.stdout, p.stderr

    def spawn(self, cmd: Sequence[str], cwd: Path, log: Path) -> int:
        log.parent.mkdir(parents=True, exist_ok=True)
        fh = open(log, "a")
        return subprocess.Popen(list(cmd), cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True,
                                env={**os.environ, "IDS_ROOT": str(ROOT)}).pid

    def alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError):
            return False
        try:                                              # reap if it is our own exited child
            done, _ = os.waitpid(pid, os.WNOHANG)
            return done == 0
        except ChildProcessError:
            return True

    def signal(self, pid: int, sig: int) -> None:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    def active_apps(self) -> List[str]:
        try:
            with urllib.request.urlopen(MASTER_JSON, timeout=3) as resp:
                return [a.get("name", "") for a in json.load(resp).get("activeapps", [])]
        except OSError:
            return []

    def port_in_use(self, port: int) -> bool:
        with socket.socket() as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def sleep(self, s: float) -> None:
        time.sleep(s)

    def now(self) -> float:
        return time.time()


def say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.is_file() else {}


def save_state(state: Mapping) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def last_json(text: str) -> dict:
    for line in reversed((text or "").strip().splitlines()):
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    return {}


def step(ops: Ops, title: str, cmd: Sequence[str], cwd: Path, timeout: int = 600) -> dict:
    say(f"→ {title}")
    rc, out, err = ops.run(cmd, cwd, timeout)
    if rc != 0:
        raise DemoError(f"{title} failed (exit {rc}):\n{err.strip()[-1500:]}")
    return last_json(out)


def up(ops: Ops, args) -> dict:
    state = load_state()
    running = {k: v for k, v in state.get("pids", {}).items() if ops.alive(v)}
    if running:
        raise DemoError(f"a demo is already running ({', '.join(running)}); `demo.py down` first")
    run_id = args.run_id or "DEV-demo-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M")
    logs = RUN_DIR / "logs"
    step(ops, "platform up (Kafka, Spark, Cassandra)", [PY, "-m", "ids_ingest.platform", "up"], M1, 900)
    step(ops, "store schema (C-04/C-05)", [PY, "-m", "ids_monitor.schema", "apply"], M4)
    bundle = step(ops, "detection bundle check (C-03)", [PY, "-m", "ids_model.bundle", "check"], M2)
    step(ops, f"topic with {args.partitions} partitions (fresh)", [PY, "-m", "ids_ingest.topic_admin", "--partitions",
                                                                   str(args.partitions), "--recreate"], M1)
    pids = {}
    say(f"→ stream job {run_id} ({args.executors} executors)")
    pids["job"] = ops.spawn([PY, "-m", "ids_stream.job", "--executors", str(args.executors), "--run-id", run_id,
                             "--starting-offsets", "earliest"], M3, logs / "job.log")
    save_state({"run_id": run_id, "pids": pids, "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    deadline = ops.now() + 180
    while f"ids-stream-{run_id}" not in ops.active_apps():
        if not ops.alive(pids["job"]):
            raise DemoError(f"the stream job exited during start-up; see {logs / 'job.log'}")
        if ops.now() > deadline:
            raise DemoError(f"the stream job did not register with Spark within 180 s; see {logs / 'job.log'}")
        ops.sleep(2)
    ops.sleep(10)                                          # query start-up after the app registers
    producer = [PY, "-m", "ids_ingest.producer", "--rate", str(args.rate), "--duration", str(args.duration), "--run-id", run_id]
    if args.attack_share > 0:
        producer += ["--attack-mode", "mixed", "--attack-share", f"{args.attack_share:g}"]
    say(f"→ producer {args.rate} ev/s for {args.duration} s" + (f", {args.attack_share:.0%} injected attacks" if args.attack_share else ""))
    pids["producer"] = ops.spawn(producer, M1, logs / "producer.log")
    dashboard = None
    if args.no_dashboard:
        pass
    elif ops.port_in_use(DASHBOARD_PORT):
        say(f"→ dashboard: port {DASHBOARD_PORT} is already serving (left as is; pick run {run_id} in its sidebar)")
    else:
        say("→ dashboard")
        pids["dashboard"] = ops.spawn([PY, "-m", "streamlit", "run", "src/ids_monitor/dashboard.py", "--server.port",
                                       str(DASHBOARD_PORT), "--server.headless", "true", "--browser.gatherUsageStats", "false",
                                       "--", "--run-id", run_id], M4, logs / "dashboard.log")
        dashboard = f"http://localhost:{DASHBOARD_PORT}"
    save_state({"run_id": run_id, "pids": pids, "started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "bundle_version": bundle.get("bundle_version")})
    return {"run_id": run_id, "pids": pids, "dashboard": dashboard or f"http://localhost:{DASHBOARD_PORT}",
            "spark_ui": "http://localhost:8080", "bundle_version": bundle.get("bundle_version"), "logs": str(logs)}


def status(ops: Ops, args) -> dict:
    state = load_state()
    procs = {k: {"pid": v, "alive": ops.alive(v)} for k, v in state.get("pids", {}).items()}
    rc, out, _ = ops.run([PY, "-m", "ids_ingest.platform", "status"], M1, 60)
    return {"run_id": state.get("run_id"), "processes": procs, "platform": last_json(out) if rc == 0 else {"ready": False}}


def stop_process(ops: Ops, name: str, pid: int) -> str:
    if not ops.alive(pid):
        return "not running"
    sig = signal.SIGTERM if name == "dashboard" else signal.SIGINT   # job: SIGINT → driver finishes its batch (S-053)
    ops.signal(pid, sig)
    deadline = ops.now() + STOP_TIMEOUT_S[name]
    while ops.alive(pid):
        if ops.now() > deadline:
            ops.signal(pid, signal.SIGINT if name == "job" else signal.SIGKILL)   # job: second SIGINT = force
            ops.sleep(5)
            if ops.alive(pid):
                ops.signal(pid, signal.SIGKILL)
            return "forced"
        ops.sleep(1)
    return "stopped"


def down(ops: Ops, args) -> dict:
    state = load_state()
    pids = state.get("pids", {})
    result = {}
    for name in STOP_ORDER:
        if name in pids:
            say(f"→ stopping {name}")
            result[name] = stop_process(ops, name, pids[name])
    if args.platform:
        step(ops, "platform down (volumes kept)", [PY, "-m", "ids_ingest.platform", "down"], M1, 300)
        result["platform"] = "down"
    if STATE.is_file():
        STATE.unlink()
    return {"run_id": state.get("run_id"), "stopped": result}


def main(argv: Optional[Sequence[str]] = None, ops: Optional[Ops] = None) -> int:
    p = argparse.ArgumentParser(prog="integration/demo.py", description="One-command pipeline demo (I-04).")
    sub = p.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("up")
    u.add_argument("--rate", type=int, default=2000)
    u.add_argument("--duration", type=int, default=3600, help="producer seconds (default 1 h)")
    u.add_argument("--attack-share", type=float, default=0.2)
    u.add_argument("--partitions", type=int, default=8)
    u.add_argument("--executors", type=int, default=2)
    u.add_argument("--run-id")
    u.add_argument("--no-dashboard", action="store_true")
    sub.add_parser("status")
    d = sub.add_parser("down")
    d.add_argument("--platform", action="store_true", help="also stop the containers (volumes kept)")
    args = p.parse_args(argv)
    ops = ops or Ops()
    try:
        out = {"up": up, "status": status, "down": down}[args.cmd](ops, args)
    except DemoError as exc:
        say(f"demo {args.cmd} failed: {exc}")
        print(json.dumps({"status": "error", "command": f"demo {args.cmd}", "error": str(exc)[:500]}))
        return 1
    print(json.dumps({"status": "ok", "command": f"demo {args.cmd}", **out}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
