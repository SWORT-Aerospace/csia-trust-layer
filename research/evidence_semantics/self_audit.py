"""Item 17. Four deliberately faulty NON-SCORED fixtures. The checker must
find all four.

These are TOOL-VALIDATION FIXTURES, NOT SCIENTIFIC RESULTS. Nothing here is
evidence about CSIA. The defects are injected into the PROBE -- the research
instrument -- because that is where the previous package's real bugs lived: a
one-message time-indexing error in the sidecar inverted a reported result, and
a self-audit that patched a different module instance than the checker used
passed for the wrong reason.

So two rules are enforced mechanically here:

  * every patch asserts it is mutating the SAME module object the checker
    imported (`assert sys.modules['probe'] is P`), and
  * DETECTION is defined in advance as "at least one published quantity
    moves". Separately, each fixture also names, in advance, WHICH quantity
    it is predicted to move. The prediction is scored on its own and a wrong
    prediction is recorded as wrong -- the fixture is not re-aimed to make it
    come true. One of the four predictions below is in fact refuted, and the
    reason it is refuted corroborates the main finding.

  python research/evidence_semantics/self_audit.py
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import contract_checker as C                                  # noqa: E402
import probe as P                                             # noqa: E402

# The checker must be looking at the module this file patches. This is the
# exact mistake the Stage 2 self-audit made and it is checked, not assumed.
assert C.P is P, "the checker imported a different `probe` module object"
assert sys.modules["probe"] is P

OUT = _HERE      # TOOL_SELF_AUDIT.json is a named deliverable (item 29)


def published():
    """Every quantity a fixture is allowed to be judged against.

    Read fresh from the instrument each time; the checker's cache is cleared
    first so nothing survives an injection.
    """
    C._CACHE.clear()
    q = {}
    # GNSS, v1.1 adapter
    r = C.run("v1_1_adapter", "I", "gnss")
    q["gnss_A_close_delay_after_I"] = C.proj_evidence(r)[1]
    q["gnss_T4_tokens_for_I"] = sorted({x["T4_channel"] for x in r})
    rn = C.run("v1_1_adapter", "N", "gnss")
    q["gnss_T4_tokens_for_N"] = sorted({x["T4_channel"] for x in rn})
    q["gnss_T4_stale_onset_for_N"] = next(
        (round(x["t"], 3) for x in rn if x["T4_channel"] == "S"), None)
    st, _tab = C.first_collapse("v1_1_adapter", "gnss", "I", "N")
    q["gnss_first_collapse_I_vs_N"] = st
    # battery, v1.1 adapter
    rb = C.run("v1_1_adapter", "X", "battery")
    q["battery_T4_tokens_for_X"] = sorted({x["T4_channel"] for x in rb})
    stb, _ = C.first_collapse("v1_1_adapter", "battery", "X", "V")
    q["battery_first_collapse_X_vs_V"] = stb
    return q


# ------------------------------------------------------------ the fixtures
def defect_phase_shift():
    """One-message phase shift: every symbol slot moves one message period.

    The exact failure class that inverted a result in the previous package.
    """
    orig = P.stream

    def shifted(word, family, hz=None, warmup_s=P.WARMUP_S):
        hz = hz or P.hz_for(family)
        msgs, t_end = orig(word, family, hz, warmup_s)
        period = 1.0 / hz
        for m in msgs:
            if m["_t_recv"] >= warmup_s:
                m["_t_recv"] = round(m["_t_recv"] + period, 6)
                P._stamp(m, m["_t_recv"], family)
        return msgs, t_end + period
    P.stream = shifted
    return lambda: setattr(P, "stream", orig)


def defect_wrong_freshness_event():
    """The channel is aged against the PREVIOUS tick instead of this one."""
    orig = P._t4_channel

    def wrong(adapter, channel, now):
        return orig(adapter, channel, now - 1.0 / P.TICK_HZ)
    P._t4_channel = wrong
    return lambda: setattr(P, "_t4_channel", orig)


def defect_sentinel_becomes_stale():
    """The producer's own disavowal is reported as ordinary ageing."""
    orig = P._t4_channel

    def blurred(adapter, channel, now):
        tok, val = orig(adapter, channel, now)
        return ("S" if tok in ("X", "R") else tok), val
    P._t4_channel = blurred
    return lambda: setattr(P, "_t4_channel", orig)


