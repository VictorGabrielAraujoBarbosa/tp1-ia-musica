#!/usr/bin/env bash
# One-time environment setup (idempotent).
#   bash tools/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

need() {
  command -v "$1" >/dev/null || { echo "missing command: $1 — $2" >&2; exit 1; }
}

need python3 "install Python 3"
need ffmpeg "install ffmpeg (Arch: sudo pacman -S ffmpeg)"
if ! command -v fluidsynth >/dev/null; then
  echo "warning: fluidsynth not found — needed for audio rendering (Arch: sudo pacman -S fluidsynth)"
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --quiet -r requirements.txt
echo "python env ready (.venv)"

if [[ ! -f soundfonts/GeneralUser-GS.sf2 ]]; then
  mkdir -p soundfonts
  echo "downloading GeneralUser GS soundfont (~32 MiB)..."
  curl -sL -o soundfonts/GeneralUser-GS.sf2 \
    "https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2"
fi
echo "soundfont ready: soundfonts/GeneralUser-GS.sf2"

echo
echo "setup OK. Next:"
echo "  source .venv/bin/activate    # or use .venv/bin/python directly"
echo "  python3 tools/import_loops.py"
echo "  python3 tools/smoke_test.py"
echo "  bash tools/run_all.sh         # regenerate every piece + reports"
