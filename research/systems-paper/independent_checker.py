"""INDEPENDENT CHECKER for Mechanism A (brief B3).

    Write a minimal read-only checker that independently determines
    which terms distinguish nominal vs target fault, which are active, and
    whether the pair is distinguishable.
    The checker must NOT import the support-aware implementation.

WHAT INDEPENDENCE MEANS HERE, EXACTLY
--------------------------------------
This module imports the standard library and `yaml`. It imports:

    NOT  csia.diagnosis.bayes        (the production likelihood)
    NOT  engineering/v1_1/support/   (support.py, decompose.py)
    NOT  csia anything at all

and a test asserts that by running it in a fresh interpreter and inspecting
`sys.modules` afterwards. Its two inputs are

    research/formalization/diagnostic_signature_matrix.yaml
        the LOW-set of each hypothesis, committed, human-readable
    research/systems-paper/results/active_sets.json
        which features were active per tick, and nothing else

If it agreed with production because it was reading production's answer, the
agreement would prove nothing. It reads neither the leader, the posterior, nor
any support label.

THE ARGUMENT IT IMPLEMENTS, IN ONE PARAGRAPH
---------------------------------------------
Production's per-tick log-likelihood for hypothesis h is

    ll_h = sum_j  g_j * [ lo_j  if feature j is in LOW(h) else hi_j ]

with lo_j = log(1 - c_j + eps) and hi_j = log(c_j + eps). For two hypotheses
a and b the difference is

    ll_a - ll_b = sum_j  g_j * (lo_j - hi_j) * ( [j in LOW(a)] - [j in LOW(b)] )

Every term where j is in both LOW sets, or in neither, contributes exactly
zero -- identically, for every value of c_j. So only features in the SYMMETRIC
DIFFERENCE LOW(a) triangle LOW(b) can separate the pair, and only those with
g_j > 0. That set is what this file calls the DISTINGUISHING TERMS. When it is
empty, ll_a - ll_b = 0 at every tick, smoothing is linear so the smoothed
difference is 0 too, and the score difference collapses to the log prior
ratio. The pair is then not merely weakly separated: it is pinned, and no
amount of further data of this kind can move it.

THE ONE DEGENERATE CASE, STATED RATHER THAN HIDDEN
---------------------------------------------------
lo_j == hi_j exactly when c_j == 0.5. Such a feature is structurally
distinguishing and numerically contributes nothing at that tick. Production
tests |contribution difference| > tau and would call it non-discriminating;
this checker, being structural, calls it distinguishing. The two therefore
disagree on a measure-zero set that the exporter records explicitly as
`degenerate_active`, and the comparison script reports it as a KNOWN
DISAGREEMENT CLASS rather than as agreement.

    python research/systems-paper/independent_checker.py
"""

from __future__ import annotations

import json
import os
import sys

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

SIGNATURES = os.path.join(ROOT, "research", "formalization",
                          "diagnostic_signature_matrix.yaml")
ACTIVE_SETS = os.path.join(_HERE, "results", "active_sets.json")
OUT = os.path.join(_HERE, "results", "checker_verdicts.json")

#: The hypothesis the paper's Mechanism A is about, and its rival.
TARGET_FAULT = "gps_fault"
NOMINAL = "nominal"


def load_low_sets(path: str = SIGNATURES) -> dict:
    """{hypothesis: frozenset(features expected LOW)} from the committed
    signature matrix. This is the ONLY structural input."""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return {h: frozenset(v or ()) for h, v in doc["hypotheses"].items()}


def distinguishing_terms(low: dict, a: str, b: str) -> frozenset:
    """LOW(a) triangle LOW(b). Every other feature contributes identically to
    both hypotheses and cannot separate them at any value of c."""
    return low[a] ^ low[b]


def active_distinguishing(low: dict, a: str, b: str, active) -> frozenset:
    return distinguishing_terms(low, a, b) & frozenset(active)


def distinguishable(low: dict, a: str, b: str, active) -> bool:
    return bool(active_distinguishing(low, a, b, active))


