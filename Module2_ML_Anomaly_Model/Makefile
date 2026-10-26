# Module 2 (REPLICA) — standard targets (Constitution Art. V)
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)

.PHONY: install test contract-test run mock clean integration-test eda

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PY) -m pytest tests/unit -q -p no:cacheprovider

contract-test:
	$(PY) -m pytest tests/contract -q -p no:cacheprovider

# Replica scope: no real training yet (M2-F03). `run` validates the installed bundle at MODEL_BUNDLE_PATH.
run:
	$(PY) -m ids_model.bundle check

# M2 mock: dummy bundle → mocks/dummy_bundle and installed at MODEL_BUNDLE_PATH; golden scores → contracts/fixtures.
mock:
	$(PY) -m ids_model.bundle make-dummy --install
	$(PY) -m ids_model.bundle golden-scores

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache

integration-test:
	$(PY) -m pytest tests/integration -q -p no:cacheprovider -m docker

# M2-F01: EDA of the replay dataset → docs/measurements/F01-eda-<date>.md + figures/
eda:
	$(PY) -m ids_model.eda
