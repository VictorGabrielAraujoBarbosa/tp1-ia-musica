#!/usr/bin/env python3
"""SMOKE-TEST FIXTURES — NOT part of the music method.

These stand in for the student code so the harness (file I/O, bar timing,
MIDI writing) can be tested before `engine/hooks.py` and `engine/markov.py`
are filled in. `PatternChain` deterministically cycles corpus tokens; it
computes no probabilities and is not a Markov model.
"""

from __future__ import annotations


def conditions(state: dict) -> dict[str, bool]:
    police_dist = None if state["police"] is None else state["you"] - state["police"]
    return {
        "behind": state["you"] < state["opp"],
        "police_near": police_dist is not None and police_dist < 0.15,
        "final_lap": max(state["you"], state["opp"]) > 0.9,
    }


def bar_context(conds: dict[str, bool], bar_index: int, prev: dict | None) -> dict:
    # Fixture: alternates meters every 4 bars on purpose, so both step grids
    # get exercised regardless of the race state.
    meter = "odd" if (bar_index // 4) % 2 else "even"
    return {
        "meter": meter,
        "stems": {"drums": True, "lead": True},
        "tension": 0.5,
        "temperature": 1.0,
    }


class PatternChain:
    """Test double: replays a corpus sequence, ignoring `history` entirely."""

    def __init__(self, stem: str, meter: str, order: int):
        self.stem = stem
        self.meter = meter
        self.order = order
        self.tokens: list[tuple] = []
        self._i = 0

    def train(self, sequences: list[list[tuple]]) -> None:
        self.tokens = [tok for seq in sequences for tok in seq]

    def sample(self, history, temperature: float = 1.0, rng=None) -> tuple:
        if not self.tokens:
            return ()
        tok = self.tokens[self._i % len(self.tokens)]
        self._i += 1
        return tok


def chain_factory(stem: str, meter: str, order: int) -> PatternChain:
    return PatternChain(stem, meter, order)
