#!/usr/bin/env python3
"""Write generated bars to a Standard MIDI File.

Boilerplate: one MIDI track per stem, drums forced to channel 10, program
changes from the engine config, tempo = piece BPM, time signatures at bar
boundaries where the meter changes.

Input shape:

    bars = [
        {"meter": "even", "tokens": {"drums": [...], "lead": [...]}},
        {"meter": "odd",  "tokens": {...}},
        ...
    ]

`tokens[stem]` is a list of Python tokens (see engine/corpus.py), one per
16th-note step of that meter.
"""

from __future__ import annotations

from pathlib import Path

import mido

from .corpus import METERS, voice_pitch

TICKS_PER_BEAT = 480
TICKS_PER_STEP = TICKS_PER_BEAT // 4  # 16th note


def _track_from_events(events: list[tuple[int, int, mido.Message]]) -> mido.MidiTrack:
    """(abs_tick, priority, message) -> MidiTrack with delta times.

    Lower priority sorts first at the same tick (use 0 for note-offs /
    meta, 1+ for note-ons) so retriggers behave.
    """
    track = mido.MidiTrack()
    last = 0
    for tick, _, msg in sorted(events, key=lambda e: (e[0], e[1])):
        msg.time = max(0, tick - last)
        track.append(msg)
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def write_midi(path: str | Path, bars: list[dict], bpm: float, stems_cfg: dict) -> None:
    """Render `bars` to a .mid file at `path`."""
    mid = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    step_ticks = TICKS_PER_STEP

    # --- conductor track: tempo + time signatures -------------------------
    meta: list[tuple[int, int, mido.Message]] = [
        (0, 0, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm))),
        (0, 0, mido.MetaMessage("track_name", name="conductor")),
    ]
    bar_start = 0
    prev_sig = None
    for bar in bars:
        spec = METERS[bar["meter"]]
        if spec["sig"] != prev_sig:
            meta.append((bar_start, 0, mido.MetaMessage(
                "time_signature",
                numerator=spec["sig"][0],
                denominator=spec["sig"][1],
            )))
            prev_sig = spec["sig"]
        bar_start += spec["steps_per_bar"] * step_ticks
    total_ticks = bar_start
    mid.tracks.append(_track_from_events(meta))

    # --- one track per stem ----------------------------------------------
    for stem, spec in stems_cfg.items():
        drum = bool(spec.get("drum", False))
        channel = int(spec.get("channel", 9 if drum else 0))
        events: list[tuple[int, int, mido.Message]] = []
        track_name = mido.MetaMessage("track_name", name=stem)
        events.append((0, 0, track_name))
        if not drum and "program" in spec:
            events.append((0, 0, mido.Message(
                "program_change", channel=channel, program=int(spec["program"]),
            )))

        bar_start = 0
        for bar in bars:
            nsteps = METERS[bar["meter"]]["steps_per_bar"]
            toks = bar["tokens"].get(stem, [])
            for s, tok in enumerate(toks[:nsteps]):
                start = bar_start + s * step_ticks
                if drum:
                    for name in tok:
                        pitch = voice_pitch(name)
                        dur = int(spec.get("drum_duration_steps", 0.5) * step_ticks)
                        end = min(start + max(1, dur), total_ticks)
                        events.append((start, 2, mido.Message(
                            "note_on", channel=channel, note=pitch,
                            velocity=int(spec.get("velocity", 100)))))
                        events.append((end, 0, mido.Message(
                            "note_off", channel=channel, note=pitch, velocity=0)))
                else:
                    for pitch, dur_steps in tok:
                        end = min(start + max(1, int(dur_steps)) * step_ticks,
                                  total_ticks)
                        events.append((start, 2, mido.Message(
                            "note_on", channel=channel, note=int(pitch),
                            velocity=int(spec.get("velocity", 80)))))
                        events.append((end, 0, mido.Message(
                            "note_off", channel=channel, note=int(pitch), velocity=0)))
            bar_start += nsteps * step_ticks

        mid.tracks.append(_track_from_events(events))

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mid.save(str(path))


def total_seconds(bars: list[dict], bpm: float) -> float:
    """Music duration of a bar list, in seconds."""
    quarter = 60.0 / bpm
    total = 0.0
    for bar in bars:
        spec = METERS[bar["meter"]]
        quarters = spec["steps_per_bar"] / 4.0
        total += quarters * quarter
    return total
