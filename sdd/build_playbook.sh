#!/usr/bin/env bash
# Regenerates SDD_PLAYBOOK.md = sdd/playbook_core.md + verbatim copies of the workspace files (Appendix).
# Run from anywhere: bash sdd/build_playbook.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/SDD_PLAYBOOK.md"

FILES=(
  README.md
  PROJECT_PLAN.md
  CONSTITUTION.md
  sdd/WORKFLOW.md
  sdd/templates/spec-template.md
  sdd/templates/plan-template.md
  sdd/templates/tasks-template.md
  sdd/templates/contract-template.md
  sdd/templates/contract-change-request-template.md
  sdd/templates/adr-template.md
  sdd/templates/integration-checklist-template.md
  sdd/templates/module-readme-template.md
  sdd/templates/development-log-template.md
  contracts/README.md
  contracts/C-01_network_event.md
  contracts/C-06_runtime_config_control.md
  contracts/versions.md
  contracts/schemas/event.schema.json
  contracts/fixtures/README.md
  contracts/fixtures/_gen/gen_events_golden.py
  contracts/python/pyproject.toml
  contracts/python/ids_contracts/__init__.py
  contracts/python/ids_contracts/events.py
  contracts/python/ids_contracts/config.py
  contracts/python/tests/test_events.py
  contracts/python/tests/test_config.py
  integration/.env.example
  docs/adr/ADR-003-dataset-variant.md
  docs/adr/ADR-006-event-timestamp.md
  docs/adr/ADR-007-eval-only-fields.md
  docs/adr/ADR-009-version-pins.md
  docs/adr/ADR-011-replay-time-model.md
  integration/README.md
  Module1_Data_Ingestion_Platform/README.md
  Module2_ML_Anomaly_Model/README.md
  Module3_Spark_Stream_Processing/README.md
  Module4_Storage_Dashboard_Benchmarking/README.md
  .gitignore
  sdd/build_playbook.sh
)

{
  cat "$ROOT/sdd/playbook_core.md"
  printf '\n---\n\n# Appendix — Workspace files (create verbatim in PR-01)\n\n'
  printf 'Each block is the **exact content** of the file at the path in its heading, relative to the workspace root.\n'
  printf 'Generated on %s. Note: `sdd/playbook_core.md` is this document minus the Appendix; recreate it by copying §0–§9.\n\n' "$(date +%Y-%m-%d)"
  i=1
  for f in "${FILES[@]}"; do
    case "$f" in
      *.md) lang=markdown ;; *.sh) lang=bash ;; *.py) lang=python ;; *.json) lang=json ;; *.toml) lang=toml ;; *) lang=text ;;
    esac
    printf '## A%d. `%s`\n\n````%s\n' "$i" "$f" "$lang"
    cat "$ROOT/$f"
    printf '````\n\n'
    i=$((i+1))
  done
} > "$OUT"

echo "Wrote $OUT ($(wc -l < "$OUT") lines)"
