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

import math
import random
from collections import Counter, defaultdict

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

        # armazenamento das transições. o dicionário guarda como chave a sequência de tamanho [order] de notas como chave, e o valor é um counter de tokens
        self.models: dict[int, dict[tuple[Token, ...], Counter[Token]]] = {
            k: defaultdict(Counter) for k in range(1, order + 1)
        }
        # Distribuição global (ordem 0 / unigrama) para fallback absoluto
        self.unigram_counts: Counter[Token] = Counter()

    def train(self, sequences: list[list[Token]]) -> None:
        """Learn transition statistics from token sequences.

        Each sequence is one loop (all bars concatenated, steps in order).
        The same (stem, meter) chain receives every loop of that stem and
        meter found in corpus.json.
        """
        for sequence in sequences:
            if not sequence:
                continue

            # Preenche o início da sequência com tokens vazios (Token()) para sempre ter sequências de ordem n
            padded_seq = [Token()] * self.order + sequence

            # Contar transições
            for i in range(self.order, len(padded_seq)):
                next_token = padded_seq[i] # para todo token (esse token vai ser o "próximo token")
                for k in range(1, self.order + 1):              # olhar para os (até) n tokens anteriores, e registrar a sequência no counter
                    context = tuple(padded_seq[i - k : i])
                    self.models[k][context][next_token] += 1

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
        if rng is None:
            rng = random.Random()

        # aqui tentamos casar o histórico com uma das sequências de ordem n. se não conseguimos, vamos diminuindo o tamanho da sequência até conseguirmos fazer um match
        chosen_counts = None
        for k in range(self.order, 0, -1):
            sub_history = tuple(history[-k:])
            if sub_history in self.models[k] and self.models[k][sub_history]:
                chosen_counts = self.models[k][sub_history]
                break

        # Se ainda assim não houver tokens aprendidos (corpus vazio), devolve repouso
        if not chosen_counts:
            return ()

        tokens = list(chosen_counts.keys())
        counts = [chosen_counts[t] for t in tokens]

        # temperatura faz a distribuição ficar mais fiel ou mais imaginativa
        if temperature <= 0.0:
            # zero ou abaixo: pega estritamente o token mais frequente de cada sequência
            max_count = max(counts)
            candidates = [t for t, c in zip(tokens, counts) if c == max_count]
            return rng.choice(candidates)

        total_count = sum(counts)
        probs = [c / total_count for c in counts]

        # Ajuste log-probabilidade com temperatura
        log_probs = [math.log(p) / temperature for p in probs]
        max_log = max(log_probs)  # Truque de estabilidade numérica contra overflow
        exp_weights = [math.exp(lp - max_log) for lp in log_probs]

        # 3. Amostragem Ponderada
        selected = rng.choices(tokens, weights=exp_weights, k=1)[0]
        return selected
