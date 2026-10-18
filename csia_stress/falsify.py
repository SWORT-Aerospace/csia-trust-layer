"""Hunt counterexamples. Stop sampling and hoping.

WHY, IN ONE MEASUREMENT
------------------------
SR-008 is the proof that random campaigns are weakest exactly where the
answer matters. 140 randomised multi-fault runs reported ZERO false alarms
for the motor_esc low-trust rule. A single deliberately CONSTRUCTED case --
three of motor_esc's four edge partners dropped, the fourth left degraded --
found a real CAUTION raised on a perfectly healthy sensor, first try.

A random campaign draws fault combinations independently. The dangerous
region of the space is a specific conjunction, and the probability of drawing
a specific four-way conjunction is small enough that 140 runs is close to
evidence of nothing. The fix is not more samples. It is to stop sampling.

WHAT THIS DOES INSTEAD
----------------------
For each CLAIM, enumerate the region of the fault space where a
counterexample would live, ORDERED MOST ADVERSARIAL FIRST, and run it. The
claims here are the safety properties the supervision overlay rests on:

    C1  the baro low-trust rule does not fire while baro is healthy
    C2  the motor_esc low-trust rule does not fire while motor_esc is healthy
    C3  the effective level is never below the frozen level
    C4  a sensor is never judged on fewer than MIN_CORROBORATORS partners

Search space per rule: every assignment of a live fault kind to the rule
sensor's EDGE PARTNERS -- because those are the only sensors whose failure
can move that sensor's trust -- with the rule's own sensor left UNFAULTED,
at the TOP of each parameter's campaign range. That is where the SR-008 case
lives, and it is small enough to enumerate rather than sample: 95
combinations for motor_esc's four partners, 8 for baro's two.

    THE 8 WAS WRITTEN AS 15 HERE UNTIL 2026-09-10. Nothing depended on it --
    the search enumerates from the applicability matrix and never read this
    sentence -- but a reader checking "did it run the whole space" against a
    prose number would have concluded it ran roughly half. The count is
    printed by every run and asserted by a test rather than restated here.

    ORDERED MOST ADVERSARIAL FIRST. Combinations degrading more partners are
    tried before those degrading fewer, so a bounded run still covers the
    dangerous region rather than a random slice of it.

THE OUTPUT IS NOT A PROOF
-------------------------
`NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE` is exactly that sentence and nothing
more. The report states how many combinations were enumerated, how many were
run, and what lies outside the space entirely -- other sensors, other
magnitudes, other timings, other flight profiles. A search that reported
"claim holds" would be a worse instrument than the random campaign it
replaces, because it would sound conclusive.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from csia.runtime.failsafe import (FailsafeConfig,               # noqa: E402
                                   FailsafePolicy)
from csia.runtime.online import OnlineTrustLayer                 # noqa: E402
from csia.sensors.faults import Fault                            # noqa: E402
from csia_stress.applicability import matrix                     # noqa: E402
from csia_stress.source import StressFlightSource                # noqa: E402

FOUND = "COUNTEREXAMPLE_FOUND"
NOT_FOUND = "NO_COUNTEREXAMPLE_IN_SEARCHED_SPACE"

#: ADVERSARIAL parameters: the TOP of each campaign range, declared here
#: before any run. A falsification search uses the worst legal magnitude --
#: using a midpoint would be searching for a counterexample with one hand.
WORST_PARAMS: dict = {
    "bias_drift": {"axis": 2, "rate": 0.20, "channel": "accel"},
    "dropout": {},
    "emi_spike": {"amplitude": 18.0, "rate_hz": 20.0},
    "gps_spoof": {"drift": (4.0, 4.0, 0.0)},
    "vibration_anomaly": {"gain": 4.5},
    "power_sag": {"depth_v": 2.0, "rpm_loss": 700.0},
}

ONSET = 20.0
DURATION = 50.0
FLIGHT = 90.0


def _partner_options(sensor: str) -> dict:
    """For each edge partner: None, or each live fault kind it responds to."""
    from csia_supervision.lowtrust import edge_partners

    mtx = matrix()
    options = {}
    for partner in sorted(edge_partners(sensor)):
        kinds = sorted(k for k, t in mtx.live_pairs() if t == partner
                       and k in WORST_PARAMS)
        options[partner] = [None] + kinds
    return options


def _combinations(sensor: str):
    """Every assignment of a fault kind to the sensor's partners.

    Yielded MOST ADVERSARIAL FIRST -- more partners degraded before fewer --
    so a bounded run covers the dangerous end of the space.
    """
    options = _partner_options(sensor)
    partners = sorted(options)
    out = []
    for assignment in itertools.product(*(options[p] for p in partners)):
        chosen = {p: k for p, k in zip(partners, assignment) if k is not None}
        if chosen:
            out.append(chosen)
    out.sort(key=lambda c: (-len(c), sorted(c.items())))
    return out


def _fires(sensor: str, assignment: dict, profile: str,
           config=None) -> dict:
    """Run one candidate. Does the rule fire with `sensor` UNFAULTED?

    `config` is an `EngineConfig` passed to the layer at construction. The
    default is the shipped one, and every result recorded before this
    parameter existed was produced with it. IT CHANGES NO FROZEN FILE:
    `OnlineTrustLayer` has always taken a config, and this only stops the
    search from being locked to one.

    A NON-DEFAULT CONFIG MOVES THE TRUST DISTRIBUTION, SO IT ALSO MOVES WHAT
    THE RULE'S THRESHOLD MEANS. The threshold was selected against the
    SHIPPED configuration's clean-flight minimum, and a search run under a
    different one is measuring a different system. Results from the two are
    not comparable and the artifact says which produced it.
    """
    from csia_supervision import SupervisedFailsafe

    faults = tuple(
        Fault(kind, partner, ONSET, DURATION, dict(WORST_PARAMS[kind]))
        for partner, kind in sorted(assignment.items()))
    source = StressFlightSource(faults=faults, truth=None,
                                flight_profile=profile, duration=FLIGHT)
    layer = OnlineTrustLayer(config=config)
    supervised = SupervisedFailsafe(policy=FailsafePolicy())

    key = f"low_trust_{sensor}"
    # TWO WINDOWS, REPORTED SEPARATELY (SR-007 again).
    #
    # `worst_trust` over the WHOLE run is dominated by the warm-up: trust
    # starts at the 0.8 Beta prior and climbs, and the first armed tick is
    # preceded by ~250 ticks of that climb. Every search reported
    # worst_trust = 0.8182 -- exactly 9/11, the prior after one step -- in
    # every combination, faulted or not. SR-007 is the record of that number
    # being read as a fault response once already.
    #
    # It cannot affect a verdict: `lowtrust.py:309` returns before
    # `arm_time`, so the rule cannot fire in the warm-up and no
    # counterexample can live there. It can and did mislead a reader, which
    # is enough reason to report the armed window separately rather than
    # instead -- replacing the field silently would change what an existing
    # number means.
    arm = FailsafeConfig().arm_time
    fired_at, worst_trust, below_frozen = None, None, False
    worst_trust_armed = None
    unjudgeable = 0
    last = 0.0
    for name, t, channels in source.samples():
        for state in layer.ingest(name, t, channels):
            supervised.update(state)
            if supervised.level.value < supervised.frozen_level.value:
                below_frozen = True          # C3 violation
            if supervised.low_trust.uncorroborated:
                unjudgeable += 1
            value = state.trust.get(sensor)
            if value is not None:
                value = float(value)
                worst_trust = value if worst_trust is None \
                    else min(worst_trust, value)
                if float(state.t) >= arm:
                    worst_trust_armed = value if worst_trust_armed is None \
                        else min(worst_trust_armed, value)
            if key in supervised.low_trust.conditions and fired_at is None:
                fired_at = float(state.t)
        last = t
    return {"fired_at": fired_at,
            "worst_trust": worst_trust,
            "worst_trust_whole_run_includes_warmup": worst_trust,
            "worst_trust_post_arm": worst_trust_armed,
            "effective_below_frozen": below_frozen,
            "unjudgeable_ticks": unjudgeable,
            "faulted": sorted(assignment.items()),
            "flight_profile": profile, "_last": last}


def search(sensor: str, limit: int | None = None,
           profiles=("hover_circle",), config=None) -> dict:
    """Enumerate and run, stopping at the first counterexample."""
    from csia_supervision.lowtrust import RULES, edge_partners

    if sensor not in RULES:
        raise ValueError(f"no low-trust rule for {sensor!r} to falsify")

    combinations = _combinations(sensor)
    total = len(combinations) * len(profiles)
    ran, counterexamples, c3_violations = 0, [], []
    worst_seen = None

    for profile in profiles:
        for assignment in combinations:
            if limit is not None and ran >= limit:
                break
            result = _fires(sensor, assignment, profile, config=config)
            ran += 1
            armed = result.get("worst_trust_post_arm")
            if armed is not None:
                worst_seen = armed if worst_seen is None \
                    else min(worst_seen, armed)
            if result["effective_below_frozen"]:
                c3_violations.append(result)
            if result["fired_at"] is not None:
                counterexamples.append(result)
                break
        if counterexamples:
            break

    return {
        "claim": (f"the {sensor} low-trust rule does not fire while "
                  f"{sensor} is healthy"),
        "sensor": sensor,
        "threshold": RULES[sensor].threshold,
        "edge_partners": sorted(edge_partners(sensor)),
        "combinations_enumerated": total,
        "combinations_run": ran,
        "search_was_exhaustive": (limit is None or ran >= total)
                                 and not counterexamples,
        "verdict": FOUND if counterexamples else NOT_FOUND,
        "counterexamples": [
            {k: v for k, v in c.items() if not k.startswith("_")}
            for c in counterexamples],
        "effective_below_frozen_violations": len(c3_violations),
        "worst_trust_seen": (round(worst_seen, 4)
                             if worst_seen is not None else None),
        "worst_trust_seen_window": (
            "POST-ARM ONLY. The whole-run minimum is the 0.8 Beta prior "
            "climbing through warm-up -- 0.8182 in every combination, "
            "faulted or not -- and SR-007 records that number being read as "
            "a fault response. The rule cannot fire before arm_time "
            "(lowtrust.py:309), so nothing here changes a verdict; it "
            "changes what a reader is shown."),
        "ordering": ("most adversarial first -- combinations degrading more "
                     "edge partners are run before those degrading fewer"),
        "not_a_proof": (
            f"{NOT_FOUND} means exactly that. Outside this space: other "
            "sensors, magnitudes below the campaign maximum, other fault "
            "timings, other flight profiles, and any interaction with the "
            "frozen policy's own rules. A search that reported 'the claim "
            "holds' would sound more conclusive than the random campaign it "
            "replaces while establishing no more."),
        "why_not_random": (
            "SR-008: 140 randomised runs found zero counterexamples for this "
            "claim; one constructed case found a real one immediately. The "
            "dangerous region is a specific conjunction, and independent "
            "draws reach it with vanishing probability."),
    }


def run(limit: int | None = None, config=None) -> dict:
    from csia.trust_engine.engine import EngineConfig
    from csia_supervision.lowtrust import MIN_CORROBORATORS, RULES

    shipped = EngineConfig()
    cfg = config or shipped
    results = [search(sensor, limit=limit, config=config)
               for sensor in sorted(RULES)]
    return {
        "schema": "csia.stress.falsification/1",
        # WHICH SYSTEM WAS SEARCHED. A rule's threshold was selected against
        # the SHIPPED configuration's clean-flight minimum, so a search under
        # a different one is a search of a different system and its result
        # must not be compared to a shipped-configuration result.
        "engine_config": {"rho_max": cfg.rho_max, "rho_min": cfg.rho_min,
                          "w_nbr": cfg.w_nbr, "w_phys": cfg.w_phys,
                          "w_temp": cfg.w_temp, "w_stat": cfg.w_stat},
        "engine_config_is_shipped_default": (
            (cfg.rho_max, cfg.rho_min, cfg.w_nbr, cfg.w_phys, cfg.w_temp,
             cfg.w_stat)
            == (shipped.rho_max, shipped.rho_min, shipped.w_nbr,
                shipped.w_phys, shipped.w_temp, shipped.w_stat)),
        "min_corroborators": MIN_CORROBORATORS,
        "worst_params": WORST_PARAMS,
        "onset_s": ONSET, "fault_duration_s": DURATION,
        "flight_duration_s": FLIGHT,
        "claims": results,
        "any_counterexample": any(r["verdict"] == FOUND for r in results),
        "method": (
            "enumeration of the region where a counterexample would live -- "
            "every assignment of a live fault kind to the rule sensor's edge "
            "partners, at the top of each campaign range, with the rule's own "
            "sensor left unfaulted -- ordered most adversarial first."),
    }


INSTRUMENT = "csia_stress.falsify"


def _controls():
    """Controls for the SEARCH, not for the physics.

    The physics is already controlled by the campaign's and the sweep's own
    pairs. What is uncontrolled here is the search harness, and it has a
    failure mode worse than any of them:

        A SEARCH OVER AN EMPTY SPACE REPORTS "NO COUNTEREXAMPLE" AND LOOKS
        EXACTLY LIKE A SEARCH THAT LOOKED HARD AND FOUND NOTHING.

    So the NEGATIVE control does not merely require NOT_FOUND -- it requires
    NOT_FOUND *having actually run combinations*. A vacuous pass is the
    thing to catch. The POSITIVE control requires the search to recognise a
    counterexample when one is placed in front of it, which is the opposite
    defect: an enumerator that runs the whole space and never notices.

    `_fires` is stubbed in both, so these check the harness in isolation.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _with(stub, limit=3):
        # Patch THIS module's own globals, not `csia_stress.falsify` by
        # name. The instrument registry loads tool files as standalone
        # module objects, so a by-name patch lands on a different module and
        # the stub silently never applies -- the control then runs real
        # flights and reports a wrong answer. Caught by the coverage test.
        scope = globals()
        original = scope["_fires"]
        scope["_fires"] = stub
        try:
            return search("baro", limit=limit)
        finally:
            scope["_fires"] = original

    # `**_` absorbs `config`, which `search` now forwards. The stubs are
    # deliberately indifferent to it: these controls check the SEARCH
    # HARNESS, and the harness must behave identically whatever engine
    # configuration it is asked to search under.
    def _fired(sensor, assignment, profile, **_):
        return {"fired_at": 30.0, "worst_trust": 0.5,
                "effective_below_frozen": False, "unjudgeable_ticks": 0,
                "faulted": sorted(assignment.items()),
                "flight_profile": profile, "_last": 90.0}

    def _never(sensor, assignment, profile, **_):
        return {"fired_at": None, "worst_trust": 0.99,
                "effective_below_frozen": False, "unjudgeable_ticks": 0,
                "faulted": sorted(assignment.items()),
                "flight_profile": profile, "_last": 90.0}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a counterexample placed in the space is found",
            kind=POSITIVE,
            run=lambda: _with(_fired)["verdict"],
            expect=lambda v: v == FOUND,
            basis=("the stub reports the rule firing on every combination; "
                   "FOUND follows from the definition of a counterexample, "
                   "not from any physics this tool measures"),
        ),
        negative=Control(
            name="a clean space reports not-found HAVING RUN SOMETHING",
            kind=NEGATIVE,
            run=lambda: (_with(_never)["verdict"],
                         _with(_never)["combinations_run"]),
            expect=lambda r: r[0] == NOT_FOUND and r[1] > 0,
            basis=("the stub never fires, so NOT_FOUND follows by "
                   "definition -- and combinations_run > 0 is what "
                   "separates a real negative from a search over an empty "
                   "space, which would report the same word"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=None,
                    help="cap combinations per claim; coverage is reported")
    ap.add_argument("--sensor", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # CONTROLS FIRST, AND THEY RAISE (MX-025).
    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    _control_report = guard(INSTRUMENT)
    print(f"instrument controls: {_control_report['verdict']}")

    rep = (run(args.limit) if args.sensor is None
           else {"schema": "csia.stress.falsification/1",
                 "claims": [search(args.sensor, limit=args.limit)]})

    rep = stamp(rep, _control_report)
    if args.out:
        path = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    for claim in rep["claims"]:
        print(f"{claim['sensor']:10s} {claim['verdict']}  "
              f"({claim['combinations_run']}/"
              f"{claim['combinations_enumerated']} combinations, "
              f"worst trust {claim['worst_trust_seen']})")
        for c in claim["counterexamples"]:
            print(f"    COUNTEREXAMPLE: {c['faulted']} -> fired at "
                  f"t={c['fired_at']}s with trust {c['worst_trust']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
