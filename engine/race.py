#!/usr/bin/env python3
"""Load `gm-race/1` recordings and sample them at a given time.

This is boilerplate: it only turns the JSON recording into a `sample(t)`
function. What you *do* with the sampled variables is up to you
(see `engine/hooks.py`).
"""

from __future__ import annotations

import json
from pathlib import Path


def clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class RaceRecording:
    """A race recording as defined in docs/contracts.md (gm-race/1).

    Usage:

        race = RaceRecording.load("web/data/comeback.json")
        state = race.sample(12.5)     # {"t": 12.5, "you": ..., "opp": ..., "police": ...}
    """

    def __init__(self, data: dict):
        if data.get("format") != "gm-race/1":
            raise ValueError(f"not a gm-race/1 file: format={data.get('format')!r}")
        self.data = data
        self.name: str = data["name"]
        self.title: str = data.get("title", data["name"])
        self.samples: list[dict] = data["samples"]

    @classmethod
    def load(cls, path: str | Path) -> RaceRecording:
        return cls(json.loads(Path(path).read_text()))

    @property
    def duration_s(self) -> float:
        return float(self.data["duration_s"])

    def event(self, type_: str) -> dict | None:
        """First event of a given type, or None."""
        return next((e for e in self.data.get("events", []) if e["type"] == type_), None)

    def sample(self, t: float) -> dict:
        """Race variables at time `t` seconds, linearly interpolated.

        Returns a fresh dict:

            {"t": float,
             "you": float,          # progress in [0, 1]
             "opp": float,          # opponent progress
             "police": float | None}  # None until the police spawns

        Derived quantities (`gap`, `police_dist`, `phase`) are intentionally
        NOT computed here — derive what you need inside hooks.conditions().
        """
        x = clamp(t, 0.0, len(self.samples) - 1)
        i = int(x)
        f = x - i
        j = min(i + 1, len(self.samples) - 1)
        a, b = self.samples[i], self.samples[j]

        def merge(key: str) -> float | None:
            va, vb = a[key], b[key]
            if va is None and vb is None:
                return None
            if va is None:
                return vb
            if vb is None:
                return va
            return lerp(va, vb, f)

        return {
            "t": float(t),
            "you": merge("you"),
            "opp": merge("opp"),
            "police": merge("police"),
        }
