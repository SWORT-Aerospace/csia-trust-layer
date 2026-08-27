"""Enumerate the case universe MECHANICALLY, and freeze the split.

Item 10 forbids choosing held-out cases because they produce interesting
defects. So the universe is defined by a rule with no judgement in it:

    every field of every MAVLink message the committed ArduPilot adapter
    declares in `HANDLED_TYPES` (csia/aircraft/adapters/ardupilot.py:77-81)

and the split is defined by a second rule about CONTAMINATION, not by
interest:

    DEVELOPMENT  = the field was analysed in a previously committed research
                   package, or its schema entry was read while designing this
                   one
    HELD_OUT     = everything else

CRITICAL: this script reads only field NAME, TYPE and UNITS out of the
message definitions. It does NOT read the `invalid=` attribute or the field
description, because those are the answer. The reference builder
(`build_reference.py`) reads them, and it must not be run until the candidate
contracts are committed and hashed.

  python research/ai_contract_synthesis/enumerate_universe.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))

MAVLINK_DIR = ("/home/user/ardupilot/ardupilot/modules/mavlink/"
               "message_definitions/v1.0")
DIALECTS = ("common.xml", "minimal.xml", "ardupilotmega.xml", "standard.xml")

# Read straight out of the committed adapter rather than retyped here.
HANDLED_SRC = "csia/aircraft/adapters/ardupilot.py"

# Fields whose semantics were analysed in a previously committed package, or
# whose schema entry was read while designing THIS package. Each entry names
# where the contamination came from. Anything not listed is held out.
CONTAMINATED = {
    "GPS_RAW_INT.fix_type": "research/evidence_semantics (gnss family, "
                            "commit 2036a2a) and three packages before it",
    "BATTERY_STATUS.current_battery": "research/evidence_semantics (battery "
                                      "family, commit 2036a2a)",
    "BATTERY_STATUS.voltages": "research/evidence_semantics CROSS_SENSOR_"
                               "AUDIT.csv (CELL_ABSENT row, commit 2036a2a)",
    "SCALED_IMU.xmag": "research/evidence_semantics (mag family, 2036a2a)",
    "SCALED_IMU.ymag": "research/evidence_semantics (mag family, 2036a2a)",
    "SCALED_IMU.zmag": "research/evidence_semantics (mag family, 2036a2a)",
}
# Whole messages whose schema block was read on screen while designing this
# package. Every field of these is contaminated even if it was never used.
CONTAMINATED_MESSAGES = {
    "BATTERY_STATUS": "the full common.xml <message id=147> block, including "
                      "every `invalid=` attribute, was printed to the "
                      "terminal while checking whether the schema carries "
                      "machine-readable sentinels. Recorded rather than "
                      "quietly excluded.",
}


def handled_types():
    """Read HANDLED_TYPES out of the committed adapter."""
    import re
    src = open(os.path.join(ROOT, HANDLED_SRC), encoding="utf-8").read()
    m = re.search(r"HANDLED_TYPES = frozenset\(\{(.*?)\}\)", src, re.S)
    if not m:
        raise AssertionError("HANDLED_TYPES not found in the adapter")
    return sorted(set(re.findall(r'"([A-Z0-9_]+)"', m.group(1))))


def load_fields(names):
    """field name/type/units only. NOT `invalid=`, NOT the description."""
    out, where = {}, {}
    for dialect in DIALECTS:
        path = os.path.join(MAVLINK_DIR, dialect)
        if not os.path.exists(path):
            continue
        for msg in ET.parse(path).getroot().iter("message"):
            n = msg.get("name")
            if n in names and n not in out:
                out[n] = [{"field": f.get("name"), "type": f.get("type"),
                           "units": f.get("units") or ""}
                          for f in msg.findall("field")]
                where[n] = dialect
    return out, where


def main() -> int:
    names = handled_types()
    fields, where = load_fields(names)
    missing = [n for n in names if n not in fields]

    cases, dev, held = [], 0, 0
    for msg in sorted(fields):
        for f in fields[msg]:
            key = f"{msg}.{f['field']}"
            reason = CONTAMINATED.get(key) or CONTAMINATED_MESSAGES.get(msg)
            split = "DEVELOPMENT" if reason else "HELD_OUT"
            dev += split == "DEVELOPMENT"
            held += split == "HELD_OUT"
            cases.append({
                "case_id": key, "message": msg, "field": f["field"],
                "type": f["type"], "units": f["units"],
                "dialect": where[msg],
                "split": split,
                "contamination": reason or "",
                "consumed_by_csia": None,   # filled by the consumer scan
            })

    # Which fields does the committed adapter actually read? A mechanical
    # grep, not a judgement. Consumed fields carry consumer-side clauses
    # (retention, freshness, merges); unconsumed ones carry only the schema
    # clause, and are the natural negative cases item 9 requires.
    consumer = open(os.path.join(ROOT, HANDLED_SRC), encoding="utf-8").read()
    for c in cases:
        c["consumed_by_csia"] = f'"{c["field"]}"' in consumer

    payload = {
        "artifact": "BENCHMARK_SPLIT",
        "universe_rule": ("every field of every MAVLink message named in "
                          f"{HANDLED_SRC}:HANDLED_TYPES"),
        "split_rule": ("DEVELOPMENT iff the field or its whole schema block "
                       "was read in a previously committed package or while "
                       "designing this one; HELD_OUT otherwise. Interest, "
                       "difficulty and defect-richness play NO part."),
        "mavlink_dir": MAVLINK_DIR,
        "dialects_searched": list(DIALECTS),
        "handled_types": names,
        "messages_resolved": sorted(fields),
        "messages_not_found": missing,
        "counts": {"total": len(cases), "development": dev, "held_out": held,
                   "consumed_by_csia": sum(1 for c in cases
                                           if c["consumed_by_csia"])},
        "cases": cases,
    }
    out = os.path.join(_HERE, "BENCHMARK_SPLIT.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  handled types: {len(names)}  resolved: {len(fields)}  "
          f"missing: {missing}")
    print(f"  cases: {len(cases)}  DEVELOPMENT {dev}  HELD_OUT {held}")
    print(f"  consumed by the adapter: {payload['counts']['consumed_by_csia']}")
    print(f"  sha256: "
          f"{hashlib.sha256(open(out, 'rb').read()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