def pinned_to_prior(low: dict, a: str, b: str, active) -> bool:
    """The strong statement: with no active distinguishing term the log
    posterior ratio equals the log prior ratio at this tick, exactly."""
    return not distinguishable(low, a, b, active)


def check_group(low: dict, active) -> dict:
    """Everything this checker can say about one distinct active set."""
    hyps = sorted(low)
    active = frozenset(active)
    pairs = {}
    for i, a in enumerate(hyps):
        for b in hyps[i + 1:]:
            terms = sorted(active_distinguishing(low, a, b, active))
            pairs[f"{a}|{b}"] = {
                "structural_terms": sorted(distinguishing_terms(low, a, b)),
                "active_distinguishing": terms,
                "distinguishable": bool(terms),
            }
    collapsed = sorted(k for k, v in pairs.items() if not v["distinguishable"])
    target_key = "|".join(sorted((NOMINAL, TARGET_FAULT)))
    return {
        "n_active": len(active),
        "evidence_available": len(active) > 0,
        "pairs": pairs,
        "collapsed_pairs": collapsed,
        "n_collapsed_pairs": len(collapsed),
        # The paper's pair, called out because it is the one Mechanism A is
        # about and burying it among 28 pairs would hide the result.
        "target_pair": target_key,
        "target_distinguishable": pairs[target_key]["distinguishable"],
        "target_active_terms": pairs[target_key]["active_distinguishing"],
    }


def run(signatures: str = SIGNATURES, active_sets: str = ACTIVE_SETS) -> dict:
    low = load_low_sets(signatures)
    with open(active_sets, encoding="utf-8") as fh:
        data = json.load(fh)

    out = {
        "artifact": "CHECKER_VERDICTS",
        "checker": "research/systems-paper/independent_checker.py",
        "independent_of": ["csia.diagnosis.bayes",
                           "engineering/v1_1/support/support.py",
                           "engineering/v1_1/support/decompose.py"],
        "inputs": {"signatures": os.path.relpath(signatures, ROOT),
                   "active_sets": os.path.relpath(active_sets, ROOT),
                   "active_sets_commit": data.get("commit")},
        "hypotheses": sorted(low),
        "target_pair": [NOMINAL, TARGET_FAULT],
        "scenarios": {},
    }
    for label in sorted(data["scenarios"]):
        scen = data["scenarios"][label]
        groups = []
        for g in scen["groups"]:
            verdict = check_group(low, g["active"])
            verdict["ticks"] = g["ticks"]
            verdict["first_tick"] = g["first_tick"]
            verdict["degenerate_active"] = g["degenerate_active"]
            # A structurally distinguishing term that is numerically
            # degenerate at this tick is the KNOWN disagreement class.
            verdict["degenerate_distinguishing"] = sorted(
                set(g["degenerate_active"]) & set(verdict["target_active_terms"]))
            groups.append(verdict)
        ticks_target_blind = sum(g["ticks"] for g in groups
                                 if not g["target_distinguishable"])
        out["scenarios"][label] = {
            "scenario": scen["scenario"],
            "ticks": scen["ticks"],
            "groups": groups,
            "ticks_target_pair_not_distinguishable": ticks_target_blind,
            "fraction_target_pair_not_distinguishable":
                round(ticks_target_blind / scen["ticks"], 6),
        }
    return out


def main() -> int:
    doc = run()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    for label in sorted(doc["scenarios"]):
        s = doc["scenarios"][label]
        print(f"  {label:<22} {s['ticks']:>5} ticks  "
              f"nominal|gps_fault NOT distinguishable for "
              f"{s['ticks_target_pair_not_distinguishable']:>5} "
              f"({100 * s['fraction_target_pair_not_distinguishable']:5.1f}%)")
    # Proof of independence, printed so a reader of the transcript can see it.
    leaked = sorted(m for m in sys.modules
                    if m.split(".")[0] in ("csia",)
                    or m in ("support", "decompose"))
    print(f"\nimported production modules: {leaked or 'NONE'}")
    print(OUT)
    return 0 if not leaked else 1


if __name__ == "__main__":
    raise SystemExit(main())
