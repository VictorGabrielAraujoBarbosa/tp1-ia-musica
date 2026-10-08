#!/usr/bin/env python3
"""End-to-end smoke test of the harness with fixture hooks/chains.

Runs generation for both sample races using `tools/dummy_hooks.py` (a test
double, not the music method), validates the trace logs and inspects the
MIDI files. This proves the plumbing works before the student code exists.

    python3 tools/smoke_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mido  # noqa: E402

from engine.corpus import load as load_corpus  # noqa: E402
from engine.generate import generate  # noqa: E402
from engine.race import RaceRecording  # noqa: E402
from tools import dummy_hooks  # noqa: E402
from tools.validate import validate_sync  # noqa: E402

OUT = ROOT / "output" / "_smoke"


def check(cond: bool, label: str, failures: list[str]) -> None:
    print(f"  {'ok  ' if cond else 'FAIL'} {label}")
    if not cond:
        failures.append(label)


def main() -> int:
    failures: list[str] = []
    cfg = json.loads((ROOT / "configs" / "base.json").read_text())
    cfg.update({"order": 2, "seed": 1, "sample_every_bars": 2, "temperature": 1.0})
    corpus = load_corpus(ROOT / "corpus" / "corpus.json")

    for race_name in ("comeback", "domination"):
        print(f"[{race_name}]")
        race = RaceRecording.load(ROOT / "web" / "data" / f"{race_name}.json")
        result = generate(
            race, corpus, cfg, dummy_hooks, OUT,
            chain_factory=dummy_hooks.chain_factory, name=race_name,
        )
        sync = json.loads(result["sync"].read_text())
        errors = validate_sync(sync)
        check(not errors, "sync log passes validation", failures)
        for err in errors:
            print(f"       {err}")

        meters = {tuple(b["meter"]) for b in sync["bars"]}
        check(meters == {(4, 4), (7, 8)}, f"both grids exercised {sorted(meters)}", failures)

        mid = mido.MidiFile(str(result["midi"]))
        note_ons = [m for m in mid if m.type == "note_on" and m.velocity > 0]
        drum_ons = [m for m in note_ons if m.channel == 9]
        lead_ons = [m for m in note_ons if m.channel == 0]
        sigs = {(m.numerator, m.denominator) for m in mid if m.type == "time_signature"}
        check(len(note_ons) > 0, f"midi has notes ({len(note_ons)})", failures)
        check(len(drum_ons) > 0 and len(lead_ons) > 0,
              f"both stems wrote notes (drums {len(drum_ons)}, lead {len(lead_ons)})", failures)
        check({(4, 4), (7, 8)} <= sigs, f"time signatures in midi {sorted(sigs)}", failures)
        check(9 in {m.channel for m in drum_ons}, "drums on channel 10", failures)

    print()
    if failures:
        print(f"SMOKE TEST FAILED ({len(failures)} checks)")
        return 1
    print("smoke test PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
