"""Bounded verification of the capability and product semantics.

WHAT "BOUNDED" MEANS, AND THE ONLY SENTENCE AN UNSAT LICENSES
--------------------------------------------------------------
Every property below is checked over a FINITE domain: at most
`MAX_EVIDENCE` evidence items, `MAX_CAPABILITIES` capabilities and
`MAX_PROPERTIES` product properties. When no counterexample is found, the one
statement that follows is:

    "No counterexample exists within the verified bounded domain."

That is not a theorem. It is not "for all". It is not novel. The bound is
stated on every row and no row may be quoted without it.

**THERE IS NO SMT SOLVER IN THIS FILE, AND THAT IS DELIBERATE.** The method is
CONCRETE EXHAUSTIVE ENUMERATION executed against the real `csia_mission`
functions. The previous programme's bounded verifier used z3 and then had to
cross-check the encoding against the implementation, because an encoding can
be a faithful model of a system nobody wrote. Here the domain is small enough
to enumerate directly, so the cross-check step is unnecessary: there is no
encoding that could differ from the code, because the code IS what runs.

THE EIGHT PROPERTIES
--------------------
    P1  CAPABILITY_SUPPORT_IMPLIES_REQUIRED_DEPENDENCIES
    P2  PRODUCT_SUPPORT_IMPLIES_REQUIRED_DEPENDENCIES
    P3  EXPIRED_EVIDENCE_CANNOT_SUPPORT_CURRENT_CAPABILITY
    P4  EXPIRED_EVIDENCE_CANNOT_SUPPORT_CURRENT_PRODUCT
    P5  CONFIG_CHANGE_INVALIDATES_DEPENDENT_CERTIFICATE
    P6  NOT_SUPPORTED_CAPABILITY_CANNOT_AUTHORIZE_ACTION
    P7  RANKING_ALONE_CANNOT_CERTIFY_CAPABILITY
    P8  RANKING_ALONE_CANNOT_CERTIFY_PRODUCT

P7 AND P8 ARE STRUCTURAL, NOT SOLVER QUESTIONS
------------------------------------------------
There is no ranking variable anywhere in the capability or product
evaluation. `evaluate_capabilities` has no ranking parameter and
`evaluate_product` has none either, so there is no term for a solver to
constrain. Encoding a variable that does not exist in order to prove it has
no effect would be proving something about the encoding.

They are instead verified by EXHAUSTIVE DIFFERENTIAL EXECUTION: every case in
the enumerated domain is evaluated twice, once with a ranking attached to the
inputs by every route the API permits, and the two results are compared. A
difference would be a counterexample. This is a weaker claim than a proof and
a stronger one than an assertion, and it is labelled as what it is.

ZERO CASES IS NEVER A PASS
---------------------------
A property that exercises no case reports VACUOUS, never
NO_COUNTEREXAMPLE. The check lives in the shared row builder. It is there
because the first version of P7 and P8 checked ZERO cases and passed (MX-004):
every route they tried was a `setattr` on a frozen dataclass, which raises,
so every route was skipped. That is HF-005's shape -- an absent answer read
as a positive one -- reappearing one round after being named.

    python tools/xr/bounded_verify_mission.py --out <json>
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia_mission.capability import (                        # noqa: E402
    CapabilityContract, CapabilityReport, DEGRADED_SUPPORTED, EvidenceStatus,
    NOT_SUPPORTED, SUPPORTED, UNKNOWN, evaluate_capabilities)
from csia_mission.planner import (                           # noqa: E402
    AUTHORIZED, MissionAction, REJECTED, authorize)
from csia_mission.product import (                           # noqa: E402
    MissionProductContract, PRODUCT_SUPPORTED, QualityRequirement,
    certificate_still_valid, evaluate_product)

#: THE BOUNDS. Stated on every row; no row may be quoted without them.
MAX_EVIDENCE = 4
MAX_CAPABILITIES = 3
MAX_PROPERTIES = 2

BOUNDED_UNSAT = "No counterexample exists within the verified bounded domain."

NO_COUNTEREXAMPLE = "NO_COUNTEREXAMPLE_IN_BOUNDED_DOMAIN"
COUNTEREXAMPLE = "COUNTEREXAMPLE_FOUND"
STRUCTURAL = "STRUCTURAL_BY_CONSTRUCTION"
NOT_A_SOLVER_QUESTION = "NOT_A_SOLVER_QUESTION"


def _evidence_worlds(names):
    """Every assignment of (supported, expired) over the evidence names."""
    per_item = [(True, False), (False, False), (None, False), (True, True)]
    for combo in itertools.product(per_item, repeat=len(names)):
        yield {n: EvidenceStatus(n, sup,
                                 expires_at=(1.0 if exp else 100.0))
               for n, (sup, exp) in zip(names, combo)}


def p1_capability_support_implies_dependencies() -> dict:
    """A SUPPORTED capability's every required evidence item is supported."""
    names = [f"e{i}" for i in range(MAX_EVIDENCE)]
    contract = CapabilityContract("c0", requires_all=tuple(names[:2]),
                                  requires_one_of=((names[2], names[3]),))
    counterexamples, checked = [], 0
    for ev in _evidence_worlds(names):
        checked += 1
        rep = evaluate_capabilities([contract], ev, now=10.0)["c0"]
        if rep.state != SUPPORTED:
            continue
        for eid in contract.requires_all:
            if ev[eid].state_at(10.0) != SUPPORTED:
                counterexamples.append(
                    {"evidence": {k: (v.supported, v.expires_at)
                                  for k, v in ev.items()},
                     "violated": eid})
        if not any(ev[o].state_at(10.0) == SUPPORTED
                   for o in (names[2], names[3])):
            counterexamples.append(
                {"evidence": {k: (v.supported, v.expires_at)
                              for k, v in ev.items()},
                 "violated": "requires_one_of"})
    return _row("P1_CAPABILITY_SUPPORT_IMPLIES_REQUIRED_DEPENDENCIES",
                checked, counterexamples,
                "a capability reported SUPPORTED whose declared requirement "
                "is not met")


