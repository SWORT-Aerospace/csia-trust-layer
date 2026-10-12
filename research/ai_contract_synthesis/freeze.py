"""Item 31. Hash the predictions BEFORE the reference exists, and commit.

`build_reference.py` refuses to run unless FREEZE.json is present and every
hash below still matches. So the ordering discipline is enforced by the code,
not by a promise in a README.

What this does NOT do, and cannot: make the evaluation blind. The miner, the
reference builder and this script are one model in one conversation. See
EVALUATION_VISIBILITY_MANIFEST.json -> honest_limitation.

  python research/ai_contract_synthesis/freeze.py          # write
  python research/ai_contract_synthesis/freeze.py --check  # verify
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
FREEZE = os.path.join(_HERE, "FREEZE.json")

# Everything that must exist and be fixed before any reference is built.
FROZEN = [
    "prompts/semantic_contract_miner_v1.md",
    "schemas/AI_CANDIDATE_CONTRACT.schema.json",
    "METRICS.md",
    "BENCHMARK_SPLIT.json",
    "HELD_OUT_PILOT.json",
    "DEVELOPMENT_CASE_MANIFEST.json",
    "EVALUATION_VISIBILITY_MANIFEST.json",
    "candidates/B1_CODE_ONLY.json",
    "candidates/NONSCORED_HALLUCINATION.json",
    "baselines/b0_heuristic.py",
    "verification/grounding.py",
    "verification/containment.py",
    "enumerate_universe.py",
    "select_pilot.py",
]


def digest(rel):
    p = os.path.join(_HERE, rel)
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> int:
    check = "--check" in sys.argv
    missing = [r for r in FROZEN if not os.path.exists(os.path.join(_HERE, r))]
    if missing:
        print(f"  MISSING: {missing}")
        return 1
    now = {r: digest(r) for r in FROZEN}

    if check:
        if not os.path.exists(FREEZE):
            print("  no FREEZE.json -- predictions were never frozen")
            return 2
        was = json.load(open(FREEZE, encoding="utf-8"))["hashes"]
        drift = sorted(r for r in FROZEN if was.get(r) != now[r])
        added = sorted(set(now) - set(was))
        if drift or added:
            print(f"  FROZEN ARTIFACTS CHANGED: {drift or added}")
            print("  Any evaluation after this point is not blind-ordered.")
            return 3
        print(f"  all {len(FROZEN)} frozen artifacts match")
        return 0

    payload = {
        "artifact": "FREEZE",
        "meaning": ("these files existed with these contents BEFORE "
                    "SOURCE_AUDITED_REFERENCE/ was built. That is an "
                    "ordering guarantee, not an independence guarantee."),
        "not_a_claim_of": ["blindness", "independence", "human review"],
        "hashes": now,
    }
    with open(FREEZE, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    for r in FROZEN:
        print(f"  {now[r][:16]}  {r}")
    print(f"\n  frozen {len(FROZEN)} artifacts -> FREEZE.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
