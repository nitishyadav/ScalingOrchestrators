"""C-06 Runtime Config and Control: env-var spec, config loader, CLI conventions.

Contract: contracts/C-06_runtime_config_control.md  (owner M1)
Precedence: overrides (CLI flags) > environment > defaults below.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

CONTRACT_ID = "C-06"
CONTRACT_VERSION = "1.0.0-rc.7"

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE_ERROR = 2

ATTACK_MODES = ("none", "ddos", "synflood", "portscan", "mixed")
RUN_ID_PATTERN = re.compile(
    r"^((E1|E2|E3|P1|LAT|REC)-p\d{1,2}-e\d{1,2}-r\d+-a\d{1,3}(-t\d{1,5})?-\d{12}|DEV-[A-Za-z0-9_.-]+)$"
)
_TRIGGER_PATTERN = re.compile(r"^\d+ (second|seconds|millisecond|milliseconds)$")
_MEMORY_PATTERN = re.compile(r"^\d+[mMgG]$")
_BOOTSTRAP_PATTERN = re.compile(r"^[^,:\s]+:\d{1,5}(,[^,:\s]+:\d{1,5})*$")
_IDENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SPARK_MASTER_PATTERN = re.compile(r"^(spark://[^\s]+:\d{1,5}|local(\[(\*|\d+)\])?)$")

WORKSPACE_MARKER = "CONSTITUTION.md"


class ConfigError(ValueError):
    """Invalid configuration value (maps to exit code 2)."""


@dataclass(frozen=True)
class EnvVar:
    name: str
    kind: str          # "str" | "int" | "float" | "path"
    default: str
    check: Optional[Callable[[Any], bool]] = None
    rule: str = ""


def _range(lo: float, hi: float) -> Callable[[Any], bool]:
    return lambda v: lo <= v <= hi


ENV_SPEC: Tuple[EnvVar, ...] = (
    EnvVar("IDS_ROOT", "path", ""),
    EnvVar("KAFKA_BOOTSTRAP", "str", "localhost:9092", _BOOTSTRAP_PATTERN.match, "host:port[,host:port]"),
    EnvVar("KAFKA_TOPIC", "str", "network-events", bool, "non-empty"),
    EnvVar("KAFKA_PARTITIONS", "int", "8", _range(1, 16), "1..16"),
    EnvVar("CASSANDRA_HOSTS", "str", "localhost", bool, "non-empty"),
    EnvVar("CASSANDRA_PORT", "int", "9042", _range(1, 65535), "1..65535"),
    EnvVar("CASSANDRA_KEYSPACE", "str", "ids", _IDENT_PATTERN.match, "CQL identifier"),
    EnvVar("SPARK_MASTER_URL", "str", "spark://localhost:7077", _SPARK_MASTER_PATTERN.match, "spark://host:port or local[*]"),
    EnvVar("SPARK_WORKERS", "int", "2", _range(1, 4), "1..4"),
    EnvVar("SPARK_EXECUTORS", "int", "2", _range(1, 8), "1..8"),
    EnvVar("SPARK_EXECUTOR_CORES", "int", "1", _range(1, 8), "1..8"),
    EnvVar("SPARK_EXECUTOR_MEMORY", "str", "768m", _MEMORY_PATTERN.match, "e.g. 512m, 1g"),
    EnvVar("TRIGGER_INTERVAL", "str", "1 second", _TRIGGER_PATTERN.match, "'<n> second(s)' or '<n> millisecond(s)'"),
    EnvVar("DATA_DIR", "path", "./runtime/data"),
    EnvVar("MODEL_BUNDLE_PATH", "path", "./runtime/bundle/current"),
    EnvVar("CHECKPOINT_DIR", "path", "./runtime/checkpoints"),
    EnvVar("RESULTS_DIR", "path", "./Module4_Storage_Dashboard_Benchmarking/results"),
    EnvVar("PRODUCER_RATE", "int", "5000", _range(1, 100_000), "1..100000 events/s"),
    EnvVar("RUN_DURATION_S", "int", "600", _range(1, 86_400), "1..86400"),
    EnvVar("ATTACK_MODE", "str", "none", lambda v: v in ATTACK_MODES, "|".join(ATTACK_MODES)),
    EnvVar("ATTACK_SHARE", "float", "0.0", _range(0.0, 1.0), "0.0..1.0"),
    EnvVar("RUN_ID", "str", "DEV-local", RUN_ID_PATTERN.match, "see C-06 §6"),
)
ENV_NAMES = tuple(v.name for v in ENV_SPEC)


@dataclass(frozen=True)
class RuntimeConfig:
    workspace_root: Path
    kafka_bootstrap: str
    kafka_topic: str
    kafka_partitions: int
    cassandra_hosts: Tuple[str, ...]
    cassandra_port: int
    cassandra_keyspace: str
    spark_master_url: str
    spark_workers: int
    spark_executors: int
    spark_executor_cores: int
    spark_executor_memory: str
    trigger_interval: str
    data_dir: Path
    model_bundle_path: Path
    checkpoint_dir: Path
    results_dir: Path
    producer_rate: int
    run_duration_s: int
    attack_mode: str
    attack_share: float
    run_id: str

    def as_dict(self) -> Dict[str, Any]:
        out = {}
        for key, value in self.__dict__.items():
            out[key] = str(value) if isinstance(value, Path) else (list(value) if isinstance(value, tuple) else value)
        return out


def find_workspace_root(start: Optional[Path] = None) -> Path:
    """Nearest directory (start or a parent) containing CONSTITUTION.md; falls back to start."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / WORKSPACE_MARKER).is_file():
            return candidate
    return start


