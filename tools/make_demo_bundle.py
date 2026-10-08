#!/usr/bin/env python3
"""Stand-in engine: placeholder audio + sync-log for each race in web/data.

The real Markov engine (work machine) will emit these two artifacts:
    web/data/<race>.sync.json    bar-by-bar log        (gm-sync/1)
    web/audio/<race>.ogg         rendered music

Until then this script:
  * runs a reference implementation of the latch/hysteresis policy the real
    engine will use (bar-line latching, 2-bar hysteresis on meter and layer
    gates), and
  * synthesizes an obvious placeholder track with the stdlib `wave` module
    (clicks = drums, low pluck = bass, sustained chord = pad, blips = lead)

so the visualizer can be tested end to end. OGG conversion uses ffmpeg when
available and silently falls back to WAV.

Usage
-----
    python3 tools/make_race.py            # once, to create the races
    python3 tools/make_demo_bundle.py     # sync + audio + bundles.json
    python3 tools/make_demo_bundle.py --only comeback
"""

from __future__ import annotations

import argparse
import array
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "web" / "data"
AUDIO_DIR = ROOT / "web" / "audio"

BPM = 128
SR = 22050
GAP_THRESHOLD = 0.03
METER_HOLD_BARS = 2
GATE_HOLD_BARS = 2

METERS = {
    "even": {"sig": [4, 4], "units": 4, "unit_quarters": 1.0},
    "odd": {"sig": [7, 8], "units": 7, "unit_quarters": 0.5},
}


