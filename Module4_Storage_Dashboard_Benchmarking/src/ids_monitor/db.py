"""Cassandra connection from C-06 settings (M4-T020)."""
from __future__ import annotations

from typing import Any, Tuple

from ids_contracts.config import RuntimeConfig

CONNECT_TIMEOUT_S = 10                # NFR-003: fail within 15 s when Cassandra is down
REQUEST_TIMEOUT_S = 30


class StoreUnavailable(RuntimeError):
    """Cassandra cannot be reached."""


def connect(cfg: RuntimeConfig) -> Tuple[Any, Any]:
    """(cluster, session) with dict rows. The caller shuts the cluster down (`close`)."""
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.policies import DCAwareRoundRobinPolicy
    from cassandra.query import dict_factory

    cluster = Cluster(list(cfg.cassandra_hosts), port=cfg.cassandra_port, connect_timeout=CONNECT_TIMEOUT_S,
                      load_balancing_policy=DCAwareRoundRobinPolicy(), protocol_version=5)
    try:
        session = cluster.connect()
    except (NoHostAvailable, OSError) as exc:
        cluster.shutdown()
        hosts = ",".join(cfg.cassandra_hosts)
        raise StoreUnavailable(f"cannot reach Cassandra at {hosts}:{cfg.cassandra_port} ({exc})") from None
    session.row_factory = dict_factory
    session.default_timeout = REQUEST_TIMEOUT_S
    return cluster, session


def close(cluster: Any) -> None:
    if cluster is not None:
        cluster.shutdown()
