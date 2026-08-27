"""B0 -- the simple mechanical baselines. No model, no judgement.

Item 15 asks for a deliberately simple heuristic so that "the AI just finds
`== -1` and calls it a sentinel" can be tested rather than dismissed. Two
variants are implemented, because while building this package it turned out
that the obvious one is not the strong one:

  B0a  REGEX OVER CONSUMER SOURCE
       Look in the committed adapter/decoder for a comparison against a
       sentinel-shaped constant near the field's name. This is what item 15
       describes.

  B0b  PARSE THE PROTOCOL SCHEMA'S `invalid=` ATTRIBUTE
       MAVLink message definitions carry a machine-readable `invalid=`
       attribute on fields that have a not-measured encoding, e.g.
           <field type="int16_t" name="current_battery" units="cA"
                  invalid="-1">
       So for this protocol the sentinel semantics can be extracted exactly,
       with an authoritative citation, by an XML attribute lookup.

B0b is the baseline that matters. It is trivial, it is not AI, and it is
right by construction wherever the schema author filled the attribute in.
Any claim that a model is needed to recover sentinel semantics has to beat
it.

  python research/ai_contract_synthesis/baselines/b0_heuristic.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

_HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(_HERE)
ROOT = os.path.abspath(os.path.join(PKG, "..", ".."))
sys.path.insert(0, PKG)

MAVLINK_DIR = ("/home/user/ardupilot/ardupilot/modules/mavlink/"
               "message_definitions/v1.0")
DIALECTS = ("common.xml", "minimal.xml", "ardupilotmega.xml", "standard.xml")

CONSUMER_FILES = ("csia/aircraft/adapters/ardupilot.py",
                  "csia/aircraft/adapters/px4.py",
                  "csia/aircraft/adapters/base.py",
                  "csia/runtime/plugins.py",
                  "csia/runtime/ulog_source.py")

# Deliberately crude. Item 15: keep it simple.
SENTINEL_TOKENS = (
    r"==\s*-1", r"!=\s*-1", r"\b65535\b", r"\bUINT16_MAX\b", r"\b32767\b",
    r"\bINT16_MAX\b", r"\b4294967295\b", r"\bUINT32_MAX\b", r"\b255\b",
    r"\bUINT8_MAX\b", r"not measured", r"NOT_MEASURED", r"\bunknown\b",
    r"\binvalid\b", r"\bstale\b", r"_ABSENT\b", r"sentinel",
)


def b0a_regex(case):
    """Look for a sentinel-shaped token on a line mentioning the field."""
    field = case["field"]
    hits = []
    for path in CONSUMER_FILES:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        for i, line in enumerate(open(full, encoding="utf-8").read()
                                 .splitlines(), 1):
            if not re.search(rf"\b{re.escape(field)}\b", line):
                continue
            # the field's own line, and the two after it, so a guard written
            # on the following line is still seen
            window = line
            for tok in SENTINEL_TOKENS:
                if re.search(tok, window, re.I):
                    hits.append({"locator": f"{path}:{i}",
                                 "quote": line.strip(), "token": tok})
                    break
    return {
        "case_id": case["case_id"], "condition": "B0_HEURISTIC",
        "variant": "B0a_regex_over_consumer_source",
        "explicit_semantic_state_found": "YES" if hits else
                                         "NO_EXPLICIT_SEMANTIC_STATE_FOUND",
        "raw_condition": (hits[0]["token"] if hits else ""),
        "support": hits[:3],
        "abstain": False,
    }


_SCHEMA = {}


def _schema():
    """message -> field -> {invalid, description}. Loaded once."""
    if _SCHEMA:
        return _SCHEMA
    for dialect in DIALECTS:
        path = os.path.join(MAVLINK_DIR, dialect)
        if not os.path.exists(path):
            continue
        for msg in ET.parse(path).getroot().iter("message"):
            name = msg.get("name")
            if name in _SCHEMA:
                continue
            _SCHEMA[name] = {
                f.get("name"): {"invalid": f.get("invalid"),
                                "description": (f.text or "").strip(),
                                "dialect": dialect}
                for f in msg.findall("field")}
    return _SCHEMA


def b0b_schema(case):
    """Read the schema's own `invalid=` attribute. One attribute lookup."""
    entry = _schema().get(case["message"], {}).get(case["field"])
    if entry is None:
        return {"case_id": case["case_id"], "condition": "B0_HEURISTIC",
                "variant": "B0b_schema_invalid_attribute",
                "explicit_semantic_state_found": "UNKNOWN",
                "raw_condition": "", "support": [], "abstain": True,
                "abstain_reason": "field not found in any searched dialect"}
    inv = entry["invalid"]
    return {
        "case_id": case["case_id"], "condition": "B0_HEURISTIC",
        "variant": "B0b_schema_invalid_attribute",
        "explicit_semantic_state_found": ("YES" if inv else
                                          "NO_EXPLICIT_SEMANTIC_STATE_FOUND"),
        "raw_condition": (f"== {inv}" if inv else ""),
        "support": ([{"locator": f"{entry['dialect']}:{case['message']}."
                                 f"{case['field']}",
                      "quote": f'invalid="{inv}"'}] if inv else []),
        "abstain": False,
    }


def main() -> int:
    pilot = json.load(open(os.path.join(PKG, "HELD_OUT_PILOT.json"),
                           encoding="utf-8"))
    split = json.load(open(os.path.join(PKG, "BENCHMARK_SPLIT.json"),
                           encoding="utf-8"))
    out = {"artifact": "B0_HEURISTIC_RESULTS",
           "note": "mechanical only; no model was consulted",
           "pilot": [], "full_universe_counts": {}}

    for case in pilot["cases"]:
        out["pilot"].append({"b0a": b0a_regex(case), "b0b": b0b_schema(case)})

    # and over the WHOLE universe, because B0b is cheap and its coverage is
    # the number that decides whether an AI miner is needed at all
    yes_a = yes_b = 0
    for case in split["cases"]:
        yes_a += b0a_regex(case)["explicit_semantic_state_found"] == "YES"
        yes_b += b0b_schema(case)["explicit_semantic_state_found"] == "YES"
    out["full_universe_counts"] = {
        "cases": len(split["cases"]),
        "B0a_regex_says_YES": yes_a,
        "B0b_schema_says_YES": yes_b,
    }

    p = os.path.join(PKG, "results", "B0_HEURISTIC_RESULTS.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"  universe: {out['full_universe_counts']['cases']} fields")
    print(f"  B0a regex over consumer source says YES for "
          f"{yes_a}")
    print(f"  B0b schema `invalid=` attribute says YES for {yes_b}")
    print("\n  pilot:")
    for r in out["pilot"]:
        a, b = r["b0a"], r["b0b"]
        print(f"    {a['case_id']:<40} B0a={a['explicit_semantic_state_found']:<32} "
              f"B0b={b['explicit_semantic_state_found']} {b['raw_condition']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
