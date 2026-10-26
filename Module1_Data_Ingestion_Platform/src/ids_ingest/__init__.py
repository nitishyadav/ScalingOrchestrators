"""Module 1 — Data Ingestion and Platform (owner: Aswin S.).

Only `ids_contracts` may be imported from outside this package (Constitution Art. III).
"""
from pathlib import Path

__version__ = "0.2.0"

MODULE_DIR = Path(__file__).resolve().parents[2]
PLATFORM_DIR = MODULE_DIR / "platform"
COMPOSE_FILE = PLATFORM_DIR / "docker-compose.yml"
