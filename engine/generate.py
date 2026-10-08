#!/usr/bin/env python3
"""Generation harness: walk the race bar by bar, call the student hooks and
the Markov chains, write .mid + trace .sync.json + run manifest.

The harness owns all I/O and timing. The only calls into student code are
`hooks.conditions`, `hooks.bar_context` and the MarkovChain methods.
"""

from __future__ import annotations

import importlib
import json
import random
from pathlib import Path

from .corpus import METERS, training_sequences
from .midi_out import total_seconds, write_midi
from .race import RaceRecording

try:
    from .markov import MarkovChain
except Exception:  # pragma: no cover - markov.py should always import
    MarkovChain = None


def _default_chain_factory(stem: str, meter: str, order: int):
    assert MarkovChain is not None
    return MarkovChain(order)


def train_chains(corpus: dict, cfg: dict, chain_factory=None):
    """Build and train one chain per (stem, meter) that has corpus material."""
    factory = chain_factory or _default_chain_factory
    order = int(cfg.get("order", 2))
    chains = {}
    trained_on = {}
    for stem in cfg["stems"]:
        for meter in ("even", "odd"):
            sequences = training_sequences(corpus, meter, stem)
            if not sequences:
                continue
            chain = factory(stem, meter, order)
            chain.train(sequences)
            chains[(stem, meter)] = chain
            trained_on[f"{stem}/{meter}"] = sum(len(s) for s in sequences)
    return chains, trained_on


def _other(meter: str) -> str:
    return "odd" if meter == "even" else "even"


def generate(
    race: RaceRecording,
    corpus: dict,
    cfg: dict,
    hooks,
    out_dir: str | Path,
    chain_factory=None,
    name: str | None = None,
) -> dict:
    """Generate one piece for one race recording.

    Returns a summary dict; writes `<out_dir>/<name>.mid`, `<name>.sync.json`
    and `<name>.run.json`.
    """
    out_dir = Path(out_dir)
    name = name or race.name
    bpm = float(cfg["bpm"])
    order = int(cfg.get("order", 2))
    seed = int(cfg.get("seed", 1))
    sample_every = max(1, int(cfg.get("sample_every_bars", 1)))
    default_temperature = float(cfg.get("temperature", 1.0))

    chains, trained_on = train_chains(corpus, cfg, chain_factory)
    rng = random.Random(seed)

    # history per (stem, meter), rolling across bars
    histories: dict[tuple[str, str], list[tuple]] = {}
    bars: list[dict] = []          # -> midi_out
    trace: list[dict] = []         # -> gm-sync/1

    ctx: dict | None = None
    state: dict | None = None
    prev_latch_ctx: dict | None = None
    t_music = t_race = 0.0
    i = 0
    skipped_stems: set[str] = set()

    while t_race < race.duration_s - 1e-9:
        if i % sample_every == 0:
            state = race.sample(t_race)
            conds = hooks.conditions(state)
            if not isinstance(conds, dict):
                raise TypeError(f"conditions() must return a dict, got {type(conds).__name__}")
            ctx = hooks.bar_context(conds, i, prev_latch_ctx)
            if not isinstance(ctx, dict):
                raise TypeError(f"bar_context() must return a dict, got {type(ctx).__name__}")
            if ctx.get("meter") not in METERS:
                raise ValueError(f'bar_context() must return "meter" in {sorted(METERS)}, '
                                 f'got {ctx.get("meter")!r}')
            if not isinstance(ctx.get("stems"), dict):
                raise ValueError('bar_context() must return "stems" as a dict of bools')
            prev_latch_ctx = ctx

        assert ctx is not None and state is not None
        meter = ctx["meter"]
        spec = METERS[meter]
        nsteps = spec["steps_per_bar"]
        temperature = float(ctx.get("temperature", default_temperature))

        stem_tokens: dict[str, list[tuple]] = {}
        for stem, on in ctx["stems"].items():
            if not on or stem not in cfg["stems"]:
                continue
            key = (stem, meter)
            chain = chains.get(key) or chains.get((stem, _other(meter)))
            if chain is None:
                if stem not in skipped_stems:
                    skipped_stems.add(stem)
                    print(f"  note: no corpus chain for stem {stem!r}; skipping")
                continue
            hist = list(histories.get(key, [()] * order))[-order:]
            tokens = []
            for _ in range(nsteps):
                tok = chain.sample(hist, temperature=temperature, rng=rng)
                tokens.append(tok)
                hist.append(tok)
                del hist[0]
            histories[key] = hist[-order:]
            stem_tokens[stem] = tokens

        bar = {"meter": meter, "tokens": stem_tokens}
        bars.append(bar)

        you, opp, police = state["you"], state["opp"], state["police"]
        gap = you - opp
        police_dist = None if police is None else you - police
        trace.append({
            "i": i,
            "t_music": round(t_music, 4),
            "t_race": round(t_race, 4),
            "meter": list(spec["sig"]),
            "tension": round(float(ctx.get("tension", 0.0)), 3),
            "layers": {
                layer: bool(ctx["stems"].get(layer, False))
                for layer in ("drums", "bass", "pad", "lead")
            },
            "state": {
                "you": round(you, 4),
                "opp": round(opp, 4),
                "police": None if police is None else round(police, 4),
                "gap": round(gap, 4),
                "police_dist": None if police_dist is None else round(police_dist, 4),
                "phase": round(max(you, opp), 4),
            },
        })

        quarter = 60.0 / bpm
        bar_dur = nsteps / 4.0 * quarter
        t_music += bar_dur
        t_race += bar_dur
        i += 1

    # --- write outputs ----------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    midi_path = out_dir / f"{name}.mid"
    sync_path = out_dir / f"{name}.sync.json"
    run_path = out_dir / f"{name}.run.json"

    write_midi(midi_path, bars, bpm, cfg["stems"])

    sync = {"format": "gm-sync/1", "bpm": int(round(bpm)), "bars": trace}
    sync_path.write_text(json.dumps(sync, indent=1) + "\n")

    odd_bars = sum(1 for b in trace if b["meter"] == [7, 8])
    metrics = {
        "bars": len(trace),
        "music_s": round(total_seconds(bars, bpm), 2),
        "odd_share": round(odd_bars / len(trace), 3) if trace else 0.0,
        "stem_on_bars": {
            stem: sum(1 for b in trace if b["layers"].get(stem))
            for stem in cfg["stems"]
        },
        "tension_mean": round(sum(b["tension"] for b in trace) / len(trace), 3) if trace else 0.0,
        "tension_max": max((b["tension"] for b in trace), default=0.0),
        "trained_steps": trained_on,
    }
    run = {
        "format": "gm-engine-run/1",
        "race": race.name,
        "name": name,
        "config": cfg,
        "outputs": {"midi": f"{name}.mid", "sync": f"{name}.sync.json"},
        "metrics": metrics,
    }
    run_path.write_text(json.dumps(run, indent=1) + "\n")

    return {"midi": midi_path, "sync": sync_path, "run": run_path, "metrics": metrics}


def resolve_hooks(dotted: str):
    """Import a hooks module by dotted path (default engine.hooks)."""
    return importlib.import_module(dotted)
