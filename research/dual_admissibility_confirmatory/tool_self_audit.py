"""Item 21: does the equivalence checker still catch the bug it once caught?

NOT A SCORED SCIENTIFIC RESULT. This is a regression guard on the instrument.

During the exploratory phase the counterexample search found a defect in the
STUDY'S OWN sidecar: it held "the last thing I saw" rather than being indexed
by time. Because the core emits the tick at tau only once a LATER sample
arrives, that sidecar answered a query for tau with state from after tau -- a
one-message phase error. The symptom was that the words IV and VV produced
identical downstream traces under a split arm, which cannot be true if the
status feature works at all.

Before that checker is frozen and relied on, it has to be shown to still
detect the defect. So the defect is deliberately re-injected into a
NON_SCORED_TEST_FIXTURE, the checker is run, and the correct implementation is
then restored and re-checked.

  python research/dual_admissibility_confirmatory/tool_self_audit.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
DEV = os.path.join(ROOT, "research", "dual_admissibility")
WITNESS = ("IV", "VV")
ARM = "S2c2"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _load("_ss", os.path.join(DEV, "semantic_search.py"))
# semantic_search loads its OWN copy of dual_arms; patching any other copy
# leaves the checker running the correct implementation and the audit
# silently passes for the wrong reason. Use the one the checker uses.
A = S.A


class PhaseMisalignedSidecar(A.GnssStatusSidecar):
    """The DEFECT, reproduced exactly: no time indexing.

    `status_contribution` answers with the most recent observation regardless
    of whether it happened before or after the queried tick. One message of
    look-ahead is all it takes.
    """

    def status_contribution(self, tau):
        if not self._msg:
            return None
        t_last, ok = self._msg[-1]          # LAST, not as-of
        if (tau - t_last) > A.MSG_FRESH_S and tau >= t_last:
            return None
        return (1.0 if ok else 0.0), 1.0

    def _hacc_ref(self, tau):
        if not self._hacc:
            return None
        return self._hacc[-1]               # LAST, not as-of


def collapse(word_a, word_b, arm):
    """Do two distinct raw words produce identical downstream state?"""
    ta = S.semantic_trace(word_a, arm)
    tb = S.semantic_trace(word_b, arm)
    key = (lambda tr: tuple((r[1], r[2], r[3], r[4], r[5], r[6])
                            for r in tr))
    return key(ta) == key(tb)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    good = A.GnssStatusSidecar
    assert S.A is A, "the checker must be using the module being patched"

    correct = collapse(*WITNESS, ARM)

    A.GnssStatusSidecar = PhaseMisalignedSidecar
    try:
        injected = collapse(*WITNESS, ARM)
    finally:
        A.GnssStatusSidecar = good          # restore, always

    restored = collapse(*WITNESS, ARM)

    detected = injected and not correct
    payload = {
        "artifact": "TOOL_SELF_AUDIT",
        "status": "NOT A SCORED SCIENTIFIC RESULT. Instrument regression "
                  "guard on a NON_SCORED_TEST_FIXTURE.",
        "witness_pair": list(WITNESS),
        "arm": ARM,
        "defect_injected": "sidecar answers with the LAST observation rather "
                           "than the one as of the queried tick -- one message "
                           "of look-ahead",
        "collapse_with_correct_implementation": correct,
        "collapse_with_defect_injected": injected,
        "collapse_after_restoring": restored,
        "checker_detects_the_defect": bool(detected),
        "implementation_restored": restored == correct,
        "reading": "the checker detects the defect if and only if the "
                   "injected run collapses the witness pair and the correct "
                   "run does not",
    }
    with open(os.path.join(OUT, "TOOL_SELF_AUDIT.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  correct implementation  -> {WITNESS[0]} == {WITNESS[1]}? "
          f"{correct}")
    print(f"  defect injected         -> {WITNESS[0]} == {WITNESS[1]}? "
          f"{injected}")
    print(f"  after restore           -> {WITNESS[0]} == {WITNESS[1]}? "
          f"{restored}")
    print(f"  CHECKER DETECTS THE DEFECT: {detected}")
    print(f"  implementation restored:    {restored == correct}")
    return 0 if detected and restored == correct else 1


if __name__ == "__main__":
    sys.exit(main())
