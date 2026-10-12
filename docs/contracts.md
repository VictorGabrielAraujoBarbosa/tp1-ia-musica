# Data contracts

Two JSON files connect the race recordings and the Markov engine.
Everything is plain JSON, offline and deterministic.

## 1. Race recording — `gm-race/1`

Produced by `tools/make_race.py` (files in `races/`). This is also the
interface a real game must implement: on every tick, expose
`{you, opp, police}` progress in `[0, 1]`, then the music system samples it.

| field | type | notes |
|---|---|---|
| `format` | `"gm-race/1"` | schema id |
| `name` | string | id, e.g. `comeback` |
| `title` | string | optional, label |
| `description` | string | optional, note |
| `sample_hz` | int | `1` |
| `duration_s` | int | race length in seconds |
| `events` | array | `{t, type}`; types: `police_spawn`, `final_lap`, `finish` |
| `samples` | array | one entry per second, `t = 0 .. duration_s` |
| `samples[].you`, `.opp` | float | progress in `[0, 1]`, non-decreasing |
| `samples[].police` | float or `null` | `null` = not yet spawned |

## 2. Trace log — `gm-sync/1`

Produced by the engine next to each generated `.mid`, one entry per generated
bar. It records the latched race state and the musical decisions of each bar
and doubles as the evaluation log for the report (meter time-share, layer
statistics, tension).

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
