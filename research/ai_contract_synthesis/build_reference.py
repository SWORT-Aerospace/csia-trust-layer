"""Build the SOURCE-AUDITED REFERENCE. Item 8.

**This is NOT a gold standard and NOT ground truth.** Item 8 and item 32 are
explicit: a reference the same model produced alongside the predictions is a
methodological limitation, not an oracle. It is called
SOURCE_AUDITED_REFERENCE because that is all it is -- a set of answers each
of which is traced to a source location a reader can check.

The reference for the sentinel/invalid clause is derived MECHANICALLY from
the authoritative protocol schema:

    <field type="int16_t" name="current_battery" units="cA" invalid="-1">

so for that clause kind the reference contains no model judgement at all. For
the clause kinds the schema is silent about -- retention, freshness, merges,
downstream consumer -- the reference is derived from the committed consumer
source, and those entries DO carry judgement and are labelled as such.

REFUSES TO RUN unless FREEZE.json exists and every frozen artifact still
hashes the same, so the reference cannot be built before the predictions were
written down.

  python research/ai_contract_synthesis/build_reference.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
OUT = os.path.join(_HERE, "SOURCE_AUDITED_REFERENCE")

MAVLINK_DIR = ("/home/user/ardupilot/ardupilot/modules/mavlink/"
               "message_definitions/v1.0")
DIALECTS = ("common.xml", "minimal.xml", "ardupilotmega.xml", "standard.xml")

CONSUMER = "csia/aircraft/adapters/ardupilot.py"


def require_freeze():
    r = subprocess.run([sys.executable, os.path.join(_HERE, "freeze.py"),
                        "--check"], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise SystemExit(
            "REFUSING TO BUILD THE REFERENCE: the frozen artifacts do not "
            "match FREEZE.json. Building now would destroy the one ordering "
            "guarantee this package has.")


def schema_entries():
    out = {}
    for d in DIALECTS:
        p = os.path.join(MAVLINK_DIR, d)
        if not os.path.exists(p):
            continue
        for msg in ET.parse(p).getroot().iter("message"):
            name = msg.get("name")
            if name in out:
                continue
            out[name] = {}
            for f in msg.findall("field"):
                out[name][f.get("name")] = {
                    "invalid": f.get("invalid"),
                    "enum": f.get("enum"),
                    "units": f.get("units"),
                    "description": re.sub(r"\s+", " ",
                                          (f.text or "")).strip(),
                    "dialect": d,
                }
    return out


def consumer_evidence(field):
    """Every executable line of the committed adapter that names the field."""
    hits = []
    src = open(os.path.join(ROOT, CONSUMER), encoding="utf-8").read()
    for i, line in enumerate(src.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if re.search(rf"(?<![\w]){re.escape(field)}(?![\w])", line):
            hits.append({"locator": f"{CONSUMER}:{i}", "text": s})
    return hits


def build_case(case, sch):
    entry = sch.get(case["message"], {}).get(case["field"])
    ev = consumer_evidence(case["field"])
    ref = {
        "case_id": case["case_id"],
        "message": case["message"],
        "field": case["field"],
        "split": case["split"],
        "derivation": {},
        "clauses": [],
        "notes": [],
    }

    # ---- sentinel / invalid clause: MECHANICAL, from the schema ----------
    if entry is None:
        ref["has_explicit_state"] = None
        ref["derivation"]["sentinel"] = "FIELD_NOT_IN_ANY_SEARCHED_DIALECT"
        ref["notes"].append("no schema entry; the sentinel clause is not "
                            "answerable from the authoritative source")
    else:
        inv = entry["invalid"]
        ref["has_explicit_state"] = bool(inv)
        ref["derivation"]["sentinel"] = (
            "MECHANICAL: the `invalid=` attribute of the field definition. "
            "No model judgement.")
        ref["schema"] = {"invalid": inv, "units": entry["units"],
                         "enum": entry["enum"],
                         "dialect": entry["dialect"],
                         "description": entry["description"][:400]}
        if inv:
            ref["clauses"].append({
                "kind": "SENTINEL_CONDITION",
                "raw_condition": f"== {inv}",
                "state": "X",
                "support": [{"locator": f"{entry['dialect']}:"
                                        f"{case['message']}.{case['field']}",
                             "quote": f'invalid="{inv}"'}],
                "support_kind": "PROTOCOL_SCHEMA",
                "derivation": "MECHANICAL",
            })

    # ---- consumer-side clauses: JUDGEMENT, and labelled as such ----------
    ref["consumer_evidence"] = ev
    ref["derivation"]["consumer_clauses"] = (
        "JUDGEMENT. Read off the committed adapter by the same model that "
        "produced the candidates. Every entry cites a line, but the reading "
        "of that line is not independent.")
    if not ev:
        ref["notes"].append("the committed adapter never names this field, "
                            "so no consumer-side clause exists and no "
                            "conformance question is answerable")
        ref["consumed"] = False
    else:
        ref["consumed"] = True
    return ref


def main() -> int:
    require_freeze()
    os.makedirs(OUT, exist_ok=True)
    split = json.load(open(os.path.join(_HERE, "BENCHMARK_SPLIT.json"),
                           encoding="utf-8"))
    sch = schema_entries()

    refs = [build_case(c, sch) for c in split["cases"]]
    with_state = sum(1 for r in refs if r["has_explicit_state"])
    without = sum(1 for r in refs if r["has_explicit_state"] is False)
    unknown = sum(1 for r in refs if r["has_explicit_state"] is None)
    consumed = sum(1 for r in refs if r.get("consumed"))

    payload = {
        "artifact": "SOURCE_AUDITED_REFERENCE",
        "NOT": ["ground truth", "a gold standard", "human reviewed",
                "independent of the predictions"],
        "sentinel_clause_derivation": "MECHANICAL, from the protocol schema's "
                                      "`invalid=` attribute",
        "consumer_clause_derivation": "MODEL JUDGEMENT over cited lines",
        "counts": {"cases": len(refs),
                   "explicit_state_YES": with_state,
                   "explicit_state_NO": without,
                   "not_in_schema": unknown,
                   "named_by_the_adapter": consumed},
        "cases": refs,
    }
    p = os.path.join(OUT, "REFERENCE.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  cases {len(refs)}: explicit state YES {with_state}, "
          f"NO {without}, not-in-schema {unknown}")
    print(f"  named by the committed adapter: {consumed}")
    print(f"  -> {os.path.relpath(p, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
