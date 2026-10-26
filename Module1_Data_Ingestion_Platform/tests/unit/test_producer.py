"""M1-T110 — replay producer with a fake clock and fake sink (M1-F03-AC-03, 04, 06, 07, 08, 09)."""
import json
import uuid

import pyarrow.parquet as pq
import pytest

from csv_factory import make_raw
from ids_contracts import FIXTURES_DIR
from ids_contracts import events as ev
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR
from ids_ingest import prepare as prep
from ids_ingest import producer as pr

FIELDS = list(pr.RECORD_FIELDS)


class FakeClock:
    def __init__(self, base_ms=1_800_000_000_000):
        self.t = 0.0
        self.base_ms = base_ms

    def monotonic(self):
        return self.t

    def wall_ms(self):
        return self.base_ms + int(round(self.t * 1000))

    def sleep(self, s):
        self.t += max(0.0, s)


class FakeSink:
    def __init__(self, partitions=4, fail_every=None, check_error=None):
        self.partitions, self.fail_every, self.check_error = partitions, fail_every, check_error
        self.messages, self.delivered, self.failed = [], 0, 0

    def check(self):
        if self.check_error:
            raise pr.SinkError(self.check_error)
        return self.partitions

    def send(self, key, value):
        self.messages.append((key, value))
        if self.fail_every and len(self.messages) % self.fail_every == 0:
            self.failed += 1
        else:
            self.delivered += 1

    def poll(self):
        pass

    def flush(self, timeout=30.0):
        return 0


@pytest.fixture
def replay_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setattr(ev, "CIC_REFERENCE", make_raw(d))
    prep.prepare_all(d)
    return d


def replay_rows(d, days=ev.REPLAY_DAYS):
    rows = []
    for day in days:
        t = pq.ParquetFile(d / "replay" / f"day={day}" / "part-00000.parquet").read(columns=FIELDS)
        rows += [dict(zip(FIELDS, r)) for r in zip(*[t.column(f).to_pylist() for f in FIELDS])]
    return rows


def decoded(sink):
    return [json.loads(v) for _, v in sink.messages]


# ---- event construction ------------------------------------------------------------------------
def test_make_event_is_strict_c01():
    rec = {"orig_ts": "3/7/2017 9:00", "src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 80,
           "bytes_sent": 5, "syn_flag": 1, "ack_flag": 0, "label": "BENIGN"}
    e = pr.make_event(rec, 1_800_000_000_123)
    assert ev.validate_event(e, strict=True) == []
    assert e["timestamp"] == 1_800_000_000_123 and e["is_injected"] is False
    assert uuid.UUID(e["event_id"]).version == 4


# ---- replay source -----------------------------------------------------------------------------
def test_replay_order_then_loop(replay_dir):
    src = pr.ReplaySource(replay_dir, allow_unverified=True)
    it = iter(src)
    expected = replay_rows(replay_dir)
    first_pass = [next(it) for _ in expected]
    assert first_pass == expected
    assert next(it) == expected[0] and src.loops == 1


def test_days_filter_uses_canonical_order(replay_dir):
    src = pr.ReplaySource(replay_dir, days=["Friday", "Monday"], loop=False, allow_unverified=True)
    assert list(src) == replay_rows(replay_dir, ["Monday", "Friday"]) and src.exhausted


def test_missing_dataset(tmp_path):
    with pytest.raises(pr.ProducerError, match="prepare"):
        pr.ReplaySource(tmp_path / "nothing")


def test_non_reference_data_rejected_unless_allowed(replay_dir, monkeypatch):
    with pytest.raises(pr.ProducerError, match="allow-unverified"):
        pr.ReplaySource(replay_dir)
    m = json.loads((replay_dir / "replay" / ev.REPLAY_MANIFEST_NAME).read_text())
    monkeypatch.setattr(ev, "REPLAY_CONTENT_SHA256", {d: v["content_sha256"] for d, v in m["days"].items()})
    pr.ReplaySource(replay_dir)       # now matches the "reference"


