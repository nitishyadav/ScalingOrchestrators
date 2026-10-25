# Tasks: M2-F04 — Detection Bundle (dummy) + Golden Scores (REPLICA)

- [x] **M2-T030** C-03 replica 0.1.1: `scores_golden.csv` format (`SCORE_COLUMNS`, `read_scores_csv`). C-02 0.1.1: floored offline timestamps · Done: 2026-10-22
- [x] **M2-T040** Tests first: `tests/unit/test_bundle.py`, `tests/contract/test_c02_c03_contract.py`, `tests/integration/test_bundle_in_spark_image.py` · Done: 2026-10-22
- [x] **M2-T050** `src/ids_model/bundle.py` (`make_dummy`, `Bundle.load` with the version guard, vectorised `score`, golden scores, CLI) · Done: 2026-10-22
- [x] **M2-T060** `make mock`: `mocks/dummy_bundle/` + installed at `runtime/bundle/current` + `contracts/fixtures/scores_golden.csv` · Done: 2026-10-22
