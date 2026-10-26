"""M4-T010 — synthetic C-04/C-05 generator (M4's mock) (M4-F01-AC-03, AC-05)."""
import json

import pytest

from conftest import BASE
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR
from ids_monitor import synthetic as syn

NOW = BASE + 3_600_000 + 4_321          # 01:00:04.321, not aligned on purpose


def gen(**kw):
    args = dict(now_ms=NOW, seconds=300, n_ips=20, anomaly_share=0.2, run_id="DEV-synthetic", seed=42)
    args.update(kw)
    return syn.generate(**args)


def test_windows_are_valid_aligned_and_recent():
    data = gen()
    windows = data["windows"]
    assert len(windows) == 30 * 20
    for r in windows:
        assert S.validate_row(r) == [], r
        assert r["window_end"] % 10_000 == 0 and NOW - 300_000 < r["window_end"] <= NOW
        assert r["run_id"] == "DEV-synthetic"


def test_exact_anomaly_share_per_window():
    by_end = {}
    for r in gen()["windows"]:
        by_end.setdefault(r["window_end"], []).append(r["is_anomaly"])
    assert all(sum(v) == 4 for v in by_end.values())          # round(0.2 × 20)
    assert S.drift_alert(sum(sum(v) for v in by_end.values()), sum(len(v) for v in by_end.values()))


def test_metrics_and_run_rows_valid():
    data = gen()
    assert len(data["metrics"]) == 60
    assert all(M.validate_metrics_row(m) == [] for m in data["metrics"])
    assert [m["batch_id"] for m in data["metrics"]] == list(range(60))
    assert M.validate_run_row(data["run"]) == [] and json.loads(data["run"]["config_json"])["synthetic"] is True


def test_deterministic_by_seed():
    assert gen() == gen()
    a, b = gen()["windows"], gen(seed=7)["windows"]
    assert [r["total_bytes"] for r in a] != [r["total_bytes"] for r in b]


def test_zero_share_has_no_anomalies():
    assert not any(r["is_anomaly"] for r in gen(anomaly_share=0.0)["windows"])


class FakeWriter:
    def __init__(self):
        self.windows, self.metrics, self.runs = [], [], []

    def write_windows(self, rows):
        self.windows += rows

    def write_metrics(self, rows):
        self.metrics += rows

    def write_run(self, row):
        self.runs.append(row)


def test_follow_writes_new_windows_in_real_time():
    clock = {"t": NOW}
    w = FakeWriter()
    syn.follow(w, seconds=30, n_ips=5, anomaly_share=0.2, run_id="DEV-f", seed=1,
               now=lambda: clock["t"], sleep=lambda s: clock.__setitem__("t", clock["t"] + int(s * 1000)))
    ends = sorted({r["window_end"] for r in w.windows})
    assert len(ends) == 3 and all(b - a == 10_000 for a, b in zip(ends, ends[1:]))
    assert len(w.windows) == 15 and len(w.metrics) == 6
    assert all(S.validate_row(r) == [] for r in w.windows)


def test_cli_writes_through_writer(capsys):
    w = FakeWriter()
    code = syn.main(["--seconds", "60", "--ips", "10", "--anomaly-share", "0.3", "--run-id", "DEV-cli"],
                    env={}, writer_factory=lambda cfg: w, now=lambda: NOW)
    s = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == EXIT_OK and s["windows_written"] == 60 == len(w.windows) and s["metrics_written"] == 12
    assert s["run_id"] == "DEV-cli" and len(w.runs) == 1


@pytest.mark.parametrize("argv", [["--anomaly-share", "1.5"], ["--ips", "0"], ["--seconds", "5"]])
def test_cli_usage_errors(argv, capsys):
    assert syn.main(argv, env={}, writer_factory=lambda cfg: FakeWriter(), now=lambda: NOW) == EXIT_USAGE_ERROR
