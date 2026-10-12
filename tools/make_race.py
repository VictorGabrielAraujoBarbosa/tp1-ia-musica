#!/usr/bin/env python3
"""Generate the scripted sample race recordings used as game-state input.

Pure stdlib, deterministic per seed.

Races
-----
comeback    You lead early, get overtaken, police spawns at 40 s and closes in,
            the gap oscillates in the hysteresis dead-zone mid-race, then you
            fight back and win.
domination  You lead from start to finish, no police. The control case: the
            music should stay even-metered and calm until the finale.

Usage
-----
    python3 tools/make_race.py                 # writes both races
    python3 tools/make_race.py --out-dir races

Output schema: see docs/contracts.md (gm-race/1).
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "races"

SAMPLE_HZ = 1

# ---------------------------------------------------------------------------
# Position keyframes. Each entry is (t_seconds, progress_0_to_1). Positions
# are piecewise-linearly interpolated, lightly noised, then forced monotonic.
# GAP keyframes are tracked as (you - opp), so opp = you - gap.
# ---------------------------------------------------------------------------

COMEBACK_YOU = [
    (0, 0.0), (20, 0.16), (40, 0.30), (60, 0.43), (80, 0.55),
    (100, 0.67), (120, 0.79), (140, 0.90), (155, 0.965), (165, 0.99),
]
COMEBACK_GAP = [
    (0, 0.0), (8, 0.025), (15, 0.02), (22, -0.01), (28, -0.06),
    (45, -0.10), (55, -0.075), (65, -0.035), (72, 0.005), (78, -0.02),
    (85, -0.045), (95, -0.02), (105, 0.03), (120, 0.06), (140, 0.075),
    (165, 0.075),
]
COMEBACK_DIST = [  # police distance behind you, after spawn at t=40
    (40, 0.26), (60, 0.18), (75, 0.10), (85, 0.065), (95, 0.055),
    (110, 0.07), (130, 0.09), (150, 0.08), (165, 0.06),
]

DOMINATION_YOU = [
    (0, 0.0), (20, 0.17), (45, 0.36), (75, 0.56),
    (105, 0.74), (130, 0.87), (150, 0.98),
]
DOMINATION_GAP = [
    (0, 0.015), (25, 0.08), (55, 0.15), (85, 0.22),
    (115, 0.26), (135, 0.25), (150, 0.24),
]


def _interp(keyframes: list[tuple[float, float]], t: float) -> float:
    """Piecewise-linear interpolation, clamped at both ends."""
    if t <= keyframes[0][0]:
        return keyframes[0][1]
    for (t0, v0), (t1, v1) in zip(keyframes, keyframes[1:]):
        if t <= t1:
            span = t1 - t0
            a = (t - t0) / span if span > 0 else 0.0
            return v0 + (v1 - v0) * a
    return keyframes[-1][1]


def _smooth_noise(rng: random.Random, n: int, amp: float, window: int = 4) -> list[float]:
    raw = [rng.uniform(-amp, amp) for _ in range(n)]
    out = []
    for i in range(n):
        lo, hi = max(0, i - window), min(n, i + window + 1)
        out.append(sum(raw[lo:hi]) / (hi - lo))
    return out


def _track(
    rng: random.Random,
    duration: int,
    keyframes: list[tuple[float, float]],
    offset_keyframes: list[tuple[float, float]] | None = None,
    noise_amp: float = 0.004,
) -> list[float]:
    n = duration + 1
    values = []
    for t in range(n):
        v = _interp(keyframes, t)
        if offset_keyframes is not None:
            v -= _interp(offset_keyframes, t)
        values.append(v)
    if noise_amp:
        noise = _smooth_noise(rng, n, noise_amp)
        values = [v + e for v, e in zip(values, noise)]
    out, prev = [], 0.0
    for v in values:
        v = min(1.0, max(prev, v))
        out.append(round(v, 4))
        prev = v
    return out


def build_race(
    name: str,
    title: str,
    description: str,
    duration: int,
    you_keyframes: list[tuple[float, float]],
    gap_keyframes: list[tuple[float, float]],
    dist_keyframes: list[tuple[float, float]] | None = None,
    seed: int = 1,
) -> dict:
    rng = random.Random(seed)
    you = _track(rng, duration, you_keyframes, noise_amp=0.004)
    opp = _track(rng, duration, you_keyframes, offset_keyframes=gap_keyframes, noise_amp=0.003)

    if dist_keyframes:
        spawn_t = int(dist_keyframes[0][0])
        police = [
            None if t < spawn_t else round(max(0.0, you[t] - _interp(dist_keyframes, t)), 4)
            for t in range(duration + 1)
        ]
    else:
        police = [None] * (duration + 1)

    samples = [
        {"t": t, "you": you[t], "opp": opp[t], "police": police[t]}
        for t in range(duration + 1)
    ]

    events = []
    spawn = next((s["t"] for s in samples if s["police"] is not None), None)
    if spawn is not None:
        events.append({"t": spawn, "type": "police_spawn"})
    final = next((s["t"] for s in samples if max(s["you"], s["opp"]) >= 0.9), None)
    if final is not None:
        events.append({"t": final, "type": "final_lap"})
    events.append({"t": duration, "type": "finish"})

    return {
        "format": "gm-race/1",
        "name": name,
        "title": title,
        "description": description,
        "sample_hz": SAMPLE_HZ,
        "duration_s": duration,
        "events": events,
        "samples": samples,
    }


def summarise(race: dict) -> str:
    samples = race["samples"]
    gaps = [s["you"] - s["opp"] for s in samples]
    behind = sum(1 for g in gaps if g < -0.03) / len(gaps)
    spawn = next((e["t"] for e in race["events"] if e["type"] == "police_spawn"), None)
    final = next((e["t"] for e in race["events"] if e["type"] == "final_lap"), None)
    return (
        f"{race['name']:<11} {race['duration_s']}s  "
        f"gap [{min(gaps):+.3f}, {max(gaps):+.3f}]  "
        f"behind(<-.03) {behind:.0%}  "
        f"police_spawn {'t=' + str(spawn) if spawn is not None else 'none'}  "
        f"final_lap t={final}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=1, help="base seed (per-race offsets)")
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    races = [
        build_race(
            "comeback", "Comeback",
            "Early lead, overtaken, police chase, fight back and win.",
            165, COMEBACK_YOU, COMEBACK_GAP, COMEBACK_DIST, seed=args.seed,
        ),
        build_race(
            "domination", "Domination",
            "Lights-to-flag lead, no police. Control case for reactivity.",
            150, DOMINATION_YOU, DOMINATION_GAP, None, seed=args.seed + 1,
        ),
    ]

    for race in races:
        path = args.out_dir / f"{race['name']}.json"
        path.write_text(json.dumps(race, indent=1) + "\n")
        print(f"wrote {path.relative_to(ROOT)}")
        print("  " + summarise(race))


if __name__ == "__main__":
    main()
