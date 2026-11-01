# Module 4 — standard targets (Constitution Art. V)
PY ?= $(shell [ -x ../.venv/bin/python ] && echo ../.venv/bin/python || echo python3)
# pytest exits 5 when no tests are collected (e.g. integration without the docker marker).
PYTEST = $(PY) -m pytest -q -p no:cacheprovider

.PHONY: install test contract-test run mock clean integration-test bench

install:
	$(PY) -m pip install -q -r requirements.txt
	$(PY) -m pip install -q -e . --no-deps

test:
	$(PYTEST) tests/unit || [ $$? -eq 5 ]

contract-test:
	$(PYTEST) tests/contract || [ $$? -eq 5 ]

integration-test:
	$(PYTEST) tests/integration -m docker || [ $$? -eq 5 ]

# M4-F01 schema apply + check (idempotent), then the M4-F02 dashboard on the C-06 `dashboard` port.
DASHBOARD_PORT = 8501
run:
	$(PY) -m ids_monitor.schema apply
	$(PY) -m streamlit run src/ids_monitor/dashboard_app.py --server.port $(DASHBOARD_PORT) --server.headless true \
		--browser.gatherUsageStats false

# M4-F03 benchmark harness: one experiment (EXP=E1|E2|E3|P1|LAT|REC), extra flags in BENCH_ARGS
# (e.g. BENCH_ARGS="--levels 1 --duration 60" for a smoke, or "--dry-run"). Needs the platform up and M1/M3 installed.
EXP ?= E1
bench:
	$(PY) -m ids_monitor.bench --experiment $(EXP) $(BENCH_ARGS)

# M4-F01: contract-valid synthetic windows and metrics for the last 300 s (mock of M3's output).
mock:
	$(PY) -m ids_monitor.synthetic $(MOCK_ARGS)

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf src/*.egg-info .pytest_cache
