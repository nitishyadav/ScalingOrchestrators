"""Cassandra access for C-04 (`ids.window_scores`) and C-05 (`ids.pipeline_metrics`, `ids.runs`) — M4-F01 (REPLICA).

Timestamps cross this API as epoch milliseconds (ints). Reads use partition-key queries only (no ALLOW FILTERING).
"""
from __future__ import annotations

import calendar
import collections
import datetime as dt
import re
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from cassandra.policies import AddressTranslator

from ids_contracts import SCHEMAS_DIR
from ids_contracts import metrics as M
from ids_contracts import store as S

HOUR_MS = 3_600_000
_UTC = dt.timezone.utc
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=_UTC)
SCHEMA_FILES = (SCHEMAS_DIR / "ids_schema.cql", SCHEMAS_DIR / "metrics_schema.cql")
WINDOW_INSERT_COLUMNS = tuple(c for c, _ in S.COLUMNS)
METRICS_INSERT_COLUMNS = tuple(c for c, _ in M.METRICS_COLUMNS)
RUN_INSERT_COLUMNS = tuple(c for c, _ in M.RUNS_COLUMNS)
TIMESTAMP_COLUMNS = frozenset(c for c, t in S.COLUMNS + M.METRICS_COLUMNS + M.RUNS_COLUMNS if t == "timestamp")
EXPECTED_TABLES = {S.TABLE: S.COLUMNS, M.METRICS_TABLE: M.METRICS_COLUMNS, M.RUNS_TABLE: M.RUNS_COLUMNS}

WINDOWS_QUERY = (f"SELECT * FROM {S.KEYSPACE}.{S.TABLE} "
                 "WHERE date_bucket = %s AND hour = %s AND window_end >= %s AND window_end <= %s")
METRICS_QUERY = f"SELECT * FROM {M.KEYSPACE}.{M.METRICS_TABLE} WHERE run_id = %s LIMIT %s"
RUNS_QUERY = f"SELECT * FROM {M.KEYSPACE}.{M.RUNS_TABLE} WHERE bucket = %s LIMIT %s"
COLUMNS_QUERY = "SELECT table_name, column_name, type FROM system_schema.columns WHERE keyspace_name = %s"


class StoreUnavailable(RuntimeError):
    """Cassandra cannot be reached (exit code 1)."""


# ---- pure helpers ------------------------------------------------------------------------------
def split_statements(cql: str) -> List[str]:
    text = re.sub(r"--[^\n]*", "", cql)
    return [" ".join(s.split()) for s in text.split(";") if s.strip()]


def ms_to_dt(ms: int) -> dt.datetime:
    return _EPOCH + dt.timedelta(milliseconds=ms)


def dt_to_ms(value: dt.datetime) -> int:
    if value.tzinfo is not None:
        value = value.astimezone(_UTC)
    return calendar.timegm(value.utctimetuple()) * 1000 + value.microsecond // 1000


def row_to_dict(row: Mapping) -> dict:
    return {k: dt_to_ms(v) if isinstance(v, dt.datetime) else v for k, v in dict(row).items()}


