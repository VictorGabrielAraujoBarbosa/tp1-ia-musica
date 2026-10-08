#!/usr/bin/env python3
"""Corpus I/O: `gm-corpus/1` files produced by tools/import_loops.py.

The corpus stores, per loop, a token per 16th-note step and per stem:

    lead  : [[pitch, duration_steps], ...]   notes starting at that step
    drums : ["kick", "hat", ...]             GM voices starting at that step
    []    : nothing starts at that step

Here they are converted back to hashable Python tuples for the Markov chains.
"""

from __future__ import annotations

import json
from pathlib import Path

# Meter table. `even` = 4/4 (16 sixteenths/bar), `odd` = 7/8 (14 sixteenths/bar).
METERS = {
    "even": {"sig": [4, 4], "steps_per_bar": 16},
    "odd": {"sig": [7, 8], "steps_per_bar": 14},
}

# General MIDI percussion note -> voice name (channel 10 mapping).
GM_VOICES = {
    35: "kick", 36: "kick2", 37: "rim", 38: "snare", 39: "clap",
    40: "snare2", 41: "tom_low", 42: "hat", 43: "tom_low2",
    44: "hat_pedal", 45: "tom_mid", 46: "open_hat", 47: "tom_mid2",
    48: "tom_high", 49: "crash", 50: "tom_high2", 51: "ride",
    52: "china", 53: "ride_bell", 54: "tambourine", 55: "splash",
    56: "cowbell", 57: "crash2", 59: "ride2",
}
VOICE_PITCH = {name: pitch for pitch, name in GM_VOICES.items()}


def voice_pitch(name: str) -> int:
    """Voice name -> GM note. Unknown voices may be written as `gm<number>`
    by the importer so nothing is lost."""
    if name in VOICE_PITCH:
        return VOICE_PITCH[name]
    if name.startswith("gm") and name[2:].isdigit():
        return int(name[2:])
    raise KeyError(f"unknown drum voice {name!r}")


def load(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text())
    if data.get("format") != "gm-corpus/1":
        raise ValueError(f"not a gm-corpus/1 file: format={data.get('format')!r}")
    return data


def to_token(kind: str, raw: list) -> tuple:
    """JSON token -> Python tuple. `kind` is "drums" or "pitched"."""
    if kind == "drums":
        return tuple(raw)
    return tuple((int(p), int(d)) for p, d in raw)


def training_sequences(corpus: dict, meter: str, stem: str) -> list[list[tuple]]:
    """All training sequences for one (meter, stem) as Python token lists.

    One sequence per loop: every bar concatenated, steps in order.
    """
    kind = "drums" if stem == "drums" else "pitched"
    sequences = []
    for loop in corpus["loops"]:
        if loop["meter"] != meter:
            continue
        steps: list[tuple] = []
        for bar in loop["bars"]:
            if stem not in bar:
                break  # this loop has no material for this stem
            steps.extend(to_token(kind, tok) for tok in bar[stem])
        while steps and not steps[-1]:  # a stem may be shorter than the file
            steps.pop()
        if steps:
            sequences.append(steps)
    return sequences
