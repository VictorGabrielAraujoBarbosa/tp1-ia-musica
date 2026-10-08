#!/usr/bin/env python3
"""Publish one generated piece to the web visualizer (the "swap", see docs/contracts.md).

Copies the piece's trace log and audio into web/, then upserts its entry in
web/data/bundles.json with `placeholder: false`. Generated bundles are sorted
before the placeholder demo ones. No page code changes are needed.

    python3 tools/install_bundle.py --src output/comeback-a \\
        --race web/data/comeback.json --id comeback-a --name "Comeback A"
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def find_one(src: Path, pattern: str) -> Path:
    matches = sorted(src.glob(pattern))
    if len(matches) != 1:
        raise SystemExit(f"expected exactly one {pattern} in {src}, found {len(matches)}")
    return matches[0]


def hyperparameters(src: Path) -> str:
    """Short '(order X, seed Y, latch Z bar(s))' summary from the run manifest."""
    runs = sorted(src.glob("*.run.json"))
    if len(runs) != 1:
        return ""
    cfg = json.loads(runs[0].read_text()).get("config", {})
    bits = []
    for key, label in (("order", "order"), ("seed", "seed"),
                       ("sample_every_bars", "latch")):
        if key in cfg:
            val = cfg[key]
            bits.append(f"{label} {val}" + (" bar(s)" if key == "sample_every_bars" else ""))
    return ", ".join(bits)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path, help="piece output directory")
    ap.add_argument("--race", required=True, type=Path, help="gm-race/1 recording used by the piece")
    ap.add_argument("--id", required=True, help="bundle id (also the name of the copied files in web/)")
    ap.add_argument("--name", default=None, help="display name (default: race title)")
    ap.add_argument("--description", default=None, help="override the auto description")
    args = ap.parse_args()

    race = json.loads(args.race.read_text())
    if race.get("format") != "gm-race/1":
        raise SystemExit(f"{args.race} is not a gm-race/1 recording")
    try:
        race_rel = args.race.resolve().relative_to(WEB.resolve())
    except ValueError:
        raise SystemExit(f"race file must live inside web/ (got {args.race}); "
                         "e.g. pass web/data/comeback.json")

    sync_src = find_one(args.src, "*.sync.json")
    audio_matches = sorted(args.src.glob("*.ogg")) or sorted(args.src.glob("*.wav"))
    if len(audio_matches) != 1:
        raise SystemExit(f"expected one .ogg or .wav in {args.src}, found {len(audio_matches)}")
    audio_src = audio_matches[0]

    (WEB / "data").mkdir(parents=True, exist_ok=True)
    (WEB / "audio").mkdir(parents=True, exist_ok=True)
    sync_dst = WEB / "data" / f"{args.id}.sync.json"
    audio_dst = WEB / "audio" / f"{args.id}{audio_src.suffix.lower()}"
    shutil.copy(sync_src, sync_dst)
    shutil.copy(audio_src, audio_dst)

    description = args.description
    if description is None:
        description = race.get("description", "")
        hp = hyperparameters(args.src)
        if hp:
            description = f"{description} ({hp})"

    bundle = {
        "id": args.id,
        "name": args.name or race.get("title", args.id),
        "description": description,
        "race": race_rel.as_posix(),
        "sync": f"data/{args.id}.sync.json",
        "audio": f"audio/{args.id}{audio_src.suffix.lower()}",
        "placeholder": False,
    }

    bundles_path = WEB / "data" / "bundles.json"
    data = (json.loads(bundles_path.read_text()) if bundles_path.exists()
            else {"format": "gm-bundles/1", "bundles": []})
    by_id = {b["id"]: b for b in data.get("bundles", [])}
    by_id[args.id] = bundle
    # stable sort: generated bundles first, placeholder demo bundles last
    data = {"format": "gm-bundles/1",
            "bundles": sorted(by_id.values(), key=lambda b: bool(b.get("placeholder", False)))}
    bundles_path.write_text(json.dumps(data, indent=1) + "\n")

    print(f"installed {args.id}: {sync_dst.relative_to(ROOT)} + {audio_dst.relative_to(ROOT)} "
          f"(race {race_rel}) -> {bundles_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
