"""Thin wrapper around the `docker` / `docker compose` CLI (M1-T022). Engine-agnostic: Docker Desktop or Colima."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Tuple

PROJECT = "ids"
_FALLBACK_DOCKER = ("/opt/homebrew/bin/docker", "/usr/local/bin/docker")


class EngineUnavailable(RuntimeError):
    """The docker CLI is missing or the engine is not running."""


class ComposeError(RuntimeError):
    """A docker compose command failed."""


def docker_bin() -> str:
    found = shutil.which("docker") or next((p for p in _FALLBACK_DOCKER if os.access(p, os.X_OK)), None)
    if not found:
        raise EngineUnavailable("docker CLI not found on PATH")
    return found


def parse_ps_output(text: str) -> List[dict]:
    """`docker compose ps --format json` prints a JSON array (old) or one object per line (new)."""
    text = text.strip()
    if not text:
        return []
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def service_state(containers: Iterable[dict]) -> str:
    """Aggregate one service's containers into: missing | exited/... | starting | unhealthy | running | healthy."""
    containers = list(containers)
    if not containers:
        return "missing"
    for c in containers:
        state = str(c.get("State", "")).lower()
        if state != "running":
            return state or "unknown"
    healths = {str(c.get("Health", "")).lower() for c in containers}
    for bad in ("unhealthy", "starting"):
        if bad in healths:
            return bad
    return "healthy" if healths == {"healthy"} else "running"


def summarize(containers: List[dict], services: Iterable[str]) -> Tuple[Dict[str, str], int]:
    """({service: state}, number of spark-worker containers)."""
    by_service: Dict[str, List[dict]] = {}
    for c in containers:
        by_service.setdefault(c.get("Service", ""), []).append(c)
    states = {s: service_state(by_service.get(s, [])) for s in services}
    return states, len(by_service.get("spark-worker", []))


Runner = Callable[..., subprocess.CompletedProcess]


class ComposeEngine:
    def __init__(self, compose_file: Path, env: Optional[Mapping[str, str]] = None, runner: Runner = subprocess.run):
        self.compose_file = Path(compose_file)
        self.env = {**os.environ, **(env or {})}
        self.runner = runner

    def _run(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        try:
            proc = self.runner(args, capture_output=True, text=True, env=self.env)
        except FileNotFoundError as exc:
            raise EngineUnavailable(str(exc)) from exc
        if check and proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            if "Cannot connect to the Docker daemon" in err or "docker daemon" in err.lower():
                raise EngineUnavailable(err)
            raise ComposeError(f"{' '.join(args[1:4])}… failed: {err[-800:]}")
        return proc

    def _compose(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return self._run([docker_bin(), "compose", "-p", PROJECT, "-f", str(self.compose_file), *args], check=check)

    def engine_info(self) -> dict:
        proc = self._run([docker_bin(), "info", "--format", "{{json .}}"], check=False)
        if proc.returncode != 0:
            raise EngineUnavailable((proc.stderr or proc.stdout).strip())
        return json.loads(proc.stdout)

    def ps(self) -> List[dict]:
        return parse_ps_output(self._compose("ps", "-a", "--format", "json").stdout)

    def up(self, workers: int) -> None:
        self._compose("up", "-d", "--build", "--remove-orphans", "--scale", f"spark-worker={workers}")

    def down(self, volumes: bool = False) -> None:
        self._compose("down", "--remove-orphans", *(["-v"] if volumes else []))

    def restart_container(self, name: str) -> None:
        self._run([docker_bin(), "restart", name])

    def exec(self, service: str, *cmd: str, check: bool = True) -> subprocess.CompletedProcess:
        return self._compose("exec", "-T", service, *cmd, check=check)
