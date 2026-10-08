#!/usr/bin/env python3
"""Render a generated .mid to audio with FluidSynth (+ ffmpeg for OGG).

    python3 tools/render_audio.py \\
        --mid output/comeback-a/comeback.mid \\
        --out output/comeback-a/comeback.ogg

Requires `fluidsynth` and a SoundFont (default: soundfonts/GeneralUser-GS.sf2,
fetched by tools/setup.sh). .wav output skips the ffmpeg step.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import mido

ROOT = Path(__file__).resolve().parents[1]
TAIL_S = 2.5  # keep this much after the last MIDI event (reverb tail)


def render(mid: str | Path, out: str | Path, soundfont: str | Path,
           sr: int = 44100) -> Path:
    mid, out, soundfont = Path(mid), Path(out), Path(soundfont)
    fluidsynth = shutil.which("fluidsynth")
    if not fluidsynth:
        raise SystemExit("fluidsynth not found (install it, e.g. `sudo pacman -S fluidsynth`)")
    if not soundfont.exists():
        raise SystemExit(f"soundfont not found: {soundfont} (run tools/setup.sh)")
    out.parent.mkdir(parents=True, exist_ok=True)

    # FluidSynth 2.6 fast-render can pad a long silence tail on multitrack
    # files; cap the output at the real MIDI length + TAIL_S.
    midi_s = mido.MidiFile(str(mid)).length
    cap = midi_s + TAIL_S

    tmpdir = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
    with tempfile.TemporaryDirectory(dir=tmpdir, prefix="render-") as td:
        wav = Path(td) / "render.wav"
        subprocess.run(
            [fluidsynth, "-ni", "-F", str(wav), "-r", str(sr), str(soundfont), str(mid)],
            check=True, capture_output=True,
        )
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            codec = ["-c:a", "pcm_s16le"] if out.suffix.lower() == ".wav" else \
                    ["-c:a", "libvorbis", "-q:a", "5"]
            subprocess.run(
                [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                 "-i", str(wav), "-t", f"{cap:.3f}", *codec, str(out)],
                check=True,
            )
        else:
            if out.suffix.lower() != ".wav":
                raise SystemExit("ffmpeg not found (needed for OGG output; use --out *.wav)")
            shutil.copy(wav, out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mid", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--soundfont", type=Path, default=ROOT / "soundfonts" / "GeneralUser-GS.sf2")
    ap.add_argument("--sr", type=int, default=44100)
    args = ap.parse_args()
    if not args.mid.exists():
        print(f"input not found: {args.mid}", file=sys.stderr)
        return 1
    out = render(args.mid, args.out, args.soundfont, args.sr)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