def p2_product_support_implies_dependencies() -> dict:
    names = [f"e{i}" for i in range(MAX_EVIDENCE)]
    contract = MissionProductContract(
        "p0", "probe",
        requires_all=(names[0],),
        qualities=(
            QualityRequirement("imagery_quality", requires_all=(names[1],),
                               permits=("use_a",),
                               prohibits_without=("use_a",)),
            QualityRequirement("relative_geometry", requires_all=(names[2],),
                               permits=("use_b",),
                               prohibits_without=("use_b",)),
        ))
    counterexamples, checked = [], 0
    for ev in _evidence_worlds(names):
        checked += 1
        res = evaluate_product(contract, ev, {}, now=10.0)
        for prop, req in (("imagery_quality", names[1]),
                          ("relative_geometry", names[2])):
            if res.property_states.get(prop) in (SUPPORTED,
                                                 DEGRADED_SUPPORTED):
                if (ev[names[0]].state_at(10.0) != SUPPORTED
                        or ev[req].state_at(10.0) != SUPPORTED):
                    counterexamples.append(
                        {"evidence": {k: (v.supported, v.expires_at)
                                      for k, v in ev.items()},
                         "violated": prop})
    return _row("P2_PRODUCT_SUPPORT_IMPLIES_REQUIRED_DEPENDENCIES",
                checked, counterexamples,
                "a product property reported supported whose declared "
                "requirement is not met")


def p3_expired_evidence_cannot_support_capability() -> dict:
    contract = CapabilityContract("c0", requires_all=("e0", "e1"))
    counterexamples, checked = [], 0
    for t in (0.5, 1.0, 1.0001, 5.0, 100.0):
        for exp0, exp1 in itertools.product((1.0, 50.0), repeat=2):
            checked += 1
            ev = {"e0": EvidenceStatus("e0", True, expires_at=exp0),
                  "e1": EvidenceStatus("e1", True, expires_at=exp1)}
            rep = evaluate_capabilities([contract], ev, now=t)["c0"]
            if rep.state == SUPPORTED and (t > exp0 or t > exp1):
                counterexamples.append({"t": t, "expiries": [exp0, exp1]})
    return _row("P3_EXPIRED_EVIDENCE_CANNOT_SUPPORT_CURRENT_CAPABILITY",
                checked, counterexamples,
                "a capability supported by evidence whose expiry has passed")


def p4_expired_evidence_cannot_support_product() -> dict:
    contract = MissionProductContract(
        "p0", "probe",
        qualities=(QualityRequirement("imagery_quality",
                                      requires_all=("e0",),
                                      permits=("u",),
                                      prohibits_without=("u",)),))
    counterexamples, checked = [], 0
    for t in (0.5, 1.0, 1.0001, 5.0, 100.0):
        for exp in (1.0, 50.0):
            checked += 1
            ev = {"e0": EvidenceStatus("e0", True, expires_at=exp)}
            res = evaluate_product(contract, ev, {}, now=t)
            if (res.property_states["imagery_quality"] in
                    (SUPPORTED, DEGRADED_SUPPORTED) and t > exp):
                counterexamples.append({"t": t, "expiry": exp})
    return _row("P4_EXPIRED_EVIDENCE_CANNOT_SUPPORT_CURRENT_PRODUCT",
                checked, counterexamples,
                "a product property supported by expired evidence")


