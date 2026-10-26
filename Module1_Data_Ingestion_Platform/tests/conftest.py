"""Shared helpers for Module 1 tests."""
import re
from pathlib import Path

import pytest
import yaml

MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
COMPOSE_FILE = MODULE_DIR / "platform" / "docker-compose.yml"
SPARK_DIR = MODULE_DIR / "platform" / "spark"
VERSIONS_MD = ROOT / "contracts" / "versions.md"
C06_MD = ROOT / "contracts" / "C-06_runtime_config_control.md"


def parse_mem(value) -> float:
    """'1280m' / '2g' / '2.25g' -> GiB."""
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([mMgG])", str(value).strip())
    assert m, f"unparseable memory value {value!r}"
    num, unit = float(m.group(1)), m.group(2).lower()
    return num if unit == "g" else num / 1024


def version_pins() -> dict:
    """{component: pin-cell} from the versions.md pin table (first two columns)."""
    pins = {}
    for line in VERSIONS_MD.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] and not set(cells[0]) <= set("-"):
            pins[cells[0]] = cells[1]
    return pins


def pinned_images() -> set:
    """All `repo:tag` image references (backticked) in versions.md."""
    return set(re.findall(r"`((?:apache/[a-z]+|cassandra):[\w.\-]+)`", VERSIONS_MD.read_text()))


@pytest.fixture(scope="session")
def compose():
    return yaml.safe_load(COMPOSE_FILE.read_text())
