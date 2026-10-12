"""Emit the CSIA-Lite demonstration artifact (phase 7 / H6).

Every number quoted in `research/consequence/CSIA_LITE.md` comes from this
file's output, not from a hand transcription. `tests/test_consequence_lite.py`
re-runs it and compares, so a stale artifact fails rather than misleads.

Standard library only, and it imports `lite` alone -- if it reached for
`csia_consequence` the independence claim would be void.

    python research/consequence/csia_lite/demo.py [out.json]
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lite                                               # noqa: E402

#: Three hypotheses over three features, CONSTRUCTED so that exactly one pair
#: -- `h_pitot_blocked` and `h_wind_shear` -- is separated by exactly one
#: feature, `f_airspeed_vs_ground`. That construction is the demonstration,
#: not a finding: the toy is built to make the mechanism visible in three
#: rows, and a reader should treat it as an illustration and nothing else.
#:
#: The first draft of this file used a different assignment in which the two
#: pitot/static hypotheses also differed on `f_baro_vs_gnss_alt`, so closing
#: the airspeed gate changed nothing and the support state stayed
#: IDENTIFIABLE. That is recorded because it is the honest shape of the
#: mechanism: occlusion bites only when the closing relation is the ONLY
#: thing separating two candidates, and redundant evidence is the defence.
LOW_SETS = {
    "h_pitot_blocked": {"f_airspeed_vs_ground", "f_airspeed_vs_throttle"},
    "h_wind_shear": {"f_airspeed_vs_throttle"},
    "h_static_port_blocked": {"f_baro_vs_gnss_alt"},
}
GATES_OPEN = {"f_airspeed_vs_ground": 1.0,
              "f_airspeed_vs_throttle": 1.0,
              "f_baro_vs_gnss_alt": 1.0}
OBSERVATION = {"f_airspeed_vs_ground": True,
               "f_airspeed_vs_throttle": True,
               "f_baro_vs_gnss_alt": False}

#: The gate that closes. Named after the PX4 and ArduPilot findings it is
#: modelled on -- the airspeed-versus-groundspeed relation that both stacks
#: suspend outside fixed-wing flight -- but it is a MODEL, and nothing here
#: was measured on either autopilot.
CLOSING = "f_airspeed_vs_ground"


def build() -> dict:
    hypotheses = sorted(LOW_SETS)
    open_report = lite.support(hypotheses, LOW_SETS, GATES_OPEN)
    demo = lite.occlusion_demo(LOW_SETS, GATES_OPEN, OBSERVATION, CLOSING)
    closed_gates = dict(GATES_OPEN, **{CLOSING: 0.0})
    closed_report = lite.support(hypotheses, LOW_SETS, closed_gates)

    all_closed = {k: 0.0 for k in GATES_OPEN}
    return {
        "schema": "csia.consequence.csia_lite_demo/1",
        "phase": "7 -- CSIA-Lite independent reproduction (H6)",
        "evidence_level": "DETERMINISTIC_SIMULATION",
        "executed_an_autopilot": False,
        "touched_hardware": False,
        "model_note": (
            "A three-hypothesis toy modelled on the airspeed relations named "
            "in the phase 6 audit, and CONSTRUCTED so that one pair is "
            "separated by exactly one feature. It demonstrates the MECHANISM. "
            "It measures nothing about PX4, ArduPilot, or any aircraft, and "
            "the construction is an illustration, not a result."),
        "redundancy_note": (
            "Occlusion bites only where the closing relation is the sole "
            "separator of two candidates. Where a second relation also "
            "separates them, closing the first changes the support state not "
            "at all -- which is why `support_all_gates_open` and "
            "`support_after_one_gate_closes` differ here by construction and "
            "would not in a redundantly instrumented system."),
        "hypotheses": sorted(LOW_SETS),
        "low_sets": {k: sorted(v) for k, v in sorted(LOW_SETS.items())},
        "gates_open": GATES_OPEN,
        "observation": OBSERVATION,
        "closing_feature": CLOSING,
        "support_all_gates_open": open_report,
        "support_after_one_gate_closes": closed_report,
        "support_all_gates_closed":
            lite.support(sorted(LOW_SETS), LOW_SETS, all_closed),
        "occlusion_demo": demo,
        "pairwise_max_abs_llr_open": {
            f"{a}|{b}": lite.max_abs_llr(a, b, LOW_SETS, GATES_OPEN)
            for i, a in enumerate(hypotheses) for b in hypotheses[i + 1:]},
        "pairwise_max_abs_llr_closed": {
            f"{a}|{b}": lite.max_abs_llr(a, b, LOW_SETS, closed_gates)
            for i, a in enumerate(hypotheses) for b in hypotheses[i + 1:]},
        "h6_outcome": (
            "H6 is not killed. Both mechanisms reproduce, and the fresh-"
            "interpreter import check finds no csia module loaded. The "
            "reproduction is independent of the CODE and not of the AUTHOR, "
            "which is a cross-check on the derivation rather than a "
            "replication by a second party."),
        "what_this_is_not": (
            "Not a measurement, not a validation, not evidence about any "
            "autopilot, and not a second party's replication."),
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    document = build()
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    if argv:
        os.makedirs(os.path.dirname(argv[0]), exist_ok=True)
        with open(argv[0], "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {argv[0]}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
