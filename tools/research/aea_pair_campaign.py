"""Does an active probe separate fault hypotheses better than doing nothing?

WHAT THE EARLIER CAMPAIGN DID NOT TEST
---------------------------------------
`active_evidence_campaign.py` (MX-037) tested whether the identifiability
model's PREDICTION is right: does a probe meeting three closed-form
conditions resolve a stated resistance change. It found no counterexample.
That is a statement about the formula and NOT about whether active evidence
acquisition is worth anything, because it had no baselines: nothing to
compare the probe against.

This campaign supplies them. Five arms over the same plant and the same
eight-hypothesis bank:

    passive         no additional action
    opportunistic   a mission manoeuvre that would happen anyway, at ZERO
                    incremental energy
    fixed           one fixed engineering probe, chosen without looking
    random_safe     a probe drawn from the library by a fixed seed
    selected        the probe the closed-form selector picks

THE FALSIFIER THAT MATTERS MOST
--------------------------------
The preregistration names it: *the same gain is achieved by simply waiting
for the next ordinary mission manoeuvre at lower cost*. The `opportunistic`
arm exists to make that falsifier reachable. If it matches `selected`, the
honest conclusion is that CSIA should wait rather than ask, and this whole
package is complexity without evidence.

WHAT THE FIRST TWO PILOT RUNS FOUND, BOTH IN THE INSTRUMENT
------------------------------------------------------------
The first pilot reported that a PASSIVE hover separated 27 of 28 pairs,
which would have made this whole package pointless. It was an artifact: six
of the twelve residuals have ZERO-WIDTH envelopes in this simulator -- the
control loop reads true vertical velocity, and the frame and sequence
counters are integers -- so "the envelopes are disjoint" degenerated into
"these two floats differ", and pairs separated on 1e-17. The governing brief
names this hazard explicitly ("zero-width clean baselines") and the first
run walked into it. Fixed by requiring the gap to exceed a declared physical
scale per residual; see `signatures.SCALES`.

The second pilot then found something real, and it is the main result:

    A PROBE IS NOT FREE INFORMATION. IT IS A SWAP.

`source_impedance` is gated on the load VARYING and `effort_drift` is gated
on the operating point being STATIONARY. The probe opens the first and
closes the second, exactly, measured. At the smallest fault magnitudes the
trade is a LOSS: the fixed probe leaves 5 pairs unresolved where passive
leaves 3.

THE METRIC
----------
Unresolved hypothesis pairs, out of the 28 that `hypotheses.pairs()` fixes
before any measurement. A pair is separated when some residual's observed
envelopes over the seed set are disjoint AND that residual's gate was open
in every seed of both hypotheses. Counted BY INDEPENDENT FAMILY, so three
views of pack current count once.

The envelope is a min-max over seeds. It is not a confidence interval, it
understates the spread, and it is therefore OPTIMISTIC about separation.
Every arm is measured the same optimistic way, so the COMPARISON is fair
even though the absolute count is not a bound.

THE OPEN-SET CONTROL
---------------------
A fault outside the bank entirely -- thermal path loss on a motor no bank
entry names -- is run through the same machinery. A system that attributes
it to a modelled hypothesis has failed H4, and that is reported as a
failure of this work rather than as a diagnosis.

WHAT THIS IS NOT
----------------
One simulator, one platform, three magnitudes per hypothesis, five seeds,
E0. It measures a surface. It promotes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import hypotheses as HY                # noqa: E402
from csia_active_evidence import identifiability as ID           # noqa: E402
from csia_active_evidence import probes as PR                    # noqa: E402
from csia_active_evidence import selector as SE                  # noqa: E402
from csia_active_evidence import signatures as SG                # noqa: E402
from csia_components import simulate as S                        # noqa: E402

INSTRUMENT = "tools.research.aea_pair_campaign"
SCHEMA = "csia.active_evidence.pair_campaign/1"

SEEDS = (0, 100, 200, 300, 400)
REFERENCE_SEED = 999           # HELD OUT
ACTION_START = 8.0
SETTLE_S = 6.0                 # before the window, for the thermal relations
DURATION = 26.0
WIN_LO, WIN_HI = ACTION_START, ACTION_START + 12.0
FAULT_START, FAULT_LEN = 2.0, 24.0
MAGNITUDE_INDICES = (0, 1, 2)  # the whole declared bracket, low to high
MAGNITUDE_INDEX = 1            # default for the controls only
RANDOM_ARM_SEED = 4242

#: The mission manoeuvre the vehicle would fly anyway. Gentle, long, and
#: NOT chosen to be diagnostic -- that is the point of the arm.
OPPORTUNISTIC_HZ = 0.1
OPPORTUNISTIC_AMPLITUDE = 0.30

ARMS = ("passive", "opportunistic", "fixed", "random_safe", "selected")


def _opportunistic(t: float) -> float:
    if t < ACTION_START:
        return 0.0
    return OPPORTUNISTIC_AMPLITUDE * float(
        np.sin(2.0 * np.pi * OPPORTUNISTIC_HZ * (t - ACTION_START)))


def _setpoint_for(arm: str, probe):
    if arm == "passive":
        return lambda _t: 0.0
    if arm == "opportunistic":
        return _opportunistic
    return probe.as_setpoint_fn(ACTION_START)


def _reference(arm, probe):
    """Held-out clean run: the effort reference and the link baseline rate.

    Taking either from the run being scored made the clean residual
    identically zero in MX-030 and every fault 'detected'.
    """
    tel = S.Platform(seed=REFERENCE_SEED, duration=DURATION,
                     setpoint=_setpoint_for(arm, probe)).run()
    w = (tel.array("t") >= WIN_LO) & (tel.array("t") <= WIN_HI)
    duty = np.asarray(tel.duty, dtype=float)[w]
    frames_err = tel.array("frames_err")
    frames_ok = tel.array("frames_ok")
    total = float(frames_err[-1] + frames_ok[-1])
    rate = float(frames_err[-1] / total) if total > 0 else 0.0
    return float(duty.mean()), rate


def _run_one(hyp, magnitude, seed, arm, probe, ref_effort, baseline_rate,
             faults=None):
    if faults is None:
        faults = hyp.fault(magnitude, FAULT_START, FAULT_LEN)
    tel = S.Platform(seed=seed, duration=DURATION,
                     setpoint=_setpoint_for(arm, probe)).run(faults)
    return SG.signature(tel, WIN_LO, WIN_HI, reference_effort=ref_effort,
                        baseline_rate=baseline_rate)


def _arm_probe(arm, requirement):
    if arm == "fixed":
        return PR.probe("triangle")
    if arm == "random_safe":
        rng = random.Random(RANDOM_ARM_SEED)
        usable = [p for p in PR.LIBRARY if p.vz_amplitude > 0]
        return rng.choice(usable)
    if arm == "selected":
        sel = SE.select(requirement)
        if sel.verdict != SE.SELECTED:
            return None
        return PR.probe(sel.probe_name)
    return PR.probe("hold")


def _incremental_energy(arm, probe) -> float:
    """Amp-seconds of EXTRA charge the arm costs, over holding station.

    The opportunistic arm is ZERO by definition: the manoeuvre happens
    whether or not CSIA wants it. Charging it for energy it did not cause
    would rig the comparison in favour of probing.
    """
    if arm in ("passive", "opportunistic"):
        return 0.0
    return probe.energy_cost_as()


def _at_magnitude(arm, probe, mi, ref_effort, baseline_rate):
    env = {}
    for hyp in HY.BANK:
        mag = hyp.magnitudes[min(mi, len(hyp.magnitudes) - 1)]
        sigs = [_run_one(hyp, mag, s, arm, probe, ref_effort, baseline_rate)
                for s in SEEDS]
        env[hyp.name] = SG.envelopes(sigs)

    unresolved = []
    for a, b in HY.pairs():
        if not SG.separated(env[a], env[b])["separated"]:
            unresolved.append(f"{a}|{b}")
    return env, unresolved


def _gates(env) -> dict:
    """Which relations were ELIGIBLE under this action, on the clean run.

    A first-class measured quantity, not a diagnostic aside. An action that
    buys one relation by closing another has a cost the pair count alone
    does not show.
    """
    nom = env["nominal"]
    return {r: bool(nom[r].gate_open_in_every_seed) for r in SG.ORDER}


def run_arm(arm, requirement) -> dict:
    probe = _arm_probe(arm, requirement)
    if probe is None:
        return {"arm": arm, "verdict": "NO_PROBE_SELECTED",
                "by_magnitude": {}, "worst_unresolved": len(HY.pairs()),
                "incremental_energy_as": 0.0}

    ref_effort, baseline_rate = _reference(arm, probe)
    by_magnitude, gates = {}, None
    for mi in MAGNITUDE_INDICES:
        env, unresolved = _at_magnitude(arm, probe, mi, ref_effort,
                                        baseline_rate)
        if mi == MAGNITUDE_INDICES[0]:
            gates = _gates(env)
            open_set = _open_set(arm, probe, env, ref_effort, baseline_rate)
        by_magnitude[str(mi)] = {
            "unresolved_pairs": len(unresolved),
            "separated_pairs": len(HY.pairs()) - len(unresolved),
            "unresolved": unresolved,
        }

    worst = max(v["unresolved_pairs"] for v in by_magnitude.values())
    total = sum(v["unresolved_pairs"] for v in by_magnitude.values())
    energy = _incremental_energy(arm, probe)
    return {
        "arm": arm,
        "probe": probe.name,
        "incremental_energy_as": energy,
        "duration_s": 0.0 if arm in ("passive", "opportunistic")
        else probe.duration_s,
        "pairs_total": len(HY.pairs()),
        "by_magnitude": by_magnitude,
        "worst_unresolved": worst,
        "total_unresolved_over_bracket": total,
        "eligible_relations": gates,
        "eligible_count": sum(1 for v in gates.values() if v),
        "open_set": open_set,
    }


def _open_set(arm, probe, env, ref_effort, baseline_rate) -> dict:
    """H4. Run a fault the bank cannot name and see what the machinery says.

    The correct answer is that the observation falls outside every modelled
    hypothesis's envelope on at least one open residual, so no label fits.
    Naming one would be a false attribution and a failure of this work.
    """
    sigs = [_run_one(None, None, s, arm, probe, ref_effort, baseline_rate,
                     faults=HY.unmodelled_fault(FAULT_START, FAULT_LEN))
            for s in SEEDS]
    unknown_env = SG.envelopes(sigs)
    consistent = []
    for name in env:
        conflict = SG.separating_residuals(unknown_env, env[name])
        if not conflict:
            consistent.append(name)
    return {
        "injected": "thermal_path_loss on esc2, which no bank entry names",
        "hypotheses_still_consistent": sorted(consistent),
        "verdict": (HY.UNKNOWN if not consistent
                    else "FALSE_ATTRIBUTION" if len(consistent) == 1
                    else "AMBIGUOUS_INCLUDING_WRONG_LABELS"),
        "false_attribution": len(consistent) == 1,
        "note": ("a single consistent modelled hypothesis means the "
                 "machinery named a cause for a fault it has no model of, "
                 "which is the failure H4 exists to detect"),
    }


# --- instrument controls ---------------------------------------------------

def _identical_hypotheses_do_not_separate(**_):
    """NEGATIVE control 2: a hypothesis against ITSELF must never separate.

    Run twice with the same fault and disjoint seeds. If the machinery finds
    a separating residual there, it is separating noise and every pair count
    in this campaign is fiction.
    """
    probe = PR.probe("triangle")
    ref, rate = _reference("fixed", probe)
    hyp = HY.hypothesis("bearing_friction")
    mag = hyp.magnitudes[MAGNITUDE_INDEX]
    a = SG.envelopes([_run_one(hyp, mag, s, "fixed", probe, ref, rate)
                      for s in SEEDS])
    b = SG.envelopes([_run_one(hyp, mag, s + 7, "fixed", probe, ref, rate)
                      for s in SEEDS])
    return SG.separated(a, b)["separated"]


def _an_obvious_fault_separates_from_nominal(**_):
    """POSITIVE control 1: bus drops at 15% must separate from nominal.

    Known without running this campaign: `error_rate` and
    `sequence_continuity` read the link counters directly, and dropping 15%
    of frames moves both by construction of the simulator's link model.
    """
    probe = PR.probe("triangle")
    ref, rate = _reference("fixed", probe)
    out = {}
    for name in ("nominal", "bus_drops"):
        h = HY.hypothesis(name)
        mag = h.magnitudes[min(MAGNITUDE_INDEX, len(h.magnitudes) - 1)]
        out[name] = SG.envelopes(
            [_run_one(h, mag, s, "fixed", probe, ref, rate) for s in SEEDS])
    return SG.separated(out["nominal"], out["bus_drops"])["separated"]


def _controls():
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)
    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="15 percent frame loss separates from nominal",
            kind=POSITIVE, run=_an_obvious_fault_separates_from_nominal,
            expect=lambda sep: sep is True,
            basis=("csia_components.simulate drops frames by incrementing "
                   "frames_err and not frames_ok; residuals.error_rate and "
                   "sequence_continuity read those counters directly, so a "
                   "15 percent loss must move them. The expected answer "
                   "comes from the simulator's link model and the residual "
                   "definitions, not from this campaign"),
        ),
        negative=Control(
            name="a hypothesis does not separate from itself",
            kind=NEGATIVE, run=_identical_hypotheses_do_not_separate,
            expect=lambda sep: sep is False,
            basis=("two runs of the SAME fault at the SAME magnitude differ "
                   "only by the seed of csia_components.simulate's noise "
                   "draws; there is no physical difference for a residual "
                   "to find, so any separation reported would be the "
                   "instrument separating noise"),
        ),
    ))


def run(quick: bool = False) -> dict:
    started = time.time()
    noise = ID.NoiseModel(sigma_v=0.0200, sigma_i=0.0786,
                          ocv_drift_v_per_s=0.0046)
    requirement = ID.probe_requirement(0.020, noise, S.PACK_R_NOMINAL)

    arms = ARMS[:2] if quick else ARMS
    results = {a: run_arm(a, requirement) for a in arms}

    base = results.get("passive", {})
    passive_total = base.get("total_unresolved_over_bracket")
    passive_gates = base.get("eligible_relations", {})
    comparison = {}
    for a, r in results.items():
        if a == "passive" or passive_total is None:
            continue
        gain = passive_total - r["total_unresolved_over_bracket"]
        gained = sorted(k for k, v in r.get("eligible_relations", {}).items()
                        if v and not passive_gates.get(k))
        lost = sorted(k for k, v in passive_gates.items()
                      if v and not r.get("eligible_relations", {}).get(k))
        per_mag = {mi: (base["by_magnitude"][mi]["unresolved_pairs"]
                        - r["by_magnitude"][mi]["unresolved_pairs"])
                   for mi in r["by_magnitude"]}
        comparison[a] = {
            "pairs_resolved_over_passive_across_bracket": gain,
            "pairs_resolved_over_passive_by_magnitude": per_mag,
            "worse_than_passive_at_some_magnitude": any(
                v < 0 for v in per_mag.values()),
            "incremental_energy_as": r["incremental_energy_as"],
            "pairs_per_amp_second": (gain / r["incremental_energy_as"])
            if r["incremental_energy_as"] > 0 else None,
            "relations_the_action_made_eligible": gained,
            "relations_the_action_made_INELIGIBLE": lost,
        }

    sel = results.get("selected", {})
    opp = results.get("opportunistic", {})
    key = "total_unresolved_over_bracket"
    falsifiers = {}
    if sel and opp:
        falsifiers["a_free_mission_manoeuvre_matches_the_selected_probe"] = (
            opp[key] <= sel[key])
    for a in ("random_safe", "fixed"):
        if a in results and sel:
            falsifiers[f"selected_does_not_beat_{a}"] = (
                results[a][key] <= sel[key])
    if sel:
        falsifiers["the_selected_probe_is_worse_than_passive_somewhere"] = (
            comparison.get("selected", {})
            .get("worse_than_passive_at_some_magnitude", False))
    falsifiers["any_arm_falsely_attributed_an_unmodelled_fault"] = any(
        r["open_set"]["false_attribution"] for r in results.values()
        if "open_set" in r)

    fired = sorted(k for k, v in falsifiers.items() if v)
    if falsifiers.get("any_arm_falsely_attributed_an_unmodelled_fault"):
        verdict = "H4_FAILED_UNMODELLED_FAULT_GIVEN_A_LABEL"
    elif not sel:
        verdict = "NOT_RUN"
    elif fired:
        verdict = "ACTIVE_PROBING_NOT_SUPPORTED_ON_THIS_GRID"
    else:
        verdict = "ACTIVE_PROBING_SUPPORTED_ON_THIS_GRID"

    return {
        "schema": SCHEMA,
        "preregistration": "research/active_evidence/PREREGISTRATION.md",
        "arms": list(arms),
        "seeds": list(SEEDS),
        "reference_seed_held_out": REFERENCE_SEED,
        "hypothesis_bank": [h.to_dict() for h in HY.BANK],
        "pairs_total": len(HY.pairs()),
        "magnitude_indices": list(MAGNITUDE_INDICES),
        "window_s": [WIN_LO, WIN_HI],
        "results": results,
        "comparison_against_passive": comparison,
        "falsifiers": falsifiers,
        "falsifiers_fired": fired,
        "verdict": verdict,
        "metric_definition": (
            "A pair is separated when some residual's observed [min,max] "
            "envelopes over the seed set are disjoint AND that residual's "
            "gate was open in every seed of both hypotheses. Counted by "
            "independent lineage family, so residuals sharing a raw channel "
            "count once."),
        "the_envelope_is_not_a_confidence_interval": (
            "A min-max over five seeds understates the population spread, so "
            "this measure is OPTIMISTIC about separation. Every arm is "
            "measured the same way, so the comparison between arms is fair; "
            "the absolute count is not a bound and must not be quoted as "
            "one."),
        "what_this_is_not": (
            "One simulator, one platform, one magnitude per hypothesis, five "
            "seeds, E0. No number here measures any real vehicle. Nothing is "
            "promoted and no novelty is claimed."),
        "elapsed_s": time.time() - started,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)          # RAISES on failure. CONTROLS FIRST.

    doc = stamp(run(quick=args.quick), report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text[:2000])
    print(f"\nverdict: {doc['verdict']}")
    print(f"{'arm':14s}{'probe':14s}{'low':>5s}{'mid':>5s}{'high':>5s}"
          f"{'sum':>6s}{'elig':>6s}{'As':>8s}")
    for a in doc["arms"]:
        r = doc["results"][a]
        m = r["by_magnitude"]
        print(f"{a:14s}{r.get('probe','-'):14s}"
              f"{m['0']['unresolved_pairs']:5d}{m['1']['unresolved_pairs']:5d}"
              f"{m['2']['unresolved_pairs']:5d}"
              f"{r['total_unresolved_over_bracket']:6d}"
              f"{r['eligible_count']:6d}{r['incremental_energy_as']:8.2f}")
    for a, c in doc["comparison_against_passive"].items():
        if c["relations_the_action_made_INELIGIBLE"]:
            print(f"  {a}: gained {c['relations_the_action_made_eligible']}, "
                  f"LOST {c['relations_the_action_made_INELIGIBLE']}")
    if doc["falsifiers_fired"]:
        print("\nFALSIFIERS FIRED:")
        for f in doc["falsifiers_fired"]:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