def _convert(var: EnvVar, raw: Any) -> Any:
    if var.kind == "int":
        try:
            if isinstance(raw, bool):
                raise ValueError
            value: Any = int(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"{var.name}={raw!r} is not an integer") from None
    elif var.kind == "float":
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"{var.name}={raw!r} is not a number") from None
    else:
        value = str(raw).strip()
    if var.check is not None and not var.check(value):
        raise ConfigError(f"{var.name}={raw!r} violates rule: {var.rule}")
    return value


def load_config(
    env: Optional[Mapping[str, str]] = None,
    overrides: Optional[Mapping[str, Any]] = None,
    cwd: Optional[Path] = None,
) -> RuntimeConfig:
    """Resolve and validate the C-06 configuration. Raises ConfigError on bad values.

    `overrides` are CLI flag values keyed by env-var name (None values are ignored).
    """
    env = os.environ if env is None else env
    overrides = {k: v for k, v in (overrides or {}).items() if v is not None}
    unknown = sorted(set(overrides) - set(ENV_NAMES))
    if unknown:
        raise ConfigError(f"unknown config keys {unknown}")

    values: Dict[str, Any] = {}
    for var in ENV_SPEC:
        if var.name in overrides:
            raw = overrides[var.name]
        elif env.get(var.name, "") != "":
            raw = env[var.name]
        else:
            raw = var.default
        values[var.name] = _convert(var, raw) if raw != "" or var.kind != "path" else ""

    root_raw = values["IDS_ROOT"]
    root = Path(root_raw).expanduser().resolve() if root_raw else find_workspace_root(cwd)
    if not root.is_dir():
        raise ConfigError(f"IDS_ROOT={root} is not a directory")

    def path(name: str) -> Path:
        p = Path(values[name]).expanduser()
        return p if p.is_absolute() else (root / p).resolve()

    if values["ATTACK_MODE"] == "none" and values["ATTACK_SHARE"] != 0.0:
        raise ConfigError("ATTACK_SHARE must be 0 when ATTACK_MODE=none")
    if values["ATTACK_MODE"] != "none" and values["ATTACK_SHARE"] <= 0.0:
        raise ConfigError("ATTACK_SHARE must be > 0 when ATTACK_MODE is not none")

    return RuntimeConfig(
        workspace_root=root,
        kafka_bootstrap=values["KAFKA_BOOTSTRAP"],
        kafka_topic=values["KAFKA_TOPIC"],
        kafka_partitions=values["KAFKA_PARTITIONS"],
        cassandra_hosts=tuple(h.strip() for h in values["CASSANDRA_HOSTS"].split(",") if h.strip()),
        cassandra_port=values["CASSANDRA_PORT"],
        cassandra_keyspace=values["CASSANDRA_KEYSPACE"],
        spark_master_url=values["SPARK_MASTER_URL"],
        spark_workers=values["SPARK_WORKERS"],
        spark_executors=values["SPARK_EXECUTORS"],
        spark_executor_cores=values["SPARK_EXECUTOR_CORES"],
        spark_executor_memory=values["SPARK_EXECUTOR_MEMORY"],
        trigger_interval=values["TRIGGER_INTERVAL"],
        data_dir=path("DATA_DIR"),
        model_bundle_path=path("MODEL_BUNDLE_PATH"),
        checkpoint_dir=path("CHECKPOINT_DIR"),
        results_dir=path("RESULTS_DIR"),
        producer_rate=values["PRODUCER_RATE"],
        run_duration_s=values["RUN_DURATION_S"],
        attack_mode=values["ATTACK_MODE"],
        attack_share=values["ATTACK_SHARE"],
        run_id=values["RUN_ID"],
    )


ENV_FILE_RELATIVE = Path("integration") / ".env"


def load_runtime_config(
    overrides: Optional[Mapping[str, Any]] = None,
    cwd: Optional[Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> RuntimeConfig:
    """What every module CLI calls (C-06 §2): `<root>/integration/.env` (if present) < process env < overrides."""
    env = dict(os.environ if env is None else env)
    root = Path(env["IDS_ROOT"]).expanduser().resolve() if env.get("IDS_ROOT") else find_workspace_root(cwd)
    env_file = root / ENV_FILE_RELATIVE
    merged = dict(read_env_file(env_file)) if env_file.is_file() else {}
    merged.update({k: v for k, v in env.items() if v != ""})
    return load_config(env=merged, overrides=overrides, cwd=root)


def validate_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.match(run_id))


def summary_line(command: str, run_id: str, status: str = "ok", **fields: Any) -> str:
    """The single JSON line every C-06 CLI prints last on stdout."""
    payload = {"status": status, "command": command, "run_id": run_id}
    payload.update(fields)
    return json.dumps(payload, separators=(",", ":"), default=str)


def read_env_file(path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file (comments and blank lines ignored, no quoting rules)."""
    result: Dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.split(" #", 1)[0].strip()
    return result
