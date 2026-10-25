"""`python -m ids_ingest.platform up|down|status|restart-worker|clean` — C-06 §5 (M1-T023; M1-F01 FR-001..FR-010)."""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Mapping, Optional, Sequence

import yaml

from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, RuntimeConfig,
                                  load_runtime_config, summary_line)

from . import COMPOSE_FILE
from ._compose import ComposeEngine, ComposeError, EngineUnavailable, summarize

SERVICES = ("kafka", "spark-master", "spark-worker", "spark-client", "cassandra")
MIN_ENGINE_MEM_GIB = 9.0
MIN_ENGINE_CPUS = 4
UP_TIMEOUT_S = 180
RESTART_TIMEOUT_S = 30
POLL_S = 3.0
GIB = 1024 ** 3
MASTER_JSON = "http://localhost:8080/json/"
ENGINE_HINT = "Is the Docker engine running? Start Docker Desktop or run `colima start`."


@dataclass
class Deps:
    engine: object
    port_in_use: Callable[[int], bool]
    master_workers: Callable[[], List[dict]]
    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


# ---- static facts from the compose file ------------------------------------------------------
def _mem_gib(value: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([mMgG])", str(value).strip())
    num, unit = float(m.group(1)), m.group(2).lower()
    return num if unit == "g" else num / 1024


def compose_facts(workers: int) -> tuple:
    """(memory limit total in GiB for `workers` workers, sorted host ports)."""
    services = yaml.safe_load(COMPOSE_FILE.read_text())["services"]
    total = sum(_mem_gib(s["mem_limit"]) * (workers if n == "spark-worker" else 1) for n, s in services.items())
    ports = sorted({int(str(p).split(":")[0]) for s in services.values() for p in s.get("ports", [])})
    return total, ports


# ---- real dependencies -----------------------------------------------------------------------
def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _master_workers() -> List[dict]:
    try:
        with urllib.request.urlopen(MASTER_JSON, timeout=3) as resp:
            return json.load(resp).get("workers", [])
    except (OSError, ValueError):
        return []


def real_deps(cfg: RuntimeConfig) -> Deps:
    for sub in ("", "data", "data/raw", "data/replay", "bundle", "checkpoints"):
        (cfg.workspace_root / "runtime" / sub).mkdir(parents=True, exist_ok=True)
    engine = ComposeEngine(COMPOSE_FILE, env={"IDS_HOST_ROOT": str(cfg.workspace_root)})
    return Deps(engine=engine, port_in_use=_port_in_use, master_workers=_master_workers)


# ---- helpers ---------------------------------------------------------------------------------
def _alive(workers: List[dict]) -> List[dict]:
    return [w for w in workers if str(w.get("state", "")).upper() == "ALIVE"]


def _status(deps: Deps):
    states, n_workers = summarize(deps.engine.ps(), SERVICES)
    alive = len(_alive(deps.master_workers())) if states.get("spark-master") == "healthy" else 0
    ready = all(v == "healthy" for v in states.values()) and n_workers > 0 and alive >= n_workers
    return states, n_workers, alive, ready


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---- commands ----------------------------------------------------------------------------------
def cmd_status(cfg, deps, args) -> int:
    states, n_workers, alive, ready = _status(deps)
    print(summary_line("platform status", cfg.run_id, status="ok" if ready else "not_ready",
                       services=states, ready=ready, workers=n_workers, alive_workers=alive))
    return EXIT_OK if ready else EXIT_RUNTIME_ERROR


def cmd_up(cfg, deps, args) -> int:
    workers = cfg.spark_workers
    info = args.engine_info
    mem_gib, cpus = info.get("MemTotal", 0) / GIB, int(info.get("NCPU", 0))
    budget, ports = compose_facts(workers)
    if mem_gib < MIN_ENGINE_MEM_GIB or cpus < MIN_ENGINE_CPUS:
        _err(f"Docker engine has {mem_gib:.1f} GiB memory / {cpus} CPUs; need ≥ {MIN_ENGINE_MEM_GIB:.0f} GiB and "
             f"≥ {MIN_ENGINE_CPUS} CPUs (e.g. `colima start --cpu 6 --memory 10`).")
        return EXIT_RUNTIME_ERROR
    if budget > mem_gib:
        _err(f"warning: container memory limits ({budget:.2f} GiB with {workers} workers) exceed engine memory "
             f"({mem_gib:.2f} GiB); fine for development, but benchmarks should use the default 2 workers.")

    running = any(str(c.get("State", "")).lower() == "running" for c in deps.engine.ps())
    if not running:
        busy = [p for p in ports if deps.port_in_use(p)]
        if busy:
            _err(f"host port(s) {busy} already in use by another process; free them and retry (nothing was started).")
            return EXIT_RUNTIME_ERROR

    start = deps.now()
    deps.engine.up(workers)
    while True:
        states, n_workers, alive, ready = _status(deps)
        if ready and n_workers == workers:
            print(summary_line("platform up", cfg.run_id, services=states, ready=True, workers=n_workers,
                               alive_workers=alive, elapsed_s=round(deps.now() - start, 1)))
            return EXIT_OK
        if deps.now() - start > args.timeout:
            _err(f"timeout after {args.timeout}s waiting for a healthy platform: {states} "
                 f"(alive workers {alive}/{workers}). Containers left running for inspection (`docker compose -p ids logs`).")
            return EXIT_RUNTIME_ERROR
        deps.sleep(POLL_S)


def cmd_down(cfg, deps, args) -> int:
    deps.engine.down(volumes=False)
    print(summary_line("platform down", cfg.run_id, volumes_kept=True))
    return EXIT_OK


def cmd_clean(cfg, deps, args) -> int:
    deps.engine.down(volumes=True)
    print(summary_line("platform clean", cfg.run_id, volumes_removed=True))
    return EXIT_OK


def cmd_restart_worker(cfg, deps, args) -> int:
    workers = sorted((c for c in deps.engine.ps() if c.get("Service") == "spark-worker"), key=lambda c: c.get("Name", ""))
    if not 1 <= args.index <= len(workers):
        _err(f"--index must be between 1 and {len(workers)} (running workers)")
        return EXIT_USAGE_ERROR
    name = next((c["Name"] for c in workers if c["Name"].endswith(f"-{args.index}")), workers[args.index - 1]["Name"])
    before = {w.get("id") for w in deps.master_workers()}
    start = deps.now()
    deps.engine.restart_container(name)
    while True:
        new = [w for w in _alive(deps.master_workers()) if w.get("id") not in before]
        elapsed = deps.now() - start
        if new:
            print(summary_line("platform restart-worker", cfg.run_id, container=name, new_worker_id=new[0].get("id"),
                               reregistered_s=round(elapsed, 1)))
            return EXIT_OK
        if elapsed > args.timeout:
            _err(f"{name} did not re-register with the master within {args.timeout}s")
            return EXIT_RUNTIME_ERROR
        deps.sleep(1.0)


# ---- entry point -----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ids_ingest.platform", description="Platform cluster control (C-06 §5).")
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up", help="start all services and wait until healthy")
    up.add_argument("--workers", type=int, help="spark-worker containers, 1..4 (→ SPARK_WORKERS)")
    up.add_argument("--timeout", type=int, default=UP_TIMEOUT_S, help="readiness timeout in seconds")
    sub.add_parser("status", help="per-service health and overall readiness")
    sub.add_parser("down", help="stop all services, keep data volumes")
    clean = sub.add_parser("clean", help="stop all services and REMOVE data volumes")
    clean.add_argument("--yes", action="store_true", help="confirm volume removal")
    rw = sub.add_parser("restart-worker", help="restart one spark-worker container")
    rw.add_argument("--index", type=int, required=True, help="1-based worker index")
    rw.add_argument("--timeout", type=int, default=RESTART_TIMEOUT_S)
    return p


COMMANDS = {"up": cmd_up, "status": cmd_status, "down": cmd_down, "clean": cmd_clean, "restart-worker": cmd_restart_worker}


def main(argv: Optional[Sequence[str]] = None, deps: Optional[Deps] = None, env: Optional[Mapping[str, str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_runtime_config(overrides={"SPARK_WORKERS": getattr(args, "workers", None)}, env=env)
    except ConfigError as exc:
        _err(f"config error: {exc}")
        return EXIT_USAGE_ERROR
    if args.command == "clean" and not args.yes:
        _err("refusing to remove platform data volumes without --yes")
        return EXIT_USAGE_ERROR
    try:
        deps = deps or real_deps(cfg)
        args.engine_info = deps.engine.engine_info()   # every command fails fast when the engine is down
        return COMMANDS[args.command](cfg, deps, args)
    except EngineUnavailable as exc:
        _err(f"{exc}\n{ENGINE_HINT}")
        return EXIT_RUNTIME_ERROR
    except ComposeError as exc:
        _err(str(exc))
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    sys.exit(main())
