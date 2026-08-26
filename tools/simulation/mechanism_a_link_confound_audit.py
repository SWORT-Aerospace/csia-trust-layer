"""Did the PX4 passive-link starvation confound the Mechanism A result?

THE QUESTION. `research/v1_1/PX4_LINK_RATE_FINDING.md` established that PX4
stream delivery is LINK/CONFIGURATION-CONDITIONED: the driven qualification
connection requests the stream and receives ~10 Hz, while CSIA's passive shadow
connection requests nothing and receives the lower default. Against a freshness
contract derived from 10 Hz, that left `baro.altitude` delivered at ~1 Hz to the
shadow consumer and `altitude_baro` carrying weight on 8.1 % of ticks.

(This is NOT a claim that PX4 intrinsically supplies the channel at 1 Hz, nor
that the declared 10 Hz is universally wrong. An earlier artifact labelled it
RATE_MISDECLARED; a controlled link-rate experiment falsified that reading and
the label is superseded by STARVED_BY_TRANSPORT.)

Mechanism A claims `SOI(gps_fault) = 1.0` -- fix loss removes the evidence
required to attribute `gps_fault`. If part of that evidence was ALREADY missing
because the transport starved it, the headline could be an artifact of the link
configuration rather than a property of the fault.

WHAT DECIDES IT, and it is structural rather than statistical. Every relation
that feeds `gps_fault` is gated on `gvalid`, the GNSS-validity flag
(`online.py:482`). Fix loss sets `gvalid = 0`, which multiplies EVERY such gate
to zero regardless of how much weight it carried beforehand. Starvation can
therefore only lower the PRE-fault pool; it cannot change the POST-fault state,
which is zero either way.

That is the argument, and this tool does not take it on trust: it parses the
gate expression of every relation out of the frozen source and checks that
`gvalid` actually appears in each one. If a relation feeding `gps_fault` were
ever gated on something else, the argument would not hold and the audit says so
instead of concluding.

WHAT STARVATION DOES COST. It narrows the demonstration. On ArduPilot the fault
removes three relations carrying weight; on PX4 it removes one, because the
other three were already dark -- one starved by the LINK CONDITION, one
structurally absent (SIH publishes no second IMU), one closed by the operating
regime (every flight is a hover, and `heading_course` needs 2.0 m/s). A reader
comparing the two platforms must be told that, and must not be told that PX4
"lacks" the evidence.

Reads committed artifacts and frozen source. Runs nothing, re-flies nothing.

  python tools/simulation/mechanism_a_link_confound_audit.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

LEDGER = os.path.join(ROOT, "research", "v1_1", "results",
                      "EVIDENCE_COVERAGE_LEDGER.json")
PROBE = os.path.join(ROOT, "research", "v1_1", "results",
                     "PX4_LINK_RATE_PROBE.json")
_ECL = os.path.join(ROOT, "tools", "simulation", "evidence_coverage_ledger.py")

# The validity flag whose collapse IS the mechanism under test.
VALIDITY_FLAG = "gvalid"
# Verdicts that mean "the TRANSPORT did not deliver this fast enough", as
# opposed to the platform not producing it or the flight profile not calling
# for it. STARVED_BY_TRANSPORT supersedes the falsified RATE_MISDECLARED.
STARVATION_VERDICTS = ("STARVED_BY_TRANSPORT", "DARK_STARVED")


def _load_ledger_module():
    spec = importlib.util.spec_from_file_location("_ecl_audit", _ECL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _why_dark(ledger, platform, relation):
    """The ledger's own account of why a relation carried no weight."""
    plat = (ledger.get("ledger") or {}).get(platform) or {}
    row = (plat.get("relations") or {}).get(relation)
    if row is None:
        return {"verdict": "NOT_IN_LEDGER", "live_share": None,
                "endpoints": {}}
    return {
        "verdict": row.get("verdict"),
        "live_share": row.get("relation_live_share"),
        "endpoints": {
            n: {"channel": e.get("channel"),
                "declared_hz": e.get("declared_hz"),
                "measured_hz": e.get("measured_hz"),
                "channel_usable_share": e.get("channel_usable_share")}
            for n, e in (row.get("endpoints") or {}).items()},
    }


