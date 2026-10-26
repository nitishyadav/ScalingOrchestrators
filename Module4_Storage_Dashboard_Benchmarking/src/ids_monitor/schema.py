"""`python -m ids_monitor.schema apply|check` — create / verify the C-04 + C-05 tables (M4-F01, REPLICA)."""
from __future__ import annotations

import argparse
import sys
from typing import Callable, Mapping, Optional, Sequence

from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

from . import store as st

HINT = "Is the platform running? (`python -m ids_ingest.platform status` in Module 1)"


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         session_factory: Optional[Callable] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_monitor.schema", description="Create or verify the C-04/C-05 tables.")
    p.add_argument("action", choices=("apply", "check"))
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    try:
        session = (session_factory or st.connect)(cfg)
    except st.StoreUnavailable as exc:
        print(f"{exc}\n{HINT}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    if args.action == "apply":
        n = st.apply_schema(session)
        print(summary_line("schema apply", cfg.run_id, statements=n, keyspace="ids"))
        return EXIT_OK
    errors = st.check_schema(session)
    if errors:
        print("schema differs from C-04/C-05:\n  " + "\n  ".join(errors), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    print(summary_line("schema check", cfg.run_id, tables=len(st.EXPECTED_TABLES), keyspace="ids"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
