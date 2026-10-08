#!/usr/bin/env python3
"""STUDENT-RESPONSIBLE FILE — state features and per-bar decisions.

Everything else in `engine/` is harness: it reads files, keeps bar time,
calls the functions below, and writes MIDI + trace logs. The musical logic
is the two functions in this file. Replace the `raise NotImplementedError`
bodies with your own code.

Flow, once per latch point (every `sample_every_bars` bars; hyperparameter
in the piece config):

    state = race.sample(t_race)          # engine/race.py   {t, you, opp, police}
    conds = conditions(state)            # <- YOU, below
    ctx   = bar_context(conds, i, prev)  # <- YOU, below
    ... harness generates that bar with the chosen meter/stems/temperature.
"""

from __future__ import annotations


class HoldCounter:
    """Counts consecutive True observations (helper; use it or delete it).

    Handy for hysteresis, e.g. "only switch to 7/8 after `behind` was True
    for two latches in a row":

        counter = HoldCounter(hold=2)
        ...
        if counter.update(conds["behind"]):
            next_meter = "odd"
    """

    def __init__(self, hold: int = 1):
        self.hold = max(1, int(hold))
        self._count = 0

    def update(self, flag: bool) -> bool:
        """Feed one observation; True when the flag has been True `hold`
        consecutive times (then the counter resets)."""
        if flag:
            self._count += 1
            if self._count >= self.hold:
                self._count = 0
                return True
        else:
            self._count = 0
        return False


def conditions(state: dict) -> dict[str, bool]:
    """Turn one race sample into boolean features/conditions.

    Parameters
    ----------
    state
        One latched sample from `RaceRecording.sample`:
        {"t": float, "you": float, "opp": float, "police": float | None}.
        `police` is None before the police car spawns. All progress values
        are floats in [0, 1].

    Returns
    -------
    dict[str, bool]
        Keys are yours. Example: {"behind": ..., "police_near": ...,
        "final_lap": ...}. This dict is handed straight to bar_context().
        Derive whatever you need, e.g.:

            gap = state["you"] - state["opp"]
            police_dist = None if state["police"] is None \
                else state["you"] - state["police"]
            phase = max(state["you"], state["opp"])

    STUDENT: implement.
    """
    flags: dict[str, bool] = {
        "ahead": state["you"] - state["opp"] > 0,
        "first half": state["you"] < 0.5,
        "police near": state["police"] is not None and abs(state["police"] - state["you"]) < 0.2,
        "opp near": abs(state["opp"] - state["you"]) < 0.05,
    }

    return flags



def bar_context(conds: dict[str, bool], bar_index: int, prev: dict | None) -> dict:
    """Decide the musical context for the bar that is about to start.

    Called at each latch point (every `sample_every_bars` bars); the context
    is held between latch points. This is where the conditions "tune" the
    Markov chain: meter selection, which stems play, sampling temperature.

    Parameters
    ----------
    conds
        The dict returned by conditions() at this latch point.
    bar_index
        Index of the bar that is about to start (0-based).
    prev
        The context dict chosen at the previous latch, or None on the first.

    Returns
    -------
    dict with at least:
        "meter": "even" | "odd"     # 4/4 or 7/8 — picks the chain set
        "stems": {"drums": bool, "lead": bool, ...}   # which chains generate
    and optionally:
        "temperature": float        # overrides the piece config value
        "tension": float in [0, 1]  # only used in the trace log

    Unknown keys are ignored. Use HoldCounter (above) or your own logic so
    the meter/layers don't flicker every bar.

    STUDENT: implement.
    """

    choices: dict = {
        "meter": "even",
        "temperature": 0.0,
        "tension": 0.0,
        "stems": {
            "drums": False,
            "lead": True,
        },
    }

    if conds["first half"]:
        choices["temperature"] = 1
        if (conds["police near"] or conds["opp near"]) and not conds["ahead"]:
            choices["tension"] = 0.6
            choices["meter"] = "odd"
            choices["stems"] = {
                "drums": True,
                "lead": True
            }
        elif conds["ahead"]:
            choices["tension"] = 0.3
            choices["meter"] = "even"
            choices["stems"] = {
                "drums": True,
                "lead": False
            }
        else:
            choices["tension"] = 0.5
            choices["meter"] = "odd"
            choices["stems"] = {
                "drums": False,
                "lead": True
            }
    else:
        choices["temperature"] = 0.5
        if (conds["police near"] or conds["opp near"]) and not conds["ahead"]:
            choices["tension"] = 1
            choices["meter"] = "odd"
            choices["stems"] = {
                "drums": True,
                "lead": True
            }
        elif conds["ahead"]:
            choices["tension"] = 0.6
            choices["meter"] = "even"
            choices["stems"] = {
                "drums": True,
                "lead": True
            }
        else:
            choices["tension"] = 0.8
            choices["meter"] = "odd"
            choices["stems"] = {
                "drums": True,
                "lead": False
            }

    return choices