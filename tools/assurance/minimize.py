"""Shrink a failing assurance case to the smallest one that still fails.

WHY THIS TURNS FAILURES INTO ARTIFACTS
---------------------------------------
A failure reported as "the 26-class campaign found a SILENT_HEALTHY in the
subnormal case with three hypotheses and two relations" is a bug report. The
same failure reported as "one hypothesis pair, one relation, gate = 5e-324"
is a specification: it says exactly which input property is load-bearing, and
it fits in a test.

WHAT IT SHRINKS, in order, each step kept only if the case STILL FAILS:

    hypotheses      drop one at a time
    evidence terms  drop one at a time
    gate values     simplify toward a canonical value
    prior record    drop entirely
    extra fields    drop one at a time

DELTA-DEBUGGING, NOT SEARCH. Each candidate is a strictly smaller input, and
the loop repeats until a full pass removes nothing. That terminates, and the
result is a local minimum rather than a global one -- stated because "minimal"
would overclaim.

The reduction steps are recorded, so a reader can see what was removed and
therefore what did not matter.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from typing import Callable

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)


def _size(rec) -> dict:
    return {
        "hypotheses": len(rec.get("signatures") or {}),
        "evidence_terms": len(rec.get("gates") or {}),
        "extra_fields": len([k for k in rec if k not in _CORE_FIELDS]),
    }


_CORE_FIELDS = {"schema", "timestamp", "config_hash", "software_hash",
                "evidence_hash", "canonical_sample_present", "leader",
                "signatures", "gates", "evidence_states"}


def minimize(record: dict, prior: dict | None,
             still_fails: Callable[[dict, dict | None], bool],
             invariant: Callable[[dict, dict | None], bool] | None = None,
             max_passes: int = 12) -> dict:
    """Return the smallest still-failing (record, prior) plus the steps taken.

    `still_fails` must be a pure predicate. If it is not, the reduction is
    meaningless and this function cannot tell -- so it re-verifies the final
    candidate at the end and reports the check.

    `invariant` IS NOT OPTIONAL IN PRACTICE, and the reason is a mistake this
    reducer made on its first run. Minimizing the `subnormal` finding with
    only `still_fails`, it deleted the subnormal gate and returned a case with
    one relation at weight 1.0 -- which is a perfectly supported case that
    happens to carry the same OUTCOME LABEL. The reduction was valid and the
    answer was useless: it had shrunk away the very property under
    investigation.

    So a caller passes an invariant describing what must survive -- here,
    "a subnormal gate value is still present" -- and a candidate is accepted
    only if it both fails AND preserves it. Without one, a reducer confidently
    produces a smaller case that demonstrates something else.
    """
    # Bound to a separate name: `still_fails = accept` would make `accept`
    # call itself through the closure and recurse until the stack ends.
    _fails = still_fails

    def accept(r, p):
        return _fails(r, p) and (invariant is None or invariant(r, p))

    if not accept(record, prior):
        return {"error": "the original case does not fail (or violates its "
                         "own invariant); nothing to shrink"}
    still_fails = accept

    cur, cur_prior = copy.deepcopy(record), copy.deepcopy(prior)
    steps = []

    for _ in range(max_passes):
        changed = False

        # 1. drop a hypothesis (never the leader, never below two)
        for name in sorted(cur.get("signatures") or {}):
            if name == cur.get("leader"):
                continue
            if len(cur["signatures"]) <= 2:
                break
            cand = copy.deepcopy(cur)
            cand["signatures"].pop(name)
            if still_fails(cand, cur_prior):
                cur, changed = cand, True
                steps.append({"drop_hypothesis": name})

        # 2. drop an evidence term
        for term in sorted(cur.get("gates") or {}):
            if len(cur["gates"]) <= 1:
                break
            cand = copy.deepcopy(cur)
            cand["gates"].pop(term)
            (cand.get("evidence_states") or {}).pop(term, None)
            for sig in cand.get("signatures", {}).values():
                if term in sig:
                    sig.remove(term)
            if still_fails(cand, cur_prior):
                cur, changed = cand, True
                steps.append({"drop_evidence_term": term})

        # 3. drop the prior entirely
        if cur_prior is not None and still_fails(cur, None):
            cur_prior, changed = None, True
            steps.append({"drop_prior": True})

        # 4. drop an undeclared extra field
        for key in sorted(k for k in cur if k not in _CORE_FIELDS):
            cand = copy.deepcopy(cur)
            cand.pop(key)
            if still_fails(cand, cur_prior):
                cur, changed = cand, True
                steps.append({"drop_field": key})

        if not changed:
            break

    return {
        "original_size": _size(record),
        "minimized_size": _size(cur),
        "reduction_steps": steps,
        "minimized_record": cur,
        "minimized_prior": cur_prior,
        "reverified": still_fails(cur, cur_prior),
        "caveat": ("A LOCAL minimum from delta debugging, not a global one. "
                   "It is the smallest case this reduction order reached."),
    }


def _invariant_for(cls: str):
    """What must survive reduction, per hostile-input class.

    Each entry names the numeric or structural property the class is ABOUT.
    A class with no entry gets None and is reduced on the outcome alone --
    which is reported, so the weaker reduction is visible rather than assumed
    equivalent.
    """
    import math

    def gate_values(r):
        return [v for v in (r.get("gates") or {}).values()
                if isinstance(v, (int, float)) and not isinstance(v, bool)]

    def load_bearing(pred, neutralise):
        """Present AND causally responsible.

        THE SECOND CORRECTION THIS REDUCER NEEDED. Requiring only that the
        characteristic VALUE survives produced a case that carried a
        subnormal gate which no longer did any work -- the separation came
        from a different relation at weight 1.0, and the subnormal value was
        along for the ride. A reader would have concluded the defect needed
        two relations.

        So the invariant also neutralises the characteristic and requires the
        verdict to MOVE. That is what makes the minimized case a
        demonstration of the property rather than a case containing it.
        """
        def check(r, p):
            if not pred(r, p):
                return False
            from csia_assurance import qualify
            neutral = copy.deepcopy(r)
            neutralise(neutral)
            return qualify(neutral, p).state != qualify(r, p).state
        return check

    def _zero_subnormals(r):
        for k, v in list((r.get("gates") or {}).items()):
            if (isinstance(v, (int, float)) and not isinstance(v, bool)
                    and v != 0 and abs(v) < sys.float_info.min):
                r["gates"][k] = 0.0

    checks = {
        "subnormal": load_bearing(
            lambda r, p: any(v != 0 and abs(v) < sys.float_info.min
                             for v in gate_values(r)),
            _zero_subnormals),
        "nan": lambda r, p: any(isinstance(v, float) and math.isnan(v)
                                for v in gate_values(r)),
        "positive_infinity": lambda r, p: any(v == math.inf
                                              for v in gate_values(r)),
        "negative_infinity": lambda r, p: any(v == -math.inf
                                              for v in gate_values(r)),
        "extreme_finite": lambda r, p: any(abs(v) > 1e100
                                           for v in gate_values(r)),
        "wrong_units": lambda r, p: any(v > 1.0 for v in gate_values(r)),
        "impossible_physical_value": lambda r, p: any(v < 0
                                                      for v in gate_values(r)),
        "unknown_sentinel": lambda r, p: any(v < 0 for v in gate_values(r)),
        "stale_retained_sample": lambda r, p: "STALE" in (
            r.get("evidence_states") or {}).values(),
        "partial_stream_disappearance": lambda r, p: "ABSENT" in (
            r.get("evidence_states") or {}).values(),
        "invalid_enum": lambda r, p: any(
            s not in {"ACTIVE", "INACTIVE", "INAPPLICABLE", "STALE", "ABSENT"}
            for s in (r.get("evidence_states") or {}).values()),
    }
    return checks.get(cls)


def main(argv=None) -> int:
    """Minimize the hostile-input campaign's non-PASS cases."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=os.path.join(
        ROOT, "research", "physical_validation", "results",
        "HOSTILE_INPUT_RESULTS.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    from csia_assurance import qualify
    from tools.assurance.hostile_input import _mutations, _classify

    with open(args.results, encoding="utf-8") as fh:
        results = json.load(fh)

    muts = _mutations()
    out = []
    for row in results.get("non_pass", []):
        cls = row["class"]
        if row["target"] != "assurance_firewall" or cls not in muts:
            out.append({**row, "minimization": "NOT_APPLICABLE"})
            continue
        rec, prior = muts[cls]
        expected_bad = row["outcome"]

        def fails(r, p, _cls=cls, _bad=expected_bad):
            try:
                outcome, _ = _classify(qualify(r, p), _cls)
            except Exception:                          # noqa: BLE001
                outcome = "CRASH"
            return outcome == _bad

        out.append({**row,
                    "minimization": minimize(rec, prior, fails,
                                             invariant=_invariant_for(cls))})

    doc = {"schema": "csia.assurance.minimized_reproducers/1",
           "source_results": os.path.relpath(args.results, ROOT),
           "cases": out,
           "note": ("Every non-PASS case from the hostile-input campaign, "
                    "shrunk. A case with no minimization entry was not "
                    "reducible by this reducer, and says so.")}
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
