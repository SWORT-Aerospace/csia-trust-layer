"""Replay a recorded evidence sequence through the capability/product layers.

THE ONE THING THIS FILE MUST NOT LET A READER CONCLUDE
--------------------------------------------------------
That the pipeline as a whole is deterministic.

**The CORE decision replay is DIVERGENT on both measured platforms (HF-004).**
ArduPilot 511 of 750 compared ticks differ categorically; PX4 144 of 750. The
cause is that the flight-log hand-off reconstruction detects a change in a
channel value, so two identical consecutive readings look like no new reading.
That limitation is unfixed, recorded, and is NOT what this file measures.

So the two questions are reported SEPARATELY and are never combined:

    CORE REPLAY LIMITATION      given a flight log, can the frozen core's
                                per-tick decisions be reproduced?
                                ANSWER: NO, on both platforms. See
                                research/physical_validation/results/
                                DECISION_REPLAY_RESULTS.json

    EXTENSION DETERMINISM       given an evidence sequence AS INPUT, does the
                                capability/product/planner chain produce the
                                same output every time?
                                ANSWER: measured here.

The second says nothing about the first. An extension that is perfectly
deterministic given inputs it cannot itself produce is exactly as useful as
its input source, and the input source currently diverges.

**Anyone quoting "the mission replay is deterministic" without the first
paragraph is quoting half a sentence.** The output document carries both.

    python tools/xr/mission_replay.py --out <json>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia_mission.capability import EvidenceStatus            # noqa: E402
from csia_mission.planner import DeterministicTestPlanner     # noqa: E402
from csia_mission.product import evaluate_products            # noqa: E402
from csia_mission.provenance import content_hash              # noqa: E402
from csia_mission.recovery import RecoveryState, step         # noqa: E402
from csia_mission.xr1_contracts import (CAPABILITIES,         # noqa: E402
                                        EVIDENCE, PRODUCTS)
from tools.xr.disaster_corridor import ACTIONS, BRANCHES      # noqa: E402

CORE_REPLAY_ARTIFACT = os.path.join(
    ROOT, "research", "physical_validation", "results",
    "DECISION_REPLAY_RESULTS.json")


def _sequence(ticks: int = 40) -> list:
    """A deterministic synthetic evidence sequence.

    SYNTHETIC ON PURPOSE, and labelled as such: the point is to measure the
    EXTENSION's determinism given inputs, not to claim those inputs came from
    a flight. They did not.
    """
    seq = []
    for i in range(ticks):
        t = i * 0.5
        killed = set()
        if 10 <= i < 20:
            killed |= {"gnss.position.supported", "gnss.velocity.supported"}
        if 25 <= i < 30:
            killed |= {"camera.rgb.available", "camera.rgb.calibration_valid"}
        seq.append((t, {e: EvidenceStatus(e, e not in killed,
                                          expires_at=t + 50.0)
                        for e in EVIDENCE}))
    return seq


def _one_pass(seq) -> dict:
    machines = {"absolute_navigation": RecoveryState(
        "absolute_navigation", required_fresh_observations=3,
        min_dwell_s=1.0)}
    planner = DeterministicTestPlanner(BRANCHES, ACTIONS)
    trace = []
    for t, ev in seq:
        stepped = step(CAPABILITIES, ev, t, machines,
                       compute={"mapping": "SUPPORTED",
                                "logging": "SUPPORTED"},
                       actuators={"elevon_left": True, "elevon_right": True})
        caps = stepped["published"]
        prods = evaluate_products(PRODUCTS, ev, caps, t)
        plan = planner.choose(caps, prods)
        trace.append({
            "t": round(t, 3),
            "capabilities": {k: v.state for k, v in sorted(caps.items())},
            "products": {k: {"state": v.state,
                             "properties": dict(v.property_states)}
                         for k, v in sorted(prods.items())},
            "branch": plan["chosen"],
        })
    return {"trace": trace, "digest": content_hash(trace)}


def _core_replay_status() -> dict:
    if not os.path.exists(CORE_REPLAY_ARTIFACT):
        return {"available": False,
                "note": "DECISION_REPLAY_RESULTS.json not present"}
    with open(CORE_REPLAY_ARTIFACT, encoding="utf-8") as fh:
        doc = json.load(fh)
    runs = [r for r in doc.get("runs", []) if r.get("verdict") != "LOG_ABSENT"]
    return {
        "available": True,
        "artifact": os.path.relpath(CORE_REPLAY_ARTIFACT, ROOT),
        "per_platform": [
            {"platform": r.get("platform"), "verdict": r.get("verdict"),
             "decisions_compared": r.get("decisions_compared"),
             "divergent": r.get("divergent")}
            for r in runs],
        "all_divergent": all(r.get("verdict") == "DIVERGENT" for r in runs),
        # DECISIONS AND VALUES ARE DIFFERENT QUESTIONS, and after HF-018 the
        # answers differ. Reporting only the first would now overclaim.
        "any_divergent": any((r.get("divergent") or 0) > 0 for r in runs),
        "all_within_numeric_tolerance": all(
            r.get("semantically_equivalent_only", 1) == 0 for r in runs),
        "per_platform_numeric": [
            {"platform": r.get("platform"),
             "bit_identical": r.get("bit_identical"),
             "within_tolerance": r.get("numerically_equivalent"),
             "outside_tolerance": r.get("semantically_equivalent_only"),
             "worst_relative_difference": r.get(
                 "worst_relative_difference")}
            for r in runs],
        "finding": "HF-004 (closed 2026-09-09 by HF-018) / HF-018",
        "why": ("The categorical divergence HF-004 recorded is gone: 0 on "
                "both platforms on the 2026-09-09 SITL runs, once the "
                "comparison joins on the layer's own tick index rather than "
                "on wall time (HF-017). THE VALUES ARE STILL NOT "
                "REPRODUCED: ArduPilot has 22 bit-identical decisions of "
                "2248 and ZERO within the 1e-12 tolerance, worst relative "
                "difference 1.80e-05; PX4 is 51 and 980 of 2242, worst "
                "6.74e-10. So the core replay reproduces DECISIONS on both "
                "platforms and VALUES on neither, and an extension whose "
                "inputs are values is not covered by the first result. The "
                "tolerance has not been widened, and the hand-offs HF-004 "
                "asked to have LOGGED are still reconstructed."),
    }


def run(passes: int = 5) -> dict:
    seq = _sequence()
    results = [_one_pass(seq) for _ in range(passes)]
    digests = [r["digest"] for r in results]
    identical = len(set(digests)) == 1

    first = results[0]["trace"]
    transitions = [row for i, row in enumerate(first)
                   if i == 0 or row["capabilities"] != first[i - 1]
                   ["capabilities"]]

    core = _core_replay_status()
    return {
        "schema": "csia.mission.replay/1",

        # ---- THE TWO ANSWERS, SEPARATED ------------------------------------
        "core_replay_limitation": core,
        "extension_determinism": {
            "passes": passes,
            "ticks_per_pass": len(seq),
            "output_digests": digests,
            "identical": identical,
            "verdict": ("DETERMINISTIC_GIVEN_ITS_INPUTS" if identical
                        else "NON_DETERMINISTIC"),
            "scope": ("SAME PROCESS, REPEATED, on a SYNTHETIC evidence "
                      "sequence. It measures whether the "
                      "capability/product/planner chain is a function of its "
                      "inputs. It does NOT measure cross-host stability and "
                      "it does NOT measure whether those inputs can be "
                      "reproduced from a flight log."),
        },

        # ---- AND THE SENTENCE THAT KEEPS THEM APART ------------------------
        "what_may_not_be_concluded": (
            "THE COMPLETE PIPELINE IS NOT DEMONSTRATED DETERMINISTIC. This "
            "sentence survives HF-004's closure, for a narrower and now "
            "precisely stated reason. The core decision replay no longer "
            "DIVERGES -- 0 categorical differences on both platforms -- but "
            "it does not reproduce the VALUES it hands on: ArduPilot has "
            "ZERO of 2248 decisions within the declared 1e-12 tolerance. "
            "This extension's determinism is conditional on inputs the core "
            "replay reproduces only to within 1.80e-05. An extension that "
            "is a perfect function of its inputs is exactly as reproducible "
            "as its input source, and the input source is not yet "
            "reproducible at the declared tolerance."),
        "transitions_observed": len(transitions),
        "capability_transitions": transitions,
        "evidence_sequence_is_synthetic": True,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--passes", type=int, default=5)
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = run(args.passes)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    e = doc["extension_determinism"]
    c = doc["core_replay_limitation"]
    print(f"\nextension: {e['verdict']} over {e['passes']} passes\n"
          f"core replay: "
          f"{'ALL DIVERGENT' if c.get('all_divergent') else 'see artifact'} "
          f"-- the two are NOT combined", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
