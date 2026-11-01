"""C-06 command conventions for M4 CLIs (M4-T020): config, exit codes, one JSON summary line last."""
from __future__ import annotations

import sys
from typing import Any, Callable, Dict, Mapping, Optional

from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, RuntimeConfig,
                                  load_runtime_config, summary_line)


class UsageError(ValueError):
    """Bad flags or arguments (exit 2)."""


class CommandFailed(RuntimeError):
    """The command ran but its outcome is a failure (exit 1). `fields` still go into the summary."""

    def __init__(self, message: str, **fields: Any):
        super().__init__(message)
        self.fields = fields


def run(command: str, handler: Callable[[RuntimeConfig], Optional[Dict[str, Any]]],
        overrides: Optional[Mapping[str, Any]] = None) -> int:
    """Load C-06 config, run `handler(cfg)`, print the summary line, and return the C-06 exit code."""
    try:
        cfg = load_runtime_config(overrides=overrides)
    except ConfigError as exc:
        print(f"{command}: config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    try:
        fields = handler(cfg) or {}
    except UsageError as exc:
        print(f"{command}: usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except CommandFailed as exc:
        print(f"{command}: {exc}", file=sys.stderr)
        print(summary_line(command, cfg.run_id, status="failed", **exc.fields))
        return EXIT_RUNTIME_ERROR
    except Exception as exc:                               # noqa: BLE001 - C-06: runtime errors exit 1, no traceback
        print(f"{command}: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    run_id = fields.pop("run_id", cfg.run_id)
    print(summary_line(command, run_id, **fields))
    return EXIT_OK
