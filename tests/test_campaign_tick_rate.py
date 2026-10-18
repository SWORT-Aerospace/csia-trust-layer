"""Every committed campaign trial must have achieved its declared tick rate.

Every analysis in this repository converts ticks to seconds at 25 Hz -- the
crossing ticks, the dwell windows, the S0 sensitivity, the R13 budget. Nothing
ever checked that a run actually ACHIEVED 25 Hz. A shadow loop that fell behind
would produce fewer ticks per second, and every downstream number expressed "in
ticks" would silently mean a different amount of time than the text claims.

The result files already carry both halves of the check (`seconds` and
`stats.ticks`); they were simply never compared. Measured across all 44
committed trials the worst deviation is 0.033 Hz, which is the single boundary
tick from a loop that fires at both t=0 and t=end: 751 = 30*25 + 1.
"""

import glob
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DECLARED_HZ = 25.0
# One extra tick over the whole run is the loop firing at both ends. Anything
# beyond a few percent means the loop did not keep up, and "ticks" stops
# meaning what every analysis assumes it means.
TOLERANCE_HZ = 0.5

PATTERNS = (
    "research/v1_1/results/mechanism_b_gps/*.json",
    "research/v1_1/results/mechanism_b/*.json",
    "research/v1_1/results/shadow_flights/*.json",
)


def _trials():
    for pat in PATTERNS:
        for path in sorted(glob.glob(os.path.join(ROOT, pat))):
            if os.path.basename(path).startswith("campaign_"):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    d = json.load(fh)
            except (OSError, ValueError):
                continue
            secs = d.get("seconds")
            ticks = (d.get("stats") or {}).get("ticks")
            if secs and ticks:
                yield os.path.relpath(path, ROOT), float(secs), int(ticks)


def test_some_trials_are_present_to_check():
    """Guard the guard: an empty scan must not pass silently."""
    assert list(_trials()), "no campaign trials found -- patterns are stale"


def test_every_trial_achieved_its_declared_tick_rate():
    bad = []
    for name, secs, ticks in _trials():
        hz = ticks / secs
        if abs(hz - DECLARED_HZ) > TOLERANCE_HZ:
            bad.append(f"{name}: {ticks} ticks / {secs:g}s = {hz:.3f} Hz")
    assert not bad, (
        "trials did not achieve the 25 Hz every analysis assumes, so their "
        "tick counts do not mean the durations the text claims:\n  "
        + "\n  ".join(bad))


def test_tick_counts_are_consistent_with_a_both_ends_loop():
    """ticks should be seconds*hz + 1, give or take a tick."""
    off = []
    for name, secs, ticks in _trials():
        expected = secs * DECLARED_HZ + 1
        if abs(ticks - expected) > 2:
            off.append(f"{name}: {ticks} ticks, expected about {expected:g}")
    assert not off, "\n  ".join(off)
