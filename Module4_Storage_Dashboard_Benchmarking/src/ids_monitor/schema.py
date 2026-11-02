"""Apply and check the C-04 / C-05 schema (M4-T021, M4-FR-001..003).

    python -m ids_monitor.schema apply [--recreate]   # idempotent; --recreate drops tables whose key changed
    python -m ids_monitor.schema check                # exit 1 when the live tables differ from the contracts

The DDL is read from contracts/schemas (never copied). `ids.` is rewritten to CASSANDRA_KEYSPACE (C-06).
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ids_contracts import SCHEMAS_DIR

from ids_monitor import cli, db

DDL_FILES = ("ids_schema.cql", "metrics_schema.cql")       # C-04, C-05
COMMAND = "ids_monitor.schema"


@dataclass(frozen=True)
class TableSpec:
    columns: Tuple[Tuple[str, str], ...]                   # (name, cql type); DDL order (live: key first, then by name)
    partition: Tuple[str, ...]
    clustering: Tuple[Tuple[str, str], ...]                # (name, 'ASC' | 'DESC')


class SchemaMigrationRequired(RuntimeError):
    """A live table has a different primary key; CREATE TABLE IF NOT EXISTS would silently keep it."""


# ---- DDL ---------------------------------------------------------------------------------------
def ddl_text(keyspace: str) -> str:
    text = "\n".join((SCHEMAS_DIR / f).read_text(encoding="utf-8") for f in DDL_FILES)
    text = re.sub(r"--[^\n]*", "", text)
    text = re.sub(r"\bKEYSPACE IF NOT EXISTS ids\b", f"KEYSPACE IF NOT EXISTS {keyspace}", text)
    return re.sub(r"\bids\.", f"{keyspace}.", text)


def statements(text: str) -> List[str]:
    """Distinct statements in file order (both files create the keyspace)."""
    out: List[str] = []
    for stmt in (" ".join(s.split()) for s in text.split(";")):
        if stmt and stmt not in out:
            out.append(stmt)
    return out


def parse_ddl(text: str) -> Dict[str, TableSpec]:
    text = re.sub(r"--[^\n]*", "", text)
    tables = {}
    for name, body, opts in re.findall(r"CREATE TABLE IF NOT EXISTS \w+\.(\w+) \((.*?)\)\s*(WITH[^;]*);", text, re.S):
        cols = tuple(re.findall(r"^\s*(\w+)\s+(\w+),\s*$", body, re.M))
        pk = re.search(r"PRIMARY KEY \(\((.*?)\),\s*(.*?)\)\s*$", body.strip(), re.S)
        order = dict(re.findall(r"(\w+) (ASC|DESC)", re.search(r"CLUSTERING ORDER BY \((.*?)\)", opts).group(1)))
        clustering = tuple((c.strip(), order.get(c.strip(), "ASC")) for c in pk.group(2).split(","))
        tables[name] = TableSpec(cols, tuple(c.strip() for c in pk.group(1).split(",")), clustering)
    return tables


# ---- live schema -------------------------------------------------------------------------------
LIVE_QUERY = ("SELECT table_name, column_name, type, kind, position, clustering_order "
              "FROM system_schema.columns WHERE keyspace_name = %s")


def schema_from_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, TableSpec]:
    by_table: Dict[str, List[Mapping[str, Any]]] = {}
    for r in rows:
        by_table.setdefault(r["table_name"], []).append(r)
    out = {}
    for table, cols in by_table.items():
        part = sorted((c for c in cols if c["kind"] == "partition_key"), key=lambda c: c["position"])
        clus = sorted((c for c in cols if c["kind"] == "clustering"), key=lambda c: c["position"])
        regular = sorted((c for c in cols if c["kind"] not in ("partition_key", "clustering")),
                         key=lambda c: c["column_name"])
        out[table] = TableSpec(
            columns=tuple((c["column_name"], c["type"]) for c in (*part, *clus, *regular)),
            partition=tuple(c["column_name"] for c in part),
            clustering=tuple((c["column_name"], str(c["clustering_order"]).upper()) for c in clus))
    return out


def live_schema(session: Any, keyspace: str) -> Dict[str, TableSpec]:
    return schema_from_rows(session.execute(LIVE_QUERY, (keyspace,)))


def diff_schema(expected: Mapping[str, TableSpec], live: Mapping[str, TableSpec]) -> List[str]:
    diffs: List[str] = []
    for table, exp in expected.items():
        got = live.get(table)
        if got is None:
            diffs.append(f"{table}: missing table")
            continue
        if (got.partition, got.clustering) != (exp.partition, exp.clustering):
            diffs.append(f"{table}: primary key is {_key(got)}, contract says {_key(exp)}")
        exp_cols, got_cols = dict(exp.columns), dict(got.columns)
        for c, t in exp.columns:
            if c not in got_cols:
                diffs.append(f"{table}: missing column {c}")
            elif got_cols[c] != t:
                diffs.append(f"{table}: column {c} is {got_cols[c]}, contract says {t}")
        diffs += [f"{table}: unexpected column {c}" for c in got_cols if c not in exp_cols]
    return diffs


def _key(t: TableSpec) -> str:
    return f"(({', '.join(t.partition)}), {', '.join(f'{c} {o}' for c, o in t.clustering)})"


# ---- apply -------------------------------------------------------------------------------------
def apply_schema(session: Any, keyspace: str, recreate: bool = False) -> Dict[str, List[str]]:
    text = ddl_text(keyspace)
    expected = parse_ddl(text)
    live = live_schema(session, keyspace)
    changed = [t for t, exp in expected.items()
               if t in live and (live[t].partition, live[t].clustering) != (exp.partition, exp.clustering)]
    if changed and not recreate:
        detail = "; ".join(f"{t}: live key {_key(live[t])} != contract {_key(expected[t])}" for t in changed)
        raise SchemaMigrationRequired(
            f"{detail}. CREATE TABLE IF NOT EXISTS keeps the old key. Re-run with --recreate to drop and "
            f"recreate (C-04 §11: DROP TABLE IF EXISTS {keyspace}.<table>; rows are lost)")
    stmts = statements(text)
    session.execute(stmts[0])                               # keyspace first
    for t in changed:
        session.execute(f"DROP TABLE IF EXISTS {keyspace}.{t}")
    for stmt in stmts[1:]:
        session.execute(stmt)
    return {"created": [t for t in expected if t not in live or t in changed], "recreated": changed}


# ---- CLI ---------------------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"python -m {COMMAND}", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="action", required=True)
    a = sub.add_parser("apply", help="create keyspace and tables (idempotent), then check")
    a.add_argument("--recreate", action="store_true", help="drop and recreate tables whose primary key changed")
    sub.add_parser("check", help="compare the live tables with the contracts")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    def handler(cfg):
        cluster, session = db.connect(cfg)
        try:
            out: Dict[str, Any] = {"action": args.action, "keyspace": cfg.cassandra_keyspace}
            if args.action == "apply":
                out.update(apply_schema(session, cfg.cassandra_keyspace, recreate=args.recreate))
            diffs = diff_schema(parse_ddl(ddl_text(cfg.cassandra_keyspace)), live_schema(session, cfg.cassandra_keyspace))
            if diffs:
                raise cli.CommandFailed("schema drift:\n  " + "\n  ".join(diffs), drift=diffs, **out)
            return {**out, "drift": []}
        finally:
            db.close(cluster)

    return cli.run(f"{COMMAND} {args.action}", handler)


if __name__ == "__main__":
    sys.exit(main())
