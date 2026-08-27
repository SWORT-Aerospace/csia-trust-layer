"""Two-phase promotion, and the hallucination-containment measurement.

Items 23-26. The architecture the brief asks for:

    PHASE 1  CONTRACT EVIDENCE     is the proposed rule supported?
    PHASE 2  IMPLEMENTATION CONFORMANCE  given a supported rule, does the
                                          implementation preserve it?

    a finding is CONFIRMED only when both pass.

Phase 1 is more than the bare grounding check in `grounding.py`, because
item 25 names the dangerous case exactly: a rule whose citation RESOLVES but
whose content is wrong. A comment can be quoted faithfully and still be
false. So Phase 1 runs four additional deterministic checks:

  C2  EXECUTABLE CORROBORATION
      Does an executable (non-comment) line in the cited file actually test
      the claimed raw condition? A rule supported only by a comment, with no
      executable branch testing it, is CONTRACT_AMBIGUOUS -- the precedence
      hierarchy puts executable source above comments.

  C3  SCHEMA CONTRADICTION
      If the field appears in the protocol schema and its `invalid=`
      attribute disagrees with the claimed sentinel, the claim is REFUTED.
      This check only exists because MAVLink happens to carry a
      machine-readable sentinel attribute. Where a protocol does not, C3 is
      simply unavailable -- which is the main limitation of the whole
      approach and is reported as such.

  C4  REACHABILITY
      If no executable line reads the field at all, no trace can exercise the
      rule and no conformance question is answerable: INCONCLUSIVE, never a
      defect.

  C5  INTERNAL CONTRADICTION
      If two decoders in the cited file read the same field in contradictory
      senses, the contract is CONTRACT_AMBIGUOUS whatever the miner claimed.

  python research/ai_contract_synthesis/verification/containment.py
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
sys.path.insert(0, _HERE)

import grounding as G                                          # noqa: E402

MAVLINK_DIR = G.MAVLINK_DIR
DIALECTS = ("common.xml", "minimal.xml", "ardupilotmega.xml", "standard.xml")

# item 49
STATES = ("AI_ONLY", "SOURCE_SUPPORTED", "SOURCE_AMBIGUOUS",
          "CHECKER_CONFIRMED_IMPLEMENTATION_VIOLATION",
          "CHECKER_PASS_TO_BOUND", "REFUTED_CONTRACT", "INCONCLUSIVE")

DISCARD_MARKERS = ("return None", "pop(", "_reject", "del ", "continue",
                   "raise", "= None")


def _is_schema_locator(loc):
    """`common.xml:GPS_RAW_INT.epv` is a SCHEMA citation, not a file:line.

    The first version tested `loc.endswith(".xml")`, which is false for a
    schema locator because the field name comes last. It therefore treated
    `common.xml` as a source path and crashed on the first B2 candidate.
    Recorded in FREEZE_AMENDMENTS.json rather than quietly corrected.
    """
    return ":" in loc and loc.rsplit(":", 1)[0].endswith(".xml")


def _file_of(clause):
    for s in clause.get("support") or []:
        loc = s["locator"]
        if ":" in loc and not _is_schema_locator(loc):
            return loc.rsplit(":", 1)[0]
    return None


def _executable_lines(path):
    """Lines that are not blank, not comments, not inside the docstring."""
    out = []
    in_doc = False
    for i, raw in enumerate(open(os.path.join(ROOT, path),
                                 encoding="utf-8").read().splitlines(), 1):
        s = raw.strip()
        if s.startswith('"""') or s.endswith('"""'):
            # crude but adequate for the small fixtures and adapters here
            if s.count('"""') == 1:
                in_doc = not in_doc
                continue
        if in_doc or not s or s.startswith("#"):
            continue
        out.append((i, raw))
    return out


def _condition_tokens(raw_condition):
    """The literal(s) a claimed condition turns on, e.g. '== -1' -> {'-1'}."""
    if not raw_condition:
        return set()
    return set(re.findall(r"-?\b\d+\b|\b[A-Z][A-Z0-9_]{2,}\b",
                          raw_condition))


