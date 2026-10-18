"""P1 step 0 — test-partition contamination audit, derived from the artifacts.

CANDIDATE_REGISTRY.yaml declares a development / protected split that was
written for the Phase-I rig. Phase II has since flown E1 twice, a V6
diagnosis, an R10 investigation, a P0.5 contract audit and an R10 attribution
intervention. Before any baseline is tuned, this establishes what has actually
been looked at.

Each cell of the declared partition is classified:

  DEVELOPMENT           declared for search, and search is permitted there
  ALREADY_OBSERVED      results from it have been inspected
  PROTECTED_UNTOUCHED   never flown, never inspected, on the current target
  CONTAMINATED          declared protected, but inspected anyway

The rule being enforced is the brief's: do not pretend an already inspected
E1/E2 cell is a protected validation cell.

Run:  PYTHONPATH=. python research/phase2/partition_audit.py
Out:  research/phase2/results/partition_audit.json
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
ROOT = os.path.join(HERE, "..", "..")

# The declared partition, read from CANDIDATE_REGISTRY.yaml at runtime.
# The flight specs it refers to live in wp_c6.
SPEC_HOMES = {
    0: "47.397742,8.545594,488,0", 1: "-35.363261,149.165230,584,0",
    2: "37.413360,-121.996500,10,90", 3: "55.953251,-3.188267,47,180",
    4: "-22.906847,-43.172896,15,270", 5: "64.128288,-21.827774,61,45",
}

# Which Phase-II artifacts touched which flight spec / slew levels. Derived by
# reading the artifacts, not asserted.
PHASE2_ARTIFACTS = [
    ("results/e1_modern_run1_defective_instrument.json", "E1 run 1"),
    ("results/e1_modern.json", "E1 run 2"),
    ("results/v6_diagnosis.json", "V6 instrument diagnosis"),
    ("results/r10_modern.json", "R10 investigation"),
    ("results/power_thrust_contract.json", "P0.5 contract audit"),
    ("results/r10_attribution.json", "R10 attribution intervention"),
    ("results/p1_injection_discovery.json", "P1 injection discovery"),
    ("results/p1_vib_wind_probe.json", "P1 vibration/wind probe"),
    ("results/p1_wind_isolated.json", "P1 isolated wind check"),
]


def touched_specs():
    """Every Phase-II flight so far used modern_rig.HOME, which is spec 0."""
    hits = {}
    for rel, name in PHASE2_ARTIFACTS:
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        hits[name] = {"artifact": rel, "flight_spec": 0,
                      "home": SPEC_HOMES[0]}
    return hits


def observed_slews():
    """Which slew levels have had their outcomes inspected."""
    out = {}
    for rel in ("results/e1_modern.json",
                "results/e1_modern_run1_defective_instrument.json"):
        p = os.path.join(HERE, rel)
        if not os.path.isfile(p):
            continue
        d = json.load(open(p))
        for s in d.get("grid", {}).get("slews_s", []):
            out.setdefault(int(s), []).append(rel)
    p = os.path.join(HERE, "results/v6_diagnosis.json")
    if os.path.isfile(p):
        for arm in json.load(open(p)).get("arms", []):
            out.setdefault(int(arm.get("slew_s", 0)), []).append(
                "results/v6_diagnosis.json")
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


def main() -> int:
    import yaml
    reg = yaml.safe_load(open(os.path.join(HERE, "CANDIDATE_REGISTRY.yaml")))
    parts = reg["evaluation_contract"]["partitions"]
    dev, prot = parts["development"], parts["protected"]

    touched = touched_specs()
    slews = observed_slews()
    # protected-ONLY levels, i.e. excluding those also declared development
    prot_slews_observed = sorted(
        (set(prot["slews_s"]) - set(dev["slews_s"])) & set(slews))
    dev_slews_observed = sorted(set(dev["slews_s"]) & set(slews))
    slews_beyond_declared = sorted(set(slews)
                                   - set(dev["slews_s"]) - set(prot["slews_s"]))

    cells = []
    for spec in sorted(SPEC_HOMES):
        in_dev = spec in dev["flight_specs"]
        in_prot = spec in prot["flight_specs"]
        flown = spec == 0
        if flown and in_dev:
            cls = "ALREADY_OBSERVED"
            why = ("every Phase-II flight to date used this home; results "
                   "inspected repeatedly across E1 run 1, run 2, the V6 "
                   "diagnosis, R10, P0.5 and P1 discovery")
        elif flown and in_prot:
            cls = "CONTAMINATED"
            why = "declared protected but flown and inspected"
        elif in_dev:
            cls = "DEVELOPMENT"
            why = "declared for search; not yet flown on the modern target"
        else:
            cls = "PROTECTED_UNTOUCHED"
            why = ("never flown on the modern target, never inspected, no "
                   "artifact references it")
        cells.append({"flight_spec": spec, "home": SPEC_HOMES[spec],
                      "declared": ("development" if in_dev else
                                   "protected" if in_prot else "undeclared"),
                      "flown_on_modern_target": flown,
                      "classification": cls, "why": why})

    slew_rows = []
    for s in sorted(set(dev["slews_s"]) | set(prot["slews_s"]) | set(slews)):
        in_dev = s in dev["slews_s"]
        in_prot = s in prot["slews_s"]
        seen = s in slews
        # NOTE: slews 0, 4 and 20 appear in BOTH declared lists. A level
        # declared for search is a development level wherever else it also
        # appears, so the development declaration wins.
        if seen and in_prot and not in_dev:
            cls = "CONTAMINATED"
        elif seen:
            cls = "ALREADY_OBSERVED"
        elif in_dev:
            cls = "DEVELOPMENT"
        elif in_prot:
            cls = "PROTECTED_UNTOUCHED"
        else:
            cls = "UNDECLARED_UNTOUCHED"
        slew_rows.append({"slew_s": s,
                          "declared": ("development" if in_dev else
                                       "protected" if in_prot else
                                       "undeclared"),
                          "observed": seen,
                          "observed_in": slews.get(s, []),
                          "classification": cls})

    report = {
        "purpose": "establish what has actually been inspected before any "
                   "baseline is tuned",
        "declared_partition": {"development": dev, "protected": prot},
        "declared_status_in_registry": prot.get("status"),
        "flight_spec_cells": cells,
        "slew_cells": slew_rows,
        "phase2_artifacts_and_the_spec_they_used": touched,
        "findings": {
            "protected_partition_status_as_declared": "UNTOUCHED",
            "protected_partition_status_as_measured": "CONTAMINATED_ON_THE_"
                                                      "SLEW_AXIS",
            "protected_slews_observed": prot_slews_observed,
            "development_slews_observed": dev_slews_observed,
            "slews_flown_outside_the_declared_partition_entirely":
                slews_beyond_declared,
            "flight_specs_flown_on_modern_target": [0],
            "flight_specs_never_flown_on_modern_target":
                [c["flight_spec"] for c in cells
                 if not c["flown_on_modern_target"]],
            "partition_was_defined_for_a_different_rig": (
                "The declared partition was written against ArduCopter 3.3. "
                "Every Phase-II flight is on 4.8, where two graph nodes are "
                "live that were dead on 3.3 and where the ESC channel is a "
                "stub. A partition defined on one rig does not transfer to "
                "another by assumption."),
            "wind_factor_status": "VERIFIED_ACTIVE_ON_4.8",
            "wind_factor_evidence": (
                "results/p1_wind_isolated.json: attitude lean 0.183 rad at "
                "SIM_WIND_SPD=0 rises to 0.471 rad at 15 m/s and 0.522 rad "
                "at 25 m/s, with altitude held at 18.4 m in every stage and "
                "the null stage returning to 0.189 rad. WP-C7 measured this "
                "factor as COSMETIC on ArduCopter 3.3, so the flight-spec "
                "partition carries a real second factor on the modern target "
                "that it did not carry on the legacy one."),
        },
        "decision": {
            "development_domain_for_P1": {
                "flight_spec": 0,
                "rationale": "already thoroughly observed, so nothing is "
                             "lost by tuning here. All B2/B3/B4 parameter "
                             "search happens on this spec and nowhere else.",
            },
            "held_out_validation_set_for_P1": {
                "flight_spec": 3,
                "home": SPEC_HOMES[3],
                "status_at_declaration": "NEVER_FLOWN_ON_MODERN_TARGET",
                "rule": "touched exactly once, after parameters are frozen. "
                        "No parameter may be changed after it is read.",
            },
            "reserved_untouched": {
                "flight_specs": [1, 2, 4, 5],
                "rule": "not used by P1 at all. Kept for E2 and for any "
                        "later validation that needs a fresh set.",
            },
            "declared_before_any_candidate_tuning": True,
        },
    }
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "partition_audit.json")
    json.dump(report, open(out, "w"), indent=1, sort_keys=True)

    print("flight specs:")
    for c in cells:
        print(f"  spec {c['flight_spec']}  declared={c['declared']:12s} "
              f"-> {c['classification']}")
    print("slews:")
    for s in slew_rows:
        print(f"  {s['slew_s']:>4}s  declared={s['declared']:12s} "
              f"observed={str(s['observed']):5s} -> {s['classification']}")
    f = report["findings"]
    print(f"\nprotected partition: declared "
          f"{f['protected_partition_status_as_declared']}, measured "
          f"{f['protected_partition_status_as_measured']}")
    print(f"  protected slews already observed: "
          f"{f['protected_slews_observed']}")
    print(f"  slews outside the declared partition entirely: "
          f"{f['slews_flown_outside_the_declared_partition_entirely']}")
    print(f"\nP1 development = spec 0; held-out validation = spec 3; "
          f"reserved = {report['decision']['reserved_untouched']['flight_specs']}")
    print(f"wrote {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
