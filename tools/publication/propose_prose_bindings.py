"""Propose artifact bindings for the 42 unbound scientific prose literals.

WHY "PROPOSE" AND NOT "APPLY"
------------------------------
These literals live in `papers/csia_systems/main.tex`, so their bindings
belong in `PAPER1_ARTIFACT_MAP.yaml` -- which the immutable E1 freeze
manifest hashes. Editing it would break the freeze it is recorded in. So this
emits a PROPOSED set, ready to be merged at a deliberate re-freeze, and
changes nothing today. Same reason HF-003's pointer correction is specified
and not applied.

WHY A NUMERIC SEARCH IS NOT ALLOWED TO DECIDE
-----------------------------------------------
The previous round tried exactly that and recorded why it failed: a scan of
131 committed artifacts matched ALL 45 numeric literals, most of them many
times. `0.906` matched a phase-2 lambda sample; `1.0` matched a hundred
places. **That is coincidence, not provenance**, and binding on it would
manufacture the false chain this audit exists to find.

So a numeric match is NECESSARY AND NOT SUFFICIENT. A candidate is proposed
only when all four hold:

    1. the value matches to the literal's PRINTED PRECISION;
    2. the artifact is not under `research/phase2/` (the phase guard forbids
       a Phase-I map from citing it);
    3. the JSON POINTER's own key path shares a meaningful token with the
       literal's description -- so `fresh_fraction` can bind a literal
       described as "fresh fraction" and cannot bind one described as
       "kappa";
    4. exactly ONE candidate survives 1-3. Two surviving candidates is
       AMBIGUOUS and is reported as unresolved, because picking one would be
       guessing.

Everything else is `UNRESOLVED`, with the reason recorded. **A high
unresolved count is the expected and correct outcome**; these numbers were
written by hand and most of them will need a human to say where they came
from.

    python tools/publication/propose_prose_bindings.py --out <yaml>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

EXTENSION = os.path.join(ROOT, "research", "physical_validation", "results",
                         "POST_E1_PROSE_LITERAL_EXTENSION.json")

#: Never cited by a Phase-I artifact map. The phase guard enforces this
#: separately; the search excludes them so a forbidden candidate is never
#: even proposed.
FORBIDDEN_PREFIXES = ("research/phase2/",)

#: Searched for candidate artifacts.
SEARCH_ROOTS = ("research", "engineering", "publication")

#: Tokens too generic to carry any binding evidence on their own.
_STOPWORDS = {
    "the", "a", "of", "in", "and", "to", "for", "at", "on", "over", "from",
    "with", "value", "number", "count", "total", "rate", "per", "is", "was",
    "reported", "observed", "measured", "under", "between", "both", "all",
}


def _tokens(text: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower())
            if t and t not in _STOPWORDS and len(t) > 2}


def _printed_precision(literal: str) -> int:
    return len(literal.split(".")[1]) if "." in literal else 0


def _walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}/{i}")
    else:
        yield path, node


def _artifacts():
    out = []
    for root in SEARCH_ROOTS:
        base = os.path.join(ROOT, root)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            rel_dir = os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
            if any(rel_dir.startswith(p.rstrip("/"))
                   for p in FORBIDDEN_PREFIXES):
                continue
            for name in sorted(files):
                if not name.endswith(".json"):
                    continue
                rel = os.path.join(rel_dir, name).replace(os.sep, "/")
                try:
                    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                        out.append((rel, json.load(fh)))
                except (OSError, ValueError):
                    continue
    return out


def candidates_for(literal: str, why: str, artifacts) -> list:
    """Every (artifact, pointer, value) passing all four rules."""
    precision = _printed_precision(literal)
    target = float(literal)
    want = _tokens(why)
    found = []

    for rel, doc in artifacts:
        for pointer, value in _walk(doc):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if round(float(value), precision) != round(target, precision):
                continue
            # RULE 3: the pointer's own path must share a token with the
            # literal's description. A bare numeric match is coincidence.
            if not (_tokens(pointer) & want):
                continue
            found.append({"artifact": rel, "json_pointer": pointer,
                          "value": value,
                          "shared_tokens": sorted(_tokens(pointer) & want)})
    return found


#: HAND-ADJUDICATED. The tool proposes; a human verifies. Every proposal was
#: opened and checked against its artifact, and TWO OF FIVE WERE WRONG --
#: which is why this layer exists rather than the tool's output being taken
#: as the answer.
#:
#: literal -> (verdict, reason)
ADJUDICATION = {
    "0.001597": ("CONFIRMED",
                 "the pointer is literally denial/channel_fresh_fraction and "
                 "the prose says 'the GPS channel's fresh fraction falls "
                 "from 1.0 to 0.001597'. Four shared tokens on a specific "
                 "path."),
    "0.9998": ("CONFIRMED",
               "the pointer is worst_case_unsupported_leader/posterior = "
               "0.999822, and the prose is 'a leader at 0.9998 with no "
               "evidence distinguishing it from its nearest rival'. The "
               "pointer name states the exact condition the prose "
               "describes."),
    "0.640319": ("CONFIRMED_WITH_CAVEAT",
                 "the prose says 'min 0.640319 ... in BOTH', so the value "
                 "appears at traces/clean/min AND traces/denial/min. The "
                 "clean pointer is proposed because the description names "
                 "the clean trace; a human should confirm which the "
                 "manuscript means, since either is numerically correct."),
    "0.678": ("REJECTED_SEMANTIC_MISMATCH",
              "numerically 0.6785 -> 0.678, but observed_range is the range "
              "over ALL 21 cells with upper bound 0.9422, while the prose "
              "says 'the measured floor ranges 0.678 to 0.700'. The prose "
              "describes a NARROWER population -- the cells where the "
              "physics residual is the binding constraint -- whose lower "
              "bound coincides with the wider one. Binding it would record a "
              "provenance chain that does not exist. The artifact carries no "
              "scalar for the population the prose means."),
    "0.7000": ("REJECTED_WRONG_QUANTITY",
               "the tool matched misclassified_cells/0/ticks_from_boundary = "
               "0.7, a TICK DISTANCE that coincidentally equals the value. "
               "The prose is 'measured minimum fused evidence in the "
               "saturated cells: 0.7000'. The artifact confirms the value "
               "only inside a prose `statement` field, and its one scalar "
               "at 0.7 is `predicted_e_f` -- the PREDICTION, not the "
               "measurement. Binding measured to predicted would be wrong in "
               "the most consequential available way."),
}

#: Specified, NOT applied. Same discipline as HF-003.
SPECIFIED_ARTIFACT_CORRECTIONS = [
    {"artifact": "research/wp_c8/results/response_surface.json",
     "add_key": "evidence_floor_confirmation.measured_e_f_saturated",
     "value_would_be": 0.7000,
     "why": ("the manuscript quotes a MEASURED minimum fused evidence of "
             "0.7000 in the saturated cells. The artifact states it only in "
             "prose and exposes `predicted_e_f` as its one 0.7 scalar, so "
             "the measured quantity has no pointer to bind to."),
     "status": "SPECIFIED_NOT_APPLIED",
     "why_not_applied": ("the artifact is committed evidence; adding a key "
                         "to a historical artifact is forbidden. It is "
                         "recorded for a deliberate regeneration.")},
    {"artifact": "research/wp_c8/results/response_surface.json",
     "add_key": "evidence_floor_confirmation.saturated_cell_range",
     "value_would_be": "[0.678, 0.700]",
     "why": ("the manuscript quotes a floor range of 0.678 to 0.700 over the "
             "physics-residual-bound cells. `observed_range` is over all 21 "
             "cells and tops out at 0.9422, so the quoted range has no "
             "artifact home."),
     "status": "SPECIFIED_NOT_APPLIED"},
]


def run() -> dict:
    with open(EXTENSION, encoding="utf-8") as fh:
        ext = json.load(fh)

    unbound = [u for u in ext["unmapped_literals"]
               if u["class"] == "SCIENTIFIC_RESULT"]
    artifacts = _artifacts()

    proposed, ambiguous, unresolved = [], [], []
    for entry in unbound:
        lit, why = entry["literal"], entry.get("why", "")
        cands = candidates_for(lit, why, artifacts)

        # Collapse candidates that are the same artifact+pointer.
        uniq = {(c["artifact"], c["json_pointer"]): c for c in cands}
        cands = sorted(uniq.values(),
                       key=lambda c: (c["artifact"], c["json_pointer"]))

        row = {"literal": lit, "why": why,
               "context": entry.get("context", "")[:200]}
        if len(cands) == 1:
            verdict, reason = ADJUDICATION.get(
                lit, ("UNVERIFIED",
                      "no human has opened this one; a tool proposal is not "
                      "a binding"))
            proposed.append({**row, **cands[0],
                             "status": "PROPOSED",
                             "human_verdict": verdict,
                             "human_reason": reason})
        elif len(cands) > 1:
            ambiguous.append({**row, "candidates": cands[:6],
                              "candidate_count": len(cands),
                              "status": "AMBIGUOUS_UNRESOLVED"})
        else:
            unresolved.append({**row, "status": "NO_CANDIDATE",
                               "reason": ("no artifact carries this value at "
                                          "its printed precision under a "
                                          "pointer whose path relates to the "
                                          "description")})

    return {
        "schema": "csia.publication.proposed_prose_bindings/1",
        "status": "PROPOSED_NOT_APPLIED",
        "why_not_applied": (
            "These bind into papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml, "
            "which the immutable E1 freeze manifest hashes. Applying them "
            "would break the freeze they are recorded in. Merge at a "
            "deliberate re-freeze."),
        "artifacts_searched": len(artifacts),
        "forbidden_prefixes": list(FORBIDDEN_PREFIXES),
        "literals_considered": len(unbound),
        "proposed": proposed,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "counts": {
            "tool_proposed": len(proposed),
            "human_confirmed": sum(
                1 for p in proposed
                if p["human_verdict"].startswith("CONFIRMED")),
            "human_rejected": sum(
                1 for p in proposed
                if p["human_verdict"].startswith("REJECTED")),
            "ambiguous": len(ambiguous),
            "no_candidate": len(unresolved),
        },
        "specified_artifact_corrections": SPECIFIED_ARTIFACT_CORRECTIONS,
        "two_of_five_tool_proposals_were_wrong": (
            "The tool proposed five and a human check rejected two: one bound "
            "a TICK DISTANCE that coincidentally equalled the value, and one "
            "bound the lower bound of a WIDER population than the prose "
            "describes. That is the whole argument for why a numeric match "
            "cannot be a binding, restated with the specific cases."),
        "rules": [
            "value matches to the literal's PRINTED precision",
            "artifact is not under a forbidden prefix",
            "the JSON pointer's path shares a meaningful token with the "
            "literal's description -- a bare numeric match is coincidence",
            "exactly ONE candidate survives; two is AMBIGUOUS, not a coin "
            "toss",
        ],
        "a_high_unresolved_count_is_correct": (
            "These numbers were written by hand and most will need a human "
            "to say where they came from. Proposing a binding this tool "
            "cannot justify would manufacture the exact false provenance "
            "chain the S0 finding was about."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    doc = run()
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    c = doc["counts"]
    print(f"\n{c['tool_proposed']} tool-proposed "
          f"({c['human_confirmed']} human-confirmed, "
          f"{c['human_rejected']} human-REJECTED), "
          f"{c['ambiguous']} ambiguous, "
          f"{c['no_candidate']} with no candidate, of "
          f"{doc['literals_considered']} literals "
          f"({doc['artifacts_searched']} artifacts searched)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
