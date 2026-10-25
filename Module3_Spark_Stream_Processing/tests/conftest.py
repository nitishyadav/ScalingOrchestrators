"""Shared helpers for Module 3 (REPLICA) tests."""
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parents[1]
ROOT = MODULE_DIR.parent
DUMMY_BUNDLE = ROOT / "Module2_ML_Anomaly_Model" / "mocks" / "dummy_bundle"