def defect_invalid_becomes_no_observation():
    """An explicit no-fix report is recorded as though nothing arrived."""
    orig = P._t4_channel

    def blurred(adapter, channel, now):
        tok, val = orig(adapter, channel, now)
        return ("N" if tok == "I" else tok), val
    P._t4_channel = blurred
    return lambda: setattr(P, "_t4_channel", orig)


FIXTURES = [
    {"id": "D1_one_message_phase_shift",
     "inject": defect_phase_shift,
     "must_move": ["gnss_A_close_delay_after_I"],
     "why": "a one-period shift moves when the previous fix ages out, so the "
            "measured admissibility delay must change",
     "if_refuted": "PREDICTION REFUTED, AND KEPT. The delay does NOT move, "
                   "because on this path the no-fix report has no effect on "
                   "admissibility at all -- A closes when the PREVIOUS fix "
                   "ages out, whichever tick the report lands on. That the "
                   "shift is invisible in this quantity is a second, "
                   "independent confirmation of the GNSS-F1 collapse. The "
                   "defect is still detected: the T4 token set moves, "
                   "because before the shifted report arrives the adapter is "
                   "still serving the retained fix."},
    {"id": "D2_wrong_freshness_event",
     "inject": defect_wrong_freshness_event,
     "must_move": ["gnss_T4_stale_onset_for_N"],
     "why": "ageing a channel against the wrong tick moves the STALE onset "
            "by exactly one tick"},
    {"id": "D3_sentinel_converted_to_stale",
     "inject": defect_sentinel_becomes_stale,
     "must_move": ["battery_T4_tokens_for_X"],
     "why": "the battery channel must stop reporting the retained-after-"
            "sentinel state, which is the whole content of the F3 finding"},
    {"id": "D4_invalid_converted_to_no_observation",
     "inject": defect_invalid_becomes_no_observation,
     "must_move": ["gnss_T4_tokens_for_I"],
     "why": "an explicit no-fix report recorded as absence would move the "
            "blame off `to_core_samples` and onto the adapter"},
]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    base = published()
    results, all_found = [], True
    for fx in FIXTURES:
        restore = fx["inject"]()
        try:
            got = published()
        finally:
            restore()
        moved = sorted(k for k in base if base[k] != got.get(k))
        detected = bool(moved)
        prediction_held = all(k in moved for k in fx["must_move"])
        all_found &= detected
        results.append({
            "fixture": fx["id"],
            "detection_rule": "at least one published quantity moves",
            "detected": detected,
            "predicted_target": fx["must_move"],
            "prediction": fx["why"],
            "prediction_held": prediction_held,
            "prediction_note": fx.get("if_refuted", ""),
            "quantities_that_moved": moved,
            "baseline": {k: base[k] for k in fx["must_move"]},
            "with_defect": {k: got.get(k) for k in fx["must_move"]},
        })

    after = published()
    restored = (after == base)

    payload = {
        "artifact": "TOOL_SELF_AUDIT",
        "status": "TOOL VALIDATION FIXTURES -- NOT SCIENTIFIC RESULTS",
        "patched_module_is_the_one_the_checker_uses": True,
        "fixtures": results,
        "all_four_detected": bool(all_found),
        "instrument_restored_exactly": bool(restored),
        "baseline": base,
    }
    with open(os.path.join(OUT, "TOOL_SELF_AUDIT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")

    payload["predictions_held"] = sum(1 for r in results
                                      if r["prediction_held"])
    payload["predictions_refuted"] = [r["fixture"] for r in results
                                      if not r["prediction_held"]]
    with open(os.path.join(OUT, "TOOL_SELF_AUDIT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")

    for r in results:
        print(f"  {r['fixture']:<42} detected={r['detected']}  "
              f"prediction_held={r['prediction_held']}  "
              f"moved={r['quantities_that_moved']}")
    print(f"\n  all four detected: {all_found}")
    print(f"  predictions held: {payload['predictions_held']}/4 "
          f"(refuted: {payload['predictions_refuted']})")
    print(f"  instrument restored exactly: {restored}")
    return 0 if (all_found and restored) else 1


if __name__ == "__main__":
    sys.exit(main())