# ---- pacing (AC-06) ----------------------------------------------------------------------------
def test_constant_rate_with_fake_clock(replay_dir):
    sink, clock = FakeSink(), FakeClock()
    stats = pr.run(pr.ReplaySource(replay_dir, allow_unverified=True), sink, mode="replay", rate=1000, duration_s=5, clock=clock)
    assert stats.produced == 5000 == sink.delivered
    ts = [e["timestamp"] for e in decoded(sink)]
    assert ts == sorted(ts)
    assert len(stats.per_second) == 5 and all(abs(n - 1000) <= 10 for n in stats.per_second)
    s = stats.summary(target_rate=1000)
    assert abs(s["achieved_rate"] - 1000) <= 10 and s["rate_p05"] >= 900 and s["status"] == "ok"


def test_loops_until_duration(replay_dir):
    stats = pr.run(pr.ReplaySource(replay_dir, allow_unverified=True), FakeSink(), mode="replay", rate=100,
                   duration_s=2, clock=FakeClock())
    assert stats.produced == 200 and stats.loops == 200 // 24 and not stats.exhausted


def test_no_loop_ends_when_data_runs_out(replay_dir):
    stats = pr.run(pr.ReplaySource(replay_dir, loop=False, allow_unverified=True), FakeSink(), mode="replay", rate=100,
                   duration_s=10, clock=FakeClock())
    assert stats.produced == 24 and stats.exhausted and stats.duration_s < 1


# ---- fixture (AC-04) ---------------------------------------------------------------------------
def test_fixture_preserves_gaps_exactly():
    sink, clock = FakeSink(partitions=1), FakeClock()
    stats = pr.run(pr.FixtureSource(), sink, mode="fixture", rate=999, duration_s=600, clock=clock)
    golden = list(ev.iter_jsonl(FIXTURES_DIR / "events_golden.jsonl"))
    got = decoded(sink)
    assert stats.produced == len(golden) == 126 and stats.injected == 25
    start = clock.base_ms
    assert [e["timestamp"] - start for e in got] == [g["timestamp"] - golden[0]["timestamp"] for g in golden]
    assert [e["src_ip"] for e in got] == [g["src_ip"] for g in golden]
    assert got[-1]["timestamp"] < got[-2]["timestamp"]          # the late event stays late
    assert all(ev.validate_event(e, strict=True) == [] for e in got)


# ---- guards (AC-07, AC-09) ---------------------------------------------------------------------
def test_invalid_records_are_not_sent():
    good = {"orig_ts": "x", "src_ip": "10.0.0.1", "dst_ip": "10.0.0.2", "dst_port": 80, "bytes_sent": 1,
            "syn_flag": 0, "ack_flag": 1, "label": "BENIGN"}
    records = [dict(good) for _ in range(10)]
    records[3]["src_ip"] = "not-an-ip"
    sink = FakeSink()
    stats = pr.run(iter(records), sink, mode="replay", rate=1000, duration_s=10, clock=FakeClock())
    assert stats.invalid == 1 and stats.produced == 10 and len(sink.messages) == 9
    assert all(json.loads(v)["src_ip"] != "not-an-ip" for _, v in sink.messages)


def test_stop_flag(replay_dir):
    sink = FakeSink()
    stats = pr.run(pr.ReplaySource(replay_dir, allow_unverified=True), sink, mode="replay", rate=1000, duration_s=60,
                   clock=FakeClock(), stop=lambda: len(sink.messages) >= 50)
    assert stats.produced == 50 and stats.summary(1000)["status"] == "stopped"


# ---- CLI (AC-08, AC-09, AC-10) -----------------------------------------------------------------
def cli(argv, tmp_path, capsys, data_dir=None, sink=None, clock=None):
    env = {"IDS_ROOT": str(tmp_path), "DATA_DIR": str(data_dir or tmp_path / "none")}
    code = pr.main(argv, env=env, sink_factory=lambda cfg: sink or FakeSink(), clock=clock or FakeClock())
    return code, capsys.readouterr()


def last(out):
    return json.loads(out.out.strip().splitlines()[-1])


