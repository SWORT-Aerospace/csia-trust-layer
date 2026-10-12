"""Item 12 HARD STOP. Reproduce the committed cross-path result exactly, or
stop.

  79/120 semantically non-equivalent words, shortest distinguishing trace 'I'

The numbers come from `research/dual_admissibility_confirmatory/` (commit
9071766). This script re-runs that checker and compares. It also asks the
independent question the new instrument makes possible: does a SEPARATELY
written stage probe agree with the old end-of-pipeline comparison about the
one fact they can both see?

Exit code 2 = STOP. Nothing downstream may be trusted.

  python research/evidence_semantics/reproduce_prior_results.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

OUT = os.path.join(_HERE, "results")
PRIOR = os.path.join(ROOT, "research", "dual_admissibility_confirmatory")

EXPECTED_DIVERGENCES = 79
EXPECTED_WORDS = 120
EXPECTED_SHORTEST = "I"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # ---- the committed checker, re-executed -----------------------------
    X = _load("_cross_path", os.path.join(PRIOR, "cross_path_checker.py"))
    X.main()
    with open(os.path.join(PRIOR, "results",
                           "COUNTEREXAMPLE_CROSS_PATH_RESULTS.json"),
              encoding="utf-8") as fh:
        prior = json.load(fh)
    pair = prior["pairs"]["v1_1_adapter__vs__plugins_py"]

    exact = (pair["semantic_divergences"] == EXPECTED_DIVERGENCES
             and prior["words_tested"] == EXPECTED_WORDS
             and pair["shortest_distinguishing_trace"] == EXPECTED_SHORTEST)

    # ---- the NEW instrument, on the one fact both can see ---------------
    # The old checker's semantic test is "does this path ever mark the core
    # slot invalid?". The new probe reads the same fact at T6. Agreement is
    # not a reproduction of 79/120 -- the projections differ -- but a
    # DISAGREEMENT here would mean one of the two instruments is wrong.
    import contract_checker as C                              # noqa: E402
    agree = {}
    for w in ("I", "N", "V"):
        a = C.run("v1_1_adapter", w, "gnss")
        b = C.run("plugins_py", w, "gnss")
        agree[w] = {
            "v1_1_ever_slot_invalid": any(r["T6_slot"] == "I" for r in a),
            "plugins_ever_slot_invalid": any(r["T6_slot"] == "I" for r in b),
        }
    cross_ok = (agree["I"]["v1_1_ever_slot_invalid"] is False
                and agree["I"]["plugins_ever_slot_invalid"] is True)

    payload = {
        "artifact": "PRIOR_RESULT_REPRODUCTION",
        "expected": {"semantic_divergences": EXPECTED_DIVERGENCES,
                     "words_tested": EXPECTED_WORDS,
                     "shortest_distinguishing_trace": EXPECTED_SHORTEST},
        "observed": {"semantic_divergences": pair["semantic_divergences"],
                     "words_tested": prior["words_tested"],
                     "shortest_distinguishing_trace":
                         pair["shortest_distinguishing_trace"]},
        "exact": bool(exact),
        "independent_instrument_agreement": agree,
        "independent_instrument_consistent": bool(cross_ok),
        "verdict": ("REPRODUCED" if exact and cross_ok else "STOP"),
    }
    with open(os.path.join(OUT, "PRIOR_RESULT_REPRODUCTION.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"\n  expected {EXPECTED_DIVERGENCES}/{EXPECTED_WORDS} shortest "
          f"{EXPECTED_SHORTEST!r}")
    print(f"  observed {pair['semantic_divergences']}/{prior['words_tested']} "
          f"shortest {pair['shortest_distinguishing_trace']!r}")
    print(f"  exact: {exact}")
    print(f"  new stage probe consistent with it: {cross_ok}")
    if not (exact and cross_ok):
        print("\n  STOP -- item 12 hard stop. Nothing downstream is valid.")
        return 2
    print("\n  REPRODUCED. Item 12 hard stop cleared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
