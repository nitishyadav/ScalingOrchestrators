# M1-ADR-003: Docker engine — Colima or Docker Desktop

| Field | Value |
|---|---|
| Status | **Accepted** (owner, 2026-10-21) |
| Deciders | Aswin S. (M1) |
| Affects | M1-F01, `contracts/versions.md` (container engine row), team setup |

## Context
The platform needs a Docker-compatible engine with Compose v2. Docker Desktop needs an admin password and a GUI first run.
Colima is a free CLI VM (Lima, Apple Virtualization.framework) exposing the same Docker API.

## Decision
Both engines are supported. The compose file and commands are identical, and nothing may depend on Desktop-only features.
The M1 owner uses **Colima 0.10.3**: `colima start --cpu 6 --memory 10 --disk 60 --vm-type vz`.
Desktop users allocate 6 CPUs and 10 GB in Settings → Resources.

## Consequences
- `ids_ingest.platform` talks only to the `docker` CLI and checks engine CPU and memory via `docker info`.
- Colima users must register the Compose plugin (`cliPluginsExtraDirs` in `~/.docker/config.json`) and run `colima stop` to free RAM.
