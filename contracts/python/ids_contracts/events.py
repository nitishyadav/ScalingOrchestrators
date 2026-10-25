"""C-01 Network Event: constants, (de)serialisation and validators.

Contract: contracts/C-01_network_event.md  (owner M1)
"""
from __future__ import annotations

import ipaddress
import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Union

from . import ContractViolation

CONTRACT_ID = "C-01"
CONTRACT_VERSION = "1.0.0-rc.5"

TOPIC_DEFAULT = "network-events"
# librdkafka setting that reproduces the Java/Spark murmur2 key partitioning (C-01 §2.1)
LIBRDKAFKA_PARTITIONER = "murmur2_random"

REQUIRED_FIELDS = (
    "event_id", "timestamp", "src_ip", "dst_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag",
)
OPTIONAL_FIELDS = ("orig_ts",)
EVAL_ONLY_FIELDS = ("label", "is_injected")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS + EVAL_ONLY_FIELDS

# The only fields feature computation / rules / scoring may read (Constitution Art. VII).
SCORING_FIELDS = ("timestamp", "src_ip", "dst_port", "bytes_sent", "syn_flag", "ack_flag")

CIC_LABELS = frozenset({
    "BENIGN", "DDoS", "PortScan", "Bot", "Infiltration", "Heartbleed",
    "DoS Hulk", "DoS GoldenEye", "DoS slowloris", "DoS Slowhttptest",
    "FTP-Patator", "SSH-Patator",
    "Web Attack - Brute Force", "Web Attack - XSS", "Web Attack - Sql Injection",
})
INJECTED_LABELS = frozenset({"INJ_DDOS", "INJ_SYNFLOOD", "INJ_PORTSCAN"})
LABELS = CIC_LABELS | INJECTED_LABELS
BENIGN_LABEL = "BENIGN"

MIN_TIMESTAMP_MS = 1_000_000_000_000  # rejects epoch *seconds* passed by mistake
MAX_INT64 = 2**63 - 1

# CIC TrafficLabelling column (after strip()) -> event field
CIC_COLUMN_MAP = {
    "Source IP": "src_ip",
    "Destination IP": "dst_ip",
    "Destination Port": "dst_port",
    "Total Length of Fwd Packets": "bytes_sent",
    "SYN Flag Count": "syn_flag",
    "ACK Flag Count": "ack_flag",
    "Timestamp": "orig_ts",
    "Label": "label",
}

REPLAY_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
CIC_FILE_ORDER = {
    "Monday": ("Monday-WorkingHours",),
    "Tuesday": ("Tuesday-WorkingHours",),
    "Wednesday": ("Wednesday-workingHours",),
    "Thursday": ("Thursday-WorkingHours-Morning-WebAttacks",
                 "Thursday-WorkingHours-Afternoon-Infilteration"),
    "Friday": ("Friday-WorkingHours-Morning",
               "Friday-WorkingHours-Afternoon-PortScan",
               "Friday-WorkingHours-Afternoon-DDos"),
}

# Reference raw input (C-01 §3.2, verified 2026-10-21): stem -> (sha256 of the CSV, valid rows after C-01 drop rules)
CIC_REFERENCE = {
    "Monday-WorkingHours": ("96f26aea87d513073769b48ce204c2921791149e1c6225f7db65a3fed7973820", 529_918),
    "Tuesday-WorkingHours": ("ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815", 445_909),
    "Wednesday-workingHours": ("ed538e85b84181e8897dedb3d37d365982f44b27eccd67c477581a8b65f3d170", 692_703),
    "Thursday-WorkingHours-Morning-WebAttacks": ("e3deaff483d18b53b100a441dff9b8919416df8876b4edcc0f0d1e4bf48397d0", 170_366),
    "Thursday-WorkingHours-Afternoon-Infilteration": ("d74238e054023c8bd4d8056650463cadb25c100fb0e26ebd4272c07b5c022c4b", 288_602),
    "Friday-WorkingHours-Morning": ("c061cd98f39d8054aeaed6244a5129a20b3985983d0d022b860ae8aa07fe8d21", 191_033),
    "Friday-WorkingHours-Afternoon-PortScan": ("7e2ddaa80a5849ba629463296b6128436c161b4a32e8034bb5beae06b0c45e08", 286_467),
    "Friday-WorkingHours-Afternoon-DDos": ("1f779b4f0d78f9225554c4de53b5a2c07912b60dcd136ee4c5c1d0d2496b7cc4", 225_745),
}
CIC_TOTAL_VALID_ROWS = 2_830_743
CIC_FILE_SUFFIX = ".pcap_ISCX.csv"