def audit_platform(platform, gates_by_relation, ledger):
    path = os.path.join(ROOT, "research", "v1_1", "results",
                        f"mechanism_a_{platform}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        res = json.load(fh)

    control, fault = res.get("control") or {}, res.get("fault") or {}
    # The relations that actually feed gps_fault, taken from the recorded
    # snapshot rather than from a list written by hand.
    snaps_c = control.get("snapshots") or {}
    snaps_f = fault.get("snapshots") or {}
    rels = sorted({r for s in snaps_c.values()
                   for r in (s.get("gps_gates") or {})})

    # STRUCTURAL CHECK: is every one of them gated on the validity flag?
    gate_check = {}
    for r in rels:
        expr = gates_by_relation.get(r, "NOT FOUND")
        gate_check[r] = {"gate_expression": expr,
                         "carries_validity_flag": VALIDITY_FLAG in expr}
    all_gated_on_validity = all(v["carries_validity_flag"]
                                for v in gate_check.values())

    def _sum(snaps, key):
        s = snaps.get(key) or {}
        return s.get("gps_gate_weight_sum")

    pre_sum = _sum(snaps_f, "at")
    post_sum = _sum(snaps_f, "post")
    late_sum = _sum(snaps_f, "late")
    control_sum = _sum(snaps_c, "late")

    # Which relations were dark BEFORE the fault, and why.
    dark_before, starved_before = {}, []
    at = (snaps_c.get("late") or {}).get("gps_gates") or {}
    for r, val in sorted(at.items()):
        if float(val[1]) > 1e-9:
            continue
        why = _why_dark(ledger, platform, r)
        dark_before[r] = why
        if why["verdict"] in STARVATION_VERDICTS:
            starved_before.append(r)

    # RULE B: the injection is only real if the vehicle showed the observable.
    iq = (fault.get("intermediate_quantity") or {})

    mechanism_holds = (post_sum == 0.0 and late_sum == 0.0
                       and (control_sum or 0) > 0
                       and int(iq.get("ticks_observed") or 0) > 0)

    if not mechanism_holds:
        conclusion = "INDETERMINATE"
        why = ("the recorded snapshots do not show the pre-fault pool "
               "collapsing to zero with the RULE B observable present")
    elif not all_gated_on_validity:
        conclusion = "INDETERMINATE"
        why = ("a relation feeding gps_fault is not gated on "
               f"{VALIDITY_FLAG!r}, so starvation cannot be ruled out "
               "structurally")
    elif not starved_before:
        conclusion = "UNAFFECTED"
        why = ("no relation feeding gps_fault was dark from transport "
               "starvation before the fault")
    else:
        live_before = len(rels) - len(dark_before)
        by_cause = {}
        for rel, w in dark_before.items():
            by_cause.setdefault(w["verdict"], []).append(rel)
        conclusion = "PARTIALLY_AFFECTED"
        why = (f"the fault removed {control_sum} unit(s) of evidence carried "
               f"by {live_before} of {len(rels)} relations, because "
               f"{len(dark_before)} were ALREADY dark before it: "
               + "; ".join(f"{v} = {k}" for k, v in sorted(by_cause.items()))
               + f". {sorted(starved_before)} is dark from TRANSPORT "
                 f"starvation on this consumer's link, so the demonstration is "
                 f"narrower than the platform allows -- which is a statement "
                 f"about the link configuration, not about PX4. It does not change the post-fault state: "
                 f"every relation feeding gps_fault is gated on "
                 f"{VALIDITY_FLAG!r}, so fix loss drives all of them to zero "
                 f"whether or not they were starved")

    return {
        "platform": platform,
        "result": res.get("claim_under_test"),
        "trial_valid": res.get("trial_valid"),
        "required_relations": rels,
        "required_channels": sorted({
            e.get("channel")
            for r in rels
            for e in (_why_dark(ledger, platform, r)["endpoints"] or {}).values()
            if e.get("channel")}),
        "gate_structure": gate_check,
        "every_relation_gated_on_validity_flag": all_gated_on_validity,
        "gps_gate_weight_sum": {
            "control_arm": control_sum,
            "fault_arm_at_onset": pre_sum,
            "fault_arm_post": post_sum,
            "fault_arm_late": late_sum},
        "rule_b_observable": {"name": iq.get("name"),
                              "ticks_observed": iq.get("ticks_observed"),
                              "first_t": iq.get("first_t")},
        "escalation_levels_seen": {"control": control.get("levels_seen"),
                                   "fault": fault.get("levels_seen")},
        "dark_before_fault": dark_before,
        "measured_availability": {
            r: _why_dark(ledger, platform, r)["live_share"] for r in rels},
        "affected_by_passive_link_starvation": bool(starved_before),
        "starved_relations": sorted(starved_before),
        "conclusion": conclusion,
        "conclusion_basis": why,
        "artifact_sources": [
            f"research/v1_1/results/mechanism_a_{platform}.json",
            "research/v1_1/results/EVIDENCE_COVERAGE_LEDGER.json",
            "research/v1_1/results/PX4_LINK_RATE_PROBE.json",
            "csia/runtime/online.py (gate expressions, parsed)"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(
        ROOT, "research", "v1_1", "results",
        "MECHANISM_A_LINK_CONFOUND_AUDIT.json"))
    args = ap.parse_args()

    if not os.path.exists(LEDGER):
        print("run tools/simulation/evidence_coverage_ledger.py first")
        return 2
    with open(LEDGER, encoding="utf-8") as fh:
        ledger = json.load(fh)
    gates = _load_ledger_module().gate_expressions()

    rows = {}
    for plat in ("ardupilot", "px4"):
        row = audit_platform(plat, gates, ledger)
        if row:
            rows[plat] = row

    if not rows:
        print("no Mechanism A artifacts found")
        return 2

    print("=== Mechanism A: did the passive-link starvation confound it?")
    for plat, r in sorted(rows.items()):
        w = r["gps_gate_weight_sum"]
        print(f"\n  {plat}")
        print(f"    relations feeding gps_fault : {r['required_relations']}")
        print(f"    all gated on {VALIDITY_FLAG!r}         : "
              f"{r['every_relation_gated_on_validity_flag']}")
        print(f"    gps gate weight  control    : {w['control_arm']}")
        print(f"    gps gate weight  post-fault : {w['fault_arm_post']}")
        print(f"    RULE B observable ticks     : "
              f"{r['rule_b_observable']['ticks_observed']}")
        if r["dark_before_fault"]:
            print("    dark BEFORE the fault:")
            for rel, why in sorted(r["dark_before_fault"].items()):
                print(f"      {rel:26s} {why['verdict']}")
        print(f"    -> {r['conclusion']}")
        print(f"       {r['conclusion_basis']}")

    verdicts = {p: r["conclusion"] for p, r in rows.items()}
    out = {
        "question": "did the PX4 passive-link transport starvation confound "
                    "Mechanism A?",
        "decides_it": (f"every relation feeding gps_fault is gated on "
                       f"{VALIDITY_FLAG!r}; fix loss sets it to zero, which "
                       f"multiplies every such gate to zero regardless of the "
                       f"weight it carried beforehand. Starvation can lower "
                       f"the PRE-fault pool and cannot change the POST-fault "
                       f"state. Verified by parsing the frozen source, not "
                       f"asserted"),
        "cost_of_starvation": ("it narrows the demonstration rather than "
                               "invalidating it, and the narrowing must be "
                               "reported: a smaller PX4 pool is not evidence "
                               "that PX4 lacks the relations, and not evidence "
                               "about PX4 at all -- it is a property of the "
                               "passive link configuration under test"),
        "superseded_label": ("an earlier artifact called the baro case "
                             "RATE_MISDECLARED; that reading was falsified by "
                             "the link-rate experiment and must not be "
                             "propagated"),
        "verdicts": verdicts,
        "platforms": rows,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    print(f"\n-> {os.path.relpath(args.out, ROOT)}")
    # A confounded or indeterminate headline is a BLOCKER and must not be a
    # quiet zero exit.
    bad = [p for p, v in verdicts.items()
           if v in ("CONFOUNDED", "INDETERMINATE")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