def test_cli_fixture_summary(tmp_path, capsys):
    code, out = cli(["--source", "fixture"], tmp_path, capsys)
    s = last(out)
    assert code == EXIT_OK and s["command"] == "producer" and s["source"] == "fixture" and s["sent"] == 126
    for key in ("produced", "sent", "failed", "invalid", "injected", "target_rate", "achieved_rate", "rate_p05",
                "rate_p50", "rate_p95", "loops", "exhausted", "partitions", "duration_s", "status", "run_id"):
        assert key in s, key


def test_cli_replay(replay_dir, tmp_path, capsys):
    code, out = cli(["--rate", "500", "--duration", "2", "--allow-unverified"], tmp_path, capsys, data_dir=replay_dir)
    s = last(out)
    assert code == EXIT_OK and s["sent"] == 1000 and s["target_rate"] == 500 and s["loops"] >= 1


def test_cli_delivery_failures_exit_1(replay_dir, tmp_path, capsys):
    code, out = cli(["--rate", "500", "--duration", "2", "--allow-unverified"], tmp_path, capsys,
                    data_dir=replay_dir, sink=FakeSink(fail_every=100))
    assert code == EXIT_RUNTIME_ERROR and last(out)["status"] == "error" and last(out)["failed"] == 10


def test_cli_sink_precheck_failure_exit_1(tmp_path, capsys):
    code, out = cli(["--source", "fixture"], tmp_path, capsys,
                    sink=FakeSink(check_error="topic 'x' does not exist; run python -m ids_ingest.topic_admin"))
    assert code == EXIT_RUNTIME_ERROR and "topic_admin" in out.err


def test_cli_missing_dataset_exit_1(tmp_path, capsys):
    code, out = cli([], tmp_path, capsys)
    assert code == EXIT_RUNTIME_ERROR and "prepare" in out.err


@pytest.mark.parametrize("argv,fragment", [
    (["--days", "Funday"], "Funday"),
    (["--rate", "0"], "PRODUCER_RATE"),
    (["--source", "fixture", "--attack-mode", "ddos", "--attack-share", "0.1"], "replay"),
    (["--attack-mode", "ddos", "--attack-share", "0.1", "--attack-start", "-1"], "attack-start"),
    (["--attack-mode", "ddos", "--attack-share", "0.1", "--attack-duration", "0"], "attack-duration"),
    (["--attack-share", "0.1"], "ATTACK_SHARE"),
])
def test_cli_usage_errors_exit_2(argv, fragment, tmp_path, capsys):
    code, out = cli(argv, tmp_path, capsys)
    assert code == EXIT_USAGE_ERROR and fragment in out.err


def test_cli_replay_with_injection(replay_dir, tmp_path, capsys):
    sink = FakeSink()
    code, out = cli(["--rate", "1000", "--duration", "5", "--allow-unverified", "--attack-mode", "mixed",
                     "--attack-share", "0.2", "--attack-start", "1", "--attack-duration", "3"],
                    tmp_path, capsys, data_dir=replay_dir, sink=sink)
    s = last(out)
    assert code == EXIT_OK and s["attack_mode"] == "mixed" and s["attack_share"] == 0.2 and s["seed"] == 42
    assert s["attack_window_s"] == [1.0, 4.0] and s["injected"] == 600 and abs(s["achieved_share"] - 0.2) < 0.001
    assert s["injected_by_type"] == {"ddos": 200, "synflood": 200, "portscan": 200}
    events = decoded(sink)
    assert sum(e["is_injected"] for e in events) == 600
    assert all(e["label"].startswith("INJ_") == e["is_injected"] for e in events)


def test_cli_without_attack_reports_none(replay_dir, tmp_path, capsys):
    code, out = cli(["--rate", "500", "--duration", "1", "--allow-unverified"], tmp_path, capsys, data_dir=replay_dir)
    s = last(out)
    assert code == EXIT_OK and s["attack_mode"] == "none" and s["injected"] == 0 and s["achieved_share"] == 0.0


def test_cli_bad_flag_exit_2(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli(["--bogus"], tmp_path, capsys)
    assert exc.value.code == EXIT_USAGE_ERROR
