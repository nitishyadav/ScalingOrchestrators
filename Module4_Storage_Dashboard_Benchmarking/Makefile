# Module 4 — standard targets (Constitution Art. V)
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)
# pytest exits 5 when no tests are collected; accepted until the first feature lands.
PYTEST = $(PY) -m pytest -q -p no:cacheprovider

.PHONY: install test contract-test run mock clean integration-test

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PYTEST) tests/unit || [ $$? -eq 5 ]

contract-test:
	$(PYTEST) tests/contract || [ $$? -eq 5 ]

integration-test:
	$(PYTEST) tests/integration -m docker || [ $$? -eq 5 ]

# Defined by M4-F01 (schema apply/check) and M4-F02 (dashboard).
run:
	@echo "run: not implemented yet (M4-F01, M4-F02)"; exit 1

# Defined by M4-F01 (synthetic C-04/C-05 rows).
mock:
	@echo "mock: not implemented yet (M4-F01)"; exit 1

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache
