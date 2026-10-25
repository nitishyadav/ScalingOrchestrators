# Module 4 (REPLICA) — standard targets (Constitution Art. V)
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)

.PHONY: install test contract-test run mock clean integration-test demo bench bench-all analyze

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PY) -m pytest tests/unit -q -p no:cacheprovider

contract-test:
	$(PY) -m pytest tests/contract -q -p no:cacheprovider

# Prepares the store (idempotent, checked against C-04/C-05), then serves the live dashboard on http://localhost:8501.
run:
	$(PY) -m ids_monitor.schema apply
	$(PY) -m ids_monitor.schema check
	$(PY) -m streamlit run src/ids_monitor/dashboard.py --server.port 8501 --server.headless true --browser.gatherUsageStats false

# Not a standard target: the dashboard on in-memory synthetic data (no platform needed).
demo:
	$(PY) -m streamlit run src/ids_monitor/dashboard.py --server.port 8501 --server.headless true --browser.gatherUsageStats false -- --demo

# M4 mock: synthetic, contract-valid C-04/C-05 rows ending now (for dashboard work before the Spark job exists).
mock:
	$(PY) mocks/synthetic_rows.py --seconds 600 --anomaly-share 0.2

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache

integration-test:
	$(PY) -m pytest tests/integration -q -p no:cacheprovider -m docker

# M4-F03 benchmark harness (needs the platform). `make bench EXP=E2`; `make bench EXP=E1 ARGS="--levels 1 --duration 60"`.
EXP ?= E1
bench:
	$(PY) -m ids_monitor.bench --experiment $(EXP) $(ARGS)

# All experiments at 600 s each (about 3 h): E1, E2, LAT, E3, P1, REC. A failed run is recorded and the next experiment still runs.
bench-all:
	for e in E1 E2 LAT E3 P1 REC; do $(PY) -m ids_monitor.bench --experiment $$e $(ARGS); done

# M4-F04: scorecard + figures from the newest report per experiment → results/analysis/
analyze:
	$(PY) -m ids_monitor.analyze
