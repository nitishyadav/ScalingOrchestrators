"""M1-T010 — static checks of the platform definition (M1-F01-AC-09; FR-001, FR-003, FR-004, FR-006, FR-007, NFR-002, NFR-005)."""
import re

from conftest import SPARK_DIR, parse_mem, pinned_images, version_pins
from ids_contracts.config import ENV_SPEC

EXPECTED_SERVICES = {"kafka", "spark-master", "spark-worker", "spark-client", "cassandra"}
EXPECTED_HOST_PORTS = {"kafka": {9092}, "spark-master": {7077, 8080}, "cassandra": {9042},
                       "spark-worker": set(), "spark-client": set()}
BUDGET_GIB = 10.0
DEFAULT_WORKERS = int(next(v.default for v in ENV_SPEC if v.name == "SPARK_WORKERS"))


def host_ports(service: dict) -> set:
    out = set()
    for p in service.get("ports", []):
        parts = str(p).split(":")
        assert len(parts) == 2, f"use HOST:CONTAINER port form, got {p!r}"
        out.add(int(parts[0]))
    return out


def env_of(service: dict) -> dict:
    env = service.get("environment", {})
    if isinstance(env, list):
        env = dict(e.split("=", 1) for e in env)
    return {k: str(v) for k, v in env.items()}


def test_service_names(compose):
    assert set(compose["services"]) == EXPECTED_SERVICES


def test_host_ports_match_c06(compose):
    for name, svc in compose["services"].items():
        assert host_ports(svc) == EXPECTED_HOST_PORTS[name], name


def test_every_service_has_healthcheck_and_memory_limit(compose):
    for name, svc in compose["services"].items():
        assert "healthcheck" in svc and svc["healthcheck"].get("test"), f"{name}: missing healthcheck"
        assert "mem_limit" in svc, f"{name}: missing mem_limit"


def test_memory_budget_fits_10_gib(compose):
    total = 0.0
    for name, svc in compose["services"].items():
        mem = parse_mem(svc["mem_limit"])
        total += mem * (DEFAULT_WORKERS if name == "spark-worker" else 1)
    assert total <= BUDGET_GIB, f"memory limits sum to {total:.2f} GiB"


def test_images_pinned_no_latest(compose):
    pinned = pinned_images()
    spark_base = next(i for i in pinned if i.startswith("apache/spark:"))
    for name, svc in compose["services"].items():
        image = svc.get("image", "")
        assert ":" in image and not image.endswith(":latest"), f"{name}: unpinned image {image!r}"
        if name.startswith("spark"):
            assert svc.get("build") or name != "spark-master" or image, name
            assert image == compose["services"]["spark-master"]["image"], "spark services must share one image"
        else:
            assert image in pinned, f"{name}: {image} not pinned in versions.md"
    dockerfile = (SPARK_DIR / "Dockerfile").read_text()
    assert re.search(rf"^FROM {re.escape(spark_base)}\s*$", dockerfile, re.M), "Dockerfile FROM must equal the versions.md Spark image"
    assert ":latest" not in dockerfile


def test_spark_python_stack_matches_versions_md():
    pins = version_pins()
    want = {"scikit-learn": pins["scikit-learn"], "numpy": pins["numpy / pandas / pyarrow"].split(" / ")[0]
            if "numpy / pandas / pyarrow" in pins else pins["numpy"],
            "pandas": pins.get("pandas"), "pyarrow": pins.get("pyarrow"), "joblib": pins.get("joblib"),
            "pyyaml": pins.get("pyyaml")}
    reqs = {}
    for line in (SPARK_DIR / "requirements-spark.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, ver = line.partition("==")
            reqs[name.lower()] = ver
    for name, ver in want.items():
        assert reqs.get(name) == ver, f"{name}: requirements-spark.txt has {reqs.get(name)}, versions.md has {ver}"


def test_kafka_is_kraft_with_dual_listeners(compose):
    env = env_of(compose["services"]["kafka"])
    assert "controller" in env["KAFKA_PROCESS_ROLES"] and "broker" in env["KAFKA_PROCESS_ROLES"]
    adv = env["KAFKA_ADVERTISED_LISTENERS"]
    assert "localhost:9092" in adv and "kafka:29092" in adv
    assert env["KAFKA_AUTO_CREATE_TOPICS_ENABLE"] == "false"   # topics only via topic_admin (C-01 §2.1)
    assert "ZOOKEEPER" not in " ".join(env)                     # M1-ADR-001


def test_workers_offer_four_executor_slots(compose):
    cmd = " ".join(compose["services"]["spark-worker"]["command"]) \
        if isinstance(compose["services"]["spark-worker"]["command"], list) else compose["services"]["spark-worker"]["command"]
    cores = int(re.search(r"--cores\s+(\d+)", cmd).group(1))
    assert cores * DEFAULT_WORKERS >= 4


def _volume_targets(svc):
    out = {}
    for v in svc.get("volumes", []):
        parts = re.sub(r"\$\{[^}]*\}", "SRC", str(v)).split(":")   # ${VAR:?msg} contains ':'
        out[parts[1]] = parts[2] if len(parts) > 2 else "rw"
    return out


def test_client_and_workers_mount_workspace_ro_and_runtime_rw(compose):
    for name in ("spark-client", "spark-worker"):
        vols = _volume_targets(compose["services"][name])
        assert vols.get("/workspace") == "ro", name
        assert vols.get("/workspace/runtime") == "rw", name


def test_client_env_uses_in_network_addresses(compose):
    env = env_of(compose["services"]["spark-client"])
    assert env["IDS_ROOT"] == "/workspace"
    assert env["KAFKA_BOOTSTRAP"] == "kafka:29092"
    assert env["CASSANDRA_HOSTS"] == "cassandra"
    assert env["SPARK_MASTER_URL"] == "spark://spark-master:7077"
