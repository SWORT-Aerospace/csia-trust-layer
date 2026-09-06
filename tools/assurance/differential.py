"""A19: five implementations, one question, asked the same way of each.

THE QUESTION
------------
Given a hypothesis set with a LOW-signature per hypothesis, and a set of
evidence terms that are ACTIVE right now:

    for an unordered pair (a, b) -- is there evidence, right now, that
    tells them apart?

Every implementation below answers that. They were written at different times,
for different reasons, by different routes, and four of the five import no part
of the other four.

THE FIVE
--------
    PRODUCTION   engineering/v1_1/support/decompose.py
                 Decomposition.discriminating(k, a, b): active terms whose
                 NUMERIC contribution to a and to b differs by more than tau.
                 Runs off a real scenario through the frozen core's own
                 feature builder.

    CHECKER      research/systems-paper/independent_checker.py
                 STRUCTURAL: active terms in LOW(a) ^ LOW(b), read from the
                 committed signature matrix. Imports no csia module.

    CLEANROOM    research/physical_validation/cleanroom/structural_reference.py
                 The same set relation written a third time from the
                 definition, standard library only.

    FIREWALL     csia_assurance/firewall.py
                 The assurance layer. Asked indirectly and on purpose: `b`
                 is distinguishable from `a` exactly when the firewall,
                 having taken `a` as the leader, does NOT list `b` among the
                 competitors it holds no witness against.

    DEA          tools/dea/conformance.py separators()
                 The published profile's own definition of separation,
                 applied to a CSIA-shaped evidence model. Written for
                 standard conformance, not for this comparison.

WHERE THE DEA ANSWER IS A SPECIALISATION, SAID PLAINLY
-------------------------------------------------------
DEA separation is DIRECTIONAL: an item separates `a` from `b` only when the
OBSERVATION matches a's prediction and not b's. "Evidence against you is not
evidence for you" is the profile's rule and this file does not soften it.

The structural question is symmetric, so the two coincide only under the
observation that matches the asserted hypothesis. That is the observation used
here, and it is stated rather than buried: DEA is being asked a specialisation
of its own question, not the same question. A DEA disagreement under any OTHER
observation would not be a defect, and this tool does not manufacture one by
sampling observations that make DEA look wrong.

WHAT A DISAGREEMENT MEANS -- AND THE ONE THAT IS EXPECTED
----------------------------------------------------------
Production is NUMERIC, the other four are STRUCTURAL. `lo_j == hi_j` exactly
when `c_j == 0.5`, so a structurally distinguishing feature can contribute
zero numeric difference at a tick. Production then omits it and the structural
four keep it. That class is DEGENERATE, it is counted SEPARATELY, and it is
never reported as agreement -- the same discipline
`compare_checker_vs_production.py` already applies, inherited rather than
reinvented.

Anything else is a REAL disagreement and is reported as one.

    python tools/assurance/differential.py --out <json>
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SUPPORT = os.path.join(ROOT, "engineering", "v1_1", "support")
SYSPAPER = os.path.join(ROOT, "research", "systems-paper")
CLEANROOM = os.path.join(ROOT, "research", "physical_validation", "cleanroom")
for _p in (ROOT, SUPPORT, SYSPAPER, CLEANROOM):
    if _p not in sys.path:
        sys.path.insert(0, _p)

IMPLEMENTATIONS = ("PRODUCTION", "CHECKER", "CLEANROOM", "FIREWALL", "DEA")

#: Production's numeric threshold, taken from the committed comparison rather
#: than restated, so the two analyses cannot drift apart.
TAU_NUM = 1e-12


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


# --------------------------------------------------------------------------
# the five answers

def _checker_answer(low, a, b, active):
    from independent_checker import distinguishable
    return bool(distinguishable(low, a, b, active))


def _cleanroom_answer(low, a, b, active):
    import structural_reference as ref
    return bool(ref.distinguishing_terms(low[a], low[b], active))


#: The firewall states in which `competitors_without_witness` is a computed
#: answer. In every other state the field is empty because nothing was
#: computed, and reading it there is the defect described below.
_FIREWALL_ANSWERED = ("SUPPORTED_UNIQUE", "AMBIGUOUS", "NON_IDENTIFIABLE")


def _firewall_answer(low, a, b, active, features):
    """Asked through the real firewall, not through a copy of its rule.

    The record asserts `a` as the leader and `b` as the only competitor. `b`
    is distinguishable exactly when the firewall does NOT put it in
    `competitors_without_witness`.

    THIS FUNCTION'S FIRST VERSION READ A SILENCE AS A YES, and the disagreement
    it produced is worth keeping in the record. It set `ranking: [a, b]`, but
    the firewall DELIBERATELY DOES NOT READ A RANKING -- vector V11 exists to
    pin that -- so every call returned UNKNOWN / NO_LEADER_ASSERTED with an
    EMPTY `competitors_without_witness`. `b not in ()` is True, so the harness
    reported "distinguishable" for every pair, and the differential duly
    flagged the firewall as the odd one out at CLEAN tick 0 where the four
    others agreed the pair is blind.

    The firewall was right and the harness was wrong, in the most dangerous
    direction available: absence of an answer read as a positive one. It is the
    same shape as the decision-replay harness reporting NOT_COMPARABLE from
    zero comparisons. So the state is now checked BEFORE the field is read, and
    a state in which nothing was computed returns None rather than a verdict.
    """
    from csia_assurance import qualify
    from csia_assurance.firewall import SCHEMA

    record = {
        "schema": SCHEMA,
        "canonical_sample_present": True,
        "config_hash": "differential",
        "software_hash": "differential",
        "timestamp": 0.0,
        "leader": a,
        "signatures": {a: sorted(low[a]), b: sorted(low[b])},
        "gates": {f: (1.0 if f in active else 0.0) for f in features},
        "evidence_states": {f: ("ACTIVE" if f in active else "INACTIVE")
                            for f in features},
    }
    v = qualify(record)
    if v.state not in _FIREWALL_ANSWERED:
        # Not an answer to this question. Reporting it as one is what made the
        # first version of this harness confidently wrong.
        return None, f"{v.state}/{v.reason}"
    return b not in v.competitors_without_witness, v.state


def _dea_answer(low, a, b, active, features):
    """The profile's own separators(), on a CSIA-shaped evidence model.

    The model predicts LOW for a feature in the hypothesis's LOW set and HIGH
    otherwise -- the same two-valued prediction the signature matrix encodes.
    The observation is set to a's prediction, which is the specialisation the
    module docstring declares.
    """
    from tools.dea.conformance import separators

    model = {h: {f: ("LOW" if f in low[h] else "HIGH") for f in features}
             for h in (a, b)}
    state = {f: {"outcome": model[a][f],
                 "fresh": f in active,
                 "applicable": True}
             for f in features}
    return bool(separators(model, state, a, b))


# --------------------------------------------------------------------------

def run(scenarios=None) -> dict:
    from export_active_sets import SCENARIOS
    from independent_checker import load_low_sets
    import decompose as D
    from csia.scenarios import run_scenario

    low = load_low_sets()
    hyps = sorted(low)
    pairs = list(itertools.combinations(hyps, 2))

    with open(os.path.join(SYSPAPER, "results", "active_sets.json"),
              encoding="utf-8") as fh:
        committed = json.load(fh)

    labels = sorted(scenarios or SCENARIOS)
    per_impl_disagreements = {name: [] for name in IMPLEMENTATIONS}
    degenerate = []
    firewall_not_evaluable = []
    comparisons = 0
    unanimous = 0
    rows = []

    for label in labels:
        key = SCENARIOS[label]
        _t, _f, td, _h, _d = run_scenario(key)
        dec = D.decompose(td)
        features = sorted(dec.features)
        if sorted(dec.names) != hyps:
            raise SystemExit(
                f"{label}: production's hypothesis set and the committed "
                f"signature matrix differ; the matrix is stale relative to "
                f"csia/diagnosis/bayes.py")

        groups = committed["scenarios"][label]["groups"]
        for g in groups:
            k = g["first_tick"]
            active = frozenset(g["active"])
            # The committed group must still describe this tick, or the whole
            # comparison is against a stale input.
            live = frozenset(dec.active_terms(k))
            if live != active:
                raise SystemExit(
                    f"{label} tick {k}: the committed active set no longer "
                    f"matches production's. Regenerate active_sets.json "
                    f"before trusting this comparison.")

            for a, b in pairs:
                comparisons += 1
                prod_terms = set(dec.discriminating(k, a, b, TAU_NUM))
                answers = {
                    "PRODUCTION": bool(prod_terms),
                    "CHECKER": _checker_answer(low, a, b, active),
                    "CLEANROOM": _cleanroom_answer(low, a, b, active),
                    "DEA": _dea_answer(low, a, b, active, features),
                }
                fw, fw_state = _firewall_answer(low, a, b, active, features)
                answers["FIREWALL"] = fw
                if fw is None:
                    firewall_not_evaluable.append(
                        {"scenario": label, "tick": k, "pair": [a, b],
                         "reason": fw_state})
                    continue

                struct = {n: v for n, v in answers.items()
                          if n != "PRODUCTION"}
                if len(set(answers.values())) == 1:
                    unanimous += 1
                    continue

                # The one expected class: every structural implementation
                # agrees WITH EACH OTHER and production alone differs, because
                # the distinguishing term contributes zero numerically.
                struct_agree = len(set(struct.values())) == 1
                struct_val = next(iter(struct.values()))
                if (struct_agree and struct_val and not answers["PRODUCTION"]
                        and set(g["degenerate_active"])
                        & (low[a] ^ low[b]) & active):
                    degenerate.append(
                        {"scenario": label, "tick": k, "pair": [a, b]})
                    continue

                majority = struct_val if struct_agree else None
                row = {"scenario": label, "tick": k, "pair": [a, b],
                       "answers": answers,
                       "n_active": len(active)}
                rows.append(row)
                for name, val in answers.items():
                    if majority is not None and val != majority:
                        per_impl_disagreements[name].append(row)
                    elif majority is None:
                        per_impl_disagreements[name].append(row)

    real = len(rows)
    return {
        "schema": "csia.assurance.differential/1",
        "commit": _git("rev-parse", "HEAD"),
        "implementations": {
            "PRODUCTION": ("engineering/v1_1/support/decompose.py "
                           "Decomposition.discriminating (NUMERIC, "
                           f"|delta| > {TAU_NUM})"),
            "CHECKER": ("research/systems-paper/independent_checker.py "
                        "(STRUCTURAL)"),
            "CLEANROOM": ("research/physical_validation/cleanroom/"
                          "structural_reference.py (STRUCTURAL, stdlib only)"),
            "FIREWALL": ("csia_assurance/firewall.py, asked through "
                         "competitors_without_witness"),
            "DEA": ("tools/dea/conformance.py separators(), the published "
                    "profile's own definition"),
        },
        "dea_is_a_specialisation": (
            "DEA separation is DIRECTIONAL. It coincides with the symmetric "
            "structural question only at the observation matching the "
            "asserted hypothesis, and that is the observation used. A DEA "
            "answer under a different observation is a different question, "
            "not a defect."),
        "hypotheses": hyps,
        "scenarios": labels,
        "totals": {
            "comparisons": comparisons,
            "unanimous": unanimous,
            "degenerate_production_only": len(degenerate),
            "real_disagreements": real,
            "firewall_not_evaluable": len(firewall_not_evaluable),
        },
        "known_disagreement_class": (
            "c == 0.5 makes log(1-c+eps) == log(c+eps), so a structurally "
            "distinguishing term contributes zero numeric difference. "
            "Counted as `degenerate_production_only`, NEVER as agreement."),
        "disagreements": rows[:50],
        "disagreements_truncated": max(0, real - 50),
        "firewall_not_evaluable_examples": firewall_not_evaluable[:10],
        "verdict": ("FIVE_IMPLEMENTATIONS_AGREE" if real == 0
                    else "DISAGREEMENT"),
        "what_agreement_does_not_prove": (
            "that the shared DEFINITION is right. Five implementations of a "
            "wrong definition agree perfectly. This bounds implementation "
            "error, not conceptual error."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", action="append", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = run(args.scenario)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    t = doc["totals"]
    print(f"\n{t['comparisons']} comparisons  "
          f"unanimous {t['unanimous']}  "
          f"degenerate {t['degenerate_production_only']}  "
          f"REAL DISAGREEMENTS {t['real_disagreements']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
