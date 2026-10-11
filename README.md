# Reactive generative music — race-reactive Markov engine

Companion workspace for the "reactive generative music for games" assignment
(DCC831, TP1). A scripted **race recording** (you / opponent / police, each
0..1) drives an **order-n Markov chain** trained on **hand-crafted LMMS
loops** in 4/4 and 7/8. The engine emits a reproducible `.mid` per run plus a
bar-by-bar trace log; audio is rendered with FluidSynth + GeneralUser GS for
audition and for the submission.

The web visualizer in `web/` is an optional extra — not part of the
deliverables — and reuses the same trace format.

## Repository layout

```
corpus/even/*.mid        hand-crafted 4/4 loops   (16 steps/bar)
corpus/odd/*.mid         hand-crafted 7/8 loops   (14 steps/bar)
corpus/corpus.json       generated: gm-corpus/1 (tokenized loops)
engine/race.py           race recording loader + sample(t)             [harness]
engine/generate.py       bar-by-bar harness: hooks -> chains -> outputs[harness]
engine/midi_out.py       tokens -> .mid (mido; drums ch10)             [harness]
engine/corpus.py         corpus I/O + training sequences               [harness]
engine/hooks.py          state features + per-bar decisions            [STUDENT]
engine/markov.py         the Markov chain (train/sample)               [STUDENT]
tools/import_loops.py    LMMS .mid -> corpus.json
tools/smoke_test.py      end-to-end test with fixture doubles
tools/render_audio.py    .mid -> .ogg (FluidSynth + ffmpeg)
tools/validate.py        contract checks for all three JSON schemas
tools/stats.py           report tables from trace logs
tools/memorization.py    verbatim-copy analysis (order trade-off evidence)
tools/compare_pieces.py  step agreement between two pieces (same-config check)
tools/run_all.sh         reproduce every piece from scratch
configs/base.json        engine + instrument + track mapping
configs/pieces/*.json    per-piece hyperparameters (seed/order/temperature/latch)
docs/engine.md           engine internals and formats
docs/contracts.md        gm-race/1, gm-sync/1, gm-bundles/1 schemas
web/                     optional visualizer (vanilla JS, no build step)
```

## Setup

Needs: Python 3 (venv), `ffmpeg`, and `fluidsynth` for rendering. On Arch:

```bash
sudo pacman -S fluidsynth ffmpeg
bash tools/setup.sh          # venv + mido + GeneralUser GS soundfont (~32 MiB)
```

## Reproduce the results

```bash
.venv/bin/python tools/import_loops.py     # corpus .mid -> corpus/corpus.json
.venv/bin/python tools/smoke_test.py       # harness check (fixture chains)
bash tools/run_all.sh                      # 3 pieces: .mid + .ogg + validate + stats
```

Or one piece at a time:

```bash
.venv/bin/python -m engine \
    --race web/data/comeback.json \
    --corpus corpus/corpus.json \
    --config configs/pieces/comeback-a.json \
    --out output/comeback-a
.venv/bin/python tools/render_audio.py \
    --mid output/comeback-a/comeback.mid --out output/comeback-a/comeback.ogg
```

Pieces and their hyperparameter variation:

| piece | race | order | seed | temperature | sample every |
|---|---|---|---|---|---|
| `comeback-a` | comeback | 1 | 11 | 0.9 | 1 bar |
| `comeback-a2` | comeback | 1 | 12 | 0.9 | 1 bar |
| `comeback-b` | comeback | 2 | 23 | 0.9 | 1 bar |
| `comeback-c` | comeback | 3 | 31 | 0.9 | 1 bar |
| `domination-a` | domination | 2 | 5 | 1.15 | 4 bars |

`comeback-a`/`a2` share one configuration and differ only in the seed;
`a → b → c` is the order ladder (1/2/3) with everything else fixed;
`domination-a` varies the latch interval and temperature instead.
`bash tools/run_all.sh` also writes `output/report-stats.md`,
`output/report-memorization.md` and `output/report-same-config.md` with the
tables used in the report.

`sample_every_bars` is how often the race recording is re-sampled; bar length
follows the current meter (4/4 = 16 sixteenths, 7/8 = 14).

## Composing the corpus in LMMS

1. Compose a loop; export each take as `.mid` into `corpus/even/` (4/4) or
   `corpus/odd/` (7/8). Multiple loops per meter are fine and help the chain.
2. Track names matter: `configs/base.json` maps `TripleOscillator` → lead and
   `GeneralUser-GS` → drums (the LMMS export drops programs and puts every
   track on channel 1, so names are the only reliable label).
3. Keep events on the 16th-note grid; notes *starting* on a step become the
   token, note lengths are quantized to steps. A stem may be shorter than the
   file (e.g. a 2-bar drum take next to a 4-bar lead) — trailing silence is
   trimmed when training.
4. Run `tools/import_loops.py` and inspect the printed token grid.

## What the student implements

- `engine/hooks.py`:
  - `conditions(state)` — one race sample `{t, you, opp, police}` →
    `dict[str, bool]` features (e.g. behind, police close, final lap).
  - `bar_context(conds, bar_index, prev)` — features → this bar's
    `{"meter": "even"|"odd", "stems": {...}, "temperature": ...}` including
    any hysteresis (see the `HoldCounter` helper).
- `engine/markov.py`: `MarkovChain.__init__/train/sample` — counting,
  normalization, smoothing and weighted sampling over the corpus tokens.

Everything else (file I/O, timing, MIDI, traces) is harness code.

## AI-use declaration

Per the assignment rules, AI tools were used for auxiliary code and must be
declared here, with links to the conversations.

> **TODO before submission:** paste the conversation links here.
>
> AI provided: the project scaffold and auxiliary code (race JSON loader,
> corpus importer/quantizer, generation harness, MIDI/trace writers, render,
> validation and statistics scripts, docs) and the *interface stubs* in
> `engine/hooks.py` and `engine/markov.py`. The Markov method itself
> (transition counting, smoothing, sampling) and the state/decision logic
> (`conditions`, `bar_context`) were implemented by the student; at the
> student's request, AI also fixed syntax/runtime errors in those two files
> (dict-literal keys, a missing return, a wrong state key) without changing
> the logic. The abstract and paper text were written by the student.

## Web visualizer (optional)

The page is bundle-driven: each entry in `web/data/bundles.json` pairs a race
recording with its trace log and audio, so no page changes are needed per
piece. `bash tools/run_all.sh` publishes generated pieces automatically (via
`tools/install_bundle.py`, which copies trace + audio into `web/` and sets
`placeholder: false`). To view:

```bash
cd web && python3 -m http.server 8000   # open http://localhost:8000
```

"Comeback A/B" show the two generated takes against the comeback race;
"Domination A" is the control case. The original stand-in bundles remain at
the bottom of the picker for comparison. See `docs/contracts.md` for the
underlying schemas.
