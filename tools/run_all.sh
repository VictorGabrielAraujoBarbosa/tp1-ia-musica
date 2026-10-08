#!/usr/bin/env bash
# Reproduce every generated piece from scratch (after hooks + markov are filled in).
#   bash tools/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[[ -x "$PY" ]] || { echo "run tools/setup.sh first" >&2; exit 1; }

$PY tools/import_loops.py

run_piece() {
  local piece="$1" race="$2"
  $PY -m engine --race "web/data/$race.json" --corpus corpus/corpus.json \
      --config "configs/pieces/$piece.json" --out "output/$piece"
  $PY tools/render_audio.py --mid "output/$piece/$race.mid" --out "output/$piece/$race.ogg"
  $PY tools/validate.py "output/$piece/$race.sync.json"
}

run_piece comeback-a comeback
run_piece comeback-b comeback
run_piece domination-a domination

echo
$PY tools/stats.py output/*/*.sync.json