def partitions_between(start_ms: int, end_ms: int) -> List[Tuple[str, int]]:
    """C-04 (date_bucket, hour) partitions whose hour overlaps [start_ms, end_ms]."""
    out, h = [], (start_ms // HOUR_MS) * HOUR_MS
    while h <= end_ms:
        out.append(S.partition_key(h))
        h += HOUR_MS
    return out


def drift_summary(rows: Iterable[Mapping]) -> dict:
    rows = list(rows)
    anomalous = sum(1 for r in rows if r["is_anomaly"])
    total = len(rows)
    return {"total": total, "anomalous": anomalous, "rate": anomalous / total if total else 0.0,
            "alert": S.drift_alert(anomalous, total)}


def aggregate_top(rows: Iterable[Mapping], n: int = 10) -> List[dict]:
    agg: Dict[str, dict] = {}
    for r in rows:
        if not r["is_anomaly"]:
            continue
        a = agg.setdefault(r["src_ip"], {"src_ip": r["src_ip"], "anomalous_windows": 0, "max_score": float("-inf"),
                                         "last_seen": 0, "_rules": set()})
        a["anomalous_windows"] += 1
        a["max_score"] = max(a["max_score"], r["anomaly_score"])
        a["last_seen"] = max(a["last_seen"], r["window_end"])
        a["_rules"].update(x for x in (r.get("rule_ids") or "").split(",") if x)
    top = sorted(agg.values(), key=lambda a: (-a["anomalous_windows"], -a["max_score"], a["src_ip"]))[:n]
    for a in top:
        a["rule_ids"] = ",".join(sorted(a.pop("_rules")))
    return top


# ---- connection and schema ---------------------------------------------------------------------
class _ToContactPoint(AddressTranslator):
    """Single node: Cassandra advertises its in-container IP; always route back to the contact point we can reach."""

    def __init__(self, host: str):
        self.host = host

    def translate(self, addr):
        return self.host


def connect(cfg, timeout_s: float = 5.0):
    from cassandra import ConsistencyLevel
    from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, NoHostAvailable
    from cassandra.policies import RoundRobinPolicy
    from cassandra.query import dict_factory

    profile = ExecutionProfile(load_balancing_policy=RoundRobinPolicy(), consistency_level=ConsistencyLevel.LOCAL_ONE,
                               request_timeout=20, row_factory=dict_factory)
    hosts = list(cfg.cassandra_hosts)
    kwargs = dict(contact_points=hosts, port=cfg.cassandra_port, protocol_version=5,
                  execution_profiles={EXEC_PROFILE_DEFAULT: profile},
                  connect_timeout=timeout_s, control_connection_timeout=timeout_s)
    if len(hosts) == 1:
        kwargs["address_translator"] = _ToContactPoint(hosts[0])
    try:
        return Cluster(**kwargs).connect()
    except (NoHostAvailable, OSError) as exc:
        raise StoreUnavailable(f"cannot reach Cassandra at {hosts}:{cfg.cassandra_port}: {exc}") from None


def apply_schema(session) -> int:
    n = 0
    for path in SCHEMA_FILES:
        for stmt in split_statements(path.read_text()):
            session.execute(stmt)
            n += 1
    return n


def check_schema(session) -> List[str]:
    actual: Dict[str, Dict[str, str]] = collections.defaultdict(dict)
    for r in session.execute(COLUMNS_QUERY, (S.KEYSPACE,)):
        actual[r["table_name"]][r["column_name"]] = r["type"]
    errors = []
    for table, cols in EXPECTED_TABLES.items():
        if table not in actual:
            errors.append(f"table {S.KEYSPACE}.{table} missing")
            continue
        want = dict(cols)
        for c, t in want.items():
            if c not in actual[table]:
                errors.append(f"{table}.{c} missing")
            elif actual[table][c] != t:
                errors.append(f"{table}.{c} is {actual[table][c]}, contract says {t}")
        errors += [f"{table}.{c} not in contract" for c in sorted(set(actual[table]) - set(want))]
    return errors


# ---- writer / reader ---------------------------------------------------------------------------
def _bind(row: Mapping, columns: Tuple[str, ...]) -> tuple:
    return tuple(ms_to_dt(row[c]) if c in TIMESTAMP_COLUMNS and row[c] is not None else row[c] for c in columns)


class StoreWriter:
    def __init__(self, session):
        self.session = session

        def prep(table, cols):
            return session.prepare(f"INSERT INTO {S.KEYSPACE}.{table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})")
        self._win = prep(S.TABLE, WINDOW_INSERT_COLUMNS)
        self._met = prep(M.METRICS_TABLE, METRICS_INSERT_COLUMNS)
        self._run = prep(M.RUNS_TABLE, RUN_INSERT_COLUMNS)

    def _many(self, stmt, rows, cols):
        from cassandra.concurrent import execute_concurrent_with_args
        execute_concurrent_with_args(self.session, stmt, [_bind(r, cols) for r in rows], concurrency=64,
                                     raise_on_first_error=True)

    def write_windows(self, rows: List[Mapping]) -> None:
        self._many(self._win, rows, WINDOW_INSERT_COLUMNS)

    def write_metrics(self, rows: List[Mapping]) -> None:
        self._many(self._met, rows, METRICS_INSERT_COLUMNS)

    def write_run(self, row: Mapping) -> None:
        self.session.execute(self._run, _bind(row, RUN_INSERT_COLUMNS))


class StoreReader:
    def __init__(self, session):
        self.session = session

    def recent_windows(self, now_ms: int, seconds: int = S.DRIFT_WINDOW_S, run_id: Optional[str] = None) -> List[dict]:
        start = now_ms - seconds * 1000
        rows = []
        for bucket, hour in partitions_between(start, now_ms):
            for r in self.session.execute(WINDOWS_QUERY, (bucket, hour, ms_to_dt(start), ms_to_dt(now_ms))):
                d = row_to_dict(r)
                if run_id is None or d["run_id"] == run_id:
                    rows.append(d)
        return sorted(rows, key=lambda d: (-d["window_end"], d["src_ip"]))

    def drift(self, now_ms: int, seconds: int = S.DRIFT_WINDOW_S, run_id: Optional[str] = None) -> dict:
        return drift_summary(self.recent_windows(now_ms, seconds, run_id))

    def top_flagged(self, now_ms: int, seconds: int = S.DRIFT_WINDOW_S, n: int = 10, run_id: Optional[str] = None):
        return aggregate_top(self.recent_windows(now_ms, seconds, run_id), n)

    def metrics(self, run_id: str, limit: int = 60) -> List[dict]:
        return [row_to_dict(r) for r in self.session.execute(METRICS_QUERY, (run_id, limit))]

    def runs(self, limit: int = 20) -> List[dict]:
        return [row_to_dict(r) for r in self.session.execute(RUNS_QUERY, (M.RUNS_BUCKET, limit))]


def delete_run(session, data: Mapping) -> None:
    """Remove rows written for a synthetic/test run (windows by full key, metrics by partition, the run row)."""
    for r in data["windows"]:
        session.execute(f"DELETE FROM {S.KEYSPACE}.{S.TABLE} WHERE date_bucket = %s AND hour = %s AND window_end = %s "
                        "AND src_ip = %s", (r["date_bucket"], r["hour"], ms_to_dt(r["window_end"]), r["src_ip"]))
    if data.get("metrics"):
        session.execute(f"DELETE FROM {M.KEYSPACE}.{M.METRICS_TABLE} WHERE run_id = %s", (data["metrics"][0]["run_id"],))
    if data.get("run"):
        session.execute(f"DELETE FROM {M.KEYSPACE}.{M.RUNS_TABLE} WHERE bucket = %s AND started_at = %s",
                        (data["run"]["bucket"], ms_to_dt(data["run"]["started_at"])))
