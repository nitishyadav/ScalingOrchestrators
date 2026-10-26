"""`python -m ids_ingest.prepare` — CIC-IDS2017 TrafficLabelling CSVs → C-01 replay dataset (M1-F02).

Streams each CSV (latin-1), selects the mapped columns by position, applies the C-01 §3.2 drop rules, and writes one
Parquet file per day in replay order (`row_idx`), plus a manifest (C-01 §2.2). Writes are atomic.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import ipaddress
import json
import math
import os
import resource
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

from ids_contracts import events as ev
from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

from . import MODULE_DIR, __version__

TOOL = "ids_ingest.prepare"
CHUNK_ROWS = 100_000
SAMPLE_MAX = 10_000
PART_FILE = "part-00000.parquet"
SAMPLE_PATH = MODULE_DIR / "mocks" / "replay_sample.parquet"

# C-01 §3.4 non-partition columns, in order (the `day` column comes from the partition directory)
SCHEMA = pa.schema([
    ("row_idx", pa.int64()), ("source_file", pa.string()), ("orig_ts", pa.string()), ("src_ip", pa.string()),
    ("dst_ip", pa.string()), ("dst_port", pa.int32()), ("bytes_sent", pa.int64()), ("syn_flag", pa.int32()),
    ("ack_flag", pa.int32()), ("label", pa.string()),
])
SAMPLE_SCHEMA = SCHEMA.append(pa.field("day", pa.string()))
_INT32_MAX = 2**31 - 1


class PrepareError(RuntimeError):
    """Input problem or failed preparation (exit code 1)."""


def raw_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "raw" / "TrafficLabelling"


def replay_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "replay"


def _stems() -> List[Tuple[str, str]]:
    return [(day, stem) for day in ev.REPLAY_DAYS for stem in ev.CIC_FILE_ORDER[day]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_text(values) -> bytes:
    """Canonical serialisation used for content_sha256 (C-01 §2.2)."""
    return ("|".join(str(v) for v in values) + "\n").encode("utf-8")


# ---- cleaning ----------------------------------------------------------------------------------
class RowCleaner:
    """Maps one CSV row to (source_file, orig_ts, src_ip, dst_ip, dst_port, bytes_sent, syn, ack, label) or a drop reason."""

    def __init__(self, raw_header: Sequence[str], source_file: str):
        header = [h.strip() for h in raw_header]
        missing = [c for c in ev.CIC_COLUMN_MAP if c not in header]
        if missing:
            raise PrepareError(f"{source_file}: missing columns {missing}")
        # first occurrence by stripped name (the duplicated `Fwd Header Length` is never selected)
        self.pos = {ev.CIC_COLUMN_MAP[c]: header.index(c) for c in ev.CIC_COLUMN_MAP}
        self.width = len(header)
        self.source_file = source_file

    def clean(self, cells: Sequence[str]):
        if not any(c.strip() for c in cells):
            return None, "empty_row"
        if len(cells) != self.width:
            return None, "wrong_field_count"
        v = {field: cells[i].strip() for field, i in self.pos.items()}
        if any(x == "" for x in v.values()):
            return None, "missing_field"
        nums = {}
        for field in ("dst_port", "bytes_sent", "syn_flag", "ack_flag"):
            try:
                x = float(v[field])
            except ValueError:
                return None, "non_numeric"
            if not math.isfinite(x):
                return None, "nan_or_inf"
            if x < 0:
                return None, "negative"
            nums[field] = math.floor(x + 0.5)          # integral in practice; half-up rounding per C-01 §3.2
        if nums["dst_port"] > 65535:
            return None, "bad_port"
        if nums["syn_flag"] > _INT32_MAX or nums["ack_flag"] > _INT32_MAX or nums["bytes_sent"] > ev.MAX_INT64:
            return None, "non_numeric"
        try:
            ipaddress.ip_address(v["src_ip"])
            ipaddress.ip_address(v["dst_ip"])
        except ValueError:
            return None, "bad_ip"
        label = ev.normalise_label(v["label"])
        if label not in ev.LABELS:
            return None, "unknown_label"
        return (self.source_file, v["orig_ts"], v["src_ip"], v["dst_ip"], nums["dst_port"], nums["bytes_sent"],
                nums["syn_flag"], nums["ack_flag"], label), None


# ---- writing -------------------------------------------------------------------------------------
class DayWriter:
    """Chunked Parquet writer for one day with a running content hash."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = 0
        self.hash = hashlib.sha256()
        self.labels: collections.Counter = collections.Counter()
        self._buf: List[tuple] = []
        self._writer: Optional[pq.ParquetWriter] = None

    def add(self, record: tuple) -> None:
        row = (self.rows, *record)
        self._buf.append(row)
        self.hash.update(_row_text(row))
        self.labels[record[-1]] += 1
        self.rows += 1
        if len(self._buf) >= CHUNK_ROWS:
            self._flush()

    def _flush(self) -> None:
        if not self._buf:
            return
        columns = list(zip(*self._buf))
        table = pa.Table.from_arrays([pa.array(col, type=f.type) for col, f in zip(columns, SCHEMA)], schema=SCHEMA)
        if self._writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = pq.ParquetWriter(self.path, SCHEMA, compression="snappy")
        self._writer.write_table(table)
        self._buf = []

    def close(self) -> None:
        self._flush()
        if self._writer is None:                       # a day with zero valid rows still gets an empty file
            self.path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(SCHEMA.empty_table(), self.path, compression="snappy")
        else:
            self._writer.close()


