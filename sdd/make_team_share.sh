#!/usr/bin/env bash
# Regenerates ../TEAM_SHARE/ (outside the repo) with the CURRENT playbook, proposal, contracts zip and message.
# Run when you are ready to send:  bash sdd/make_team_share.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/../TEAM_SHARE"
STAMP="$(date +%Y-%m-%d)"
bash "$ROOT/sdd/build_playbook.sh" >/dev/null
rm -rf "$OUT" && mkdir -p "$OUT"
find "$ROOT/contracts" -name __pycache__ -type d -prune -exec rm -rf {} +
(cd "$ROOT" && zip -qr "$OUT/contracts_$STAMP.zip" contracts -x '*/__pycache__/*' '*.egg-info/*' '*/.pytest_cache/*' '*/.DS_Store')
cp "$ROOT/SDD_PLAYBOOK.md" "$OUT/"
cp "$ROOT/../1_PHASE_1_IDEA_GEN/des_project_proposal 3.html" "$OUT/"
sed "s/contracts_[0-9-]*\.zip/contracts_$STAMP.zip/g" "$ROOT/sdd/team_message.md" > "$OUT/MESSAGE_TO_TEAM.md"
echo "Team share ready in $OUT:"; ls -1 "$OUT"
