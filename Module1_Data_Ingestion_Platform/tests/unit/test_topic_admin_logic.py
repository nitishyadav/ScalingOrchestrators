"""M1-T011 — topic_admin decision table and behaviour with a fake admin (M1-F01-AC-05; FR-005, FR-010)."""
import json

import pytest

from ids_ingest import topic_admin as ta
from ids_contracts.config import EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR


class FakeAdmin:
    def __init__(self, topics=None, fail=False):
        self.topics = dict(topics or {})
        self.configs = {}
        self.calls = []
        self.fail = fail

    def partitions(self, topic):
        if self.fail:
            raise ta.AdminError("broker unreachable")
        self.calls.append(("partitions", topic))
        return self.topics.get(topic)

    def create(self, topic, partitions, replication, config):
        self.calls.append(("create", topic, partitions, replication))
        self.topics[topic] = partitions
        self.configs[topic] = dict(config)

    def increase(self, topic, partitions):
        self.calls.append(("increase", topic, partitions))
        self.topics[topic] = partitions

    def delete(self, topic):
        self.calls.append(("delete", topic))
        self.topics.pop(topic, None)

    def set_config(self, topic, config):
        self.calls.append(("set_config", topic))
        self.configs.setdefault(topic, {}).update(config)


@pytest.mark.parametrize(
    "existing,requested,recreate,expected",
    [
        (None, 4, False, ta.Action.CREATE),
        (None, 4, True, ta.Action.CREATE),
        (4, 4, False, ta.Action.NOOP),
        (4, 8, False, ta.Action.INCREASE),
        (8, 1, False, ta.Action.REFUSE),
        (8, 1, True, ta.Action.RECREATE),
        (4, 4, True, ta.Action.RECREATE),
    ],
)
def test_plan_action(existing, requested, recreate, expected):
    assert ta.plan_action(existing, requested, recreate) is expected


def test_create_uses_c01_topic_config():
    admin = FakeAdmin()
    result = ta.ensure_topic(admin, "network-events", 4, recreate=False)
    assert result == {"topic": "network-events", "partitions": 4, "action": "create"}
    assert ("create", "network-events", 4, 1) in admin.calls
    assert admin.configs["network-events"]["retention.ms"] == "1800000"


def test_noop_and_increase_reassert_config():
    admin = FakeAdmin({"network-events": 4})
    assert ta.ensure_topic(admin, "network-events", 4, False)["action"] == "noop"
    assert ta.ensure_topic(admin, "network-events", 8, False)["action"] == "increase"
    assert admin.topics["network-events"] == 8
    assert admin.configs["network-events"]["retention.ms"] == "1800000"


def test_shrink_refused_without_recreate():
    admin = FakeAdmin({"network-events": 8})
    with pytest.raises(ta.TopicShrinkRefused):
        ta.ensure_topic(admin, "network-events", 1, False)
    assert admin.topics["network-events"] == 8


def test_recreate_deletes_then_creates():
    admin = FakeAdmin({"network-events": 8})
    result = ta.ensure_topic(admin, "network-events", 1, True)
    assert result["action"] == "recreate" and admin.topics["network-events"] == 1
    names = [c[0] for c in admin.calls]
    assert names.index("delete") < names.index("create")


def _run(argv, admin, capsys):
    code = ta.main(argv, admin_factory=lambda cfg: admin, env={})
    out = capsys.readouterr()
    return code, out


def test_main_success_prints_summary_line(capsys):
    code, out = _run(["--partitions", "4"], FakeAdmin(), capsys)
    assert code == EXIT_OK
    summary = json.loads(out.out.strip().splitlines()[-1])
    assert summary == {"status": "ok", "command": "topic_admin", "run_id": "DEV-local",
                       "topic": "network-events", "partitions": 4, "action": "create"}


@pytest.mark.parametrize("argv", [["--partitions", "0"], ["--partitions", "17"], ["--partitions", "x"], ["--bogus"]])
def test_main_usage_errors_exit_2(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        code, _ = _run(argv, FakeAdmin(), capsys)
        raise SystemExit(code)
    assert exc.value.code == EXIT_USAGE_ERROR


def test_main_shrink_exit_2(capsys):
    code, out = _run(["--partitions", "1"], FakeAdmin({"network-events": 8}), capsys)
    assert code == EXIT_USAGE_ERROR and "--recreate" in out.err


def test_main_broker_down_exit_1(capsys):
    code, out = _run(["--partitions", "4"], FakeAdmin(fail=True), capsys)
    assert code == EXIT_RUNTIME_ERROR and "broker unreachable" in out.err