# ---- prepare -----------------------------------------------------------------------------------
def _read_manifest(data_dir: Path) -> Optional[dict]:
    path = replay_dir(data_dir) / ev.REPLAY_MANIFEST_NAME
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def prepare_all(data_dir: Path, force: bool = False, allow_unverified: bool = False) -> dict:
    data_dir = Path(data_dir)
    src = raw_dir(data_dir)
    known = {f"{stem}{ev.CIC_FILE_SUFFIX}" for _, stem in _stems()}
    ignored = sorted(p.name for p in src.glob("*.csv") if p.name not in known) if src.is_dir() else []

    inputs = []
    for day, stem in _stems():
        path = src / f"{stem}{ev.CIC_FILE_SUFFIX}"
        if not path.is_file():
            raise PrepareError(f"missing raw file {path} (copy the TrafficLabelling CSVs to {src})")
        sha = _sha256(path)
        verified = sha == ev.CIC_REFERENCE.get(stem, (None,))[0]
        if not verified and not allow_unverified:
            raise PrepareError(f"{path.name}: sha256 {sha} does not match C-01 reference "
                               f"(use --allow-unverified to proceed; the manifest will record it)")
        inputs.append({"source_file": stem, "day": day, "sha256": sha, "verified": verified, "path": path})

    previous = _read_manifest(data_dir)
    fingerprint = [(i["source_file"], i["sha256"]) for i in inputs]
    if (previous and not force and previous.get("contract_version") == ev.CONTRACT_VERSION
            and previous.get("tool_version") == __version__
            and [(i["source_file"], i["sha256"]) for i in previous.get("inputs", [])] == fingerprint):
        return _summary("noop", previous, ignored)

    out = replay_dir(data_dir)
    tmp = data_dir / f"replay.tmp-{os.getpid()}"
    old = data_dir / f"replay.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        manifest = _build(inputs, tmp)
        errors = ev.validate_manifest(manifest)
        if errors:
            raise PrepareError(f"internal error, manifest invalid: {errors}")
        (tmp / ev.REPLAY_MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n")
        if out.exists():
            os.replace(out, old)
        os.replace(tmp, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
    return _summary("rebuild" if previous else "create", manifest, ignored)


def _build(inputs: List[dict], tmp: Path) -> dict:
    days: Dict[str, dict] = {}
    labels: collections.Counter = collections.Counter()
    manifest_inputs = []
    for day in ev.REPLAY_DAYS:
        writer = DayWriter(tmp / f"day={day}" / PART_FILE)
        day_inputs = [i for i in inputs if i["day"] == day]
        for item in day_inputs:
            dropped: collections.Counter = collections.Counter()
            data_rows = valid_rows = 0
            with open(item["path"], "r", encoding="latin-1", newline="") as fh:
                reader = csv.reader(fh)
                try:
                    cleaner = RowCleaner(next(reader), item["source_file"])
                except StopIteration:
                    raise PrepareError(f"{item['path'].name} is empty") from None
                for cells in reader:
                    data_rows += 1
                    record, reason = cleaner.clean(cells)
                    if reason:
                        dropped[reason] += 1
                    else:
                        writer.add(record)
                        valid_rows += 1
            manifest_inputs.append({"source_file": item["source_file"], "day": day, "sha256": item["sha256"],
                                    "verified": item["verified"], "data_rows": data_rows, "valid_rows": valid_rows,
                                    "dropped": dict(sorted(dropped.items()))})
        writer.close()
        labels.update(writer.labels)
        days[day] = {"rows": writer.rows, "files": [i["source_file"] for i in day_inputs],
                     "content_sha256": writer.hash.hexdigest(), "path": f"day={day}/{PART_FILE}"}
    return {
        "contract": ev.CONTRACT_ID, "contract_version": ev.CONTRACT_VERSION, "tool": TOOL, "tool_version": __version__,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "inputs": manifest_inputs, "days": days, "total_rows": sum(d["rows"] for d in days.values()),
        "labels": dict(sorted(labels.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def _summary(action: str, manifest: dict, ignored: List[str]) -> dict:
    dropped: collections.Counter = collections.Counter()
    for item in manifest["inputs"]:
        dropped.update(item["dropped"])
    return {"action": action, "total_rows": manifest["total_rows"], "days": len(manifest["days"]),
            "dropped": dict(sorted(dropped.items())), "verified_inputs": sum(i["verified"] for i in manifest["inputs"]),
            "ignored_files": ignored}


# ---- verify ------------------------------------------------------------------------------------
def verify_replay(data_dir: Path) -> List[str]:
    out = replay_dir(data_dir)
    manifest = _read_manifest(data_dir)
    if manifest is None:
        return [f"no replay dataset/manifest at {out}"]
    errors = ev.validate_manifest(manifest)
    if errors:
        return errors
    present = sorted(p.name for p in out.glob("day=*"))
    expected = sorted(f"day={d}" for d in manifest["days"])
    if present != expected:
        errors.append(f"day directories {present} != manifest {expected}")
    for day, info in manifest["days"].items():
        path = out / info["path"]
        if not path.is_file():
            errors.append(f"{day}: missing {info['path']}")
            continue
        table = pq.ParquetFile(path).read()            # the file itself; `day` comes from the directory
        cols = {f.name: str(f.type) for f in table.schema}
        cols["day"] = "string"
        schema_errors = ev.validate_replay_columns(cols)
        if schema_errors:
            errors.append(f"{day}: schema {schema_errors}")
            continue
        if table.num_rows != info["rows"]:
            errors.append(f"{day}: {table.num_rows} rows, manifest says {info['rows']}")
            continue
        columns = [table.column(f.name).to_pylist() for f in SCHEMA]
        if columns[0] != list(range(table.num_rows)):
            errors.append(f"{day}: row_idx is not contiguous 0..{table.num_rows - 1}")
            continue
        digest = hashlib.sha256()
        for row in zip(*columns):
            digest.update(_row_text(row))
        if digest.hexdigest() != info["content_sha256"]:
            errors.append(f"{day}: content_sha256 mismatch (data changed since preparation)")
    return errors


# ---- sample ------------------------------------------------------------------------------------
def make_sample(data_dir: Path, out_path: Path = SAMPLE_PATH, max_rows: int = SAMPLE_MAX) -> dict:
    """Deterministic stratified sample: the first `max_rows // n_labels` rows of every label, in (day, row_idx) order."""
    manifest = _read_manifest(data_dir)
    if manifest is None:
        raise PrepareError("no replay dataset; run prepare first")
    labels = list(manifest["labels"])
    quota = max(1, max_rows // len(labels))
    taken: collections.Counter = collections.Counter()
    rows: List[tuple] = []
    for day in ev.REPLAY_DAYS:
        if day not in manifest["days"] or all(taken[lab] >= quota for lab in labels):
            continue
        pf = pq.ParquetFile(replay_dir(data_dir) / manifest["days"][day]["path"])
        for batch in pf.iter_batches(batch_size=CHUNK_ROWS):
            cols = [batch.column(f.name).to_pylist() for f in SCHEMA]
            for row in zip(*cols):
                if taken[row[-1]] < quota:
                    taken[row[-1]] += 1
                    rows.append((*row, day))
    rows = rows[:max_rows]
    columns = list(zip(*rows)) if rows else [[] for _ in SAMPLE_SCHEMA]
    table = pa.Table.from_arrays([pa.array(c, type=f.type) for c, f in zip(columns, SAMPLE_SCHEMA)], schema=SAMPLE_SCHEMA)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, out_path, compression="snappy")
    return {"sample_rows": table.num_rows, "sample_labels": len(set(r[-2] for r in rows)), "sample_path": str(out_path)}


# ---- CLI ---------------------------------------------------------------------------------------
def _peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024, 1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ids_ingest.prepare",
                                description="Build the C-01 replay dataset from the CIC-IDS2017 TrafficLabelling CSVs.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true", help="check an existing replay dataset and exit")
    mode.add_argument("--force", action="store_true", help="rebuild even if the dataset is up to date")
    p.add_argument("--allow-unverified", action="store_true", help="accept inputs whose sha256 differs from C-01")
    p.add_argument("--sample", action="store_true", help=f"also write the mock sample {SAMPLE_PATH.name}")
    return p


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         sample_out: Path = SAMPLE_PATH) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify_only and (args.sample or args.allow_unverified):
        parser.error("--verify-only cannot be combined with other options")
    try:
        cfg = load_runtime_config(env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    start = time.monotonic()
    try:
        if args.verify_only:
            errors = verify_replay(cfg.data_dir)
            if errors:
                print("replay dataset verification FAILED:\n  " + "\n  ".join(errors), file=sys.stderr)
                return EXIT_RUNTIME_ERROR
            m = _read_manifest(cfg.data_dir)
            result = {"action": "verify", "ok": True, "total_rows": m["total_rows"], "days": len(m["days"])}
        else:
            result = prepare_all(cfg.data_dir, force=args.force, allow_unverified=args.allow_unverified)
            if args.sample:
                result.update(make_sample(cfg.data_dir, sample_out))
    except PrepareError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    result.update(elapsed_s=round(time.monotonic() - start, 1), peak_rss_mb=_peak_rss_mb())
    print(summary_line("prepare", cfg.run_id, **result))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
