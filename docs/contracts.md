# Data contracts

Three JSON files connect the sample races, the Markov engine (work machine)
and the web visualizer. Everything is plain JSON, offline and deterministic.

## 1. Race recording — `gm-race/1`

Produced by `tools/make_race.py`. This is also the interface a real game must
implement: on every tick, expose `{you, opp, police}` progress in `[0, 1]`,
then the music system samples it.

| field | type | notes |
|---|---|---|
| `format` | `"gm-race/1"` | schema id |
| `name` | string | bundle id, e.g. `comeback` |
| `title` | string | optional, UI label |
| `description` | string | optional, UI note |
| `sample_hz` | int | `1` |
| `duration_s` | int | race length in seconds |
| `events` | array | `{t, type}`; types: `police_spawn`, `final_lap`, `finish` |
| `samples` | array | one entry per second, `t = 0 .. duration_s` |
| `samples[].you`, `.opp` | float | progress in `[0, 1]`, non-decreasing |
| `samples[].police` | float or `null` | `null` = not yet spawned |

## 2. Sync log — `gm-sync/1`

Produced by the engine. Stand-in for now: `tools/make_demo_bundle.py` mirrors
the latch/hysteresis policy the real engine will use, so the page can be tested
end-to-end. One entry per generated bar; the visualizer interpolates between
entries. It doubles as the evaluation log for the report (meter time-share,
layer statistics).

| field | type | notes |
|---|---|---|
| `format` | `"gm-sync/1"` | schema id |
| `bpm` | int | constant tempo |
| `bars[].i` | int | bar index, from 0 |
| `bars[].t_music` | float | music time at bar start (s) |
| `bars[].t_race` | float | race time latched for this bar (s) |
| `bars[].meter` | `[num, den]` | `[4, 4]` or `[7, 8]` |
| `bars[].tension` | float | `0..1`, continuous, latched at bar start |
| `bars[].layers` | object | `drums`, `bass`, `pad`, `lead` booleans |
| `bars[].state` | object | `you`, `opp`, `police`, `gap`, `police_dist`, `phase` at latch |

Invariants:

- `t_music` and `t_race` increase monotonically.
- Bar duration = `meter_quarters * 60 / bpm`, where
  `meter_quarters = num * 4 / den` (4/4 → 4, 7/8 → 3.5).
- `layers` and `meter` change only at bar boundaries.

## 3. Bundle manifest — `gm-bundles/1`

`web/data/bundles.json` lists what the visualizer can load. Paths are relative
to `web/`, so the page works from any static HTTP server.

```json
{
  "format": "gm-bundles/1",
  "bundles": [
    {
      "id": "comeback",
      "name": "Comeback",
      "description": "Early lead, overtaken, police chase, fight back and win.",
      "race": "data/comeback.json",
      "sync": "data/comeback.sync.json",
      "audio": "audio/comeback.ogg",
      "placeholder": true
    }
  ]
}
```

`placeholder: true` means stand-in audio/sync; `false` means real engine output.
The page treats both identically.

## The swap

When the Markov engine exists on the work machine it must:

1. emit `web/data/<name>.sync.json` with the `gm-sync/1` schema,
2. render `<name>.mid` to `web/audio/<name>.ogg` (FluidSynth + soundfont),
3. add or update its entry in `bundles.json`.

No page code changes are required.
