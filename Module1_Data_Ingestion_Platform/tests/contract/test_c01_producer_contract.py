"""M1-T111 — what the producer puts on the wire is C-01 (M1-F03-AC-10)."""
import json

import pyarrow.parquet as pq

from conftest import MODULE_DIR
from ids_contracts import events as ev
from ids_ingest import producer as pr

SAMPLE = MODULE_DIR / "mocks" / "replay_sample.parquet"


class CaptureSink:
    def __init__(self):
        self.messages, self.delivered, self.failed = [], 0, 0

    def check(self):
        return 1

    def send(self, key, value):
        self.messages.append((key, value))
        self.delivered += 1

    def poll(self):
        pass

    def flush(self, timeout=30.0):
        return 0


class Clock:
    t = 0.0

    def monotonic(self):
        return self.t

    def wall_ms(self):
        return 1_800_000_000_000 + int(self.t * 1000)

    def sleep(self, s):
        self.t += s


def sample_records():
    t = pq.read_table(SAMPLE, columns=list(pr.RECORD_FIELDS))
    return [dict(zip(pr.RECORD_FIELDS, r)) for r in zip(*[t.column(f).to_pylist() for f in pr.RECORD_FIELDS])]


def test_every_message_is_c01_keyed_by_src_ip():
    records = sample_records()
    sink = CaptureSink()
    stats = pr.run(iter(records), sink, mode="replay", rate=100_000, duration_s=60, clock=Clock())
    assert stats.produced == len(records) == len(sink.messages) and stats.invalid == 0
    for (key, value), rec in zip(sink.messages, records):
        assert b"\n" not in value
        event = ev.decode_event(value)
        assert ev.validate_event(event, strict=True) == []
        assert key == ev.event_key(event) == rec["src_ip"].encode()
        assert value == ev.encode_event(event)              # compact JSON in contract field order
        assert {k: event[k] for k in pr.RECORD_FIELDS} == rec and event["is_injected"] is False


def test_injected_events_are_c01():
    from ids_ingest.injector import InjectingSource
    sink = CaptureSink()
    src = InjectingSource(iter(sample_records()), mode="mixed", share=0.2, rate=100_000)
    stats = pr.run(src, sink, mode="replay", rate=100_000, duration_s=60, clock=Clock())
    assert stats.invalid == 0 and stats.injected == src.injected > 0
    for key, value in sink.messages:
        event = ev.decode_event(value)
        assert ev.validate_event(event, strict=True) == [] and key == ev.event_key(event)
        assert event["is_injected"] == (event["label"] in ev.INJECTED_LABELS)


def test_kafka_config_uses_murmur2_partitioner():
    assert pr.KAFKA_PRODUCER_CONFIG["partitioner"] == ev.LIBRDKAFKA_PARTITIONER == "murmur2_random"


def test_fixture_mode_emits_the_golden_events_verbatim_except_ids_and_time():
    sink = CaptureSink()
    pr.run(pr.FixtureSource(), sink, mode="fixture", rate=1, duration_s=600, clock=Clock())
    golden = list(ev.iter_jsonl(pr.FIXTURE_PATH))
    assert len(sink.messages) == len(golden)
    for (_, value), g in zip(sink.messages, golden):
        e = json.loads(value)
        assert {k: v for k, v in e.items() if k not in ("event_id", "timestamp")} == \
               {k: v for k, v in g.items() if k not in ("event_id", "timestamp")}
