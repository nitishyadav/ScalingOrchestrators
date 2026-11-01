"""M4 contract tests: what M4 provides as C-04 (DDL + mock rows) matches ids_contracts (AC-09)."""
from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_monitor import schema as SC
from ids_monitor.synthetic import generate_run

BASE = 1_767_225_600_000


def test_applied_ddl_is_the_contract_ddl():
    spec = SC.parse_ddl(SC.ddl_text(S.KEYSPACE))
    assert spec["window_scores"].columns == S.COLUMNS
    assert spec["window_scores"].partition == S.PARTITION_KEY
    assert spec["window_scores"].clustering == S.CLUSTERING
    assert spec["pipeline_metrics"].columns == M.METRICS_COLUMNS
    assert spec["runs"].columns == M.RUNS_COLUMNS


def test_mock_rows_satisfy_c04_and_c05():
    r = generate_run(end_ms=BASE + 3_600_000, seed=42, n_ips=50, n_windows=30, anomaly_share=0.2, run_id="DEV-contract")
    assert r.windows and all(S.validate_row(w) == [] for w in r.windows)
    assert r.metrics and all(M.validate_metrics_row(m) == [] for m in r.metrics)
    assert M.validate_run_row(r.run) == []
    assert {c for c, _ in S.COLUMNS} == set(r.windows[0])
