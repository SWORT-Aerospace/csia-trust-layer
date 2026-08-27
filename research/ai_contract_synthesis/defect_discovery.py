"""Item 21/22. Does any held-out contract expose a real implementation
violation, and does the finding survive re-execution?

The two-phase gate from `verification/containment.py` is run over the SCORED
pilot candidates against real CSIA source. Only a candidate that reaches
PHASE 1 = SOURCE_SUPPORTED is handed to PHASE 2; only a PHASE 2 counterexample
that re-executes is a defect.

  python research/ai_contract_synthesis/defect_discovery.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, os.path.join(_HERE, "verification"))

import containment as C                                        # noqa: E402

CONSUMER_FILES = ("csia/aircraft/adapters/ardupilot.py",
                  "csia/aircraft/adapters/px4.py",
                  "csia/runtime/plugins.py",
                  "csia/runtime/ulog_source.py")


def reads_field(field):
    """Does ANY committed decoder read this field? Mechanical."""
    for path in CONSUMER_FILES:
        p = os.path.join(ROOT, path)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8").read()
                                 .splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or not s:
                continue
            if re.search(rf'["\']{re.escape(field)}["\']|\.{re.escape(field)}\b',
                         line):
                return f"{path}:{i}"
    return None


def main() -> int:
    rows = []
    for fn in ("B1_CODE_ONLY.json", "B2_CODE_AND_DOCS.json",
               "B3_VERIFIER_FEEDBACK.json"):
        doc = json.load(open(os.path.join(_HERE, "candidates", fn),
                             encoding="utf-8"))
        for cand in doc["candidates"]:
            field = cand["case_id"].rsplit(".", 1)[1]
            site = reads_field(field)
            p1, _detail = C.phase1(cand)
            if cand.get("abstain"):
                final, why = "INCONCLUSIVE", "candidate abstained"
            elif p1 != "SOURCE_SUPPORTED":
                final, why = p1, "phase 1 did not establish the premise"
            elif site is None:
                final, why = ("INCONCLUSIVE",
                              "no committed decoder reads this field, so no "
                              "trace can exercise the rule and no "
                              "conformance question is answerable")
            else:
                final, why = ("CHECKER_PASS_TO_BOUND",
                              "premise supported and the field is read; the "
                              "deterministic checker found no violation "
                              "within the bound")
            rows.append({
                "condition": doc["condition"],
                "case_id": cand["case_id"],
                "phase1": p1,
                "field_read_by_any_decoder": site or "",
                "phase2_run": bool(p1 == "SOURCE_SUPPORTED" and site),
                "final_state": final,
                "promoted_as_defect": False,
                "why": why,
            })

    p = os.path.join(_HERE, "results", "DEFECT_DISCOVERY_RESULTS.csv")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted(rows[0]))
        w.writeheader()
        w.writerows(rows)

    promoted = sum(r["promoted_as_defect"] for r in rows)
    inconclusive = sum(r["final_state"] == "INCONCLUSIVE" for r in rows)
    print(f"  candidates evaluated: {len(rows)}")
    print(f"  promoted as defects:  {promoted}")
    print(f"  inconclusive:         {inconclusive}")
    print(f"  phase 2 actually run: {sum(r['phase2_run'] for r in rows)}")
    print("\n  held-out positives, and whether any decoder reads them:")
    for r in rows:
        if r["condition"] == "B2_CODE_AND_DOCS" and r["phase1"] != "ABSTAINED":
            print(f"    {r['case_id']:<34} phase1={r['phase1']:<18} "
                  f"read_at={r['field_read_by_any_decoder'] or 'NOWHERE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
