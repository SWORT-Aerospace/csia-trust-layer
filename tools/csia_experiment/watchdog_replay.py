"""Replay one flight log twice, changing ONLY the runtime stale-timeout table.

WHY THIS EXISTS
---------------
The PX4 repeat (Campaign P1) does not reproduce the original n=1 trial's
PRE-FAULT trust: 0.9856 originally against 0.9522 repeated. ArduPilot's does
reproduce (0.9246 against 0.9248). Two campaigns disagreeing on one platform
and agreeing on the other is a fact; attributing it to anything requires a
controlled experiment, and this is that experiment.

THE CONTROL
-----------
The SAME committed flight log is driven through the SAME frozen core twice.
The log, the tick rate, the field mode and the core are identical between the
two runs. The ONLY difference is the table passed as `stale_timeout_s`:

    frozen    csia/runtime/online.py:STALE_TIMEOUT_S            gps 0.5 s
    derived   csia/v1_1/staleness.py:build_runtime_stale_timeouts  gps 1.0 s

So any difference in the resulting trust is attributable to the watchdog and to
nothing else. That is the whole point: without holding the log fixed, a
difference between two campaigns has as many candidate causes as there are
things that changed between them.

MEASURED, ON PX4 (2026-09-06)
------------------------------
    original log, frozen table   0.986420      artifact says 0.985624
    original log, derived table  0.952526      P1 repeat says 0.952172
    repeat   log, frozen table   0.985924
    repeat   log, derived table  0.949056

Both logs reproduce BOTH values, each to within ~0.003. The watchdog change
accounts for the PX4 pre-fault difference.

THE LIMIT, STATED BECAUSE IT IS LOAD-BEARING
---------------------------------------------
**This replay is NOT a valid instrument on ArduPilot.** On the original
ArduPilot log it gives 0.979440 (frozen) and 0.941275 (derived), against a
measured 0.924639 and 0.924816 -- wrong by 0.055 and 0.017, and wrong in a
direction the flights did not show at all. `core_samples_for_tick` reconstructs
hand-offs by detecting a CHANGED channel value, so two identical consecutive
readings look like no new reading; ArduPilot's higher channel rates make that
under-count bias much larger. The bias is documented in
tools/deploy/profile_core_from_log.py, where the reconstruction lives.

Consequence: this tool says the watchdog explains PX4's pre-fault difference,
and says NOTHING about why ArduPilot's pre-fault trust was stable across the
same change. That remains UNRESOLVED and is labelled as such in the
reconciliation rather than filled in by analogy.

    python tools/csia_experiment/watchdog_replay.py --log <flight log> \
        --platform px4
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.runtime.online import (OnlineTrustLayer,            # noqa: E402
                                 STALE_TIMEOUT_S)
from csia.v1_1.staleness import build_runtime_stale_timeouts  # noqa: E402
from tools.deploy.profile_core_from_log import (              # noqa: E402
    core_samples_for_tick, load_ticks)

#: The preregistered PRE window, shared with extract_trust_a2.py. Not a knob.
PRE = (10.0, 12.0)


def replay(path: str, stale: dict, node: str = "gps", window=PRE):
    """Median trust of `node` over `window`, driving the frozen core."""
    layer = OnlineTrustLayer(tick_hz=25.0, field_mode=True,
                             stale_timeout_s=stale)
    prev, values = None, []
    lo, hi = window
    for tick in load_ticks(path):
        states = []
        for sensor, t, chans in core_samples_for_tick(tick, prev):
            states.extend(layer.ingest(sensor, t, chans))
        prev = {k: v["value"]
                for k, v in tick["canonical"]["channels"].items()
                if v.get("usable")}
        for s in states:
            if lo <= s.t < hi and node in s.trust:
                values.append(s.trust[node])
    return (statistics.median(values) if values else None), len(values)


def compare(path: str, platform: str, node: str = "gps") -> dict:
    frozen, n_frozen = replay(path, dict(STALE_TIMEOUT_S), node)
    derived, n_derived = replay(path, build_runtime_stale_timeouts(platform),
                                node)
    return {
        "log": os.path.relpath(path, ROOT),
        "platform": platform,
        "node": node,
        "window": list(PRE),
        "frozen_watchdog_s": STALE_TIMEOUT_S[node],
        "derived_watchdog_s": build_runtime_stale_timeouts(platform)[node],
        "trust_under_frozen": frozen,
        "trust_under_derived": derived,
        "difference": (None if frozen is None or derived is None
                       else derived - frozen),
        "n_states_frozen": n_frozen,
        "n_states_derived": n_derived,
        "validity_note": (
            "This reconstruction under-counts core hand-offs -- two identical "
            "consecutive readings are indistinguishable from no new reading. "
            "It reproduces PX4's measured values to ~0.003 and does NOT "
            "reproduce ArduPilot's, so it must not be used to draw an "
            "ArduPilot conclusion. See the module docstring."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", required=True)
    ap.add_argument("--platform", required=True, choices=("ardupilot", "px4"))
    ap.add_argument("--node", default="gps")
    args = ap.parse_args(argv)
    print(json.dumps(compare(args.log, args.platform, args.node), indent=2,
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
