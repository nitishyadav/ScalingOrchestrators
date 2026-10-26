"""Contract tests for C-06 Runtime Config and Control."""
import json

import pytest

from ids_contracts import CONTRACTS_DIR
from ids_contracts import config as cfg

ROOT = CONTRACTS_DIR.parent
ENV_EXAMPLE = ROOT / "integration" / ".env.example"


def test_defaults_load_and_resolve_paths_against_workspace_root():
    c = cfg.load_config(env={}, cwd=ROOT / "Module1_Data_Ingestion_Platform")
    assert c.workspace_root == ROOT
    assert c.kafka_topic == "network-events"
    assert c.kafka_partitions == 8
    assert c.cassandra_hosts == ("localhost",)
    assert (c.spark_workers, c.spark_executor_memory) == (2, "768m")
    assert c.data_dir == ROOT / "runtime" / "data"
    assert c.results_dir == ROOT / "Module4_Storage_Dashboard_Benchmarking" / "results"
    assert c.attack_mode == "none" and c.attack_share == 0.0


def test_precedence_override_beats_env_beats_default():
    env = {"PRODUCER_RATE": "7000", "KAFKA_PARTITIONS": "4"}
    c = cfg.load_config(env=env, overrides={"PRODUCER_RATE": 9000, "KAFKA_PARTITIONS": None}, cwd=ROOT)
    assert c.producer_rate == 9000
    assert c.kafka_partitions == 4


def test_empty_env_value_falls_back_to_default():
    assert cfg.load_config(env={"KAFKA_TOPIC": ""}, cwd=ROOT).kafka_topic == "network-events"


@pytest.mark.parametrize(
    "key,value",
    [
        ("KAFKA_PARTITIONS", "0"), ("KAFKA_PARTITIONS", "17"), ("SPARK_WORKERS", "5"), ("KAFKA_PARTITIONS", "eight"),
        ("PRODUCER_RATE", "0"), ("ATTACK_MODE", "nuke"), ("ATTACK_SHARE", "1.5"),
        ("TRIGGER_INTERVAL", "1s"), ("SPARK_EXECUTOR_MEMORY", "1GB"), ("KAFKA_BOOTSTRAP", "localhost"),
        ("CASSANDRA_KEYSPACE", "ids-prod"), ("RUN_ID", "my run"), ("SPARK_MASTER_URL", "http://x:7077"),
    ],
)
def test_invalid_values_raise_config_error(key, value):
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={key: value}, cwd=ROOT)


def test_attack_mode_and_share_must_be_consistent():
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={"ATTACK_MODE": "none", "ATTACK_SHARE": "0.2"}, cwd=ROOT)
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={"ATTACK_MODE": "ddos", "ATTACK_SHARE": "0"}, cwd=ROOT)
    c = cfg.load_config(env={"ATTACK_MODE": "ddos", "ATTACK_SHARE": "0.2"}, cwd=ROOT)
    assert (c.attack_mode, c.attack_share) == ("ddos", 0.2)


def test_unknown_override_key_rejected():
    with pytest.raises(cfg.ConfigError):
        cfg.load_config(env={}, overrides={"KAFKA_TOPICS": "x"}, cwd=ROOT)


@pytest.mark.parametrize(
    "run_id,ok",
    [("E1-p4-e2-r5000-a0-202611061430", True), ("E3-p8-e2-r5000-a20-202611071000", True),
     ("DEV-local", True), ("DEV-aswin_test.1", True), ("E4-p4-e2-r5000-a0-202611061430", False),
     ("E1-p4-e2-r5000-a0-2026", False), ("dev-local", False),
     ("LAT-p8-e2-r5000-a0-t250-202610251430", True), ("P1-p16-e4-r12000-a0-202610251430", True),
     ("REC-p8-e2-r5000-a0-202610251430", True), ("E3-p8-e2-r5000-a100-202610251430", True),
     ("LAT-p8-e2-r5000-a0-t-202610251430", False)],
)
def test_run_id_pattern(run_id, ok):
    assert cfg.validate_run_id(run_id) is ok


def test_summary_line_is_single_json_line():
    line = cfg.summary_line("producer", "DEV-local", sent=10, achieved_rate=5000.0)
    assert "\n" not in line
    data = json.loads(line)
    assert data == {"status": "ok", "command": "producer", "run_id": "DEV-local", "sent": 10, "achieved_rate": 5000.0}


def test_env_example_matches_env_spec_and_loads():
    env = cfg.read_env_file(ENV_EXAMPLE)
    assert list(env) == list(cfg.ENV_NAMES)
    for var in cfg.ENV_SPEC:
        if var.name != "IDS_ROOT":
            assert env[var.name] == var.default, var.name
    cfg.load_config(env=env, cwd=ROOT)


def test_runtime_config_layers_env_file_under_process_env(tmp_path):
    (tmp_path / "CONSTITUTION.md").write_text("x")
    (tmp_path / "integration").mkdir()
    (tmp_path / "integration" / ".env").write_text("PRODUCER_RATE=6000\nKAFKA_PARTITIONS=4\n# comment\n")
    c = cfg.load_runtime_config(env={"KAFKA_PARTITIONS": "16"}, cwd=tmp_path / "integration")
    assert c.workspace_root == tmp_path.resolve()
    assert c.producer_rate == 6000          # from .env
    assert c.kafka_partitions == 16         # process env beats .env
    c2 = cfg.load_runtime_config(env={}, overrides={"PRODUCER_RATE": 7000}, cwd=tmp_path)
    assert c2.producer_rate == 7000         # override beats .env


def test_runtime_config_without_env_file_uses_defaults(tmp_path):
    (tmp_path / "CONSTITUTION.md").write_text("x")
    assert cfg.load_runtime_config(env={}, cwd=tmp_path).kafka_partitions == 8


def test_config_as_dict_is_json_serialisable():
    json.dumps(cfg.load_config(env={}, cwd=ROOT).as_dict())
