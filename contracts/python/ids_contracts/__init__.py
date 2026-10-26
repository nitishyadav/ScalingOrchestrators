"""Shared contract package for all modules.

The only cross-module import allowed by the constitution (Art. III). Holds constants, models and
validators for contracts C-01..C-06. Never put business logic here.

Install from any module folder with:  pip install -e ../contracts/python
"""
from pathlib import Path

__version__ = "1.0.0rc1"

# Editable install keeps the package inside the workspace: contracts/python/ids_contracts/__init__.py
CONTRACTS_DIR = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
FIXTURES_DIR = CONTRACTS_DIR / "fixtures"


class ContractViolation(ValueError):
    """Raised when data does not satisfy a contract."""
