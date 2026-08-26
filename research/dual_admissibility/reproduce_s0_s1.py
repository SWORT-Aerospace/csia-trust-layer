"""Item 8 hard stop: reproduce the committed S0/S1 tradeoff, or stop.

The dual-admissibility study is only worth running if the tradeoff that
motivates it is real in this checkout. So before anything else, S0 and S1 are
replayed through a SEPARATE implementation of the tick loop and checked against
the numbers already committed in
research/invalidity_masking/results/DIAGNOSTIC_CONSEQUENCES.json.

  S0 (DROP)                    gps_fault posterior 0.892201, 963 leading ticks
  S1 (PROPAGATE_INVALID_HOLD)  gps_fault posterior 0.722429, 836 leading ticks

EXACT equality is required, not approximate. Both paths run the same frozen
core over the same bytes with the same clock; anything other than a bit-for-bit
match means the two loops differ somewhere, and the difference has to be
understood before it is built on.

Exit code 2 = STOP. Nothing downstream should run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
COMMITTED = os.path.join(ROOT, "research", "invalidity_masking", "results",
                         "DIAGNOSTIC_CONSEQUENCES.json")
OUT = os.path.join(_HERE, "results")

# committed policy name -> this study's arm name
MAP = {"DROP": "S0", "PROPAGATE_INVALID_HOLD": "S1"}
CHECKS = (("final_post_gps_fault", "D_final_post_gps_fault"),
          ("max_post_gps_fault", "D_max_post_gps_fault"),
          ("n_ticks_top_cause_gps_fault", "D_ticks_top_cause_gps_fault"),
          ("min_trust_gps", "min_trust_gps"),
          ("final_trust_gps", "final_trust_gps"),
          ("n_ticks", "n_ticks"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
R = _load("_dual_replay", os.path.join(_HERE, "dual_replay.py"))


def main() -> int:
    with open(COMMITTED, encoding="utf-8") as fh:
        committed = json.load(fh)
    onset = float(committed["onset_s"])
    with open(FIXTURE, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != committed["fixture_sha256"]:
        print("STOP: the fixture is not the one the committed numbers came "
              f"from\n  committed {committed['fixture_sha256']}\n  found     "
              f"{sha}")
        return 2

    cap = H.load_fixture(FIXTURE)
    report, ok = [], True
    for policy, arm in MAP.items():
        want = committed["policies"][policy]
        got = R.summarise(R.replay(cap["messages"], arm), t_from=onset)
        for wkey, gkey in CHECKS:
            a, b = want[wkey], got[gkey]
            same = (a == b)
            ok &= same
            report.append({"arm": arm, "committed_policy": policy,
                           "metric": wkey, "committed": a, "reproduced": b,
                           "exact_match": same})
            flag = "ok " if same else "MISMATCH"
            print(f"  {flag} {arm:<4} {wkey:<28} committed={a}  "
                  f"reproduced={b}")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "S0_S1_REPRODUCTION.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "S0_S1_REPRODUCTION",
            "purpose": "item 8 gate: the motivating tradeoff must reproduce "
                       "through an independently written tick loop before S2 "
                       "is implemented",
            "fixture": committed["fixture"],
            "fixture_sha256": sha,
            "onset_s": onset,
            "exact_reproduction": bool(ok),
            "checks": report,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")

    if not ok:
        print("\nSTOP: the committed S0/S1 tradeoff did not reproduce "
              "exactly. Investigate before implementing S2.")
        return 2
    print("\n  S0/S1 tradeoff reproduced exactly. Proceeding is permitted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
