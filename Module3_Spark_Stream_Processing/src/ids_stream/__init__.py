"""Module 3 — Spark Stream Processing. REPLICA built by Aswin S. (M1); canonical owner Kumari Priyanka.

`spec` and `job` are pure Python (host); `app` is the PySpark driver and runs only in the platform's Spark image.
Only `ids_contracts` may be imported from outside this package (Constitution Art. III).
"""
from pathlib import Path

__version__ = "0.1.0-replica"
PACKAGE_DIR = Path(__file__).resolve().parent
MODULE_DIR = PACKAGE_DIR.parents[1]
