"""Does judging on uncontaminated evidence rescue the withdrawn motor_esc rule?

THE QUESTION, AND WHY IT IS NOT RHETORICAL
-------------------------------------------
SR-010 withdrew the motor_esc low-trust rule. The falsification search found
a healthy motor_esc raising CAUTION on combination 1 of 95: battery dropped
and vibration at 0.300 were both correctly REJECTED as corroborators, imu0
(0.918) and imu1 (0.939) still supplied the two the guard requires, and
motor_esc sat at 0.667 -- dragged there by the very partner the guard had
just ruled unfit to judge it.

    The guard gates WHETHER TO JUDGE. It does not clean THE VALUE BEING
    JUDGED.

`csia_supervision/contamination.py` now computes the trust attributable to
partners in good standing, exactly, outside the frozen core. This probe asks
whether judging on THAT value avoids the false alarm, and it is entirely
possible that the answer is no.

A CORRECTION TO A CLAIM I MADE IN SR-010
-----------------------------------------
The withdrawal note in `csia_supervision/lowtrust.py` says reinstating the
rule "needs a trust value computed WITHOUT the rejected partners, which is a
frozen-core change". THAT WAS WRONG. The recursion reproduces exactly outside
the core -- measured drift 0.0 over 4500 ticks on three profiles with every
partner admissible -- because every term it needs is already published in
`TrustState`. No frozen file changes here or anywhere.

THE PROCEDURE, DECLARED BEFORE THE ADVERSARIAL RUNS
----------------------------------------------------
Written down before any of the 95 combinations was run, because a threshold
chosen after seeing which combinations fire is not a threshold, it is a fit:

  1. Measure the minimum RESTRICTED motor_esc trust on CLEAN flights, over
     the ARMED window only -- SR-007 is the record of what happens when the
     warm-up floor is read as a mechanism.
  2. The threshold must sit strictly below that minimum, with margin, so it
     cannot fire on a nominal flight.
  3. Among values satisfying (2), take an EXISTING `FailsafeConfig` constant.
     Invent no float.
  4. If no frozen constant satisfies (2), report that and stop. The rule
     stays withdrawn.

THE KILL CONDITIONS, ALSO DECLARED IN ADVANCE
----------------------------------------------
The rule stays WITHDRAWN if any of these holds:

  K1  no `FailsafeConfig` constant sits below the clean-flight minimum,
  K2  any of the 95 adversarial combinations fires on a healthy motor_esc,
  K3  the restriction leaves coverage at zero on a material share of armed
      ticks -- a judgement resting on no admitted evidence is not a
      judgement, and answering "silent" there is luck rather than design.

K3 is the kill condition FUTURE_DIRECTIONS named: "if the renormalised trust
is too noisy to threshold on a sparsely-corroborated sensor, the rule shape
is unsalvageable."
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.runtime.failsafe import FailsafeConfig                 # noqa: E402
from csia.runtime.online import OnlineTrustLayer                 # noqa: E402
from csia_stress.source import StressFlightSource                # noqa: E402
from csia_supervision.contamination import (PRIOR_TRUST,         # noqa: E402
                                            ShadowTrust,
                                            supporting_edges)
from csia_supervision.lowtrust import _standing                  # noqa: E402

INSTRUMENT = "csia_stress.contamination_probe"

TARGET = "motor_esc"

#: Clean flight profiles, both of them. A threshold chosen on one and
#: applied to the other is a threshold chosen on half the evidence.
CLEAN_PROFILES = ("hover_circle", "fast_cruise")
CLEAN_DURATION = 60.0

#: Required gap between the clean-flight minimum and the threshold. Not a
#: tuned number: it is the same margin discipline the baro rule used.
MARGIN = 0.05

#: How far the restricted-to-ALL reconstruction may sit from the frozen
#: core's own trust before the reconstruction is called wrong.
#:
#: NOT A TOLERANCE CHOSEN TO MAKE A CONTROL PASS. `c_nbr` is a ratio of two
#: sums of positive doubles, and a mathematically identical expression
#: evaluated by a different code path differs by a few units in the last
#: place. Measured: exactly 1 ulp (2.220446e-16) in every run tried, on
#: 12 s clean flights and on 90 s adversarial ones alike, and it does NOT
#: accumulate through the recursion -- 2250 ticks later it is still 1 ulp.
#: A structurally wrong reconstruction is not off by an ulp; the first
#: disagreement observed sat in the 16th significant digit.
ULP_BOUND = 4 * sys.float_info.epsilon


def _admissible_good_standing(config: FailsafeConfig):
    """Partners above the threshold the system ALREADY applies to them.

    Introduces no new number. This is the same predicate
    `has_corroboration` uses to decide whether to judge at all -- applied
    here to decide what to judge ON, which is the whole difference.
    """
    def fn(sensor, state, prev_trust):
        good = set()
        for partner, value in (state.trust or {}).items():
            if partner == sensor:
                continue
            if not (state.fresh or {}).get(partner, False):
                continue
            if float(value) >= _standing(partner, config):
                good.add(partner)
        return good
    return fn


def _run(faults, flight_profile: str, duration: float, config: FailsafeConfig):
    """One flight. Returns core and restricted trust traces for TARGET."""
    source = StressFlightSource(faults=tuple(faults), truth=None,
                                flight_profile=flight_profile,
                                duration=duration)
    layer = OnlineTrustLayer()
    sensors = None
    shadow = None
    prev = None
    arm = config.arm_time

    core_min = restricted_min = None
    zero_coverage_ticks = armed_ticks = 0
    # THE TWO THINGS THIS PROBE EXISTS TO SEE, and neither is the headline
    # false-alarm count.
    #
    # `worst_admitted_consistency` is the mechanism. If a partner in GOOD
    # STANDING carries an edge whose consistency is ~0, then restricting to
    # partners in good standing cannot clean the value, because the
    # contamination arrives through an admitted edge. Partner-level standing
    # and edge-level agreement are different facts.
    #
    # `max_restricted_at_zero_coverage` is the second failure mode, and it is
    # worse than the first. With no admissible partner the neighbour term
    # drops out entirely and the sensor is scored on its physics checks
    # alone -- which read healthy. A sensor nothing can vouch for then
    # reports HIGH trust, which is the exact state the corroboration guard
    # exists to refuse to judge.
    worst_admitted_consistency = None
    max_restricted_at_zero_coverage = None
    last = 0.0
    states = []
    for name, t, channels in source.samples():
        states.extend(layer.ingest(name, t, channels))
        last = t
    states.extend(layer.flush(last))

    for state in states:
        if sensors is None:
            sensors = sorted(state.trust)
            shadow = ShadowTrust(sensors,
                                 admissible=_admissible_good_standing(config))
            prev = {n: PRIOR_TRUST for n in sensors}
        # THE TRUST MAP THIS TICK'S EDGE WEIGHTS WERE BUILT FROM, held
        # separately because `prev` is overwritten immediately below. Reusing
        # the overwritten name in the analysis would weight every edge by the
        # partner's CURRENT trust -- the one-tick error `contamination.py`
        # exists to warn about, made in the file that warns about it.
        weighting_trust = prev
        shadow.step(state, prev)
        prev = dict(state.trust)
        if float(state.t) < arm:
            continue
        armed_ticks += 1
        core = state.trust.get(TARGET)
        if core is not None:
            core = float(core)
            core_min = core if core_min is None else min(core_min, core)
        rest = shadow.trust.get(TARGET)
        if rest is not None:
            rest = float(rest)
            restricted_min = rest if restricted_min is None \
                else min(restricted_min, rest)
        if shadow.coverage.get(TARGET, 0.0) <= 0.0:
            zero_coverage_ticks += 1
            if rest is not None:
                max_restricted_at_zero_coverage = rest \
                    if max_restricted_at_zero_coverage is None \
                    else max(max_restricted_at_zero_coverage, rest)
        else:
            admitted = _admissible_good_standing(config)(
                TARGET, state, weighting_trust)
            for c in supporting_edges(TARGET, state, weighting_trust):
                if c.partner in admitted:
                    worst_admitted_consistency = c.consistency \
                        if worst_admitted_consistency is None \
                        else min(worst_admitted_consistency, c.consistency)

    return {
        "core_min_trust": core_min,
        "restricted_min_trust": restricted_min,
        "armed_ticks": armed_ticks,
        "zero_coverage_ticks": zero_coverage_ticks,
        "zero_coverage_fraction": (zero_coverage_ticks / armed_ticks
                                   if armed_ticks else None),
        "worst_admitted_edge_consistency": worst_admitted_consistency,
        "max_restricted_trust_at_zero_coverage":
            max_restricted_at_zero_coverage,
    }


def _clean_baseline(config: FailsafeConfig) -> dict:
    """Step 1 of the declared procedure. No faults, both flight profiles."""
    rows = {}
    for profile in CLEAN_PROFILES:
        rows[profile] = _run((), profile, CLEAN_DURATION, config)
    minima = [r["restricted_min_trust"] for r in rows.values()
              if r["restricted_min_trust"] is not None]
    return {"per_profile": rows,
            "clean_min_restricted_trust": min(minima) if minima else None,
            "window": "armed only (t >= arm_time), per SR-007"}


def _select_threshold(clean_min, config: FailsafeConfig) -> dict:
    """Steps 2-4. An existing constant, or nothing."""
    if clean_min is None:
        return {"selected": None, "reason": "no clean minimum was measurable"}
    ceiling = clean_min - MARGIN
    candidates = {name: float(getattr(config, name))
                  for name in ("nav_caution", "heading_caution",
                               "struct_critical", "power_critical",
                               "att_caution", "att_emergency")}
    below = {k: v for k, v in candidates.items() if v < ceiling}
    if not below:
        return {"selected": None, "candidates": candidates, "ceiling": ceiling,
                "reason": ("K1: no FailsafeConfig constant sits below the "
                           "clean-flight minimum with margin")}
    name = max(below, key=lambda k: below[k])
    return {"selected": name, "value": below[name], "ceiling": ceiling,
            "candidates": candidates,
            "basis": ("an existing frozen FailsafeConfig constant, chosen as "
                      "the largest that clears the clean-flight minimum by "
                      f"{MARGIN}; no float invented")}


def run(limit: int | None = None) -> dict:
    # The SAME search space, the SAME magnitudes and the SAME timings the
    # falsification search used, imported rather than restated so the two
    # cannot drift apart and be compared anyway.
    from csia.sensors.faults import Fault                       # noqa: PLC0415
    from csia_stress.falsify import (DURATION, FLIGHT, ONSET,   # noqa: PLC0415
                                     WORST_PARAMS, _combinations)

    config = FailsafeConfig()
    clean = _clean_baseline(config)
    threshold = _select_threshold(clean["clean_min_restricted_trust"], config)

    result = {
        "schema": "csia.stress.contamination_probe/1",
        "target": TARGET,
        "procedure": "declared in this module's docstring before any "
                     "adversarial combination was run",
        "clean_baseline": clean,
        "threshold_selection": threshold,
    }
    if threshold["selected"] is None:
        result["verdict"] = "RULE_STAYS_WITHDRAWN"
        result["kill_condition"] = "K1"
        return result

    limit_value = float(threshold["value"])
    combinations = _combinations(TARGET)
    if limit is not None:
        combinations = combinations[:limit]

    fired, worst = [], []
    zero_cov_runs = 0
    for assignment in combinations:
        faults = tuple(
            Fault(kind, partner, ONSET, DURATION, dict(WORST_PARAMS[kind]))
            for partner, kind in sorted(assignment.items()))
        row = _run(faults, "hover_circle", FLIGHT, config)
        row["faulted"] = sorted(assignment.items())
        core_fires = (row["core_min_trust"] is not None
                      and row["core_min_trust"] < limit_value)
        rest_fires = (row["restricted_min_trust"] is not None
                      and row["restricted_min_trust"] < limit_value)
        row["core_would_fire"] = core_fires
        row["restricted_would_fire"] = rest_fires
        if (row["zero_coverage_fraction"] or 0.0) > 0.0:
            zero_cov_runs += 1
        if rest_fires:
            fired.append(row)
        worst.append(row)

    worst.sort(key=lambda r: (r["restricted_min_trust"] is None,
                              r["restricted_min_trust"]))
    core_false_alarms = sum(1 for r in worst if r["core_would_fire"])
    admitted_zero = [r for r in worst
                     if r["worst_admitted_edge_consistency"] is not None
                     and r["worst_admitted_edge_consistency"] < 0.01]
    zero_cov_trust = [r["max_restricted_trust_at_zero_coverage"]
                      for r in worst
                      if r["max_restricted_trust_at_zero_coverage"]
                      is not None]
    silenced = [r for r in worst
                if r["core_would_fire"] and not r["restricted_would_fire"]]
    silenced_blind = [r for r in silenced if r["zero_coverage_ticks"] > 0]

    result.update({
        "combinations_enumerated": len(_combinations(TARGET)),
        "combinations_run": len(worst),
        "threshold_applied": limit_value,
        "core_false_alarms": core_false_alarms,
        "restricted_false_alarms": len(fired),
        "runs_with_any_zero_coverage_tick": zero_cov_runs,
        "mechanism": {
            "runs_where_an_ADMITTED_partner_carried_a_dead_edge":
                len(admitted_zero),
            "why_that_matters": (
                "Partner-level standing and edge-level agreement are "
                "different facts, and the restriction only filters on the "
                "first. Traced on combination 0 at t=40.0 s: motor_esc sat "
                "at 0.65000 with three incident edges all at consistency "
                "0.0000, and the only ADMITTED partner was imu0 at trust "
                "0.8528 against its att_caution standing of 0.82. imu0's "
                "bias drift breaks the accel/motor-current relation while "
                "imu0's own trust -- held up by its other edges and its "
                "physics checks -- stays above threshold. Restricting to "
                "partners in good standing therefore cannot clean the "
                "value: the contamination arrives through an admitted "
                "edge."),
            "max_restricted_trust_when_nothing_was_admissible":
                (max(zero_cov_trust) if zero_cov_trust else None),
            "why_THAT_is_worse": (
                "With no admissible partner the neighbour term drops out and "
                "the sensor is scored on physics, temporal and statistical "
                "checks alone, all of which read healthy. Measured on "
                "combination 0: from t=49.6 s the restricted trust climbs "
                "from 0.65 to 0.987 while the core stays pinned at 0.65. A "
                "sensor nothing is in a position to vouch for then reports "
                "HIGH trust -- the opposite error, and the exact state the "
                "corroboration guard exists to refuse to judge."),
        },
        "silenced_but_blind": {
            "count": len(silenced_blind),
            "of_runs_silenced_by_the_restriction": len(silenced),
            "why_this_is_not_a_win": (
                "A run the core would have flagged and the restriction does "
                "not is only an improvement if the restriction made the "
                "evidence CLEANER. Where coverage fell to zero it made the "
                "evidence ABSENT: the neighbour term drops out, the physics "
                "checks read healthy, and the sensor is silent because "
                "nothing was left to disagree with it. That is the same "
                "state the corroboration guard refuses to judge in, and "
                "counting it as a false alarm avoided would be counting "
                "blindness as accuracy."),
            "runs": silenced_blind,
        },
        # EVERY ROW, not a top-five. A claim about the other 90 that cannot
        # be checked from the artifact is a claim that should not be made.
        "all_runs": worst,
        "worst_five": worst[:5],
        "counterexamples": fired[:5],
    })
    if fired:
        result["verdict"] = "RULE_STAYS_WITHDRAWN"
        result["kill_condition"] = "K2"
    elif zero_cov_runs:
        result["verdict"] = "RULE_STAYS_WITHDRAWN"
        result["kill_condition"] = "K3"
    else:
        result["verdict"] = "NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE"
    result["what_this_is_not"] = (
        "NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE is that sentence and nothing "
        "more. The space is fault assignments to this sensor's edge partners "
        "at the top of each campaign range, on one flight profile. Other "
        "sensors, other magnitudes, other timings and other profiles lie "
        "outside it. It does not reinstate the rule; reinstating a rule is a "
        "decision, and no stage promotes itself.")
    return result


def _controls():
    """The restriction must RESPOND and must be FAITHFUL.

    Positive: restricting to no admissible partner must remove the
    neighbour term, so coverage falls to zero. An instrument whose
    restriction did nothing would report the core's own trust and find no
    false alarms for the same reason a disconnected meter reads zero.

    Negative: restricting to EVERY partner must reproduce the frozen core
    exactly. That is the only reason to believe a restricted number means
    anything, and it is checked against the core's published trust rather
    than against another copy of this module.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _short_states():
        source = StressFlightSource(faults=(), truth=None,
                                    flight_profile="hover_circle",
                                    duration=12.0)
        layer = OnlineTrustLayer()
        states, last = [], 0.0
        for name, t, channels in source.samples():
            states.extend(layer.ingest(name, t, channels))
            last = t
        states.extend(layer.flush(last))
        return states

    def _drive(admissible):
        states = _short_states()
        sensors = sorted(states[0].trust)
        shadow = ShadowTrust(sensors, admissible=admissible)
        prev = {n: PRIOR_TRUST for n in sensors}
        drift = 0.0
        for state in states:
            shadow.step(state, prev)
            prev = dict(state.trust)
            for n in sensors:
                core = (state.trust or {}).get(n)
                if core is not None:
                    drift = max(drift, abs(float(core) - shadow.trust[n]))
        return {"coverage": dict(shadow.coverage), "max_drift": drift}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="restricting to no admissible partner drops the neighbour "
                 "evidence entirely",
            kind=POSITIVE,
            run=lambda: _drive(lambda s, st, pt: set()),
            expect=lambda d: max(d["coverage"].values()) == 0.0
            and d["max_drift"] > 0.0,
            basis=("a weighted mean over an empty partner set has no "
                   "admitted weight; coverage zero follows by arithmetic, "
                   "and a trust computed without the neighbour term cannot "
                   "equal one computed with it"),
        ),
        negative=Control(
            name="restricting to every partner reproduces the frozen core "
                 "to within floating-point representation",
            kind=NEGATIVE,
            run=lambda: _drive(
                lambda s, st, pt: set(st.trust) - {s}),
            expect=lambda d: d["max_drift"] <= ULP_BOUND,
            basis=("the frozen core's own published trust in TrustState, "
                   "computed by csia/trust_engine/engine.py and not by this "
                   "module; the bound is 4 units in the last place of a "
                   "double, which is arithmetic and not a chosen tolerance"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N combinations (most "
                         "adversarial first); the report says how many of "
                         "the enumerated space that was")
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    control_report = guard(INSTRUMENT)

    doc = stamp(run(limit=args.limit), control_report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
