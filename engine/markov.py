#!/usr/bin/env python3
"""STUDENT-RESPONSIBLE FILE — the Markov chain itself.

The corpus gives you one or more token sequences per (stem, meter). A token
is everything that *starts* at one 16th-note step:

    lead   (pitched): ((pitch, duration_steps), ...)   e.g. ((61, 3), (64, 1))
    drums  (GM kit) : ("kick", "hat", ...)             e.g. ("kick", "open_hat")
    ()              : nothing starts at that step

Sequences for training are built by `engine/corpus.py`
(`training_sequences`): one list per loop, all bars concatenated, steps in
order. The harness in `engine/generate.py` calls:

    MarkovChain(order)                    # once per (stem, meter)
    chain.train(sequences)
    chain.sample(history, temperature, rng)   # once per generated step

Everything else is handled for you. Implement the class below.

Suggested shape
---------------
* `__init__`: store the order n (memory = the n previous tokens).
* `train`: for every position in every training sequence, look at the
  history of the n previous tokens (pad the sequence start with `()`
  tokens) and count which token came next. Normalise the counts into
  transition probabilities. Think about smoothing: a plain count table
  gives probability 0 to unseen transitions.
* `sample`: given exactly `order` history tokens, look up the conditional
  distribution and draw from it. `temperature` < 1 sharpens the
  distribution (more faithful to the corpus), > 1 flattens it (more
  random). Use `rng` (a `random.Random`) for reproducibility. Histories
  never seen in training will happen — pick a fallback (back off to a
  shorter history, or fall back to the overall token distribution).
"""

from __future__ import annotations

import random

# A token as produced by engine/corpus.py. Treat it as opaque.
Token = tuple


class MarkovChain:
    """Order-n Markov chain over step tokens. STUDENT IMPLEMENTATION."""

    def __init__(self, order: int):
        """Create an order-`order` chain (order = number of previous tokens
        used as context)."""
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        # STUDENT: add whatever state you need (e.g. a counts dictionary).

    def train(self, sequences: list[list[Token]]) -> None:
        """Learn transition statistics from token sequences.

        Each sequence is one loop (all bars concatenated, steps in order).
        The same (stem, meter) chain receives every loop of that stem and
        meter found in corpus.json.
        """
        raise NotImplementedError("implement MarkovChain.train() in engine/markov.py")

    def sample(
        self,
        history: list[Token],
        temperature: float = 1.0,
        rng: random.Random | None = None,
    ) -> Token:
        """Draw the next token after `history` (exactly `order` tokens).

        Called once for every 16th-note step of every generated bar. The
        history starts padded with `()` tokens and rolls forward as the bar
        is generated, so it can contain contexts that were never seen in
        training — decide how to fall back.
        """
        raise NotImplementedError("implement MarkovChain.sample() in engine/markov.py")
