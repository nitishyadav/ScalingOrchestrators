# Setup and Run Guide

End-to-end instructions for running the IDS pipeline demo on a new machine (macOS with Apple Silicon).

---

## Prerequisites — Install Once

### System dependencies (via Homebrew)

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install python@3.11
brew install colima
brew install docker
brew install docker-compose
```

### Java 17 (needed for PySpark tests)

```bash
brew install openjdk@17
```

---

## One-time Configuration

### 1. Link docker-compose as a Docker CLI plugin

```bash
mkdir -p ~/.docker/cli-plugins
ln -sfn /opt/homebrew/opt/docker-compose/bin/docker-compose ~/.docker/cli-plugins/docker-compose
```

### 2. Add DOCKER_HOST to your shell profile (permanent)

```bash
echo 'export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock' >> ~/.zshrc
source ~/.zshrc
```

### 3. Copy the env file

```bash
cp integration/.env.example integration/.env
# No edits needed for local demo — defaults work as-is
```

---

## Every Time You Start (after reboot)

### Start Colima VM (Docker runtime)

```bash
colima start --cpu 6 --memory 12
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
```

> If already started: `colima status` to check.
> Restart if needed: `colima stop && colima start --cpu 6 --memory 12`

---

## Project Setup — Once per Clone

```bash
# Clone and enter repo
git clone <repo-url>
cd ScalingOrchestrators

# Create shared venv
python3.11 -m venv .venv
source .venv/bin/activate

# Install all modules
(cd contracts/python && pip install -e .)
(cd Module1_Data_Ingestion_Platform && make install)
(cd Module2_ML_Anomaly_Model && make install)
(cd Module3_Spark_Stream_Processing && make install)
(cd Module4_Storage_Dashboard_Benchmarking && make install)
```

---

## Train the Real Model — Once per Clone

The project ships with a dummy model bundle that scores randomly. Train the real Isolation Forest before running the demo for meaningful results.

> **Requires:** the CIC-IDS2017 CSVs in `runtime/data/raw/TrafficLabelling/` (8 files, ~1.1 GB).
> The dataset is not in the repo — copy it there manually before this step.

```bash
source .venv/bin/activate
cd Module2_ML_Anomaly_Model
python -m ids_model.train --install
cd ..
```

Training uses Monday's benign traffic (~80% of `Monday-WorkingHours.pcap_ISCX.csv`) and picks the anomaly threshold on Tuesday–Thursday. Takes a few minutes. When done, `runtime/bundle/current/manifest.json` will show a version like `0.3.0` instead of `0.0.0-dummy`.

Use `--sample` for a faster test run (smaller dataset slice):
```bash
python -m ids_model.train --install --sample
```

---

## Run the Demo

```bash
source .venv/bin/activate
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock

python integration/demo.py up --rate 500 --executors 1
```

Wait ~3 minutes for all services to become healthy, then open:

| UI | URL |
|---|---|
| Dashboard | http://localhost:8501 |
| Spark UI | http://localhost:8080 |

The demo runs at 500 events/s with 1 Spark executor. This is intentionally conservative to avoid OOM on laptops with 16–24 GB RAM. Raise `--rate` and `--executors` on machines with more headroom.

---

## Stop Everything

```bash
python integration/demo.py down
colima stop   # optional — frees 12 GB RAM
```

---

## Troubleshooting

### "docker CLI not found on PATH"
Colima is not running or `DOCKER_HOST` is not set.
```bash
colima start --cpu 6 --memory 12
export DOCKER_HOST=unix://$HOME/.colima/default/docker.sock
```

### "timeout after 180s waiting for a healthy platform"
Services are slow to start on first pull. Run `demo up` again — containers are already up and will pass the health check immediately on the second attempt.

### Spark job OOM (exit 137) / blank dashboard
The Spark workers ran out of memory. Use `--executors 1` and `--rate 500` (already the recommended defaults above). Check container memory with:
```bash
docker stats --no-stream
```

### "table anomaly_scores does not exist"
The Cassandra schema was not applied. Run:
```bash
cd Module4_Storage_Dashboard_Benchmarking && make run
```

### Dashboard shows 89%+ anomaly rate / drift alert
Expected when using the dummy model bundle (`bundle_version: 0.0.0-dummy`). The mock Isolation Forest scores randomly. Train the real model from Module 2 for meaningful scores:
```bash
cd Module2_ML_Anomaly_Model && python -m ids_model.train --install
```

---

## Revert Colima After Project (optional)

```bash
colima stop
colima delete
colima start   # back to default resource limits
```
