"""Select the held-out pilot subset MECHANICALLY (item 30: 8-15 cases).

The selection rule contains no judgement about which cases are interesting:

  * stratify on `consumed_by_csia`, because item 9 requires negative cases and
    a field the adapter never reads is the natural negative;
  * stratify on message, so the pilot is not eight fields of one message;
  * within a stratum, order by SHA-256 of the case id under a fixed salt and
    take the first.

The salt is fixed here and committed. Re-running gives the same pilot.

  python research/ai_contract_synthesis/select_pilot.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
SALT = "csia-ai-contract-synthesis-pilot-v1"
TARGET = 14                    # inside item 30's 8-15 band
MAX_PER_MESSAGE = 2            # so the pilot is not one message eight times


def rank(case_id):
    return hashlib.sha256((SALT + "|" + case_id).encode()).hexdigest()


def main() -> int:
    split = json.load(open(os.path.join(_HERE, "BENCHMARK_SPLIT.json"),
                           encoding="utf-8"))
    held = [c for c in split["cases"] if c["split"] == "HELD_OUT"]

    picked, per_msg = [], {}
    # alternate strata so the pilot carries both consumed and unconsumed
    # fields rather than whatever the hash happens to favour
    want_consumed = True
    pool = sorted(held, key=lambda c: rank(c["case_id"]))
    while len(picked) < TARGET:
        made_progress = False
        for c in pool:
            if c in picked:
                continue
            if c["consumed_by_csia"] != want_consumed:
                continue
            if per_msg.get(c["message"], 0) >= MAX_PER_MESSAGE:
                continue
            picked.append(c)
            per_msg[c["message"]] = per_msg.get(c["message"], 0) + 1
            made_progress = True
            break
        want_consumed = not want_consumed
        if not made_progress and len(picked) < TARGET:
            # one stratum exhausted; try the other, and stop if both are
            if all(c in picked or per_msg.get(c["message"], 0) >= MAX_PER_MESSAGE
                   for c in pool):
                break

    payload = {
        "artifact": "HELD_OUT_PILOT",
        "rule": ("stratified on consumed_by_csia and capped at "
                 f"{MAX_PER_MESSAGE} per message; within a stratum ordered by "
                 f"SHA-256(salt|case_id) with salt {SALT!r}. No case was "
                 "chosen for being interesting."),
        "salt": SALT,
        "target": TARGET,
        "selected": len(picked),
        "consumed": sum(1 for c in picked if c["consumed_by_csia"]),
        "not_consumed": sum(1 for c in picked if not c["consumed_by_csia"]),
        "messages": sorted({c["message"] for c in picked}),
        "cases": [{k: c[k] for k in ("case_id", "message", "field", "type",
                                     "units", "dialect", "consumed_by_csia")}
                  for c in picked],
    }
    out = os.path.join(_HERE, "HELD_OUT_PILOT.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  pilot: {len(picked)} cases across "
          f"{len(payload['messages'])} messages "
          f"({payload['consumed']} consumed, "
          f"{payload['not_consumed']} not consumed)")
    for c in picked:
        print(f"    {c['case_id']:<40} {c['type']:<12} "
              f"consumed={c['consumed_by_csia']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
