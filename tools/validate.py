#!/usr/bin/env python3
"""Validate gm-race/1, gm-corpus/1 and gm-sync/1 files.

    python3 tools/validate.py races/comeback.json corpus/corpus.json output/*/comeback.sync.json

Exits non-zero if any file has errors. Checks the invariants listed in
docs/contracts.md (monotonic time, bar duration from meter + bpm, ranges,
token grid sizes, ...).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LAYERS = ("drums", "bass", "pad", "lead")
STATE_KEYS = ("you", "opp", "police", "gap", "police_dist", "phase")
METER_STEPS = {(4, 4): 16, (7, 8): 14}


def validate_race(d: dict) -> list[str]:
    e: list[str] = []
    if d.get("format") != "gm-race/1":
        return [f"format is {d.get('format')!r}, expected 'gm-race/1'"]
    duration = d.get("duration_s")
    samples = d.get("samples")
    if not isinstance(duration, int) or duration < 1:
        e.append(f"duration_s must be a positive int, got {duration!r}")
    if not isinstance(samples, list) or len(samples) != (duration or 0) + 1:
        e.append(f"samples length {len(samples or [])} != duration_s + 1 ({duration})")
        return e
    prev = {"you": 0.0, "opp": 0.0, "police": None}
    for i, s in enumerate(samples):
        if s.get("t") != i:
            e.append(f"sample {i}: t={s.get('t')!r}, expected {i}")
        for key in ("you", "opp"):
            v = s.get(key)
            if not isinstance(v, (int, float)) or not 0 <= v <= 1:
                e.append(f"sample {i}: {key}={v!r} not in [0, 1]")
            elif v < prev[key] - 1e-9:
                e.append(f"sample {i}: {key} decreased ({prev[key]} -> {v})")
            prev[key] = v
        police = s.get("police")
        if police is None:
            if prev["police"] is not None:
                e.append(f"sample {i}: police disappeared")
        else:
            if not 0 <= police <= 1:
                e.append(f"sample {i}: police={police!r} not in [0, 1]")
            if prev["police"] is not None and police < prev["police"] - 1e-9:
                e.append(f"sample {i}: police decreased ({prev['police']} -> {police})")
            prev["police"] = police
    types = {ev.get("type") for ev in d.get("events", [])}
    if types - {"police_spawn", "final_lap", "finish"}:
        e.append(f"unknown event types: {sorted(types - {'police_spawn', 'final_lap', 'finish'})}")
    if "finish" not in types:
        e.append("no finish event")
    return e


def validate_sync(d: dict) -> list[str]:
    e: list[str] = []
    if d.get("format") != "gm-sync/1":
        return [f"format is {d.get('format')!r}, expected 'gm-sync/1'"]
    bpm = d.get("bpm")
    if not isinstance(bpm, (int, float)) or bpm <= 0:
        e.append(f"bpm must be positive, got {bpm!r}")
        return e
    bars = d.get("bars") or []
    if not bars:
        return ["no bars"]
    quarter = 60.0 / bpm
    for k, bar in enumerate(bars):
        where = f"bar {k}"
        if bar.get("i") != k:
            e.append(f"{where}: i={bar.get('i')!r}")
        if k == 0 and bar.get("t_music") != 0:
            e.append(f"{where}: t_music={bar.get('t_music')} at first bar")
        meter = tuple(bar.get("meter", ()))
        if meter not in METER_STEPS:
            e.append(f"{where}: meter={bar.get('meter')!r}")
            continue
        if not 0 <= float(bar.get("tension", -1)) <= 1:
            e.append(f"{where}: tension={bar.get('tension')!r} outside [0, 1]")
        layers = bar.get("layers") or {}
        if set(layers) != set(LAYERS):
            e.append(f"{where}: layers keys {sorted(layers)} != {sorted(LAYERS)}")
        if any(not isinstance(v, bool) for v in layers.values()):
            e.append(f"{where}: layers values must be booleans")
        state = bar.get("state") or {}
        if set(state) != set(STATE_KEYS):
            e.append(f"{where}: state keys {sorted(state)} != {sorted(STATE_KEYS)}")
        for key in ("you", "opp"):
            v = state.get(key)
            if v is not None and not 0 <= v <= 1:
                e.append(f"{where}: state.{key}={v!r} outside [0, 1]")
        if k:
            prev = bars[k - 1]
            if not all(isinstance(b.get(key), (int, float))
                       for b in (bar, prev) for key in ("t_music", "t_race")):
                e.append(f"{where}: missing/invalid t_music or t_race")
                continue
            dt_music = bar["t_music"] - prev["t_music"]
            dt_race = bar["t_race"] - prev["t_race"]
            expected = METER_STEPS[tuple(prev["meter"])] / 4.0 * quarter
            if dt_music <= 0 or dt_race <= 0:
                e.append(f"{where}: time did not advance")
            if abs(dt_music - expected) > 1e-3 or abs(dt_race - expected) > 1e-3:
                e.append(f"{where}: dt={dt_music:.4f}/{dt_race:.4f}, expected {expected:.4f}")
    return e


def validate_corpus(d: dict) -> list[str]:
    e: list[str] = []
    if d.get("format") != "gm-corpus/1":
        return [f"format is {d.get('format')!r}, expected 'gm-corpus/1'"]
    if not d.get("loops"):
        e.append("no loops")
    for loop in d.get("loops", []):
        where = f"loop {loop.get('id')!r}"
        meter = loop.get("meter")
        if meter not in ("even", "odd"):
            e.append(f"{where}: meter={meter!r}")
            continue
        steps_per_bar = 16 if meter == "even" else 14
        if not loop.get("bars"):
            e.append(f"{where}: no bars")
        for b, bar in enumerate(loop.get("bars", [])):
            if not isinstance(bar, dict) or not bar:
                e.append(f"{where} bar {b}: empty")
                continue
            for stem, toks in bar.items():
                if len(toks) != steps_per_bar:
                    e.append(f"{where} bar {b}: {stem} has {len(toks)} steps, "
                             f"expected {steps_per_bar}")
                    continue
                for s, tok in enumerate(toks):
                    if stem == "drums":
                        if not all(isinstance(v, str) for v in tok):
                            e.append(f"{where} bar {b} step {s}: bad drum token {tok!r}")
                    else:
                        for pair in tok:
                            if (not isinstance(pair, list) or len(pair) != 2
                                    or not isinstance(pair[0], int)
                                    or not isinstance(pair[1], int) or pair[1] < 1):
                                e.append(f"{where} bar {b} step {s}: bad token {pair!r}")
    return e


VALIDATORS = {"gm-race/1": validate_race, "gm-sync/1": validate_sync, "gm-corpus/1": validate_corpus}


def validate_file(path: str | Path) -> tuple[str, list[str]]:
    data = json.loads(Path(path).read_text())
    fmt = data.get("format", "?")
    validator = VALIDATORS.get(fmt)
    if validator is None:
        return fmt, [f"unknown format {fmt!r}"]
    return fmt, validator(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args()
    failed = False
    for path in args.files:
        fmt, errors = validate_file(path)
        status = "ok" if not errors else "FAIL"
        print(f"{status:4} {path}  ({fmt})")
        for err in errors:
            print(f"     - {err}")
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
