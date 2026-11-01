"""M4-T211: benchmark maths (AC-03, AC-04, AC-05). All times in epoch ms."""
import pytest

from ids_monitor import bench_math as BM

T0 = 1_793_975_400_000            # producer start
S = 1000


def batch(ts, rows=5000, p95=400.0, p50=200.0, written=40, proc=6000.0, dur=800):
    lat = (None, None) if written == 0 else (p50, p95)
    return {"run_id": "R", "batch_ts": ts, "batch_id": 0, "input_rows": rows, "input_rows_per_sec": float(rows),
            "processed_rows_per_sec": proc, "batch_duration_ms": dur, "latency_p50_ms": lat[0], "latency_p95_ms": lat[1],
            "latency_max_ms": None if written == 0 else p95 + 100, "windows_written": written, "anomalies_written": 0,
            "kafka_partitions": 8, "executors": 2}


def run_metrics():
    """Producer runs 120 s at 5,000 ev/s from T0. 1 s batches. Warm-up batches are slow, 3 drain batches follow."""
    ms = [batch(T0 + i * S, p95=2000.0) for i in range(1, 61)]                                # warm-up (excluded)
    ms += [batch(T0 + i * S, p95=300.0 + (i % 5) * 10) for i in range(61, 121)]               # steady: 60 batches
    ms[70] = batch(T0 + 71 * S, written=0)                                                    # no rows written: no latency
    ms += [batch(T0 + 120 * S + k * S, rows=1000) for k in (1, 2, 3)]                       # drain after the producer ended
    return ms[::-1]                                                                           # C-05 reads come newest first


# ---- AC-03 ----
def test_steady_state_selection():
    st = BM.steady(run_metrics(), T0 + 60 * S, T0 + 120 * S)                               # (start, end]: a batch covers (ts − 1 s, ts]
    assert [b["batch_ts"] for b in st] == [T0 + i * S for i in range(61, 121)]               # oldest first


def test_summary_throughput_latency_backlog():
    s = BM.summarize(run_metrics(), T0, T0 + 120 * S, warmup_s=60, target_rate=5000, producer_rate=5000.0)
    assert s["steady_batches"] == 60 and s["steady_span_s"] == 60.0
    assert s["sustained_evs"] == 5000.0                                                     # 60 × 5,000 / 60 s
    assert s["producer_bound"] is True and s["keeping_up"] is True
    assert s["backlog_s"] == 3.0                                                            # last input batch 3 s after the end
    assert s["p95_ms"] == 320.0                                                             # median of 300..340 (59 batches)
    assert s["p95_tail_ms"] == 340.0 and s["p50_ms"] == 200.0
    assert s["spark_processed_median"] == 6000.0 and s["batch_ms_median"] == 800.0
    assert s["status"] == "ok"


def test_saturated_run_is_not_producer_bound():
    ms = [batch(T0 + i * S, rows=9000) for i in range(1, 121)]
    s = BM.summarize(ms, T0, T0 + 120 * S, warmup_s=60, target_rate=15000, producer_rate=14800.0)
    assert s["sustained_evs"] == 9000.0 and s["producer_bound"] is False and s["keeping_up"] is False


def test_no_steady_batches_is_a_failure():
    s = BM.summarize([batch(T0 + 5 * S)], T0, T0 + 120 * S, warmup_s=60, target_rate=5000)
    assert s["status"] == "failed" and "no batches" in s["reason"] and s["sustained_evs"] is None


def test_30s_samples():
    rows = BM.samples(run_metrics(), T0, T0 + 120 * S)
    assert [r["t_s"] for r in rows] == [0, 30, 60, 90]
    assert rows[0]["evs"] == 5000.0 and rows[0]["batches"] == 30                            # bins are (t, t + 30 s]
    assert rows[2]["p95_median_ms"] == 320.0 and rows[0]["p95_max_ms"] == 2000.0
    assert sum(r["batches"] for r in rows) == 120                                           # drain batches are outside


# ---- AC-04 efficiency ----
def test_efficiency_exact_lower_bound_and_inconclusive():
    rows = BM.efficiency([(1, 4000.0, False), (4, 9000.0, False), (8, 12000.0, True)])
    assert [(r["n"], r["speedup"], r["efficiency"], r["qualifier"]) for r in rows] == [
        (1, 1.0, 1.0, "exact"), (4, 2.25, 0.5625, "exact"), (8, 3.0, 0.375, "lower_bound")]
    assert {r["qualifier"] for r in BM.efficiency([(1, 4000.0, True), (4, 4000.0, True)])} == {"inconclusive"}
    assert BM.efficiency([(1, None, False), (4, 9000.0, False)])[1]["efficiency"] is None


# ---- AC-05 detection, banner, recovery ----
def w(end, anomalous, attack=False, inj=False):
    return {"window_end": end, "is_anomaly": anomalous, "label_attack": attack or inj,
            "label_type": "INJ_DDOS" if inj else ("DDoS" if attack else "BENIGN")}


def test_detection_rates():
    ws = ([w(T0, True, inj=True)] * 9 + [w(T0, False, inj=True)] + [w(T0, True)] * 2 + [w(T0, False)] * 98
          + [w(T0, True, attack=True)])
    d = BM.detection(ws)
    assert d["windows"] == 111 and d["injected_windows"] == 10 and d["recall_injected"] == 0.9
    assert d["benign_windows"] == 100 and d["fpr_benign"] == 0.02 and d["cic_attack_windows"] == 1
    assert d["anomalous_share"] == round(12 / 111, 4)
    assert BM.detection([])["recall_injected"] is None


def test_banner_rolling_300s_every_30s():
    ws = [w(T0 + i * 10 * S, i >= 40) for i in range(60)]                    # anomalous from 400 s, one window per 10 s
    b = BM.banner(ws, T0, T0 + 600 * S)
    assert b["samples"] == 11                                                 # 300, 330, …, 600 s
    assert b["max_share"] == pytest.approx(20 / 29, abs=1e-4)                 # at 600 s: windows in (300, 600], 20 of 29
    assert b["first_alert_s"] == 450                                          # 6 of 30 = 0.2 > 0.15 (at 420 s: 0.1)
    assert b["share_above"] == round(6 / 11, 4)                               # 450, 480, …, 600 s


def test_recovery_after_restart():
    restart = T0 + 300 * S
    ms = [batch(T0 + i * S, p95=300.0) for i in range(1, 300)]
    ms += [batch(restart + 20 * S, p95=9000.0), batch(restart + 21 * S, p95=4000.0)]           # 20 s gap, slow catch-up
    ms += [batch(restart + (22 + k) * S, p95=500.0) for k in range(10)]                        # back under max(600, 1300)
    r = BM.recovery(ms, restart)
    assert r["first_batch_s"] == 20.0 and r["max_gap_s"] == 21.0                              # 299 s → 320 s
    assert r["pre_p95_ms"] == 300.0 and r["threshold_ms"] == 1300.0
    assert r["recovered_s"] == 22.0 and r["passed"] is True
    never = BM.recovery(ms[:301], restart)
    assert never["recovered_s"] is None and never["passed"] is False
