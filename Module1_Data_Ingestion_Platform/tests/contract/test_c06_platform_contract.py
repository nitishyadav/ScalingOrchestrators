"""M1-T013 — C-06 contract tests for the platform (M1-F01-AC-11): the doc, the compose file and the CLIs agree."""
import re
import subprocess
import sys

import pytest
import yaml

from conftest import C06_MD, COMPOSE_FILE, MODULE_DIR
from ids_contracts.config import EXIT_OK, EXIT_USAGE_ERROR

NOT_IN_M1_COMPOSE = {"zookeeper", "dashboard"}   # zookeeper: unused (M1-ADR-001); dashboard: M4-owned


def c06_service_table() -> dict:
    """{service: set(host ports)} parsed from C-06 §4."""
    text = C06_MD.read_text()
    section = text.split("## 4.", 1)[1].split("\n## ", 1)[0]
    table = {}
    for line in section.splitlines():
        m = re.match(r"\|\s*`([a-z\-]+)`[^|]*\|\s*([^|]*)\|", line)
        if m:
            ports = {int(p) for p in re.findall(r"\b(\d{4,5})\b", m.group(2))}
            table[m.group(1)] = ports
    return table


def compose_host_ports() -> dict:
    services = yaml.safe_load(COMPOSE_FILE.read_text())["services"]
    return {n: {int(str(p).split(":")[0]) for p in s.get("ports", [])} for n, s in services.items()}


def test_compose_services_and_ports_equal_c06_section_4():
    doc, impl = c06_service_table(), compose_host_ports()
    assert set(impl) == set(doc) - NOT_IN_M1_COMPOSE
    for name, ports in impl.items():
        if name == "spark-master":
            assert ports == {7077, 8080}
        else:
            assert ports == doc[name], name


def cli(*args):
    return subprocess.run([sys.executable, "-m", *args], capture_output=True, text=True, cwd=MODULE_DIR,
                          env={"PATH": "/usr/bin:/bin", "IDS_ROOT": str(MODULE_DIR.parent)}, timeout=60)


@pytest.mark.parametrize("module", ["ids_ingest.platform", "ids_ingest.topic_admin", "ids_ingest.prepare", "ids_ingest.producer"])
def test_help_exits_0(module):
    assert cli(module, "--help").returncode == EXIT_OK


@pytest.mark.parametrize(
    "args",
    [("ids_ingest.platform", "up", "--bogus"), ("ids_ingest.platform", "up", "--workers", "9"),
     ("ids_ingest.platform", "clean"), ("ids_ingest.topic_admin", "--partitions", "0"),
     ("ids_ingest.topic_admin", "--partitions", "99"), ("ids_ingest.prepare", "--bogus"),
     ("ids_ingest.producer", "--days", "Funday"), ("ids_ingest.producer", "--rate", "0"),
     ("ids_ingest.producer", "--source", "fixture", "--attack-mode", "ddos", "--attack-share", "0.1"),
     ("ids_ingest.producer", "--attack-mode", "ddos", "--attack-share", "0.1", "--attack-start", "-1"),
     ("ids_ingest.producer", "--bogus")],
)
def test_usage_errors_exit_2(args):
    assert cli(*args).returncode == EXIT_USAGE_ERROR
