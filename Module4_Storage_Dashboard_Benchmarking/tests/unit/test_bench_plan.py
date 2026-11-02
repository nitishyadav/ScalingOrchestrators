"""M4-T210: plans, run IDs and commands (AC-01, AC-02)."""
import pytest

from ids_contracts.config import validate_run_id
from ids_monitor import bench_plan as BP

STAMP = "202611061430"


# ---- AC-01 plans and run IDs ----
@pytest.mark.parametrize("exp, levels", [("E1", ["1", "4", "8", "16"]), ("E2", ["1", "2", "4"]), ("E3", ["0", "5", "20", "100"]),
                                         ("P1", ["16x4"]), ("LAT", ["1000", "500", "250"]), ("REC", ["8x2"])])
def test_levels_per_experiment(exp, levels):
    assert [s.level for s in BP.plan(exp)] == levels


def test_fixed_settings_follow_the_spec_table():
    e1 = BP.plan("E1")
    assert {(s.executors, s.rate, s.trigger_ms, s.attack_share) for s in e1} == {(4, 15_000, 1000, 0.0)}
    assert [s.partitions for s in e1] == [1, 4, 8, 16]
    e2 = BP.plan("E2")
    assert [s.executors for s in e2] == [1, 2, 4] and {s.partitions for s in e2} == {8} and {s.rate for s in e2} == {15_000}
    assert [s.attack_share for s in BP.plan("E3")] == [0.0, 0.05, 0.2, 1.0]
    (p1,) = BP.plan("P1")
    assert (p1.partitions, p1.executors, p1.rate) == (16, 4, 12_000)
    assert [s.trigger_ms for s in BP.plan("LAT")] == [1000, 500, 250]
    (rec,) = BP.plan("REC")
    assert rec.restart_at == 0.5 and (rec.partitions, rec.executors, rec.rate) == (8, 2, 5_000)


def test_run_ids_are_valid_and_carry_the_configuration():
    ids = {BP.run_id(s, STAMP) for exp in BP.EXPERIMENTS for s in BP.plan(exp)}
    assert all(validate_run_id(r) for r in ids)
    assert BP.run_id(BP.plan("E1")[1], STAMP) == "E1-p4-e4-r15000-a0-202611061430"
    assert BP.run_id(BP.plan("E3")[2], STAMP) == "E3-p8-e2-r5000-a20-202611061430"
    assert BP.run_id(BP.plan("LAT")[1], STAMP) == "LAT-p8-e2-r5000-a0-t500-202611061430"   # -t only for LAT
    assert "-t" not in BP.run_id(BP.plan("REC")[0], STAMP)


def test_stamp_is_utc_minutes():
    assert BP.stamp(1_793_975_400_000) == "202611061430"                 # 2026-11-06 14:30:00 UTC


def test_levels_filter_and_errors():
    assert [s.level for s in BP.plan("E1", ["16", "1"])] == ["1", "16"]  # plan order kept
    with pytest.raises(ValueError, match="unknown level"):
        BP.plan("E1", ["3"])
    with pytest.raises(ValueError, match="unknown experiment"):
        BP.plan("E9")


# ---- AC-02 commands: C-06 CLIs and flags only ----
C06_FLAGS = {
    "ids_ingest.topic_admin": {"--partitions", "--recreate"},
    "ids_stream.job": {"--executors", "--trigger", "--run-id", "--await-seconds"},
    "ids_ingest.producer": {"--source", "--rate", "--duration", "--days", "--attack-mode", "--attack-share", "--seed", "--run-id"},
    "ids_ingest.platform": {"restart-worker", "--index"},
}


def flags(argv):
    return {a for a in argv[1:] if a.startswith("--") or a == "restart-worker"}


@pytest.mark.parametrize("exp", list(BP.EXPERIMENTS))
def test_commands_use_only_c06_clis_and_flags(exp):
    for spec in BP.plan(exp):
        cmds = BP.commands(spec, BP.run_id(spec, STAMP), duration_s=600)
        for argv in cmds.values():
            assert argv[0] in C06_FLAGS and flags(argv) <= C06_FLAGS[argv[0]], argv


def test_command_values():
    spec = BP.plan("LAT")[1]
    rid = BP.run_id(spec, STAMP)
    c = BP.commands(spec, rid, duration_s=600)
    assert c["topic"] == ["ids_ingest.topic_admin", "--partitions", "8", "--recreate"]
    assert c["job"] == ["ids_stream.job", "--executors", "2", "--trigger", "500 milliseconds", "--run-id", rid,
                        "--await-seconds", "1200"]
    assert c["producer"] == ["ids_ingest.producer", "--source", "replay", "--days", "Monday", "--rate", "5000",
                             "--duration", "600", "--run-id", rid, "--seed", "42"]
    assert "restart" not in c
    e3 = BP.commands(BP.plan("E3")[1], "X", duration_s=60)["producer"]
    assert e3[-4:] == ["--attack-mode", "mixed", "--attack-share", "0.05"]
    assert "--attack-mode" not in BP.commands(BP.plan("E3")[0], "X", duration_s=60)["producer"]   # 0 % = mode none
    assert BP.commands(BP.plan("REC")[0], "X", duration_s=60)["restart"] == ["ids_ingest.platform", "restart-worker",
                                                                           "--index", "1"]
    assert BP.trigger_text(1000) == "1 second" and BP.trigger_text(250) == "250 milliseconds"