def clamp(v: float, a: float, b: float) -> float:
    return max(a, min(b, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# ---------------------------------------------------------------------------
# Reference policy (port this to the real engine)
# ---------------------------------------------------------------------------

def state_at(samples: list[dict], t: float) -> dict:
    """Race state at (fractional) race time t, linearly interpolated."""
    x = clamp(t, 0.0, len(samples) - 1)
    i = int(x)
    f = x - i
    j = min(i + 1, len(samples) - 1)
    a, b = samples[i], samples[j]

    def merge(key: str):
        va, vb = a[key], b[key]
        if va is None and vb is None:
            return None
        if va is None:
            return vb
        if vb is None:
            return va
        return lerp(va, vb, f)

    you, opp, police = merge("you"), merge("opp"), merge("police")
    return {
        "you": you,
        "opp": opp,
        "police": police,
        "gap": you - opp,
        "police_dist": None if police is None else you - police,
        "phase": max(you, opp),
    }


def tension_of(s: dict) -> float:
    dist = 1.0 if s["police_dist"] is None else s["police_dist"]
    proximity = clamp(1.0 - dist / 0.30, 0.0, 1.0)
    finale = clamp((s["phase"] - 0.72) / 0.28, 0.0, 1.0)
    return clamp(0.7 * proximity + 0.5 * finale, 0.0, 1.0)


def desire_of(s: dict) -> dict:
    dist = 1.0 if s["police_dist"] is None else s["police_dist"]
    duress = dist < 0.12
    finale = s["phase"] > 0.88
    return {
        "drums": True,
        "bass": True,
        "pad": (not duress) and (not finale),
        "lead": finale or dist < 0.08,
    }


class Gate:
    """Layer gate with a minimum number of bars before it may flip."""

    def __init__(self, on: bool, min_bars: int = GATE_HOLD_BARS):
        self.on = on
        self.min_bars = min_bars
        self.streak = 0

    def update(self, desired: bool) -> bool:
        if desired == self.on:
            self.streak = 0
        else:
            self.streak += 1
            if self.streak >= self.min_bars:
                self.on = desired
                self.streak = 0
        return self.on


def build_sync(race: dict, bpm: int = BPM) -> tuple[dict, float]:
    samples = race["samples"]
    duration = float(race["duration_s"])
    quarter = 60.0 / bpm

    gates = {"drums": Gate(True), "bass": Gate(True), "pad": Gate(True), "lead": Gate(False)}
    meter = "even"
    behind = ahead = 0
    bars = []
    t_music = t_race = 0.0
    i = 0

    while t_race < duration - 1e-9:
        s = state_at(samples, t_race)
        gap = s["gap"]

        if gap < -GAP_THRESHOLD:
            behind += 1
            ahead = 0
        elif gap > GAP_THRESHOLD:
            ahead += 1
            behind = 0
        else:
            behind = ahead = 0

        if meter == "even" and behind >= METER_HOLD_BARS:
            meter = "odd"
        elif meter == "odd" and ahead >= METER_HOLD_BARS:
            meter = "even"

        desire = desire_of(s)
        layers = {name: gate.update(desire[name]) for name, gate in gates.items()}
        spec = METERS[meter]

        bars.append({
            "i": i,
            "t_music": round(t_music, 4),
            "t_race": round(t_race, 4),
            "meter": list(spec["sig"]),
            "tension": round(tension_of(s), 3),
            "layers": layers,
            "state": {
                "you": round(s["you"], 4),
                "opp": round(s["opp"], 4),
                "police": None if s["police"] is None else round(s["police"], 4),
                "gap": round(gap, 4),
                "police_dist": None if s["police_dist"] is None else round(s["police_dist"], 4),
                "phase": round(s["phase"], 4),
            },
        })

        bar_dur = spec["units"] * spec["unit_quarters"] * quarter
        t_music += bar_dur
        t_race += bar_dur
        i += 1

    return {"format": "gm-sync/1", "bpm": bpm, "bars": bars}, t_music


# ---------------------------------------------------------------------------
# Placeholder synthesis (stdlib-only)
# ---------------------------------------------------------------------------

def add_pluck(buf: list[float], t: float, freq: float, amp: float, decay: float) -> None:
    start = int(t * SR)
    if start >= len(buf):
        return
    n = int(decay * 4 * SR)
    for k, idx in enumerate(range(start, min(start + n, len(buf)))):
        env = math.exp(-k / (decay * SR))
        buf[idx] += amp * env * math.sin(2 * math.pi * freq * k / SR)


def add_pad(buf: list[float], t0: float, t1: float, freqs: list[float], amp: float,
            attack: float = 0.35, release: float = 0.45) -> None:
    start = int(t0 * SR)
    end = min(len(buf), int(t1 * SR))
    total = (end - start) / SR
    if total <= 0:
        return
    n = len(freqs)
    for idx in range(start, end):
        tt = (idx - start) / SR
        env = min(1.0, tt / attack if attack else 1.0,
                  (total - tt) / release if release else 1.0)
        if env <= 0:
            continue
        value = sum(math.sin(2 * math.pi * f * tt) for f in freqs) / n
        buf[idx] += amp * env * value


def synth(sync: dict, total_music: float) -> list[float]:
    n = int(total_music * SR) + 1
    buf = [0.0] * n
    lead_notes = [440.0, 523.25, 659.25, 783.99]
    quarter = 60.0 / sync["bpm"]

    for bar in sync["bars"]:
        odd = bar["meter"] == [7, 8]
        spec = METERS["odd" if odd else "even"]
        unit_dur = spec["unit_quarters"] * quarter
        t0 = bar["t_music"]
        t1 = t0 + spec["units"] * unit_dur

        # drums: click every unit, accented downbeat with a low thump
        for u in range(spec["units"]):
            t = t0 + u * unit_dur
            accent = u == 0
            add_pluck(buf, t, 1568.0 if accent else 1046.5, 0.5 if accent else 0.22, 0.03)
            if accent:
                add_pluck(buf, t, 80.0, 0.30, 0.08)

        # bass: root pluck on every unit
        if bar["layers"]["bass"]:
            for u in range(spec["units"]):
                add_pluck(buf, t0 + u * unit_dur, 110.0, 0.18, 0.18)

        # pad: sustained A-minor chord for the bar
        if bar["layers"]["pad"]:
            add_pad(buf, t0, t1, [220.0, 261.63, 329.63], 0.09)

        # lead: blips on beats 0 and 2, cycling through the pentatonic
        if bar["layers"]["lead"]:
            for k, u in enumerate((0, 2)):
                if u < spec["units"]:
                    note = lead_notes[(bar["i"] * 2 + k) % len(lead_notes)]
                    add_pluck(buf, t0 + u * unit_dur, note, 0.12, 0.30)

    peak = max(abs(v) for v in buf) or 1.0
    scale = 0.9 / peak
    return [v * scale for v in buf]


def write_wav(path: Path, buf: list[float]) -> None:
    data = array.array("h", (int(clamp(v, -1.0, 1.0) * 32767) for v in buf))
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())


def to_ogg(wav_path: Path, ogg_path: Path) -> Path | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(wav_path), "-c:a", "libvorbis", "-q:a", "4", str(ogg_path)],
        check=True,
    )
    return ogg_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_bundles(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("bundles", [])
    except json.JSONDecodeError:
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--audio-dir", type=Path, default=AUDIO_DIR)
    ap.add_argument("--only", action="append", default=None, help="race name(s), repeatable")
    args = ap.parse_args()

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    race_files = sorted(
        p for p in args.data_dir.glob("*.json")
        if not p.name.endswith(".sync.json") and p.name != "bundles.json"
    )
    if not race_files:
        raise SystemExit("no race recordings found - run tools/make_race.py first")

    new_bundles = []
    for path in race_files:
        race = json.loads(path.read_text())
        name = race["name"]
        if args.only and name not in args.only:
            continue

        sync, total = build_sync(race)
        sync_path = args.data_dir / f"{name}.sync.json"
        sync_path.write_text(json.dumps(sync, indent=1) + "\n")

        buf = synth(sync, total)
        wav_path = args.audio_dir / f"{name}.wav"
        write_wav(wav_path, buf)
        ogg_path = to_ogg(wav_path, args.audio_dir / f"{name}.ogg")
        audio_rel = f"audio/{name}.ogg" if ogg_path else f"audio/{name}.wav"

        odd = sum(1 for b in sync["bars"] if b["meter"] == [7, 8])
        lead_bars = sum(1 for b in sync["bars"] if b["layers"]["lead"])
        pad_bars = sum(1 for b in sync["bars"] if b["layers"]["pad"])
        print(f"{name}: {len(sync['bars'])} bars, {total:.1f}s music, "
              f"odd {odd / len(sync['bars']):.0%}, pad {pad_bars}, lead {lead_bars}, "
              f"audio {audio_rel}")

        new_bundles.append({
            "id": name,
            "name": race.get("title", name.title()),
            "description": race.get("description", ""),
            "race": f"data/{name}.json",
            "sync": f"data/{name}.sync.json",
            "audio": audio_rel,
            "placeholder": True,
        })

    bundles_path = args.data_dir / "bundles.json"
    existing = load_bundles(bundles_path)
    by_id = {b["id"]: b for b in existing}
    for b in new_bundles:
        by_id[b["id"]] = b
    order = [b["id"] for b in existing] + [b["id"] for b in new_bundles if b["id"] not in {x["id"] for x in existing}]
    bundles_path.write_text(json.dumps(
        {"format": "gm-bundles/1", "bundles": [by_id[i] for i in order]},
        indent=1,
    ) + "\n")
    print(f"wrote {bundles_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
