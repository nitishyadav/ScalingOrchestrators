# Module 1 — standard targets (Constitution Art. V)
# Uses the workspace venv (../.venv) when present, otherwise python3 on PATH.
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)

.PHONY: install test contract-test run mock clean integration-test data-test

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PY) -m pytest tests/unit -q -p no:cacheprovider

contract-test:
	$(PY) -m pytest tests/contract -q -p no:cacheprovider

# Starts the platform (C-06 §4); reads integration/.env if present.
run:
	$(PY) -m ids_ingest.platform up

# M1 mocks: mocks/replay_sample.parquet (replay-dataset sample for M2, from the prepared data) and
# contracts/fixtures/events_golden.jsonl (events; replayed via the producer from M1-F03).
mock:
	$(PY) -m ids_ingest.prepare --sample

# Removes generated files only. Platform data volumes: python -m ids_ingest.platform clean --yes
clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache

# Not a standard target: live tests against a running Docker engine (slow).
integration-test:
	$(PY) -m pytest tests/integration -q -p no:cacheprovider -m "docker and not perf"

# Not a standard target: dataset preparation on the real CIC files (needs runtime/data/raw/TrafficLabelling).
data-test:
	$(PY) -m pytest tests/integration/test_prepare_real_data.py -q -p no:cacheprovider -m data
