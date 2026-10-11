#!/usr/bin/env bash
# Reproduce every generated piece from scratch (after hooks + markov are filled in).
#   bash tools/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "run tools/setup.sh first" >&2; exit 1; }

$PY tools/import_loops.py

run_piece() {
  local piece="$1" race="$2" label="$3"
  $PY -m engine --race "web/data/$race.json" --corpus corpus/corpus.json \
      --config "configs/pieces/$piece.json" --out "output/$piece"
  $PY tools/render_audio.py --mid "output/$piece/$race.mid" --out "output/$piece/$race.ogg"
  $PY tools/validate.py "output/$piece/$race.sync.json"
  $PY tools/install_bundle.py --src "output/$piece" --race "web/data/$race.json" \
      --id "$piece" --name "$label"
}

run_piece comeback-a comeback "Comeback A"
run_piece comeback-a2 comeback "Comeback A2"
run_piece comeback-b comeback "Comeback B"
run_piece comeback-c comeback "Comeback C"
run_piece domination-a domination "Domination A"

echo
$PY tools/stats.py output/[!_]*/*.sync.json | tee output/report-stats.md
echo
$PY tools/memorization.py output/[!_]*/ | tee output/report-memorization.md
echo
$PY tools/compare_pieces.py output/comeback-a output/comeback-a2 | tee output/report-same-config.md