# A literal only counts as TESTED when it appears in a comparison or a
# branch. The first version of C2 accepted any executable occurrence, and was
# fooled twice by the fixtures it exists to catch:
#   * `FLOW_QUALITY_UNKNOWN = 255` -- a constant DEFINITION read as a test
#   * `1.0 if msg["valid"] else 0.25` -- the `0` inside the float `0.25`
# Both are recorded in CLAIM_LEDGER.json rather than quietly fixed.
_COND_CTX = re.compile(r"(^|\s)(if|elif|while|assert)\s|==|!=|<=|>=|<|>")


def _literal_re(tok):
    """Match an integer literal, but never inside a float or identifier."""
    if re.fullmatch(r"-?\d+", tok):
        return re.compile(rf"(?<![\w.]){re.escape(tok)}(?![\w.])")
    return re.compile(rf"(?<![\w]){re.escape(tok)}(?![\w])")


def c2_executable_corroboration(clause):
    """Is the claimed condition actually tested by executable code?"""
    path = _file_of(clause)
    if path is None:
        return {"check": "C2", "result": "NOT_APPLICABLE",
                "why": "no source-file citation"}
    toks = _condition_tokens(clause.get("raw_condition", ""))
    field = None
    m = re.match(r"^([A-Za-z_][\w]*)", clause.get("raw_condition", "") or "")
    if m:
        field = m.group(1)
    lines = _executable_lines(path)
    tested, defined_only = [], []
    for i, raw in lines:
        if field and field not in raw:
            continue
        if not any(_literal_re(t).search(raw) for t in toks):
            continue
        if not _COND_CTX.search(raw):
            # e.g. `FLOW_QUALITY_UNKNOWN = 255`: the literal is DEFINED here,
            # not tested. A definition is not evidence that the branch exists.
            defined_only.append(f"{path}:{i}")
            continue
        tested.append(f"{path}:{i}")
    if not toks:
        return {"check": "C2", "result": "NOT_APPLICABLE",
                "why": "clause states no raw condition"}
    if tested:
        return {"check": "C2", "result": "CORROBORATED", "lines": tested}
    if defined_only:
        return {"check": "C2", "result": "DEFINED_NOT_TESTED",
                "lines": defined_only,
                "why": "the literal appears only in a constant definition; "
                       "no executable branch tests it"}
    only_comment = all((s.get("locator") and
                        _is_comment_line(s["locator"]))
                       for s in (clause.get("support") or []))
    return {"check": "C2",
            "result": "CONTRADICTED_BY_EXECUTABLE" if only_comment
                      else "NOT_CORROBORATED",
            "why": (f"no executable line in {path} tests "
                    f"{sorted(toks)}; the claim rests on "
                    f"{'a comment' if only_comment else 'a line that does '
                       'not implement it'}")}


def c6_effect_corroboration(clause):
    """A clause claiming a DISCARD must show a discard in the cited region.

    Item 25's dangerous case is a clause whose citation resolves and whose
    condition is genuinely tested, but whose claimed CONSEQUENCE is invented.
    Checking the condition alone cannot catch that; checking the effect can,
    at least when the effect is syntactically visible.
    """
    text = (clause.get("statement", "") or "").lower()
    wants_discard = any(w in text for w in
                        ("discard", "must not be used", "dropped",
                         "unusable", "not usable"))
    if not wants_discard:
        return {"check": "C6", "result": "NOT_APPLICABLE",
                "why": "clause claims no discard effect"}
    path = _file_of(clause)
    if path is None:
        return {"check": "C6", "result": "NOT_APPLICABLE",
                "why": "no source-file citation"}
    lines = dict(_executable_lines(path))
    near = set()
    for s in clause.get("support") or []:
        loc = s["locator"]
        if _is_schema_locator(loc) or ":" not in loc:
            continue
        ref = loc.rsplit(":", 1)[1]
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", ref)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        near |= set(range(a - 3, b + 4))
    blob = " ".join(lines[i] for i in sorted(near) if i in lines)
    if any(mk in blob for mk in DISCARD_MARKERS):
        return {"check": "C6", "result": "CORROBORATED"}
    return {"check": "C6", "result": "EFFECT_NOT_IMPLEMENTED",
            "why": "the clause claims the value is discarded, but no discard "
                   "appears within three lines of the citation"}


def _is_comment_line(locator):
    if _is_schema_locator(locator) or ":" not in locator:
        return False
    path, ref = locator.rsplit(":", 1)
    if not re.fullmatch(r"\d+", ref):
        return False
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return False
    lines = open(full, encoding="utf-8").read().splitlines()
    n = int(ref)
    return 1 <= n <= len(lines) and lines[n - 1].strip().startswith("#")


_SCHEMA = {}


def _schema():
    if _SCHEMA:
        return _SCHEMA
    for d in DIALECTS:
        p = os.path.join(MAVLINK_DIR, d)
        if not os.path.exists(p):
            continue
        for msg in ET.parse(p).getroot().iter("message"):
            if msg.get("name") in _SCHEMA:
                continue
            _SCHEMA[msg.get("name")] = {
                f.get("name"): f.get("invalid") for f in msg.findall("field")}
    return _SCHEMA


def c3_schema_contradiction(case_id, clause):
    """Does an authoritative schema attribute refute the claimed sentinel?"""
    if "." not in case_id:
        return {"check": "C3", "result": "NOT_APPLICABLE",
                "why": "case id is not MESSAGE.field"}
    msg, field = case_id.rsplit(".", 1)
    entry = _schema().get(msg)
    if entry is None or field not in entry:
        return {"check": "C3", "result": "NOT_APPLICABLE",
                "why": "field not in any searched protocol dialect"}
    declared = entry[field]
    claimed = (clause.get("raw_condition") or "").replace("==", "").strip()
    if clause["kind"] not in ("SENTINEL_CONDITION", "INVALID_CONDITION"):
        return {"check": "C3", "result": "NOT_APPLICABLE",
                "why": "clause is not a sentinel/invalid claim"}
    if declared is None:
        return {"check": "C3", "result": "REFUTED",
                "why": f"the schema declares NO invalid encoding for "
                       f"{msg}.{field}, but the clause asserts {claimed!r}"}
    ok = _norm_lit(declared) == _norm_lit(claimed)
    return {"check": "C3", "result": "CORROBORATED" if ok else "REFUTED",
            "why": f"schema invalid={declared!r} vs claimed {claimed!r}"}


def _norm_lit(s):
    return re.sub(r"[\[\]\s]", "", str(s or "")).upper()


def c4_reachability(clause):
    """Can any trace exercise this rule at all?"""
    path = _file_of(clause)
    if path is None:
        return {"check": "C4", "result": "NOT_APPLICABLE",
                "why": "no source-file citation"}
    m = re.match(r"^([A-Za-z_][\w]*)", clause.get("raw_condition", "") or "")
    field = m.group(1) if m else None
    if not field:
        return {"check": "C4", "result": "NOT_APPLICABLE",
                "why": "clause names no field"}
    for _i, raw in _executable_lines(path):
        if re.search(rf"(?<![\w.]){re.escape(field)}(?![\w])", raw):
            return {"check": "C4", "result": "REACHABLE"}
    return {"check": "C4", "result": "UNREACHABLE",
            "why": f"no executable line in {path} reads {field!r}, so no "
                   f"trace can exercise the rule"}


def c5_internal_contradiction(clause):
    """Do two readers in the cited file disagree about the same field?"""
    path = _file_of(clause)
    if path is None:
        return {"check": "C5", "result": "NOT_APPLICABLE"}
    m = re.match(r"^([A-Za-z_][\w]*)", clause.get("raw_condition", "") or "")
    field = m.group(1) if m else None
    if not field:
        return {"check": "C5", "result": "NOT_APPLICABLE"}
    pos, neg = [], []
    for i, raw in _executable_lines(path):
        if not re.search(rf"(?<![\w.]){re.escape(field)}(?![\w])", raw):
            continue
        if re.search(rf"not\s+\w*\[?['\"]?{re.escape(field)}", raw):
            neg.append(f"{path}:{i}")
        elif re.search(rf"bool\(\s*\w*\[?['\"]?{re.escape(field)}", raw):
            pos.append(f"{path}:{i}")
    if pos and neg:
        return {"check": "C5", "result": "CONTRADICTORY_READERS",
                "lines": sorted(pos + neg)}
    return {"check": "C5", "result": "CONSISTENT"}


def phase1(cand):
    """Contract evidence. Returns (status, checks)."""
    ground = G.validate_candidate(cand)
    if cand.get("abstain"):
        return "ABSTAINED", {"grounding": ground, "checks": []}

    checks, verdicts = [], []
    for cl in cand.get("clauses", []):
        row = {"kind": cl["kind"],
               "c2": c2_executable_corroboration(cl),
               "c3": c3_schema_contradiction(cand["case_id"], cl),
               "c4": c4_reachability(cl),
               "c5": c5_internal_contradiction(cl),
               "c6": c6_effect_corroboration(cl)}
        checks.append(row)
        if row["c3"]["result"] == "REFUTED":
            verdicts.append("REFUTED_CONTRACT")
        elif row["c5"]["result"] == "CONTRADICTORY_READERS":
            verdicts.append("SOURCE_AMBIGUOUS")
        elif row["c4"]["result"] == "UNREACHABLE":
            verdicts.append("INCONCLUSIVE")
        elif row["c2"]["result"] in ("CONTRADICTED_BY_EXECUTABLE",
                                     "NOT_CORROBORATED",
                                     "DEFINED_NOT_TESTED"):
            verdicts.append("SOURCE_AMBIGUOUS")
        elif row["c6"]["result"] == "EFFECT_NOT_IMPLEMENTED":
            verdicts.append("SOURCE_AMBIGUOUS")
        else:
            verdicts.append("SOURCE_SUPPORTED")

    if ground["validator_status"] == "UNSUPPORTED_INFERENCE":
        status = "AI_ONLY"
    elif "REFUTED_CONTRACT" in verdicts:
        status = "REFUTED_CONTRACT"
    elif "SOURCE_AMBIGUOUS" in verdicts:
        status = "SOURCE_AMBIGUOUS"
    elif "INCONCLUSIVE" in verdicts:
        status = "INCONCLUSIVE"
    elif verdicts and all(v == "SOURCE_SUPPORTED" for v in verdicts):
        status = "SOURCE_SUPPORTED"
    else:
        status = "INCONCLUSIVE"
    return status, {"grounding": ground, "checks": checks}


def promote(cand):
    """The full two-phase decision. PHASE 2 is only reached from
    SOURCE_SUPPORTED -- item 26."""
    p1, detail = phase1(cand)
    if p1 != "SOURCE_SUPPORTED":
        return {"case_id": cand["case_id"], "phase1": p1,
                "phase2": "NOT_RUN",
                "final": ("INCONCLUSIVE" if p1 in ("ABSTAINED",
                                                   "INCONCLUSIVE")
                          else p1),
                "promoted_as_defect": False, "detail": detail}
    # PHASE 2 would hand the contract to the deterministic checker from
    # research/evidence_semantics. For the NON-SCORED fixtures there is no
    # CSIA pipeline to run, so it is recorded as not applicable rather than
    # simulated.
    return {"case_id": cand["case_id"], "phase1": p1,
            "phase2": "PENDING_CHECKER",
            "final": "SOURCE_SUPPORTED",
            "promoted_as_defect": False, "detail": detail}


def main() -> int:
    path = os.path.join(PKG, "candidates", "NONSCORED_HALLUCINATION.json")
    doc = json.load(open(path, encoding="utf-8"))
    assert doc["scored"] is False, "these fixtures must never be scored"

    rows, contained = [], 0
    for cand in doc["candidates"]:
        r = promote(cand)
        r["hallucination_class"] = cand.get("hallucination_class")
        r["fixture_truth"] = cand.get("fixture_truth")
        # containment: the wrong rule did NOT become a confirmed defect
        r["contained"] = not r["promoted_as_defect"] and \
            r["final"] != "CHECKER_CONFIRMED_IMPLEMENTATION_VIOLATION"
        r["stopped_at_phase1"] = r["phase2"] == "NOT_RUN"
        contained += r["contained"]
        rows.append(r)

    payload = {
        "artifact": "HALLUCINATION_CONTAINMENT",
        "status": "NON-SCORED TOOL-VALIDATION FIXTURES",
        "fixtures": len(rows),
        "contained": contained,
        "containment_rate": round(contained / len(rows), 3),
        "stopped_before_phase2": sum(r["stopped_at_phase1"] for r in rows),
        "results": rows,
    }
    p = os.path.join(PKG, "results", "HALLUCINATION_CONTAINMENT.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    for r in rows:
        print(f"  {r['case_id']:<36} phase1={r['phase1']:<20} "
              f"final={r['final']:<20} contained={r['contained']}")
    print(f"\n  containment {contained}/{len(rows)} = "
          f"{payload['containment_rate']}")
    print(f"  stopped before phase 2: {payload['stopped_before_phase2']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