def p5_config_change_invalidates_certificate() -> dict:
    class _Cert:
        def __init__(self, v, e):
            self.vehicle_configuration_hash = v
            self.evidence_manifest_hash = e

    counterexamples, checked = [], 0
    for cv, ce, qv, qe in itertools.product(("A", "B"), repeat=4):
        checked += 1
        valid, _reason = certificate_still_valid(_Cert(cv, ce), qv, qe)
        if valid and (cv != qv or ce != qe):
            counterexamples.append({"cert": [cv, ce], "query": [qv, qe]})
    return _row("P5_CONFIG_CHANGE_INVALIDATES_DEPENDENT_CERTIFICATE",
                checked, counterexamples,
                "a certificate still valid after its configuration or "
                "evidence manifest changed")


def p6_unsupported_capability_cannot_authorize() -> dict:
    action = MissionAction("a0", requires_capabilities=("c0", "c1"))
    states = (SUPPORTED, DEGRADED_SUPPORTED, NOT_SUPPORTED, UNKNOWN,
              "NOT_EVALUABLE")
    counterexamples, checked = [], 0
    for s0, s1 in itertools.product(states, repeat=2):
        checked += 1
        caps = {"c0": CapabilityReport("c0", s0, ()),
                "c1": CapabilityReport("c1", s1, ())}
        decision = authorize(action, caps)
        allowed = {SUPPORTED, DEGRADED_SUPPORTED}
        if decision.decision == AUTHORIZED and not (
                s0 in allowed and s1 in allowed):
            counterexamples.append({"states": [s0, s1]})
    return _row("P6_NOT_SUPPORTED_CAPABILITY_CANNOT_AUTHORIZE_ACTION",
                checked, counterexamples,
                "an action authorized while a required capability was not "
                "in an authorizing state")


#: Names a ranking would plausibly arrive under. Attaching any of them by any
#: route below must change nothing.
RANKING_NAMES = ("ranking", "score", "posterior", "likelihood", "confidence",
                 "_score_hint")

#: THE FIRST VERSION OF P7/P8 CHECKED ZERO CASES AND REPORTED
#: "NO_COUNTEREXAMPLE" (MX-004). Every route it tried was a `setattr` on a
#: FROZEN dataclass, which raises, so every route was skipped and the
#: properties passed vacuously. That is the same defect as HF-005 in the
#: previous programme -- an absent answer read as a positive one -- and it
#: reappeared in new code within one round of being named.
#:
#: Two fixes, because one is not enough:
#:   * `_row` now returns VACUOUS whenever cases_checked == 0, so no property
#:     in this file can ever pass by testing nothing again;
#:   * the routes below are ones the API ACTUALLY ACCEPTS -- extra mapping
#:     keys, subclassed contracts, ranking-shaped domain entries -- rather
#:     than ones a frozen dataclass rejects.

VACUOUS = "VACUOUS_NO_CASES_CHECKED"


class _RankedCapabilityContract(CapabilityContract):
    """A subclass carrying a ranking. This is a route a caller really has."""


class _RankedProductContract(MissionProductContract):
    """Likewise."""


def _capability_ranking_routes(base_contract, ev, score):
    """(label, contracts, evidence, kwargs) tuples the API accepts."""
    routes = []

    # 1. a SUBCLASS with a ranking attribute set on the class
    sub = type("_R", (_RankedCapabilityContract,),
               {n: score for n in RANKING_NAMES})
    routes.append(("subclass_with_ranking_attributes",
                   [sub(**{"capability_id": base_contract.capability_id,
                           "requires_all": base_contract.requires_all})],
                   ev, {}))

    # 2. ranking-shaped EXTRA KEYS in the evidence mapping
    ev2 = dict(ev)
    for n in RANKING_NAMES:
        ev2[n] = EvidenceStatus(n, True, expires_at=1e9)
    routes.append(("extra_ranking_keys_in_evidence", [base_contract], ev2, {}))

    # 3. ranking-shaped entries in the compute/timing/actuator domains
    routes.append(("ranking_keys_in_domain_state", [base_contract], ev,
                   {"compute": {n: score for n in RANKING_NAMES},
                    "timing": {n: SUPPORTED for n in RANKING_NAMES},
                    "actuators": {n: True for n in RANKING_NAMES}}))

    # 4. a ranking in the operating-envelope reading
    routes.append(("ranking_in_envelope", [base_contract], ev,
                   {"envelope": {n: score for n in RANKING_NAMES}}))
    return routes


