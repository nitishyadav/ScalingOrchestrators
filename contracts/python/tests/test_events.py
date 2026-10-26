"""Contract tests for C-01 Network Event."""
import copy
import json

import pytest

from ids_contracts import FIXTURES_DIR, SCHEMAS_DIR, ContractViolation
from ids_contracts import events as ev

GOLDEN = FIXTURES_DIR / "events_golden.jsonl"


@pytest.fixture(scope="module")
def golden():
    return list(ev.iter_jsonl(GOLDEN))


@pytest.fixture
def valid():
    return {
        "event_id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
        "timestamp": 1767225600123,
        "src_ip": "172.16.0.1",
        "dst_ip": "192.168.10.50",
        "dst_port": 80,
        "bytes_sent": 1032,
        "syn_flag": 1,
        "ack_flag": 0,
        "orig_ts": "7/7/2017 3:56",
        "label": "DDoS",
        "is_injected": False,
    }


def test_golden_fixture_shape(golden):
    assert len(golden) == 126
    assert {e["src_ip"] for e in golden} == {"192.168.10.5", "172.16.0.10", "172.16.0.20", "172.16.0.30"}
    assert len({e["event_id"] for e in golden}) == 126


def test_golden_fixture_validates_strict(golden):
    for e in golden:
        assert ev.validate_event(e, strict=True) == [], e


def test_golden_fixture_has_late_event_within_watermark(golden):
    max_seen = max(e["timestamp"] for e in golden[:-1])
    late = golden[-1]
    assert late["timestamp"] < max_seen
    assert max_seen - late["timestamp"] < 60_000


