#!/usr/bin/env python3
"""Import hand-crafted LMMS loops into a `gm-corpus/1` file.

Scans `corpus/<meter>/*.mid`, maps LMMS tracks to stems by track name,
quantizes notes to the 16th-note grid and writes `corpus/corpus.json`.

    corpus/even/loop-01.mid   ->  meter "even" (4/4, 16 steps/bar)
    corpus/odd/loop-01.mid    ->  meter "odd"  (7/8, 14 steps/bar)

Track -> stem mapping comes from `configs/base.json` (`track_stems`), e.g.
"TripleOscillator" -> lead, "GeneralUser-GS" -> drums. Unmapped or empty
tracks are skipped.

Usage:
    python3 tools/import_loops.py
    python3 tools/import_loops.py --corpus-dir corpus --out corpus/corpus.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mido  # noqa: E402

from engine.corpus import GM_VOICES, METERS  # noqa: E402


def track_notes(track: mido.MidiTrack) -> tuple[str | None, list[tuple[int, int, int]]]:
    """(track name, [(onset_tick, pitch, dur_ticks), ...]) for one MIDI track."""
    name = next((m.name for m in track if m.type == "track_name"), None)
    notes: list[tuple[int, int, int]] = []
    open_notes: dict[tuple[int, int], list[int]] = {}
    t = 0
    for msg in track:
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_notes.setdefault((msg.channel, msg.note), []).append(t)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            starts = open_notes.get((msg.channel, msg.note))
            if starts:
                start = starts.pop(0)
                notes.append((start, msg.note, t - start))
    for (_, pitch), starts in open_notes.items():  # still sounding at track end
        for start in starts:
            notes.append((start, pitch, max(32, t - start)))
    return name, notes


def import_file(path: Path, meter: str, step_ticks: int, track_stems: dict[str, str],
                max_dev: int = 8) -> dict:
    mid = mido.MidiFile(str(path))
    if mid.ticks_per_beat % 4:
        raise SystemExit(f"{path}: ticks_per_beat={mid.ticks_per_beat} is not divisible by 4")

    stems: dict[str, dict[int, dict]] = {}  # stem -> step -> {pitch: dur_steps}
    drum_steps: dict[str, dict[int, set]] = {}  # stem -> step -> {voice}
    worst_dev = 0
    warnings: list[str] = []

    for track in mid.tracks:
        name, notes = track_notes(track)
        if name not in track_stems:
            if name is not None and notes:
                warnings.append(f"track {name!r} has notes but no stem mapping; skipped")
            continue
        stem = track_stems[name]
        drum = stem == "drums"
        bucket = {} if drum else stems.setdefault(stem, {})
        dset = drum_steps.setdefault(stem, {}) if drum else None
        for onset, pitch, dur in notes:
            step = round(onset / step_ticks)
            worst_dev = max(worst_dev, abs(onset - step * step_ticks))
            dur_steps = max(1, round(dur / step_ticks))
            if drum:
                voice = GM_VOICES.get(pitch, f"gm{pitch}")
                dset.setdefault(step, set()).add(voice)
            else:
                prev = bucket.setdefault(step, {}).get(pitch)
                bucket[step][pitch] = max(dur_steps, prev or 0)

    if worst_dev > max_dev:
        warnings.append(f"max onset deviation {worst_dev} ticks from the 16th grid")

    steps_per_bar = METERS[meter]["steps_per_bar"]
    # loop length in steps: last event (onset + duration) decides the bars
    last_step = 0
    for bucket in stems.values():
        for step, pitches in bucket.items():
            last_step = max(last_step, step + max(pitches.values(), default=1))
    for dset in drum_steps.values():
        for step in dset:
            last_step = max(last_step, step + 1)
    n_bars = max(1, -(-last_step // steps_per_bar))  # ceil

    bars = []
    for b in range(n_bars):
        bar: dict[str, list] = {}
        lo, hi = b * steps_per_bar, (b + 1) * steps_per_bar
        for stem, bucket in stems.items():
            bar[stem] = [
                [[p, bucket[step][p]] for p in sorted(bucket[step])] if step in bucket else []
                for step in range(lo, hi)
            ]
        for stem, dset in drum_steps.items():
            bar[stem] = [sorted(dset.get(step, set())) for step in range(lo, hi)]
        bars.append(bar)

    input_notes = (
        sum(len(pitches) for bucket in stems.values() for pitches in bucket.values())
        + sum(len(voices) for dset in drum_steps.values() for voices in dset.values())
    )
    return {
        "id": f"{meter}/{path.stem}",
        "meter": meter,
        "bars": bars,
        "notes": input_notes,
        "worst_dev_ticks": worst_dev,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-dir", type=Path, default=ROOT / "corpus")
    ap.add_argument("--out", type=Path, default=ROOT / "corpus" / "corpus.json")
    ap.add_argument("--config", type=Path, default=ROOT / "configs" / "base.json",
                    help="base config with the track_stems mapping")
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text())
    track_stems = cfg.get("track_stems", {"TripleOscillator": "lead", "GeneralUser-GS": "drums"})

    loops = []
    bpm = None
    ppq = None
    for meter in ("even", "odd"):
        folder = args.corpus_dir / meter
        for path in sorted(folder.glob("*.mid")):
            mid = mido.MidiFile(str(path))
            ppq = ppq or mid.ticks_per_beat
            if mid.ticks_per_beat != ppq:
                raise SystemExit(f"{path}: mixed ticks_per_beat ({mid.ticks_per_beat} != {ppq})")
            for track in mid.tracks:
                for msg in track:
                    if msg.type == "set_tempo":
                        bpm = bpm or round(60_000_000 / msg.tempo)
                        break
            loop = import_file(path, meter, ppq // 4, track_stems)
            loops.append(loop)
            stems = sorted({k for bar in loop["bars"] for k in bar})
            print(f"{loop['id']:<16} {loop['meter']:<4} {len(loop['bars'])} bars "
                  f"stems={','.join(stems)} notes={loop['notes']} "
                  f"worst_dev={loop['worst_dev_ticks']}t")

    corpus = {
        "format": "gm-corpus/1",
        "bpm": bpm or 140,
        "ticks_per_beat": ppq or 480,
        "step_ticks": (ppq or 480) // 4,
        "stems": sorted({k for loop in loops for bar in loop["bars"] for k in bar}),
        "meters": {m: {"sig": METERS[m]["sig"], "steps_per_bar": METERS[m]["steps_per_bar"]}
                   for m in ("even", "odd")},
        "loops": loops,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(corpus, indent=1) + "\n")
    print(f"wrote {args.out.relative_to(ROOT)}  ({len(loops)} loops, bpm {corpus['bpm']})")


if __name__ == "__main__":
    main()
