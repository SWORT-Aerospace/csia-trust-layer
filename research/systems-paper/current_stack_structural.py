"""MECHANISM A's STRUCTURAL PREDICATE, TESTED ON REAL CURRENT-STACK TICKS.

Brief B2/B6. Claim `SC-26`.

WHAT THIS IS, AND WHAT IT IS NOT
---------------------------------
It is **not** a replication of self-occlusion. Self-occlusion needs a fault
that REMOVES the GNSS fix, and no fix-loss arm exists on ArduPilot 4.8 in this
repository. Nothing here claims one.

It is a **negative control on real current-stack data**, and it is the one
direction that could have falsified the structural account. The preregistered
Mechanism B campaign (`research/v1_1/CURRENT_STACK_REPLICATION.md`) ran 20
ArduPilot 4.8 trials whose validity criterion was that the fix NEVER dropped --
`gvalid = 1.0` on every scored tick, 0 ticks closed. Under
`research/math-paper/FORMAL_CORE.md` P3 the pair `nominal | gps_fault` is
distinguishable exactly when `phys_gps` is active, so the structural predicate
MUST report "distinguishable" on every one of those ticks.

If it reported a collapse on even one fix-preserving tick, the account in
`MECHANISM_A.md` would be wrong. It does not, on 15,595 ticks.

That is a weaker statement than a replication and a stronger one than nothing:
the predicate has been run against real ArduPilot 4.8 traces rather than only
against the bench simulator, and it behaved as the theory requires.

INDEPENDENCE
------------
Reads the committed signature table through `independent_checker`, which
imports no `csia` module and no part of the support-aware implementation, and
reads the campaign's per-trial tick CSVs. It does not import the campaign's
analysis code either.

    python research/systems-paper/current_stack_structural.py
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

TICKS = os.path.join(ROOT, "research", "v1_1", "results", "mechanism_b_gps",
                     "ticks", "*.ticks.csv")
CAMPAIGN = os.path.join(ROOT, "research", "v1_1", "results",
                        "current_stack_replication.json")
OUT = os.path.join(_HERE, "results", "current_stack_structural.json")

#: Matches the frozen core's own epsilon, as the bench-side export does.
GATE_EPS = 1e-9

#: The single relation the target pair turns on. LOW(nominal) = {} and
#: LOW(gps_fault) = {phys_gps}, so the symmetric difference is exactly this.
TARGET_FEATURE = "phys_gps"
NOMINAL, TARGET_FAULT = "nominal", "gps_fault"


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _load_low_sets():
    """Through the independent checker, by path, so this file inherits its
    independence rather than re-implementing the structural rule."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_cs_independent_checker",
        os.path.join(_HERE, "independent_checker.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_low_sets(), mod


def analyse() -> dict:
    low, checker = _load_low_sets()
    expected = low[NOMINAL] ^ low[TARGET_FAULT]
    if expected != frozenset({TARGET_FEATURE}):
        raise RuntimeError(
            f"the signature table no longer makes {TARGET_FEATURE!r} the sole "
            f"term distinguishing {NOMINAL} from {TARGET_FAULT}: {expected}. "
            f"This script's single-column reading of the tick logs is then "
            f"invalid and must not be used.")

    files = sorted(glob.glob(TICKS))
    if not files:
        raise RuntimeError(f"no tick logs at {TICKS}")

    per_condition: dict = {}
    total = closed = collapsed = 0
    falsifying = []

    for path in files:
        name = os.path.basename(path).replace(".ticks.csv", "")
        cond = name.split("_")[1]
        slot = per_condition.setdefault(
            cond, {"trials": 0, "ticks": 0, "gate_closed_ticks": 0,
                   "pair_not_distinguishable_ticks": 0})
        slot["trials"] += 1
        for row in csv.DictReader(open(path, encoding="utf-8")):
            gate = float(row["gate_applicable"])
            active = frozenset({TARGET_FEATURE}) if gate > GATE_EPS \
                else frozenset()
            distinguishable = bool(expected & active)
            total += 1
            slot["ticks"] += 1
            if gate <= GATE_EPS:
                closed += 1
                slot["gate_closed_ticks"] += 1
            if not distinguishable:
                collapsed += 1
                slot["pair_not_distinguishable_ticks"] += 1
                if len(falsifying) < 20:
                    falsifying.append({"trial": name,
                                       "tick": int(row["tick"]),
                                       "gate_applicable": gate})

    # The falsification test, stated before the numbers are read: on a
    # FIX-PRESERVING trial the predicate must never report a collapse.
    consistent = (closed == 0 and collapsed == 0)

    campaign = json.load(open(CAMPAIGN, encoding="utf-8"))
    return {
        "artifact": "CURRENT_STACK_STRUCTURAL",
        "platform": "ArduPilot 4.8 SITL",
        "is_a_replication_of_self_occlusion": False,
        "why_not": "self-occlusion requires a fault that REMOVES the GNSS "
                   "fix. These 20 trials are fix-PRESERVING by their own "
                   "validity criterion, so they cannot exhibit it. This is a "
                   "negative control, not a replication.",
        "generation_command":
            "python research/systems-paper/current_stack_structural.py",
        "commit": _git("rev-parse", "HEAD"),
        "source_ticks": os.path.relpath(os.path.dirname(TICKS), ROOT),
        "source_campaign": os.path.relpath(CAMPAIGN, ROOT),
        "campaign_verdicts": {
            "ardupilot": campaign["platforms"]["ardupilot"]["verdict"],
            "px4": campaign["platforms"]["px4"]["verdict"],
        },
        "structural_rule":
            f"D({NOMINAL}, {TARGET_FAULT}) = "
            f"(LOW({NOMINAL}) sym-diff LOW({TARGET_FAULT})) intersect ACTIVE "
            f"= {{{TARGET_FEATURE}}} intersect ACTIVE",
        "gate_eps": GATE_EPS,
        "trials": len(files),
        "ticks": total,
        "gate_closed_ticks": closed,
        "pair_not_distinguishable_ticks": collapsed,
        "per_condition": {k: per_condition[k] for k in sorted(per_condition)},
        "falsifying_ticks": falsifying,
        "predeclared_test":
            "on a fix-preserving trial the structural predicate must report "
            "the pair DISTINGUISHABLE at every tick. A single collapse would "
            "falsify the account in MECHANISM_A.md.",
        "consistent_with_the_structural_account": consistent,
        "what_this_does_not_show":
            "that self-occlusion occurs on ArduPilot 4.8. No fix-loss arm "
            "exists on that platform in this repository, and none was "
            "constructed.",
    }


def main() -> int:
    doc = analyse()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"platform: {doc['platform']}   trials: {doc['trials']}   "
          f"ticks: {doc['ticks']}")
    for cond, row in doc["per_condition"].items():
        print(f"  {cond:<8} trials={row['trials']}  ticks={row['ticks']:>5}  "
              f"gate_closed={row['gate_closed_ticks']:>3}  "
              f"pair_collapsed={row['pair_not_distinguishable_ticks']:>3}")
    print(f"\npredeclared test: {doc['predeclared_test']}")
    print(f"consistent: {doc['consistent_with_the_structural_account']}")
    print(f"NOT a replication of self-occlusion: {doc['why_not'][:70]}...")
    print(f"\n{OUT}\n  sha256 {_sha(OUT)}")
    return 0 if doc["consistent_with_the_structural_account"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