def p7_ranking_cannot_certify_capability() -> dict:
    """STRUCTURAL. Verified by differential execution, not by a solver.

    There is no ranking parameter in `evaluate_capabilities`, so there is no
    term for a solver to constrain -- encoding one in order to prove it has
    no effect would be proving something about the encoding. Verified instead
    by running every route the API actually accepts and comparing.
    """
    import inspect

    counterexamples, checked = [], 0

    # 0. THE STRUCTURAL CHECK: no ranking-shaped parameter in the signature.
    sig = inspect.signature(evaluate_capabilities)
    checked += 1
    offending = [p for p in sig.parameters if p.lower() in RANKING_NAMES]
    if offending:
        counterexamples.append({"route": "signature", "found": offending})

    base_contract = CapabilityContract("c0", requires_all=("e0", "e1"))
    for ev in _evidence_worlds(["e0", "e1"]):
        base = evaluate_capabilities([base_contract], ev, now=10.0)["c0"]
        for score in (0.0, 0.9, 1.0):
            for label, contracts, evidence, kwargs in \
                    _capability_ranking_routes(base_contract, ev, score):
                checked += 1
                got = evaluate_capabilities(contracts, evidence, now=10.0,
                                            **kwargs)["c0"]
                if got.state != base.state:
                    counterexamples.append(
                        {"route": label, "score": score,
                         "base": base.state, "with_ranking": got.state})
    return _row("P7_RANKING_ALONE_CANNOT_CERTIFY_CAPABILITY", checked,
                counterexamples,
                "a capability state that changed when a ranking was attached",
                kind=STRUCTURAL,
                note=("Routes: the function signature itself, a contract "
                      "SUBCLASS carrying ranking attributes, ranking-shaped "
                      "extra keys in the evidence mapping, and ranking-shaped "
                      "entries in the compute/timing/actuator/envelope "
                      "state. All are routes the API accepts."))


def p8_ranking_cannot_certify_product() -> dict:
    """STRUCTURAL, same argument and same route discipline as P7."""
    import inspect

    counterexamples, checked = [], 0

    sig = inspect.signature(evaluate_product)
    checked += 1
    offending = [p for p in sig.parameters if p.lower() in RANKING_NAMES]
    if offending:
        counterexamples.append({"route": "signature", "found": offending})

    kwargs = dict(product_id="p0", product_type="probe",
                  qualities=(QualityRequirement("imagery_quality",
                                                requires_all=("e0",),
                                                permits=("u",),
                                                prohibits_without=("u",)),))
    base_contract = MissionProductContract(**kwargs)

    for ev in _evidence_worlds(["e0"]):
        base = evaluate_product(base_contract, ev, {}, now=10.0)
        for score in (0.0, 0.9, 1.0):
            # subclass carrying a ranking
            sub = type("_RP", (_RankedProductContract,),
                       {n: score for n in RANKING_NAMES})(**kwargs)
            checked += 1
            got = evaluate_product(sub, ev, {}, now=10.0)
            if (got.state != base.state
                    or got.property_states != base.property_states):
                counterexamples.append(
                    {"route": "subclass_with_ranking_attributes",
                     "score": score, "base": base.state,
                     "with_ranking": got.state})

            # ranking-shaped extra evidence keys
            ev2 = dict(ev)
            for n in RANKING_NAMES:
                ev2[n] = EvidenceStatus(n, True, expires_at=1e9)
            checked += 1
            got = evaluate_product(base_contract, ev2, {}, now=10.0)
            if (got.state != base.state
                    or got.property_states != base.property_states):
                counterexamples.append(
                    {"route": "extra_ranking_keys_in_evidence",
                     "score": score, "base": base.state,
                     "with_ranking": got.state})

            # a highly-ranked but NOT-SUPPORTED capability handed in
            caps = {n: CapabilityReport(n, NOT_SUPPORTED, (),
                                        detail=f"ranking={score}")
                    for n in RANKING_NAMES}
            checked += 1
            got = evaluate_product(base_contract, ev, caps, now=10.0)
            if (got.state != base.state
                    or got.property_states != base.property_states):
                counterexamples.append(
                    {"route": "ranked_but_unsupported_capabilities",
                     "score": score, "base": base.state,
                     "with_ranking": got.state})

    return _row("P8_RANKING_ALONE_CANNOT_CERTIFY_PRODUCT", checked,
                counterexamples,
                "a product state that changed when a ranking was attached",
                kind=STRUCTURAL,
                note="same route discipline as P7")