def verify_cic_file(path: Union[str, Path]) -> List[str]:
    """Check a raw CIC CSV against CIC_REFERENCE by name and SHA-256. Empty list = identical to the reference."""
    import hashlib
    path = Path(path)
    stem = path.name[: -len(CIC_FILE_SUFFIX)] if path.name.endswith(CIC_FILE_SUFFIX) else path.stem
    if stem not in CIC_REFERENCE:
        return [f"'{path.name}' is not a C-01 source file"]
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    expected = CIC_REFERENCE[stem][0]
    return [] if digest.hexdigest() == expected else [f"{path.name}: sha256 {digest.hexdigest()} != reference {expected}"]


# Replay dataset (Parquet) column -> Arrow type name
REPLAY_COLUMNS = {
    "row_idx": "int64",
    "source_file": "string",
    "orig_ts": "string",
    "src_ip": "string",
    "dst_ip": "string",
    "dst_port": "int32",
    "bytes_sent": "int64",
    "syn_flag": "int32",
    "ack_flag": "int32",
    "label": "string",
    "day": "string",
}


def normalise_label(raw: str) -> str:
    """Normalise a raw CIC label: trim and replace the non-ASCII dash used in web-attack labels."""
    label = raw.strip()
    for bad in ("–", "—", "\x96", "�"):
        label = label.replace(bad, "-")
    return " ".join(label.split())


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_ip(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def validate_event(event: Mapping[str, Any], strict: bool = False) -> List[str]:
    """Return a list of violations (empty = valid). strict=True also rejects unknown fields."""
    if not isinstance(event, Mapping):
        return ["event is not a JSON object"]
    errors: List[str] = []

    for name in REQUIRED_FIELDS:
        if name not in event or event[name] is None:
            errors.append(f"missing required field '{name}'")
    if strict:
        unknown = sorted(set(event) - set(ALL_FIELDS))
        if unknown:
            errors.append(f"unknown fields {unknown}")

    if "event_id" in event and event["event_id"] is not None:
        try:
            uuid.UUID(str(event["event_id"]))
            if not isinstance(event["event_id"], str):
                raise ValueError
        except ValueError:
            errors.append("event_id is not a UUID string")

    ts = event.get("timestamp")
    if ts is not None:
        if not _is_int(ts):
            errors.append("timestamp must be an integer (epoch ms)")
        elif ts < MIN_TIMESTAMP_MS:
            errors.append("timestamp looks like seconds, expected epoch milliseconds")

    for name in ("src_ip", "dst_ip"):
        if event.get(name) is not None and not _is_ip(event[name]):
            errors.append(f"{name} is not a valid IP address")

    port = event.get("dst_port")
    if port is not None and not (_is_int(port) and 0 <= port <= 65535):
        errors.append("dst_port must be an integer in 0..65535")

    b = event.get("bytes_sent")
    if b is not None and not (_is_int(b) and 0 <= b <= MAX_INT64):
        errors.append("bytes_sent must be a non-negative int64")

    for name in ("syn_flag", "ack_flag"):
        v = event.get(name)
        if v is not None and not (_is_int(v) and v >= 0):
            errors.append(f"{name} must be a non-negative integer")

    if "orig_ts" in event and event["orig_ts"] is not None and not isinstance(event["orig_ts"], str):
        errors.append("orig_ts must be a string or null")

    label = event.get("label")
    if label is not None and label not in LABELS:
        errors.append(f"label '{label}' is not in the C-01 label set")
    injected = event.get("is_injected")
    if injected is not None and not isinstance(injected, bool):
        errors.append("is_injected must be a boolean")
    if injected is True and not (isinstance(label, str) and label in INJECTED_LABELS):
        errors.append("is_injected=true requires an INJ_* label")
    if injected is False and isinstance(label, str) and label in INJECTED_LABELS:
        errors.append("INJ_* label requires is_injected=true")

    return errors


def check_event(event: Mapping[str, Any], strict: bool = False) -> None:
    """Raise ContractViolation if the event is invalid."""
    errors = validate_event(event, strict=strict)
    if errors:
        raise ContractViolation("; ".join(errors))


def encode_event(event: Mapping[str, Any]) -> bytes:
    """Kafka message value: compact UTF-8 JSON, fields in contract order."""
    ordered = {k: event[k] for k in ALL_FIELDS if k in event}
    return json.dumps(ordered, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def event_key(event: Mapping[str, Any]) -> bytes:
    """Kafka message key: src_ip as UTF-8."""
    return str(event["src_ip"]).encode("utf-8")


def decode_event(value: Union[bytes, str]) -> Dict[str, Any]:
    """Parse a Kafka message value. Raises ContractViolation on non-JSON or non-finite numbers."""
    try:
        text = value.decode("utf-8") if isinstance(value, (bytes, bytearray)) else value
        obj = json.loads(text, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ContractViolation(f"not a JSON event: {exc}") from exc
    if not isinstance(obj, dict):
        raise ContractViolation("event is not a JSON object")
    return obj


def _reject_constant(name: str) -> float:
    raise ValueError(f"non-finite number {name} not allowed")


def iter_jsonl(path: Union[str, Path]) -> Iterator[Dict[str, Any]]:
    """Yield events from a JSON-lines file (blank lines skipped)."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield decode_event(line)


# Reference replay data (C-01 §2.2): per-day content_sha256 of a correctly prepared dataset (verified 2026-10-21).
# Equal hashes ⇔ identical replay rows, so every replica can prove it replays the same data.
REPLAY_CONTENT_SHA256 = {
    "Monday": "0c4e8d6c4d0396921692bdf74b2369fc6fb6973b33e0ded1fea8fb90db3c7bdd",
    "Tuesday": "83e9850002902736f7ff712e54311de90a80a3a4bdfafd48dc3ccc540289b493",
    "Wednesday": "27da03964e1505a7adab8dbbc9d344c28ab0ed1856cd7bcd19336110283a707a",
    "Thursday": "edc0c2432a87166aca81c1f6f3171061962a9feda985af94845ddf1dff7e7a95",
    "Friday": "43d3015a1c1be8fe34660233f137cf9945febf163c35ca3e1e51e6a6b260ca45",
}

REPLAY_MANIFEST_NAME = "_manifest.json"
DROP_REASONS = ("empty_row", "wrong_field_count", "missing_field", "non_numeric", "nan_or_inf",
                "negative", "bad_port", "bad_ip", "unknown_label")
MANIFEST_KEYS = ("contract", "contract_version", "tool", "tool_version", "created_at", "inputs", "days",
                 "total_rows", "labels")
MANIFEST_INPUT_KEYS = ("source_file", "day", "sha256", "verified", "data_rows", "valid_rows", "dropped")
MANIFEST_DAY_KEYS = ("rows", "files", "content_sha256", "path")


def validate_manifest(manifest: Mapping[str, Any]) -> List[str]:
    """Check a replay-dataset manifest (C-01 §2.2) for structure and internal consistency. Empty list = valid."""
    errors = [f"manifest missing '{k}'" for k in MANIFEST_KEYS if k not in manifest]
    if errors:
        return errors
    if manifest["contract"] != CONTRACT_ID:
        errors.append(f"manifest contract is {manifest['contract']!r}, expected {CONTRACT_ID!r}")
    inputs, days = manifest["inputs"], manifest["days"]
    for i, item in enumerate(inputs):
        missing = [k for k in MANIFEST_INPUT_KEYS if k not in item]
        if missing:
            errors.append(f"inputs[{i}] missing {missing}")
            continue
        unknown = sorted(set(item["dropped"]) - set(DROP_REASONS))
        if unknown:
            errors.append(f"inputs[{i}] has unknown drop reasons {unknown}")
        if item["data_rows"] != item["valid_rows"] + sum(item["dropped"].values()):
            errors.append(f"inputs[{i}] ({item['source_file']}): data_rows != valid_rows + dropped")
    for day, info in days.items():
        missing = [k for k in MANIFEST_DAY_KEYS if k not in info]
        if missing:
            errors.append(f"days[{day}] missing {missing}")
        elif day not in REPLAY_DAYS:
            errors.append(f"unknown day {day!r}")
    if errors:
        return errors
    valid_sum = sum(i["valid_rows"] for i in inputs)
    day_sum = sum(d["rows"] for d in days.values())
    if not manifest["total_rows"] == valid_sum == day_sum:
        errors.append(f"total_rows {manifest['total_rows']} != inputs valid {valid_sum} / days {day_sum}")
    if sum(manifest["labels"].values()) != manifest["total_rows"]:
        errors.append("label counts do not sum to total_rows")
    unknown_labels = sorted(set(manifest["labels"]) - LABELS)
    if unknown_labels:
        errors.append(f"unknown labels {unknown_labels}")
    return errors


def validate_replay_columns(columns: Mapping[str, str]) -> List[str]:
    """Check a replay-dataset schema given as {column: arrow_type_name}. Empty list = valid."""
    errors = []
    for name, typ in REPLAY_COLUMNS.items():
        if name not in columns:
            errors.append(f"missing column '{name}'")
        elif name != "day" and str(columns[name]) != typ:
            errors.append(f"column '{name}' has type {columns[name]}, expected {typ}")
    extra = sorted(set(columns) - set(REPLAY_COLUMNS))
    if extra:
        errors.append(f"unexpected columns {extra}")
    return errors


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
