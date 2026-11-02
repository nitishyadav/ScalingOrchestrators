"""Read and write the C-04 / C-05 tables (M4-T022, M4-FR-004/005/008/009).

Rows are plain dicts with timestamps as epoch ms, exactly as `ids_contracts` validates them.
Window reads use only partition-key queries, one per 5-minute bucket (C-04 §5, M4-ADR-001).
"""
from __future__ import annotations

import calendar
import datetime as dt
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ids_contracts import metrics as M
from ids_contracts import store as S

_TS = {c for c, t in (*S.COLUMNS, *M.METRICS_COLUMNS, *M.RUNS_COLUMNS) if t == "timestamp"}


def to_ms(value: Any) -> Optional[int]:
    """Driver timestamp (naive UTC datetime, or aware) → epoch ms. Ints pass through."""
    if value is None or isinstance(value, int):
        return value
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc)
    return calendar.timegm(value.utctimetuple()) * 1000 + value.microsecond // 1000


def current_ms() -> int:
    return int(time.time() * 1000)


def _from_driver(row: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: (to_ms(v) if k in _TS else v) for k, v in row.items()}


@dataclass(frozen=True)
class ReadResult:
    rows: List[Dict[str, Any]]                             # newest window_end first
    invalid: int                                           # live rows skipped because validate_row failed
    partitions: int                                        # partition-key queries issued


class Store:
    def __init__(self, session: Any, keyspace: str = S.KEYSPACE):
        self._session = session
        self._ks = keyspace
        self._prepared: Dict[str, Any] = {}

    # ---- statements ----
    def _stmt(self, query: str):
        if query not in self._prepared:
            from cassandra import ConsistencyLevel
            p = self._session.prepare(query)
            p.consistency_level = ConsistencyLevel.LOCAL_ONE                  # C-04 §2: reads and writes
            self._prepared[query] = p
        return self._prepared[query]

    # ---- C-04 reads ----
    def read_windows(self, start_ms: int, end_ms: int, run_id: Optional[str] = None) -> ReadResult:
        """Rows with window_end in [start_ms, end_ms], optionally only `run_id` (filtered client-side)."""
        stmt = self._stmt(f"SELECT * FROM {self._ks}.{S.TABLE} WHERE date_bucket = ? AND bucket = ? "
                          f"AND window_end >= ? AND window_end <= ?")
        keys = S.partition_keys(start_ms, end_ms)
        rows: List[Dict[str, Any]] = []
        invalid = 0
        for date_bucket, bucket in keys:                    # newest partition first, rows newest first within
            for raw in self._session.execute(stmt, (date_bucket, bucket, start_ms, end_ms)):
                row = _from_driver(raw)
                if S.validate_row(row):
                    invalid += 1
                elif run_id is None or row["run_id"] == run_id:
                    rows.append(row)
        rows.sort(key=lambda r: (-r["window_end"], r["src_ip"]))
        return ReadResult(rows, invalid, len(keys))

    def read_recent(self, seconds: int = S.DRIFT_WINDOW_S, now_ms: Optional[int] = None,
                    run_id: Optional[str] = None) -> ReadResult:
        end = current_ms() if now_ms is None else now_ms
        return self.read_windows(end - seconds * 1000, end, run_id)

    # ---- C-05 reads ----
    def latest_metrics(self, run_id: str, limit: int = 60) -> List[Dict[str, Any]]:
        stmt = self._stmt(f"SELECT * FROM {self._ks}.{M.METRICS_TABLE} WHERE run_id = ? LIMIT ?")
        return [_from_driver(r) for r in self._session.execute(stmt, (run_id, limit))]

    def latest_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        stmt = self._stmt(f"SELECT * FROM {self._ks}.{M.RUNS_TABLE} WHERE bucket = ? LIMIT ?")
        return [_from_driver(r) for r in self._session.execute(stmt, (M.RUNS_BUCKET, limit))]

    # ---- writes (validated first; nothing is sent if any row is invalid) ----
    def _write(self, table: str, columns, rows: Iterable[Mapping[str, Any]], validate) -> int:
        rows = list(rows)
        for i, row in enumerate(rows):
            errors = validate(row)
            if errors:
                raise ValueError(f"{table} row {i} violates the contract: {'; '.join(errors)}")
        names = [c for c, _ in columns]
        stmt = self._stmt(f"INSERT INTO {self._ks}.{table} ({', '.join(names)}) "
                          f"VALUES ({', '.join('?' for _ in names)})")
        for row in rows:
            self._session.execute(stmt, tuple(row[c] for c in names))
        return len(rows)

    def write_windows(self, rows: Iterable[Mapping[str, Any]]) -> int:
        return self._write(S.TABLE, S.COLUMNS, rows, S.validate_row)

    def write_metrics(self, rows: Iterable[Mapping[str, Any]]) -> int:
        return self._write(M.METRICS_TABLE, M.METRICS_COLUMNS, rows, M.validate_metrics_row)

    def write_run(self, row: Mapping[str, Any]) -> int:
        return self._write(M.RUNS_TABLE, M.RUNS_COLUMNS, [row], M.validate_run_row)