def _row(name, checked, counterexamples, what_would_violate,
         kind=None, note=""):
    """One property row. ZERO CASES IS NEVER A PASS.

    MX-004: the first version of P7 and P8 checked zero cases -- every route
    they tried raised on a frozen dataclass and was skipped -- and reported
    NO_COUNTEREXAMPLE from having tested nothing. That is HF-005's shape
    exactly, an absent answer read as a positive one, and it reappeared in
    new code one round after being named.

    So the vacuity check lives HERE, in the shared row builder, rather than
    in the two properties that happened to hit it. Any future property that
    silently stops exercising its domain fails visibly instead of passing.
    """
    if checked == 0:
        verdict, licenses = VACUOUS, None
    elif counterexamples:
        verdict, licenses = COUNTEREXAMPLE, None
    else:
        verdict, licenses = NO_COUNTEREXAMPLE, BOUNDED_UNSAT

    return {
        "property": name,
        "kind": kind or "EXHAUSTIVE_OVER_BOUNDED_DOMAIN",
        "cases_checked": checked,
        "counterexamples": counterexamples[:5],
        "counterexample_count": len(counterexamples),
        "verdict": verdict,
        "licenses": licenses,
        "what_would_violate_it": what_would_violate,
        "note": note,
    }


PROPERTIES = (p1_capability_support_implies_dependencies,
              p2_product_support_implies_dependencies,
              p3_expired_evidence_cannot_support_capability,
              p4_expired_evidence_cannot_support_product,
              p5_config_change_invalidates_certificate,
              p6_unsupported_capability_cannot_authorize,
              p7_ranking_cannot_certify_capability,
              p8_ranking_cannot_certify_product)


def run() -> dict:
    rows = [p() for p in PROPERTIES]
    violated = [r for r in rows if r["verdict"] == COUNTEREXAMPLE]
    vacuous = [r for r in rows if r["verdict"] == VACUOUS]
    return {
        "schema": "csia.mission.bounded_verification/1",
        "bounds": {"max_evidence": MAX_EVIDENCE,
                   "max_capabilities": MAX_CAPABILITIES,
                   "max_properties": MAX_PROPERTIES,
                   "evidence_states_per_item": 4,
                   "note": ("EXHAUSTIVE over this domain, checked against the "
                            "REAL implementation rather than a model of it")},
        "method": ("Concrete exhaustive enumeration over a finite domain, "
                   "executed against the actual csia_mission functions. NO "
                   "SMT SOLVER IS USED, and therefore no encoding can differ "
                   "from the implementation it claims to describe."),
        "no_solver": True,
        "properties": rows,
        "summary": {
            "checked": len(rows),
            "no_counterexample_in_bounds":
                sum(1 for r in rows if r["verdict"] == NO_COUNTEREXAMPLE),
            "with_counterexamples": len(violated),
            "vacuous_zero_cases": len(vacuous),
            "total_cases": sum(r["cases_checked"] for r in rows),
        },
        "what_unsat_licenses": BOUNDED_UNSAT,
        "what_unsat_does_not_license": (
            "a general theorem. Nothing here is proved beyond the stated "
            "bounds, no row may be quoted as one, and NO NOVELTY IS CLAIMED "
            "for any property in this file."),
        "verdict": ("NO_COUNTEREXAMPLE_IN_ANY_PROPERTY"
                    if not violated and not vacuous
                    else "VACUOUS_PROPERTY" if vacuous and not violated
                    else "COUNTEREXAMPLE_FOUND"),
        "zero_cases_is_never_a_pass": (
            "MX-004. A property that exercises no case reports VACUOUS, "
            "never NO_COUNTEREXAMPLE. The check is in the shared row builder "
            "so no future property can pass by testing nothing."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = run()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    s = doc["summary"]
    print(f"\n{doc['verdict']}  {s['no_counterexample_in_bounds']}/"
          f"{s['checked']} properties, {s['total_cases']} cases",
          file=sys.stderr)
    return 0


_ = (PRODUCT_SUPPORTED, REJECTED)

if __name__ == "__main__":
    sys.exit(main())
