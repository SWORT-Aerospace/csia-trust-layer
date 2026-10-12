"""Bounded verification of the assurance support semantics, with Z3.

WHAT "BOUNDED" MEANS HERE, AND WHY THE WORD IS IN EVERY VERDICT
---------------------------------------------------------------
Each property is checked by asking Z3 for a COUNTEREXAMPLE inside a small
finite universe: at most `H` hypotheses and `E` evidence terms, with binary
signatures and binary activity. If Z3 returns `unsat`, the only honest
statement is:

    "No counterexample exists within the verified bounded domain."

That is NOT a theorem about all H and all E, and this file never prints one.
`sat` is the interesting case: the model is a concrete counterexample, it is
archived, and it is minimised by `tools/assurance/minimize.py`.

WHY THE ENCODING MIRRORS THE DEFINITION AND NOT THE CODE
--------------------------------------------------------
The support semantics are one line:

    D(a, b) = (LOW(a) XOR LOW(b)) AND ACTIVE

so the Z3 encoding is that line over Booleans, written from the definition in
`docs/ASSURANCE_REFERENCE_SEMANTICS.md`. Encoding the Python instead would
verify that the Python agrees with a transcription of itself.

`--cross-check` closes that gap from the other side: it enumerates the same
small universe concretely and runs the ACTUAL firewall on each case, so the
implementation is checked against the encoding rather than assumed equal.

    python tools/assurance/bounded_verify.py --max-h 4 --max-e 6 --out <json>
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

try:
    import z3
except ImportError:                                    # pragma: no cover
    z3 = None

#: Every property carries the exact sentence its UNSAT result licenses.
BOUNDED_UNSAT = "No counterexample exists within the verified bounded domain."


def _sig_vars(s, H, E):
    """low[h][e] -- is term e expected LOW under hypothesis h."""
    return [[z3.Bool(f"{s}_low_{h}_{e}") for e in range(E)] for h in range(H)]


def _act_vars(s, E):
    return [z3.Bool(f"{s}_act_{e}") for e in range(E)]


def _D(low, act, a, b, E):
    """The distinguishing set is non-empty: some active term differs."""
    return z3.Or([z3.And(act[e], low[a][e] != low[b][e]) for e in range(E)])


def _solve(name, statement, constraints, H, E, extract):
    s = z3.Solver()
    s.set("timeout", 60_000)
    for c in constraints:
        s.add(c)
    result = s.check()
    row = {"property": name, "statement": statement, "bound_H": H,
           "bound_E": E, "result": str(result)}
    if result == z3.sat:
        row["verdict"] = "COUNTEREXAMPLE_FOUND"
        row["counterexample"] = extract(s.model())
    elif result == z3.unsat:
        row["verdict"] = "NO_COUNTEREXAMPLE_IN_BOUNDED_DOMAIN"
        row["licensed_statement"] = BOUNDED_UNSAT
        row["not_licensed"] = ("a general theorem; nothing here is proved "
                               "for H or E beyond the stated bounds")
    else:
        row["verdict"] = "UNKNOWN_SOLVER_RESULT"
        row["note"] = "timeout or incompleteness; NOT a pass"
    return row


def _model_dump(m, low, act, H, E):
    def b(x):
        v = m.eval(x, model_completion=True)
        return bool(z3.is_true(v))
    return {
        "low": {f"h{h}": [f"e{e}" for e in range(E) if b(low[h][e])]
                for h in range(H)},
        "active": [f"e{e}" for e in range(E) if b(act[e])],
    }


def check_all(H: int, E: int) -> list:
    """The eight properties, each as a satisfiability question."""
    rows = []

    # ---- P1 RANKING INDEPENDENCE, P2 PRIOR INDEPENDENCE -------------------
    #
    # These two are STRUCTURAL FACTS about the encoding, not solver questions:
    # neither a ranking value nor a prior appears anywhere in D(a,b), so no
    # assignment of them can change it. Asking Z3 about a variable the
    # formula does not contain would produce a vacuous unsat and look like
    # evidence. So they are checked by the cross-check instead, which varies
    # the actual ranking and prior fields through the real firewall, and this
    # file records why they are not solver rows.
    for name, what in (("P1_RANKING_INDEPENDENCE", "ranking values"),
                       ("P2_PRIOR_INDEPENDENCE", "prior values")):
        rows.append({
            "property": name, "bound_H": H, "bound_E": E,
            "result": "NOT_A_SOLVER_QUESTION",
            "verdict": "STRUCTURAL_BY_CONSTRUCTION",
            "statement": f"changing {what} alone cannot create structural "
                         f"support",
            "why_not_encoded": (
                f"{what} do not appear in D(a,b) = (LOW(a) XOR LOW(b)) AND "
                f"ACTIVE. Encoding an absent variable would yield a vacuous "
                f"unsat that reads as evidence. Checked instead by "
                f"--cross-check, which varies the real field through the real "
                f"firewall."),
        })

    # ---- P3 SYMMETRY ------------------------------------------------------
    low, act = _sig_vars("p3", H, E), _act_vars("p3", E)
    rows.append(_solve(
        "P3_SYMMETRY", "D(a,b) is non-empty iff D(b,a) is non-empty",
        [z3.Or([_D(low, act, a, b, E) != _D(low, act, b, a, E)
                for a in range(H) for b in range(H) if a != b])],
        H, E, lambda m: _model_dump(m, low, act, H, E)))

    # ---- P4 IRRELEVANT-EVIDENCE INDEPENDENCE ------------------------------
    #
    # Deactivating a term that does not differ between a and b cannot change
    # whether they are distinguishable.
    low, act = _sig_vars("p4", H, E), _act_vars("p4", E)
    act2 = _act_vars("p4b", E)
    k = z3.Int("p4_k")
    cons = [k >= 0, k < E]
    for e in range(E):
        # act2 equals act everywhere except possibly at index k, where the
        # term is non-discriminating for the pair (0,1) and is switched off.
        cons.append(z3.Implies(k != e, act2[e] == act[e]))
    cons.append(z3.Or([z3.And(k == e, low[0][e] == low[1][e],
                              z3.Not(act2[e])) for e in range(E)]))
    cons.append(_D(low, act, 0, 1, E) != _D(low, act2, 0, 1, E))
    rows.append(_solve(
        "P4_IRRELEVANT_EVIDENCE_INDEPENDENCE",
        "removing a term that does not discriminate a,b cannot change D(a,b)",
        cons, H, E,
        lambda m: {**_model_dump(m, low, act, H, E),
                   "active_after": [f"e{e}" for e in range(E)
                                    if z3.is_true(m.eval(act2[e],
                                                         model_completion=True))]}))

    # ---- P5 ADDITION MONOTONICITY, PAIR SPECIFIC --------------------------
    #
    # Activating one more term cannot destroy an existing distinguishability
    # between the same pair.
    low, act = _sig_vars("p5", H, E), _act_vars("p5", E)
    act2 = _act_vars("p5b", E)
    cons = [z3.And([z3.Implies(act[e], act2[e]) for e in range(E)]),
            _D(low, act, 0, 1, E), z3.Not(_D(low, act2, 0, 1, E))]
    rows.append(_solve(
        "P5_ADDITION_MONOTONICITY_PAIR_SPECIFIC",
        "activating further evidence cannot destroy a pair's existing "
        "distinguishability",
        cons, H, E,
        lambda m: _model_dump(m, low, act, H, E)))

    # ---- P6 SUPPORT-WITNESS REQUIREMENT -----------------------------------
    low, act = _sig_vars("p6", H, E), _act_vars("p6", E)
    supported = z3.And([_D(low, act, 0, j, E) for j in range(1, H)])
    cons = [supported, z3.Or([z3.Not(_D(low, act, 0, j, E))
                              for j in range(1, H)])]
    rows.append(_solve(
        "P6_SUPPORT_WITNESS_REQUIREMENT",
        "SUPPORTED_UNIQUE(h) implies an active discriminator against every "
        "modeled competitor",
        cons, H, E, lambda m: _model_dump(m, low, act, H, E)))

    # ---- P7 CONFIGURATION INVALIDATION ------------------------------------
    #
    # If a load-bearing discriminator's activity changes, the previous
    # SUPPORTED_UNIQUE cannot simply carry over.
    low, act = _sig_vars("p7", H, E), _act_vars("p7", E)
    act2 = _act_vars("p7b", E)
    before = z3.And([_D(low, act, 0, j, E) for j in range(1, H)])
    after = z3.And([_D(low, act2, 0, j, E) for j in range(1, H)])
    changed = z3.Or([act[e] != act2[e] for e in range(E)])
    # A counterexample would be: config changed in a way that removes support,
    # yet the "before" verdict is still the one that would be reported.
    cons = [before, changed, z3.Not(after)]
    p7 = _solve(
        "P7_CONFIGURATION_INVALIDATION_HAZARD_EXISTS",
        "a configuration change that removes a load-bearing discriminator "
        "CAN remove support. SAT here is the EXPECTED and desired result: it "
        "demonstrates the hazard is real, which is what makes the "
        "recomputation rule load-bearing rather than decorative. It is not a "
        "falsification of P7.",
        cons, H, E, lambda m: _model_dump(m, low, act, H, E),
    )
    rows.append(p7)

    # P7 proper: take the hazard the solver just produced and run it through
    # the REAL implementation. A hazard nobody checked the implementation
    # against would be a solver result about a formula, not about CSIA.
    if p7.get("verdict") == "COUNTEREXAMPLE_FOUND":
        rows.append(_p7_followthrough(p7["counterexample"], H, E))
    else:
        rows.append({
            "property": "P7_CONFIGURATION_INVALIDATION",
            "bound_H": H, "bound_E": E,
            "result": "NOT_EXERCISED",
            "verdict": "NO_HAZARD_INSTANCE_TO_TEST",
            "statement": ("the hazard search returned no instance, so the "
                          "implementation could not be exercised against "
                          "one. NOT a pass."),
        })

    # ---- P8 EXPIRY --------------------------------------------------------
    #
    # A witness that depended only on terms that are no longer active cannot
    # still be current.
    low, act = _sig_vars("p8", H, E), _act_vars("p8", E)
    act2 = _act_vars("p8b", E)
    cons = [
        _D(low, act, 0, 1, E),
        z3.And([z3.Implies(act2[e], act[e]) for e in range(E)]),
        z3.And([z3.Implies(z3.And(act[e], low[0][e] != low[1][e]),
                           z3.Not(act2[e])) for e in range(E)]),
        _D(low, act2, 0, 1, E),
    ]
    rows.append(_solve(
        "P8_EXPIRY",
        "a witness resting only on terms that have gone inactive cannot "
        "remain valid",
        cons, H, E, lambda m: _model_dump(m, low, act, H, E)))

    return rows


def _p7_followthrough(model: dict, H: int, E: int) -> dict:
    """Run the solver's hazard instance through the real firewall.

    Builds the BEFORE configuration from the model, takes a certificate, then
    switches off one discriminator the certificate rested on and asks whether
    that certificate is still current. The answer must be NO.
    """
    from csia_assurance import (SEMANTICS_VERSION, build_certificate,
                                qualify)
    from csia_assurance.firewall import SCHEMA
    from csia_assurance.witness import certificate_is_current

    terms = [f"e{j}" for j in range(E)]
    signatures = {f"h{h}": list(model["low"].get(f"h{h}", []))
                  for h in range(H)}
    active = set(model.get("active", []))
    base = {"schema": SCHEMA, "timestamp": 1.0, "config_hash": "cfg-before",
            "software_hash": "sw", "evidence_hash": "ev",
            "canonical_sample_present": True, "leader": "h0",
            "signatures": signatures,
            "gates": {t: (1.0 if t in active else 0.0) for t in terms},
            "evidence_states": {t: "ACTIVE" for t in terms}}

    before = qualify(base)
    cert = build_certificate(before, base, SEMANTICS_VERSION)

    # Switch off every term the certificate's witnesses rested on.
    load_bearing = {d for w in cert.witnesses
                    for d in w.active_discriminator_ids}
    after_rec = dict(base, timestamp=2.0, config_hash="cfg-after",
                     gates={t: (0.0 if t in load_bearing else
                                base["gates"][t]) for t in terms})
    after = qualify(after_rec)
    still_current, why = certificate_is_current(cert, after_rec,
                                                SEMANTICS_VERSION)

    held = (before.state == "SUPPORTED_UNIQUE"
            and after.state != "SUPPORTED_UNIQUE"
            and still_current is False)
    return {
        "property": "P7_CONFIGURATION_INVALIDATION",
        "bound_H": H, "bound_E": E,
        "result": "EXERCISED_AGAINST_IMPLEMENTATION",
        "verdict": "HOLDS" if held else "VIOLATED",
        "statement": ("a certificate does not survive a configuration change "
                      "that removes a load-bearing discriminator"),
        "evidence": {
            "before_state": before.state,
            "after_state": after.state,
            "load_bearing_discriminators": sorted(load_bearing),
            "certificate_still_current": still_current,
            "staleness_reason": why,
        },
        "note": ("This row uses the SOLVER'S OWN hazard instance against the "
                 "real firewall, so it is a statement about CSIA rather than "
                 "about a formula."),
    }


def cross_check(H: int, E: int, limit: int = 20000) -> dict:
    """Enumerate the same small universe and run the REAL firewall on it.

    This is what stops the Z3 encoding from being verified against itself. It
    also carries P1 and P2, which are not solver questions: for every case it
    perturbs the ranking value and the prior and asserts the verdict does not
    move.
    """
    from csia_assurance import qualify
    from csia_assurance.firewall import SCHEMA

    names = [f"h{i}" for i in range(H)]
    terms = [f"e{j}" for j in range(E)]
    checked = mismatches = p1p2 = 0
    failures = []

    sig_space = list(itertools.product([0, 1], repeat=E))
    for sigs in itertools.product(sig_space, repeat=H):
        for act in itertools.product([0, 1], repeat=E):
            if checked >= limit:
                break
            signatures = {n: [terms[j] for j in range(E) if s[j]]
                          for n, s in zip(names, sigs)}
            gates = {terms[j]: float(act[j]) for j in range(E)}
            rec = {"schema": SCHEMA, "timestamp": 1.0, "config_hash": "c",
                   "software_hash": "s", "evidence_hash": "e",
                   "canonical_sample_present": True, "leader": names[0],
                   "signatures": signatures, "gates": gates,
                   "evidence_states": {t: "ACTIVE" for t in terms}}
            v = qualify(rec)

            # The definition, computed directly here.
            active = {terms[j] for j in range(E) if act[j]}
            expect_empty = [
                n for n in names[1:]
                if not ((set(signatures[names[0]]) ^ set(signatures[n]))
                        & active)]
            expected = ("SUPPORTED_UNIQUE" if not expect_empty
                        else "NON_IDENTIFIABLE"
                        if len(expect_empty) == H - 1 else "AMBIGUOUS")
            checked += 1
            if v.state != expected:
                mismatches += 1
                if len(failures) < 5:
                    failures.append({"signatures": signatures,
                                     "gates": gates,
                                     "expected": expected, "got": v.state})

            # P1 and P2: fields the semantics must not read.
            perturbed = dict(rec, leader_weight=0.99999, ranking=[1, 2, 3],
                             priors={n: 0.5 for n in names})
            if qualify(perturbed).state != v.state:
                p1p2 += 1
                if len(failures) < 10:
                    failures.append({"property": "P1/P2",
                                     "signatures": signatures,
                                     "gates": gates})
        if checked >= limit:
            break

    return {"cases_checked": checked, "semantic_mismatches": mismatches,
            "ranking_or_prior_sensitivities": p1p2, "failures": failures,
            "note": ("Enumerated concretely and run through the ACTUAL "
                     "firewall, so the Z3 encoding is checked against the "
                     "implementation rather than against a transcription of "
                     "it. P1 and P2 live here because a ranking value and a "
                     "prior do not appear in the encoding at all.")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-h", type=int, default=4)
    ap.add_argument("--max-e", type=int, default=6)
    ap.add_argument("--cross-check-h", type=int, default=3)
    ap.add_argument("--cross-check-e", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    if z3 is None:
        print("z3-solver is not installed", file=sys.stderr)
        return 2

    rows = check_all(args.max_h, args.max_e)
    doc = {
        "schema": "csia.assurance.bounded_verification/1",
        "solver": f"z3 {z3.get_version_string()}",
        "bounds": {"max_hypotheses": args.max_h, "max_evidence": args.max_e},
        "what_unsat_licenses": BOUNDED_UNSAT,
        "what_unsat_does_not_license": (
            "a general theorem. Nothing here is proved beyond the stated "
            "bounds, and no row may be quoted as one."),
        "properties": rows,
        "cross_check": cross_check(args.cross_check_h, args.cross_check_e),
        "summary": {
            "checked_by_solver": sum(1 for r in rows
                                     if r["result"] != "NOT_A_SOLVER_QUESTION"),
            "structural_by_construction": sum(
                1 for r in rows if r["result"] == "NOT_A_SOLVER_QUESTION"),
            "counterexamples": sum(1 for r in rows
                                   if r["verdict"] == "COUNTEREXAMPLE_FOUND"),
            "no_counterexample_in_bounds": sum(
                1 for r in rows
                if r["verdict"] == "NO_COUNTEREXAMPLE_IN_BOUNDED_DOMAIN"),
            "unknown_solver_results": sum(
                1 for r in rows if r["verdict"] == "UNKNOWN_SOLVER_RESULT"),
        },
    }
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
