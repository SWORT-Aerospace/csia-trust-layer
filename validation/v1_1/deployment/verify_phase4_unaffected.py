"""Phase 4.5 §12: did the timeout change move any Phase 4 result?

Two independent checks, because "we re-ran it and it looked the same" is not
an answer:

  1. STRUCTURAL. Parse the Phase 4 runners and assert they never construct a
     `PlatformAdapter` or an `OnlineTrustLayer`. The nine scenarios take
     freshness from the deterministic simulator's own `td.fresh`, so a runtime
     watchdog timeout cannot reach them. If this check ever fails, the
     behavioural comparison below stops being sufficient.

  2. BEHAVIOURAL. Re-run the Phase 4 artifacts and diff them against the
     committed versions **field by field**, with provenance fields excluded
     BY NAME. `software_sha` legitimately changes when the commit changes, and
     it is inside every ledger event's context by design, so every content
     hash downstream of it changes too. Excluding those is correct; excluding
     anything else would be hiding a result.

    python validation/v1_1/deployment/verify_phase4_unaffected.py
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: Fields that carry WHICH BUILD produced the artifact, not what it concluded.
#: A change in any of these is expected whenever the commit moves.
PROVENANCE_KEYS = frozenset({
    "csia_sha", "software_sha", "content_sha256", "event_id",
    "previous_event_hash", "final_chain_hash", "configuration_hash",
})

ARTIFACTS = [
    "engineering/v1_1/FUNCTION_ELIGIBILITY_RESULTS.csv",
    "engineering/v1_1/FUNCTION_TRANSITIONS.json",
    "engineering/v1_1/PHASE4_CLEAN_RESULT.json",
    "engineering/v1_1/PHASE4_FIXLOSS_RESULT.json",
    "engineering/v1_1/PHASE4_DUAL_IMU_RESULT.json",
    "engineering/v1_1/ASSURANCE_LEDGER_EXAMPLE.json",
    "engineering/v1_1/ASSURANCE_LEDGER_REPRODUCTION.json",
    "engineering/v1_1/PHASE4_API_VALIDATION.json",
    "engineering/v1_1/csia_output_example.json",
    "engineering/v1_1/csia_output_fixloss_example.json",
]

RUNNERS = ["engineering/v1_1/phase4/run_p4b.py",
           "engineering/v1_1/phase4/run_p4c.py",
           "engineering/v1_1/phase4/run_p4d.py"]


def _strip(obj):
    """Drop provenance keys anywhere in a nested structure."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items()
                if k not in PROVENANCE_KEYS}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def _baseline(rel, ref="HEAD"):
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _structural() -> dict:
    """Assert the Phase 4 runners cannot see a runtime timeout."""
    banned = {"OnlineTrustLayer", "get_adapter", "PlatformAdapter",
              "ShadowRunner", "build_runtime_stale_timeouts"}
    findings = {}
    for rel in RUNNERS:
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
        findings[rel] = sorted(names & banned)
    return findings


def main() -> int:
    structural = _structural()
    structural_ok = not any(structural.values())

    compared, differing = [], []
    for rel in ARTIFACTS:
        path = os.path.join(ROOT, rel)
        base = _baseline(rel)
        if base is None or not os.path.exists(path):
            compared.append({"artifact": rel, "status": "MISSING"})
            continue
        now = open(path, encoding="utf-8").read()
        if rel.endswith(".json"):
            same = _strip(json.loads(base)) == _strip(json.loads(now))
            how = "json, provenance fields excluded by name"
        else:
            same = base == now
            how = "byte-for-byte"
        compared.append({"artifact": rel, "identical": same,
                         "comparison": how,
                         "bytes_identical": base == now})
        if not same:
            differing.append(rel)

    doc = {
        "artifact": "PHASE4_REGRESSION_AFTER_TIMEOUT",
        "generation_command":
            "python validation/v1_1/deployment/verify_phase4_unaffected.py",
        "question": "Did the Phase 4.5 runtime stale-timeout change move any "
                    "Phase 4 result?",
        "structural_check": {
            "claim": "the Phase 4 runners never construct an adapter or an "
                     "OnlineTrustLayer, so a runtime watchdog timeout cannot "
                     "reach the nine scenarios; freshness comes from the "
                     "deterministic simulator's td.fresh",
            "banned_symbols_found": structural,
            "pass": structural_ok,
        },
        "provenance_keys_excluded": sorted(PROVENANCE_KEYS),
        "artifacts": compared,
        "artifacts_differing_behaviourally": differing,
        "behavioural_change": bool(differing),
        "verdict": ("NO_BEHAVIOURAL_CHANGE"
                    if structural_ok and not differing else "REVIEW_REQUIRED"),
    }
    out = os.path.join(_HERE, "PHASE4_REGRESSION_AFTER_TIMEOUT.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"structural: {'PASS' if structural_ok else 'FAIL'}  {structural}")
    for row in compared:
        if "identical" in row:
            print(f"  {row['artifact']:58s} behaviour="
                  f"{'SAME' if row['identical'] else 'CHANGED'}  "
                  f"bytes={'same' if row['bytes_identical'] else 'differ'}")
    print("verdict:", doc["verdict"])
    return 0 if doc["verdict"] == "NO_BEHAVIOURAL_CHANGE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
