"""`python -m ids_ingest.topic_admin --partitions N [--recreate]` — C-01 §2.1 topic, C-06 §5 (M1-T024; M1-F01 FR-005)."""
from __future__ import annotations

import argparse
import sys
import time
from enum import Enum
from typing import Callable, Mapping, Optional, Protocol, Sequence

from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, RuntimeConfig,
                                  load_runtime_config, summary_line)

REPLICATION_FACTOR = 1
TOPIC_CONFIG = {"retention.ms": "1800000"}   # C-01 §2.1 (30 min)


class Action(Enum):
    CREATE = "create"
    NOOP = "noop"
    INCREASE = "increase"
    RECREATE = "recreate"
    REFUSE = "refuse"


class AdminError(RuntimeError):
    """Broker unreachable or an admin operation failed."""


class TopicShrinkRefused(ValueError):
    """Kafka cannot reduce partitions; --recreate is required."""


class Admin(Protocol):
    def partitions(self, topic: str) -> Optional[int]: ...
    def create(self, topic: str, partitions: int, replication: int, config: Mapping[str, str]) -> None: ...
    def increase(self, topic: str, partitions: int) -> None: ...
    def delete(self, topic: str) -> None: ...
    def set_config(self, topic: str, config: Mapping[str, str]) -> None: ...


def plan_action(existing: Optional[int], requested: int, recreate: bool) -> Action:
    if existing is None:
        return Action.CREATE
    if recreate:
        return Action.RECREATE
    if existing == requested:
        return Action.NOOP
    return Action.INCREASE if requested > existing else Action.REFUSE


def ensure_topic(admin: Admin, topic: str, partitions: int, recreate: bool) -> dict:
    existing = admin.partitions(topic)
    action = plan_action(existing, partitions, recreate)
    if action is Action.REFUSE:
        raise TopicShrinkRefused(
            f"topic '{topic}' has {existing} partitions; Kafka cannot shrink to {partitions}. Re-run with --recreate "
            f"(deletes all data in the topic).")
    if action is Action.RECREATE:
        admin.delete(topic)
    if action in (Action.CREATE, Action.RECREATE):
        admin.create(topic, partitions, REPLICATION_FACTOR, TOPIC_CONFIG)
    elif action is Action.INCREASE:
        admin.increase(topic, partitions)
    if action in (Action.NOOP, Action.INCREASE):
        admin.set_config(topic, TOPIC_CONFIG)
    return {"topic": topic, "partitions": partitions, "action": action.value}


class ConfluentAdmin:
    """Admin adapter over confluent-kafka (M1-ADR-002)."""

    def __init__(self, bootstrap: str, timeout_s: float = 15.0):
        from confluent_kafka.admin import AdminClient
        self.timeout = timeout_s
        # IPv4 only: Colima forwards 127.0.0.1, so `localhost` → ::1 attempts just produce warnings
        self.client = AdminClient({"bootstrap.servers": bootstrap, "socket.timeout.ms": 10000,
                                   "broker.address.family": "v4"})

    def partitions(self, topic: str) -> Optional[int]:
        from confluent_kafka import KafkaError, KafkaException
        try:
            md = self.client.list_topics(topic=topic, timeout=self.timeout)
        except KafkaException as exc:
            raise AdminError(f"cannot reach broker: {exc}") from exc
        t = md.topics.get(topic)
        if t is None or (t.error is not None and t.error.code() == KafkaError.UNKNOWN_TOPIC_OR_PART):
            return None
        if t.error is not None:
            raise AdminError(f"metadata error for '{topic}': {t.error}")
        return len(t.partitions)

    def _result(self, futures: dict, what: str) -> None:
        for name, fut in futures.items():
            try:
                fut.result(timeout=self.timeout)
            except Exception as exc:  # confluent-kafka raises KafkaException with a KafkaError payload
                raise AdminError(f"{what} '{name}' failed: {exc}") from exc

    def _wait(self, topic: str, predicate: Callable[[Optional[int]], bool], what: str, limit_s: float = 30.0) -> None:
        deadline = time.monotonic() + limit_s
        while not predicate(self.partitions(topic)):
            if time.monotonic() > deadline:
                raise AdminError(f"timed out waiting for topic '{topic}' to be {what}")
            time.sleep(0.5)

    def create(self, topic, partitions, replication, config) -> None:
        from confluent_kafka.admin import NewTopic
        deadline = time.monotonic() + 30
        while True:   # right after a delete the broker may still report "marked for deletion"
            try:
                self._result(self.client.create_topics(
                    [NewTopic(topic, num_partitions=partitions, replication_factor=replication, config=dict(config))]),
                    "create")
                break
            except AdminError as exc:
                if "TOPIC_ALREADY_EXISTS" not in str(exc) or time.monotonic() > deadline:
                    raise
                time.sleep(1.0)
        self._wait(topic, lambda n: n == partitions, f"created with {partitions} partitions")

    def increase(self, topic, partitions) -> None:
        from confluent_kafka.admin import NewPartitions
        self._result(self.client.create_partitions([NewPartitions(topic, partitions)]), "increase partitions of")
        self._wait(topic, lambda n: n == partitions, f"at {partitions} partitions")

    def delete(self, topic) -> None:
        self._result(self.client.delete_topics([topic]), "delete")
        self._wait(topic, lambda n: n is None, "deleted")

    def set_config(self, topic, config) -> None:
        from confluent_kafka.admin import AlterConfigOpType, ConfigEntry, ConfigResource
        entries = [ConfigEntry(k, v, incremental_operation=AlterConfigOpType.SET) for k, v in config.items()]
        self._result(self.client.incremental_alter_configs(
            [ConfigResource("topic", topic, incremental_configs=entries)]), "set config of")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m ids_ingest.topic_admin",
                                description="Create, grow or recreate the C-01 event topic (C-06 §5).")
    p.add_argument("--partitions", type=int, help="number of partitions, 1..16 (→ KAFKA_PARTITIONS)")
    p.add_argument("--recreate", action="store_true", help="delete and recreate the topic (required to shrink)")
    return p


def main(argv: Optional[Sequence[str]] = None,
         admin_factory: Optional[Callable[[RuntimeConfig], Admin]] = None,
         env: Optional[Mapping[str, str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_runtime_config(overrides={"KAFKA_PARTITIONS": args.partitions}, env=env)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    factory = admin_factory or (lambda c: ConfluentAdmin(c.kafka_bootstrap))
    try:
        result = ensure_topic(factory(cfg), cfg.kafka_topic, cfg.kafka_partitions, args.recreate)
    except TopicShrinkRefused as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE_ERROR
    except AdminError as exc:
        print(f"{exc}\nIs the platform running? `python -m ids_ingest.platform status`", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    print(summary_line("topic_admin", cfg.run_id, **result))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
