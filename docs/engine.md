# Engine internals

How the pieces fit together. The web visualizer is optional; everything here
is the assignment deliverable.

```
race recording (gm-race/1)          configs/base.json + configs/pieces/*.json
        |                                          |
        v                                          v
  engine/race.py  --sample(t)-->  engine/hooks.py  (STUDENT: features + bar decisions)
        |                                          |
        v                                          v
  corpus/<meter>/*.mid --> tools/import_loops.py --> corpus/corpus.json (gm-corpus/1)
                                            |
                                            v
                     engine/generate.py  +  engine/markov.py (STUDENT: the chain)
                                            |
                        +-------------------+-------------------+
                        v                                       v
              <piece>.mid (mido)                       <piece>.sync.json (gm-sync/1)
                        |
                        v
        tools/render_audio.py -> .ogg   (FluidSynth + GeneralUser GS)
```

## Corpus (`gm-corpus/1`)

Built by `tools/import_loops.py` from `corpus/<meter>/*.mid`:

```json
{
 "format": "gm-corpus/1", "bpm": 140, "ticks_per_beat": 128, "step_ticks": 32,
 "stems": ["drums", "lead"],
 "meters": {"even": {"sig": [4, 4], "steps_per_bar": 16},
            "odd":  {"sig": [7, 8], "steps_per_bar": 14}},
 "loops": [
  {"id": "even/loop-01", "meter": "even", "bars": [
     {"drums": [["kick", "hat"], [], ...], "lead": [[[61, 3]], [], ...]},
     ...]}
 ]
}
```

- A **token** is what *starts* at one 16th-note step.
- `lead` tokens: `[[pitch, duration_steps], ...]` (`[]` = nothing starts).
- `drums` tokens: `["kick", "hat", ...]` (`[]` = nothing hits).
- LMMS export quirks handled here: everything lands on channel 1 and programs
  are dropped, so stems are identified by **track name**
  (`configs/base.json` → `track_stems`); drums are re-channeled to 10 on
  export. The folder (`even/` vs `odd/`) defines the meter.

## Engine config

`configs/base.json` plus a piece override (shallow merge). Keys:

| key | meaning |
|---|---|
| `bpm` | tempo, 140 to match the corpus |
| `order` | Markov order (context length in tokens), **hyperparameter** |
| `seed` | RNG seed for reproducible runs, **hyperparameter** |
| `temperature` | sampling temperature, **hyperparameter** (student code receives it) |
| `sample_every_bars` | how often race state is re-sampled, **hyperparameter** |
| `hooks` | dotted module with `conditions` / `bar_context` |
| `stems` | per-stem MIDI channel, program, velocity, drum flag |
| `track_stems` | LMMS track name → stem, used by the importer |

Behavior notes:

- The race clock advances 1:1 with music time (a bar consumes
  `steps_per_bar/4` quarters of both). The state is latched at bar starts and
  held for `sample_every_bars` bars; meter, stems and temperature are then
  constant for that span.
- Chains are per `(stem, meter)` because the grids differ (16 vs 14 steps).
  If a stem has no corpus for the current meter, the other meter's chain is
  used as fallback (the token vocabulary is meter-independent).
- Trace logs (`gm-sync/1`) are the same schema the web demo reads; the extra
  `.run.json` captures the config + metrics for reproducibility.

## Student code

- `engine/hooks.py` — `conditions(state)` and `bar_context(conds, i, prev)`
  (the only places musical state logic lives).
- `engine/markov.py` — `MarkovChain.train` / `MarkovChain.sample`.

Tests: `tools/smoke_test.py` runs the whole harness with fixture doubles
(`tools/dummy_hooks.py`) so plumbing bugs are caught before student code exists.
