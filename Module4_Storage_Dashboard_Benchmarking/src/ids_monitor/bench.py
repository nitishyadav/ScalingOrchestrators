"""`python -m ids_monitor.bench --experiment E1|E2|E3|P1|LAT|REC` — M4-F03 benchmark harness (REPLICA).

Drives the platform only through C-06 CLIs (M1 topic_admin / producer / platform, M3 job), then reads C-05 metrics
(and C-04 windows for E3) back from Cassandra. Raw results: RESULTS_DIR/raw/<run_id>/; summary: RESULTS_DIR/<EXP>-<stamp>.{json,md}.
Usage:
    python -m ids_monitor.bench --experiment E1 --dry-run
    python -m ids_monitor.bench --experiment E1 --levels 1 --duration 60          # smoke
    python -m ids_monitor.bench --experiment E2                                    # 3 × 600 s
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ids_contracts import metrics as M
from ids_contracts import store as S
from ids_contracts.config import (EXIT_OK, EXIT_RUNTIME_ERROR, EXIT_USAGE_ERROR, ConfigError, load_runtime_config,
                                  summary_line)

R_REF = 5000
REPLAY_DAYS = "Monday"                 # benign background: E3's attack share is exactly the injected share (spec §2)
ATTACK_MODE = "mixed"
REGISTER_TIMEOUT_S, START_GRACE_S = 180, 10
DRAIN_TIMEOUT_S, DRAIN_QUIET_S = 120, 8
STOP_TIMEOUT_S, POLL_S = 120, 2
SAMPLE_S = 30
KEEP_UP_SHARE, KEEP_UP_BACKLOG_S = 0.95, 10
METRIC_FIELDS = tuple(c for c, _ in M.METRICS_COLUMNS)


# ---- plans (AC-01) -------------------------------------------------------------------------------
@dataclass(frozen=True)
class RunSpec:
    experiment: str
    level: str
    partitions: int
    executors: int
    rate: int = R_REF
    share: float = 0.0
    trigger: str = "1 second"
    restart_at: Optional[float] = None          # fraction of the producer run (REC)

    def run_id(self, stamp: str) -> str:
        t = f"-t{trigger_ms(self.trigger)}" if self.experiment == "LAT" else ""
        return (f"{self.experiment}-p{self.partitions}-e{self.executors}-r{self.rate}-a{round(self.share * 100)}{t}-{stamp}")


def trigger_ms(trigger: str) -> int:
    n, unit = trigger.split()
    return int(float(n) * (1 if unit.startswith("millisecond") else 1000))


EXPERIMENTS: Dict[str, List[RunSpec]] = {
    "E1": [RunSpec("E1", str(p), p, 2) for p in (1, 4, 8, 16)],
    "E2": [RunSpec("E2", str(e), 8, e) for e in (1, 2, 4)],
    "E3": [RunSpec("E3", str(a), 8, 2, share=a / 100) for a in (0, 5, 20, 100)],
    "P1": [RunSpec("P1", "1", 16, 4, rate=12_000)],
    "LAT": [RunSpec("LAT", str(trigger_ms(t)), 8, 2, trigger=t) for t in ("1 second", "500 milliseconds", "250 milliseconds")],
    "REC": [RunSpec("REC", "1", 8, 2, restart_at=0.5)],
}


def plan(experiment: str, levels: Optional[Sequence[str]] = None) -> List[RunSpec]:
    specs = EXPERIMENTS[experiment]
    if levels:
        unknown = set(levels) - {s.level for s in specs}
        if unknown:
            raise ValueError(f"{experiment} has no level(s) {sorted(unknown)}; levels are {[s.level for s in specs]}")
        specs = [s for s in specs if s.level in set(levels)]
    return list(specs)


def utc_stamp(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y%m%d%H%M")


def commands(spec: RunSpec, run_id: str, duration: int, budget: int, py: str = sys.executable) -> dict:
    producer = [py, "-m", "ids_ingest.producer", "--days", REPLAY_DAYS, "--rate", str(spec.rate), "--duration", str(duration),
                "--run-id", run_id]
    if spec.share > 0:
        producer += ["--attack-mode", ATTACK_MODE, "--attack-share", f"{spec.share:g}"]
    return {
        "topic": [py, "-m", "ids_ingest.topic_admin", "--partitions", str(spec.partitions), "--recreate"],
        "job": [py, "-m", "ids_stream.job", "--executors", str(spec.executors), "--trigger", spec.trigger, "--run-id", run_id,
                "--await-seconds", str(budget), "--starting-offsets", "earliest"],
        "producer": producer,
        "restart": [py, "-m", "ids_ingest.platform", "restart-worker", "--index", "1"] if spec.restart_at else None,
    }


# ---- maths (AC-02, AC-03) ------------------------------------------------------------------------
def _median(values) -> Optional[float]:
    values = [v for v in values if v is not None]
    return float(statistics.median(values)) if values else None


def summarize_metrics(metrics: Sequence[Mapping], start_ms: int, end_ms: int, warmup_s: float, target_rate: int) -> dict:
    """Steady state = batches in [start + warmup, end] (producer time). FR-022."""
    rows = sorted(metrics, key=lambda m: m["batch_ts"])
    inputs = [m for m in rows if m["input_rows"] > 0]
    steady = [m for m in inputs if start_ms + warmup_s * 1000 <= m["batch_ts"] <= end_ms]
    p95s = [m["latency_p95_ms"] for m in steady if m["latency_p95_ms"] is not None]
    span_s = (inputs[-1]["batch_ts"] - inputs[0]["batch_ts"]) / 1000 if len(inputs) > 1 else 0
    sustained = sum(m["input_rows"] for m in inputs) / span_s if span_s else None
    backlog = max(0.0, (inputs[-1]["batch_ts"] - end_ms) / 1000) if inputs else None
    return {
        "batches": len(rows), "input_batches": len(inputs), "steady_batches": len(steady),
        "input_rows": sum(m["input_rows"] for m in rows),
        "sustained_evs": sustained,
        "capacity_rows_per_s": _median(m["processed_rows_per_sec"] for m in steady),
        "latency_p95_ms": _median(p95s),
        "latency_p95_worst_ms": M.percentile(p95s, 95),
        "batch_duration_ms": _median(m["batch_duration_ms"] for m in steady),
        "backlog_s": backlog,
        "keeping_up": bool(sustained is not None and sustained >= KEEP_UP_SHARE * target_rate
                           and backlog is not None and backlog <= KEEP_UP_BACKLOG_S),
    }


def samples(metrics: Sequence[Mapping], start_ms: int, bin_s: int = SAMPLE_S) -> List[dict]:
    """30 s samples (proposal Week 8), relative to producer start."""
    bins: Dict[int, List[Mapping]] = {}
    for m in metrics:
        if m["batch_ts"] >= start_ms:
            bins.setdefault((m["batch_ts"] - start_ms) // (bin_s * 1000), []).append(m)
    out = []
    for k in sorted(bins):
        b = bins[k]
        p95 = [m["latency_p95_ms"] for m in b if m["latency_p95_ms"] is not None]
        out.append({"t_s": k * bin_s, "batches": len(b), "input_evs": sum(m["input_rows"] for m in b) / bin_s,
                    "capacity_median": _median(m["processed_rows_per_sec"] for m in b if m["input_rows"] > 0),
                    "p95_median_ms": _median(p95), "p95_max_ms": max(p95) if p95 else None})
    return out


def efficiency(points: Sequence[Tuple[int, Optional[float]]]) -> List[dict]:
    """(T_N / T_1) / (N / N_1) with T = capacity; the smallest N is the base (FR-024)."""
    pts = sorted(points)
    n1, t1 = pts[0]
    out = []
    for n, t in pts:
        speedup = t / t1 if t is not None and t1 else None
        out.append({"n": n, "capacity": t, "speedup": speedup,
                    "efficiency": speedup / (n / n1) if speedup is not None else None})
    return out


def _rate(flagged: int, total: int) -> Optional[float]:
    return flagged / total if total else None


def detection(windows: Sequence[Mapping], start_ms: int, end_ms: int, step_s: int = SAMPLE_S,
              span_s: int = S.DRIFT_WINDOW_S) -> dict:
    """E3 detection from C-04 rows (FR-025). Banner = 300 s rolling anomalous share, sampled every 30 s."""
    rows = [w for w in windows if start_ms < w["window_end"] <= end_ms + 60_000]
    groups = {
        "injected": [w for w in rows if str(w["label_type"]).startswith("INJ_")],
        "cic_attack": [w for w in rows if w["label_attack"] and not str(w["label_type"]).startswith("INJ_")],
        "benign": [w for w in rows if not w["label_attack"]],
    }
    flagged = {k: sum(1 for w in v if w["is_anomaly"]) for k, v in groups.items()}
    shares, t = [], start_ms + min(span_s, max(step_s, (end_ms - start_ms) // 1000)) * 1000
    ends = sorted((w["window_end"], bool(w["is_anomaly"])) for w in rows)
    while t <= end_ms:
        inside = [a for e, a in ends if t - span_s * 1000 < e <= t]
        if inside:
            shares.append((sum(inside), len(inside)))
        t += step_s * 1000
    alerts = [S.drift_alert(a, n) for a, n in shares]
    return {
        "windows": len(rows), "anomalous": sum(1 for w in rows if w["is_anomaly"]),
        "anomalous_share": _rate(sum(1 for w in rows if w["is_anomaly"]), len(rows)),
        "injected": {"windows": len(groups["injected"]), "flagged": flagged["injected"],
                     "recall": _rate(flagged["injected"], len(groups["injected"]))},
        "cic_attack": {"windows": len(groups["cic_attack"]), "flagged": flagged["cic_attack"],
                       "recall": _rate(flagged["cic_attack"], len(groups["cic_attack"]))},
        "benign": {"windows": len(groups["benign"]), "flagged": flagged["benign"],
                   "fpr": _rate(flagged["benign"], len(groups["benign"]))},
        "banner": {"samples": len(shares), "max_share": max((a / n for a, n in shares), default=None),
                   "alert_fraction": _rate(sum(alerts), len(alerts)) if alerts else None,
                   "threshold": S.DRIFT_THRESHOLD, "span_s": span_s},
    }


def recovery(metrics: Sequence[Mapping], restart_ms: int, pre_n: int = 20) -> dict:
    """P5 (FR-026): first input batch after the restart, largest gap, and time until latency is back to normal."""
    inputs = sorted((m for m in metrics if m["input_rows"] > 0), key=lambda m: m["batch_ts"])
    pre = [m["latency_p95_ms"] for m in inputs if m["batch_ts"] < restart_ms and m["latency_p95_ms"] is not None][-pre_n:]
    after = [m for m in inputs if m["batch_ts"] > restart_ms]
    near = [m["batch_ts"] for m in inputs if restart_ms - 30_000 <= m["batch_ts"] <= restart_ms + 180_000]
    pre_med = _median(pre)
    recovered = None
    if pre_med is not None:
        limit = max(2 * pre_med, pre_med + 1000)
        for i in range(len(after) - 2):
            if all(m["latency_p95_ms"] is not None and m["latency_p95_ms"] <= limit for m in after[i:i + 3]):
                recovered = (after[i]["batch_ts"] - restart_ms) / 1000
                break
    return {"restart_ms": restart_ms, "pre_p95_ms": pre_med,
            "first_batch_after_s": (after[0]["batch_ts"] - restart_ms) / 1000 if after else None,
            "max_gap_s": max((b - a for a, b in zip(near, near[1:])), default=0) / 1000,
            "recovered_s": recovered, "p5_pass": recovered is not None and recovered < 30}


# ---- orchestration (AC-04) -----------------------------------------------------------------------
class Interrupted(Exception):
    pass


class SubprocessCli:
    """Real C-06 CLI adapter. Children get their own session so a terminal Ctrl-C reaches only the harness,
    which then forwards exactly one SIGINT (the job wrapper treats a second one as 'force', S-053)."""

    def __init__(self, env: Mapping[str, str]):
        self.env = dict(env)

    def run(self, cmd, cwd, timeout):
        p = subprocess.run(cmd, cwd=cwd, env=self.env, capture_output=True, text=True, timeout=timeout, start_new_session=True)
        return p.returncode, p.stdout, p.stderr

    def start(self, cmd, cwd, out: Path, err: Path):
        return subprocess.Popen(cmd, cwd=cwd, env=self.env, stdout=open(out, "w"), stderr=open(err, "w"), text=True,
                                start_new_session=True)


class Clock:
    def now_ms(self) -> int:
        return int(time.time() * 1000)

    def sleep(self, s: float) -> None:
        time.sleep(s)


def last_json(text: str) -> Optional[dict]:
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None


def _write_csv(path: Path, rows: Sequence[Mapping], fields: Sequence[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


class Runner:
    def __init__(self, cli, store, clock, results_dir: Path, root: Path, py: str = sys.executable,
                 log: Callable[[str], None] = lambda m: print(m, file=sys.stderr, flush=True)):
        self.cli, self.store, self.clock, self.results_dir, self.py, self.log = cli, store, clock, Path(results_dir), py, log
        self.m1, self.m3 = root / "Module1_Data_Ingestion_Platform", root / "Module3_Spark_Stream_Processing"

    # one level
    def run_one(self, spec: RunSpec, run_id: str, duration: int, warmup: float) -> dict:
        raw = self.results_dir / "raw" / run_id
        raw.mkdir(parents=True, exist_ok=True)
        budget = REGISTER_TIMEOUT_S + START_GRACE_S + duration + DRAIN_TIMEOUT_S + STOP_TIMEOUT_S + 60
        cmds = commands(spec, run_id, duration, budget, self.py)
        result = {"run_id": run_id, "spec": asdict(spec), "duration_s": duration, "warmup_s": warmup, "status": "ok"}
        _dump(raw / "config.json", {**result, "commands": cmds})
        job = producer = None
        t = {}
        try:
            self.log(f"[{run_id}] topic: {spec.partitions} partitions")
            rc, out, err = self.cli.run(cmds["topic"], self.m1, 180)
            if rc != 0:
                raise RuntimeError(f"topic_admin exit {rc}: {err.strip()[-500:]}")
            self.log(f"[{run_id}] stream job: {spec.executors} executors, trigger {spec.trigger}")
            t["job_start"] = self.clock.now_ms()
            job = self.cli.start(cmds["job"], self.m3, raw / "job.stdout", raw / "job.log")
            self._wait_registered(run_id, job)
            self.clock.sleep(START_GRACE_S)
            self.log(f"[{run_id}] producer: {spec.rate} ev/s for {duration} s" + (f", attack share {spec.share:g}" if spec.share else ""))
            t["producer_start"] = self.clock.now_ms()
            producer = self.cli.start(cmds["producer"], self.m1, raw / "producer.stdout", raw / "producer.log")
            if cmds["restart"]:
                self._sleep_until(t["producer_start"] + spec.restart_at * duration * 1000, producer)
                t["restart"] = self.clock.now_ms()
                self.log(f"[{run_id}] restarting spark worker 1")
                rc, out, err = self.cli.run(cmds["restart"], self.m1, 240)
                result["restart"] = last_json(out) or {"exit": rc, "stderr": err.strip()[-500:]}
            self._wait_exit(producer, duration + 120)
            t["producer_end"] = self.clock.now_ms()
            self._drain(run_id, t["producer_end"])
        except KeyboardInterrupt:
            result["status"] = "interrupted"
        except Exception as exc:                       # noqa: BLE001 — a failed run is recorded, the experiment continues
            result["status"], result["error"] = "failed", str(exc)
        finally:
            for proc in (producer, job):
                if proc is not None:
                    self._stop(proc)
        t.setdefault("producer_end", self.clock.now_ms())
        result["times_ms"] = t
        self._collect(spec, run_id, raw, result, t, warmup)
        _dump(raw / "summary.json", result)
        self.log(f"[{run_id}] {result['status']}: " + json.dumps(result.get("summary", {}), default=str))
        return result

    def _wait_registered(self, run_id: str, job) -> None:
        deadline = self.clock.now_ms() + REGISTER_TIMEOUT_S * 1000
        while self.clock.now_ms() < deadline:
            if any(r.get("run_id") == run_id for r in self.store.runs(50)):
                return
            if job.poll() is not None:
                raise RuntimeError(f"stream job exited early (exit {job.poll()}); see job.log")
            self.clock.sleep(POLL_S)
        raise RuntimeError(f"stream job did not register within {REGISTER_TIMEOUT_S} s")

    def _sleep_until(self, when_ms: float, proc) -> None:
        while self.clock.now_ms() < when_ms and proc.poll() is None:
            self.clock.sleep(min(POLL_S, max(0.0, (when_ms - self.clock.now_ms()) / 1000)))

    def _wait_exit(self, proc, timeout_s: float) -> None:
        deadline = self.clock.now_ms() + timeout_s * 1000
        while proc.poll() is None:
            if self.clock.now_ms() > deadline:
                raise RuntimeError(f"producer still running {timeout_s} s after start")
            self.clock.sleep(POLL_S)
        if proc.poll() != 0:
            raise RuntimeError(f"producer exit {proc.poll()}; see producer.log")

    def _drain(self, run_id: str, producer_end: int) -> None:
        deadline = self.clock.now_ms() + DRAIN_TIMEOUT_S * 1000
        while self.clock.now_ms() < deadline:
            newest = next((m for m in self.store.metrics(run_id, 50) if m["input_rows"] > 0), None)
            if newest and newest["batch_ts"] >= producer_end - 2000 and self.clock.now_ms() - newest["batch_ts"] >= DRAIN_QUIET_S * 1000:
                return
            self.clock.sleep(3)
        self.log(f"[{run_id}] drain timeout ({DRAIN_TIMEOUT_S} s); collecting anyway")

    def _stop(self, proc) -> None:
        if proc.poll() is not None:
            return
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGINT)                       # job wrapper: second Ctrl-C = force
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _collect(self, spec: RunSpec, run_id: str, raw: Path, result: dict, t: Mapping, warmup: float) -> None:
        for name in ("producer", "job"):
            out = raw / f"{name}.stdout"
            summary = last_json(out.read_text()) if out.is_file() else None
            if summary is not None:
                _dump(raw / f"{name}.json", summary)
                result[name] = summary
        if "producer_start" not in t:
            return
        try:
            metrics = sorted(self.store.metrics(run_id, 1_000_000), key=lambda m: m["batch_ts"])
        except Exception as exc:                       # noqa: BLE001
            result["collect_error"] = str(exc)
            return
        _write_csv(raw / "metrics.csv", metrics, METRIC_FIELDS)
        smp = samples(metrics, t["producer_start"])
        _write_csv(raw / "samples.csv", smp, ("t_s", "batches", "input_evs", "capacity_median", "p95_median_ms", "p95_max_ms"))
        result["summary"] = summarize_metrics(metrics, t["producer_start"], t["producer_end"], warmup, spec.rate)
        if spec.experiment == "E3":
            lo, hi = t["producer_start"] - 60_000, t["producer_end"] + 90_000
            wins = self.store.recent_windows(hi, (hi - lo) // 1000 + 1, run_id)
            result["detection"] = detection(wins, t["producer_start"], t["producer_end"])
            _dump(raw / "detection.json", result["detection"])
        if "restart" in t:
            result["recovery"] = recovery(metrics, t["restart"])
            _dump(raw / "recovery.json", result["recovery"])

    # one experiment
    def run_experiment(self, experiment: str, specs: Sequence[RunSpec], duration: int, warmup: float) -> dict:
        warmup = min(warmup, duration / 3)
        started, runs, previous, interrupted = utc_stamp(self.clock.now_ms()), [], None, False
        for spec in specs:
            stamp = utc_stamp(self.clock.now_ms())
            if stamp == previous:                        # run IDs carry minutes: never reuse one
                self.clock.sleep(60 - (self.clock.now_ms() // 1000) % 60)
                stamp = utc_stamp(self.clock.now_ms())
            previous = stamp
            result = self.run_one(spec, spec.run_id(stamp), duration, warmup)
            runs.append(result)
            if result["status"] == "interrupted":
                interrupted = True
                break
        report = experiment_report(experiment, runs, duration, warmup)
        report.update(interrupted=interrupted, report_stem=f"{experiment}-{started}")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        _dump(self.results_dir / f"{report['report_stem']}.json", report)
        (self.results_dir / f"{report['report_stem']}.md").write_text(report_markdown(report))
        return report


# ---- reports -------------------------------------------------------------------------------------
TARGETS = {
    "E1": "P3: efficiency 1 → 4 partitions ≥ 0.5 (minimum acceptable speedup 1.5×, D-05)",
    "E2": "P4: efficiency 1 → 4 executors ≥ 0.5 (minimum acceptable speedup 1.5×, D-05)",
    "E3": "F2: benign-only (0 %) window FPR < 5 %; F5: banner fires on the all-attack load (100 %, ADR-013)",
    "P1": "P1: sustained ≥ 10,000 ev/s at 16 partitions × 4 executors",
    "LAT": "P2: p95 end-to-end latency < 500 ms at 5,000 ev/s (D-01 definition), D-13",
    "REC": "P5: recovery after a Spark worker restart < 30 s",
}


def experiment_report(experiment: str, runs: Sequence[Mapping], duration: int, warmup: float) -> dict:
    report = {"experiment": experiment, "target": TARGETS[experiment], "duration_s": duration, "warmup_s": warmup,
              "runs": list(runs), "checks": {}}
    ok = [r for r in runs if r["status"] == "ok" and r.get("summary")]
    if experiment in ("E1", "E2"):
        key = "partitions" if experiment == "E1" else "executors"
        report["efficiency"] = efficiency([(r["spec"][key], r["summary"]["capacity_rows_per_s"]) for r in ok]) if ok else []
        at4 = next((e for e in report["efficiency"] if e["n"] == 4), None)
        if at4 and report["efficiency"][0]["n"] == 1 and at4["efficiency"] is not None:
            report["checks"]["efficiency_at_4"] = {"value": at4["efficiency"], "target": 0.5, "pass": at4["efficiency"] >= 0.5,
                                                   "speedup": at4["speedup"], "minimum_speedup_pass": at4["speedup"] >= 1.5}
    if experiment == "P1" and ok:
        s = ok[0]["summary"]
        report["checks"]["sustained_10k"] = {"value": s["sustained_evs"], "target": 10_000, "keeping_up": s["keeping_up"],
                                             "pass": bool(s["sustained_evs"] and s["sustained_evs"] >= 10_000 and s["keeping_up"])}
    if experiment == "LAT":
        for r in ok:
            p95 = r["summary"]["latency_p95_ms"]
            report["checks"][f"p95_t{r['spec']['level']}ms"] = {"value": p95, "target": 500, "pass": p95 is not None and p95 < 500}
    if experiment == "E3":
        for r in ok:
            d = r.get("detection") or {}
            if r["spec"]["share"] == 0 and d:
                fpr = d["benign"]["fpr"]
                report["checks"]["F2_benign_fpr"] = {"value": fpr, "target": 0.05, "pass": fpr is not None and fpr < 0.05}
            if r["spec"]["share"] == 1.0 and d:
                frac = d["banner"]["alert_fraction"]
                report["checks"]["F5_banner_all_attack"] = {"value": frac, "pass": bool(frac and frac > 0.5)}
    if experiment == "REC" and ok and ok[0].get("recovery"):
        rec = ok[0]["recovery"]
        report["checks"]["P5_recovery"] = {"value": rec["recovered_s"], "target": 30, "pass": rec["p5_pass"]}
    return report


def _f(v, fmt="{:,.0f}"):
    return "—" if v is None else fmt.format(v)


def report_markdown(report: Mapping) -> str:
    lines = [f"# {report['experiment']} — benchmark results", "",
             f"Target: {report['target']}. Each run: {report['duration_s']} s replay, steady state after {report['warmup_s']:g} s warm-up.",
             "Capacity = median `processed_rows_per_sec` (Spark progress). Latency = median of per-batch p95 (`detected_at − max_event_ts`, D-01).",
             "", "| Level | Run ID | Status | Sustained ev/s | Capacity rows/s | p95 ms (median / worst) | Batch ms | Backlog s | Keeping up |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in report["runs"]:
        s = r.get("summary") or {}
        lines.append(f"| {r['spec']['level']} | `{r['run_id']}` | {r['status']} | {_f(s.get('sustained_evs'))} | "
                     f"{_f(s.get('capacity_rows_per_s'))} | {_f(s.get('latency_p95_ms'))} / {_f(s.get('latency_p95_worst_ms'))} | "
                     f"{_f(s.get('batch_duration_ms'))} | {_f(s.get('backlog_s'), '{:.1f}')} | {s.get('keeping_up', '—')} |")
    if report.get("efficiency"):
        lines += ["", "| N | Capacity rows/s | Speedup | Efficiency |", "|---|---|---|---|"]
        lines += [f"| {e['n']} | {_f(e['capacity'])} | {_f(e['speedup'], '{:.2f}')} | {_f(e['efficiency'], '{:.2f}')} |"
                  for e in report["efficiency"]]
        lines.append("\nE1/E2 replay at a fixed 5,000 ev/s, so the sustained rate cannot show scaling; efficiency uses capacity (FR-024).")
    det = [r for r in report["runs"] if r.get("detection")]
    if det:
        lines += ["", "| Attack share | Windows | Anomalous share | Injected recall | Benign FPR | CIC-attack windows | Banner: max 300 s share / samples alerting |",
                  "|---|---|---|---|---|---|---|"]
        for r in det:
            d = r["detection"]
            lines.append(f"| {r['spec']['level']} % | {d['windows']:,} | {_f(d['anomalous_share'], '{:.1%}')} | "
                         f"{_f(d['injected']['recall'], '{:.1%}')} | {_f(d['benign']['fpr'], '{:.2%}')} | {d['cic_attack']['windows']:,} | "
                         f"{_f(d['banner']['max_share'], '{:.1%}')} / {_f(d['banner']['alert_fraction'], '{:.0%}')} |")
    for r in report["runs"]:
        if r.get("recovery"):
            rec = r["recovery"]
            lines += ["", f"Recovery: first input batch {_f(rec['first_batch_after_s'], '{:.1f}')} s after the restart, largest gap "
                          f"{_f(rec['max_gap_s'], '{:.1f}')} s, latency back to normal after **{_f(rec['recovered_s'], '{:.1f}')} s** "
                          f"(pre-restart p95 {_f(rec['pre_p95_ms'])} ms)."]
    if report["checks"]:
        lines += ["", "| Check | Value | Pass |", "|---|---|---|"]
        lines += [f"| {k} | {_f(v.get('value'), '{:,.3f}')} | {'✅' if v['pass'] else '❌'} |" for k, v in report["checks"].items()]
    return "\n".join(lines) + "\n"


# ---- CLI -----------------------------------------------------------------------------------------
def _real_runner(cfg, env):
    from . import store as st
    reader = st.StoreReader(st.connect(cfg))
    child_env = {**os.environ, **env, "IDS_ROOT": str(cfg.workspace_root)}
    return Runner(SubprocessCli(child_env), reader, Clock(), cfg.results_dir, cfg.workspace_root)


def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         runner_factory: Optional[Callable] = None) -> int:
    p = argparse.ArgumentParser(prog="python -m ids_monitor.bench", description="M4-F03 benchmark harness (replica).")
    p.add_argument("--experiment", required=True, choices=sorted(EXPERIMENTS))
    p.add_argument("--levels", help="comma-separated subset of levels, e.g. 1,4")
    p.add_argument("--duration", type=int, help="replay seconds per run (→ RUN_DURATION_S, default 600)")
    p.add_argument("--warmup", type=float, default=60.0, help="seconds excluded from steady state (default 60)")
    p.add_argument("--dry-run", action="store_true", help="print the plan and commands; run nothing")
    args = p.parse_args(argv)
    try:
        cfg = load_runtime_config(env=env)
        specs = plan(args.experiment, args.levels.split(",") if args.levels else None)
    except (ConfigError, ValueError) as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    duration = args.duration or cfg.run_duration_s
    if args.dry_run:
        stamp = utc_stamp(int(time.time() * 1000))
        ids = []
        for spec in specs:
            rid = spec.run_id(stamp)
            ids.append(rid)
            for name, cmd in commands(spec, rid, duration, duration + 490, "python").items():
                if cmd:
                    print(f"{rid}  {name:8s} {' '.join(cmd)}")
        print(summary_line("bench", cfg.run_id, experiment=args.experiment, dry_run=True, runs=ids,
                           results_dir=str(cfg.results_dir)))
        return EXIT_OK
    try:
        runner = (runner_factory or _real_runner)(cfg, dict(env or {}))
    except Exception as exc:                           # noqa: BLE001 — store unreachable etc.
        print(f"cannot start the harness: {exc}\nIs the platform running? (`python -m ids_ingest.platform status`)", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    report = runner.run_experiment(args.experiment, specs, duration, args.warmup)
    failed = [r["run_id"] for r in report["runs"] if r["status"] != "ok"]
    print(summary_line("bench", cfg.run_id, status="stopped" if report["interrupted"] else "ok", experiment=args.experiment,
                       runs=[r["run_id"] for r in report["runs"]], failed=failed, results_dir=str(cfg.results_dir),
                       report=str(cfg.results_dir / f"{report['report_stem']}.md"), checks=report["checks"]))
    return EXIT_RUNTIME_ERROR if failed and not report["interrupted"] else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
