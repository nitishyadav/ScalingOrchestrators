# Module 3 (REPLICA) — standard targets (Constitution Art. V)
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)

.PHONY: install test contract-test run mock clean integration-test

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PY) -m pytest tests/unit -q -p no:cacheprovider

contract-test:
	$(PY) -m pytest tests/contract -q -p no:cacheprovider

# Runs the stream job on the platform until stopped (Ctrl-C → graceful stop). Platform + topic + bundle must exist.
run:
	$(PY) -m ids_stream.job

# M3 mock for M4: synthetic C-04/C-05 rows are M4's own mock (python ../Module4_*/mocks/synthetic_rows.py); M3 ships none.
mock:
	@echo "M3 has no separate mock: consumers of C-04/C-05 use Module4's synthetic_rows.py (contract-identical rows)."

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache ../runtime/build/ids_stream.zip

integration-test:
	$(PY) -m pytest tests/integration -q -p no:cacheprovider -m docker
