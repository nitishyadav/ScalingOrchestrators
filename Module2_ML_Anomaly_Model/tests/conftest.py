"""Shared helpers for Module 2 (REPLICA) tests."""
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
DUMMY = MODULE_DIR / "mocks" / "dummy_bundle"
