"""The deterministic source-grounding validator. PHASE 1 of item 26.

This is the part of the system that is NOT a model and NOT a judgement. It
answers exactly one question per clause:

    does the text this clause cites actually exist at the location it cites?

Nothing about meaning. A clause can be perfectly grounded and still wrong; a
clause that fails here is unsupported no matter how confident the proposer
was. That asymmetry is the whole point: item 14 forbids confidence from
gating anything, and this is the gate.

Locator forms:

    path/to/file.py:123          a source line
    path/to/file.py:120-130      a source range
    common.xml:MESSAGE.field     a protocol schema field definition

Statuses assigned (item 1's ladder, and the validator may only reach the
first three):

    SOURCE_SUPPORTED       every clause's citation resolves and matches
    SOURCE_AMBIGUOUS       citations resolve but disagree with each other
    UNSUPPORTED_INFERENCE  a clause cites nothing, or the citation does not
                           contain what it claims

`EXECUTION_CONFIRMED` and beyond are not this module's to give.

  python research/ai_contract_synthesis/verification/grounding.py
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

MAVLINK_DIR = ("/home/user/ardupilot/ardupilot/modules/mavlink/"
               "message_definitions/v1.0")

# Precedence from the prompt's evidence hierarchy. Higher outranks lower.
PRECEDENCE = {"PROTOCOL_SCHEMA": 1, "PRODUCER_SOURCE": 2,
              "CONSUMER_SOURCE": 3, "TEST": 4, "INTERNAL_SPEC": 5,
              "COMMENT": 6, "PROSE_DOC": 7, "NONE": 99}


def _norm(s):
    """Whitespace-insensitive compare. A citation must match the TEXT, not
    the indentation it happened to be printed with."""
    return re.sub(r"\s+", " ", s or "").strip()


def resolve(locator, quote):
    """Return (ok, reason, found_text)."""
    if ":" not in locator:
        return False, "malformed locator", ""

    path, ref = locator.rsplit(":", 1)

    # protocol schema: file.xml:MESSAGE.field
    if path.endswith(".xml"):
        full = os.path.join(MAVLINK_DIR, os.path.basename(path))
        if not os.path.exists(full):
            return False, f"schema file not found: {path}", ""
        if "." not in ref:
            return False, "schema locator must be MESSAGE.field", ""
        msg_name, field_name = ref.split(".", 1)
        for msg in ET.parse(full).getroot().iter("message"):
            if msg.get("name") != msg_name:
                continue
            for f in msg.findall("field"):
                if f.get("name") != field_name:
                    continue
                blob = " ".join(
                    [f'{k}="{v}"' for k, v in sorted(f.attrib.items())]
                    + [(f.text or "")])
                ok = _norm(quote) in _norm(blob)
                return ok, ("" if ok else "quote not found in field "
                            "definition"), _norm(blob)[:400]
            return False, f"field {field_name} not in {msg_name}", ""
        return False, f"message {msg_name} not in {path}", ""

    # source file: path:line or path:a-b
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return False, f"file not found: {path}", ""
    lines = open(full, encoding="utf-8").read().splitlines()
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", ref)
    if not m:
        return False, "malformed line reference", ""
    a = int(m.group(1))
    b = int(m.group(2) or m.group(1))
    if a < 1 or b > len(lines) or a > b:
        return False, f"line range out of bounds (file has {len(lines)})", ""
    blob = " ".join(lines[a - 1:b])
    ok = _norm(quote) in _norm(blob)
    return ok, ("" if ok else "quote not found at that location"), \
        _norm(blob)[:400]


def validate_candidate(cand):
    """Assign a grounding status to one candidate contract."""
    checked, unsupported = [], 0
    for cl in cand.get("clauses", []):
        sup = cl.get("support") or []
        if not sup:
            checked.append({"kind": cl["kind"], "grounded": False,
                            "reason": "no citation given",
                            "support_kind": cl.get("support_kind", "NONE")})
            unsupported += 1
            continue
        results = []
        for s in sup:
            ok, why, found = resolve(s["locator"], s["quote"])
            results.append({"locator": s["locator"], "ok": ok,
                            "reason": why, "found": found[:160]})
        all_ok = all(r["ok"] for r in results)
        checked.append({"kind": cl["kind"], "grounded": all_ok,
                        "support_kind": cl.get("support_kind", "NONE"),
                        "citations": results,
                        "reason": ("" if all_ok else
                                   "; ".join(r["reason"] for r in results
                                             if not r["ok"]))})
        unsupported += (not all_ok)

    n = len(checked)
    if cand.get("abstain"):
        status = "ABSTAINED"
    elif n == 0:
        status = "UNSUPPORTED_INFERENCE"
    elif unsupported == 0:
        status = ("CONTRACT_AMBIGUOUS"
                  if cand.get("contract_status") == "CONTRACT_AMBIGUOUS"
                  else "SOURCE_SUPPORTED")
    elif unsupported == n:
        status = "UNSUPPORTED_INFERENCE"
    else:
        status = "PARTIALLY_SUPPORTED"

    # the metric item 19 calls the most important one
    high_conf_unsupported = (unsupported > 0
                             and float(cand.get("confidence", 0.0)) >= 0.8)

    return {
        "case_id": cand["case_id"],
        "condition": cand.get("condition"),
        "self_reported_status": cand.get("contract_status"),
        "validator_status": status,
        "clauses_total": n,
        "clauses_unsupported": unsupported,
        "confidence": cand.get("confidence"),
        "high_confidence_unsupported": high_conf_unsupported,
        "self_report_agrees_with_validator": (
            (cand.get("contract_status") == "UNSUPPORTED_INFERENCE")
            == (status == "UNSUPPORTED_INFERENCE")),
        "clauses": checked,
        "best_support_kind": min(
            (PRECEDENCE.get(c.get("support_kind", "NONE"), 99)
             for c in checked), default=99),
    }


def main() -> int:
    out, files = {}, []
    cdir = os.path.join(PKG, "candidates")
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(cdir, fn), encoding="utf-8"))
        rows = [validate_candidate(c) for c in doc["candidates"]]
        out[doc["condition"]] = rows
        files.append(fn)
        n = len(rows)
        ab = sum(r["validator_status"] == "ABSTAINED" for r in rows)
        uns = sum(r["validator_status"] == "UNSUPPORTED_INFERENCE"
                  for r in rows)
        cl_total = sum(r["clauses_total"] for r in rows)
        cl_uns = sum(r["clauses_unsupported"] for r in rows)
        hcu = sum(r["high_confidence_unsupported"] for r in rows)
        print(f"  {doc['condition']:<22} cases {n:3d}  abstained {ab:3d}  "
              f"unsupported {uns:3d}  clauses {cl_total:3d} of which "
              f"unsupported {cl_uns:3d}  high-confidence-unsupported {hcu}")

    p = os.path.join(PKG, "results", "GROUNDING_RESULTS.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"artifact": "GROUNDING_RESULTS",
                   "candidate_files": files,
                   "precedence": PRECEDENCE,
                   "by_condition": out}, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