def test_golden_fixture_is_deterministic(tmp_path, monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen", FIXTURES_DIR / "_gen" / "gen_events_golden.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rebuilt = b"".join(ev.encode_event(e) + b"\n" for e in gen.build())
    assert rebuilt == GOLDEN.read_bytes()


def test_valid_event_passes(valid):
    assert ev.validate_event(valid, strict=True) == []
    ev.check_event(valid)


@pytest.mark.parametrize(
    "field,value,fragment",
    [
        ("timestamp", 1767225600, "seconds"),
        ("timestamp", "1767225600123", "integer"),
        ("dst_port", 70000, "dst_port"),
        ("dst_port", True, "dst_port"),
        ("bytes_sent", -1, "bytes_sent"),
        ("syn_flag", 1.0, "syn_flag"),
        ("src_ip", "999.1.1.1", "src_ip"),
        ("event_id", "not-a-uuid", "event_id"),
        ("label", "Bogus", "label"),
        ("is_injected", True, "INJ_"),
    ],
)
def test_invalid_values_rejected(valid, field, value, fragment):
    bad = copy.deepcopy(valid)
    bad[field] = value
    errors = ev.validate_event(bad)
    assert errors and any(fragment in msg for msg in errors), errors
    with pytest.raises(ContractViolation):
        ev.check_event(bad)


def test_missing_required_field(valid):
    del valid["src_ip"]
    assert any("src_ip" in m for m in ev.validate_event(valid))


def test_unknown_fields_only_rejected_in_strict_mode(valid):
    valid["future_field"] = 1
    assert ev.validate_event(valid) == []
    assert ev.validate_event(valid, strict=True)


def test_optional_and_eval_fields_may_be_absent(valid):
    for name in ("orig_ts", "label", "is_injected"):
        valid.pop(name)
    assert ev.validate_event(valid, strict=True) == []


def test_encode_decode_roundtrip(valid):
    raw = ev.encode_event(valid)
    assert b"\n" not in raw and b" " not in raw.replace(b"7/7/2017 3:56", b"")
    assert ev.decode_event(raw) == valid
    assert ev.event_key(valid) == b"172.16.0.1"


@pytest.mark.parametrize("raw", [b"not json", b"[1,2]", b'{"timestamp": NaN}', b"\xff\xfe"])
def test_decode_rejects_garbage(raw):
    with pytest.raises(ContractViolation):
        ev.decode_event(raw)


def test_scoring_fields_exclude_eval_only():
    assert not set(ev.SCORING_FIELDS) & set(ev.EVAL_ONLY_FIELDS)


@pytest.mark.parametrize(
    "raw,expected",
    [(" BENIGN ", "BENIGN"), ("Web Attack \x96 Brute Force", "Web Attack - Brute Force"),
     ("Web Attack � XSS", "Web Attack - XSS"), ("Web Attack – Sql Injection", "Web Attack - Sql Injection")],
)
def test_normalise_label(raw, expected):
    assert ev.normalise_label(raw) == expected
    assert expected in ev.LABELS


def test_cic_reference_is_consistent_with_file_order():
    stems = [s for day in ev.REPLAY_DAYS for s in ev.CIC_FILE_ORDER[day]]
    assert stems == list(ev.CIC_REFERENCE)
    assert sum(rows for _, rows in ev.CIC_REFERENCE.values()) == ev.CIC_TOTAL_VALID_ROWS == 2_830_743
    assert all(len(sha) == 64 for sha, _ in ev.CIC_REFERENCE.values())


def test_verify_cic_file(tmp_path):
    bogus = tmp_path / "Monday-WorkingHours.pcap_ISCX.csv"
    bogus.write_text("not the real file")
    assert ev.verify_cic_file(bogus) and "sha256" in ev.verify_cic_file(bogus)[0]
    other = tmp_path / "notes.csv"
    other.write_text("x")
    assert "not a C-01 source file" in ev.verify_cic_file(other)[0]


def _manifest():
    return {
        "contract": "C-01", "contract_version": ev.CONTRACT_VERSION, "tool": "ids_ingest.prepare",
        "tool_version": "0.2.0", "created_at": "2026-10-21T00:00:00Z",
        "inputs": [{"source_file": "Monday-WorkingHours", "day": "Monday", "sha256": "0" * 64, "verified": True,
                    "data_rows": 12, "valid_rows": 10, "dropped": {"empty_row": 2}}],
        "days": {"Monday": {"rows": 10, "files": ["Monday-WorkingHours"], "content_sha256": "a" * 64,
                            "path": "day=Monday/part-00000.parquet"}},
        "total_rows": 10, "labels": {"BENIGN": 10},
    }


def test_replay_reference_hashes_cover_all_days():
    assert list(ev.REPLAY_CONTENT_SHA256) == list(ev.REPLAY_DAYS)
    assert all(len(h) == 64 for h in ev.REPLAY_CONTENT_SHA256.values())


def test_valid_manifest_passes():
    assert ev.validate_manifest(_manifest()) == []


@pytest.mark.parametrize(
    "mutate,fragment",
    [
        (lambda m: m.pop("labels"), "missing 'labels'"),
        (lambda m: m.update(total_rows=11), "total_rows"),
        (lambda m: m["inputs"][0]["dropped"].update(meteor_strike=1), "unknown drop reasons"),
        (lambda m: m["inputs"][0].update(data_rows=99), "data_rows != valid_rows"),
        (lambda m: m["labels"].update(BENIGN=9), "label counts"),
        (lambda m: m["days"].update(Sunday=m["days"]["Monday"]), "unknown day"),
        (lambda m: m.update(contract="C-02"), "expected 'C-01'"),
    ],
)
def test_invalid_manifest_detected(mutate, fragment):
    m = _manifest()
    mutate(m)
    errors = ev.validate_manifest(m)
    assert errors and any(fragment in e for e in errors), errors


def test_replay_columns_validator():
    assert ev.validate_replay_columns(dict(ev.REPLAY_COLUMNS)) == []
    cols = dict(ev.REPLAY_COLUMNS)
    cols["dst_port"] = "int64"
    del cols["label"]
    cols["extra"] = "string"
    errors = ev.validate_replay_columns(cols)
    assert len(errors) == 3


def test_json_schema_agrees_with_python_validator(golden, valid):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SCHEMAS_DIR / "event.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for e in golden + [valid]:
        assert not list(validator.iter_errors(e)), e
    assert set(schema["required"]) == set(ev.REQUIRED_FIELDS)
    assert set(schema["properties"]) == set(ev.ALL_FIELDS)
    assert set(schema["properties"]["label"]["enum"]) == set(ev.LABELS)
    bad = dict(valid, is_injected=True)
    assert list(validator.iter_errors(bad))
