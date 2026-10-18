"""Separate "which number is this?" from "which path names it?".

WHAT WAS LEFT
-------------
`resolve_ambiguous_bindings.py` narrowed the prose literals by section and
left 19 STILL_AMBIGUOUS. Reading them shows they are not one problem but
three, and lumping them together is why they looked intractable:

  DUPLICATE_POINTER   two JSON pointers into the SAME artifact reaching the
                      SAME quantity, because the artifact publishes a run
                      both in full and as a summary projection of itself.
                      The quantity is not ambiguous at all -- only the path
                      is. This is decidable mechanically and this tool does
                      it.

  DISTINCT_DATA       candidates that are genuinely different measurements
                      which happen to share a rounded value. Deciding needs
                      the prose's stated condition matched against sibling
                      fields, and it is left to a human.

  TOO_COMMON          values like 1.000 and 0.000 that appear everywhere.
                      MX-013 already records that a tool guessed two of
                      five of these wrongly. They should not be auto-bound
                      at any confidence.

WHAT "SAME QUANTITY" MEANS HERE, PRECISELY
-------------------------------------------
Two candidates are the same quantity when they are in the same artifact,
carry the same value, end in the same key, and one's containing object is a
FIELD SUBSET of the other's with every shared field equal. That last clause
is what makes it mechanical rather than a guess: a summary projection agrees
with its source on everything it chooses to carry. If any shared field
differs, they are two different records and this tool says nothing.

**NOTHING IS APPLIED.** These bind into
`papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml`, which the E1 freeze manifest
hashes; writing them would break the freeze they are recorded in. The output
is a proposal set for a deliberate re-freeze, exactly as
`resolve_ambiguous_bindings.py` leaves its own.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

SOURCE = "research/publication/AMBIGUOUS_BINDING_RESOLUTION.json"

DUPLICATE_POINTER = "DUPLICATE_POINTER"
DISTINCT_DATA = "DISTINCT_DATA_SHARING_A_VALUE"
TOO_COMMON = "VALUE_TOO_COMMON_TO_BIND"
UNCHANGED = "STILL_AMBIGUOUS"

#: Values that occur so often that section context cannot narrow them. Named
#: explicitly rather than discovered, so the list is reviewable.
COMMON_VALUES = {"0.000", "1.000", "0.0", "1.0"}


def _load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_pointer(doc, pointer: str):
    """Walk a JSON pointer, returning (value, parent_object)."""
    node, parent = doc, None
    for raw in pointer.strip("/").split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        parent = node
        if isinstance(node, list):
            node = node[int(key)]
        else:
            node = node[key]
    return node, parent


def _is_projection_of(small: dict, large: dict) -> bool:
    """True when `small` is a field subset of `large` and they agree.

    A summary projection carries fewer fields than its source and agrees on
    every field it does carry. Disagreement on any shared field means two
    different records, and the answer is then no.
    """
    if not isinstance(small, dict) or not isinstance(large, dict):
        return False
    if not small or set(small) >= set(large):
        return False
    return all(k in large and large[k] == v for k, v in small.items())


def classify(literal: dict) -> dict:
    """Decide what KIND of ambiguity one literal has."""
    cands = literal.get("surviving") or []
    out = {"literal": literal["literal"],
           "section": literal.get("section"),
           "candidate_count": len(cands)}

    if literal["literal"] in COMMON_VALUES:
        out["kind"] = TOO_COMMON
        out["why"] = (
            "this value appears throughout the repository as a saturated "
            "probability, a full gate weight or a unit coefficient. Section "
            "context cannot narrow it, and MX-013 records a tool binding two "
            "of five such proposals wrongly. It should not be auto-bound.")
        return out

    artifacts = {c["artifact"] for c in cands}
    values = {round(float(c["value"]), 9) for c in cands}
    if len(cands) < 2 or len(artifacts) != 1 or len(values) != 1:
        out["kind"] = UNCHANGED
        out["why"] = ("candidates span more than one artifact or more than "
                      "one value; this tool only decides path aliasing "
                      "within a single artifact")
        return out

    artifact = artifacts.pop()
    try:
        doc = _load(artifact)
        parents = []
        for c in cands:
            _, parent = _resolve_pointer(doc, c["json_pointer"])
            parents.append(parent)
    except Exception as exc:
        out["kind"] = UNCHANGED
        out["why"] = f"could not resolve pointers: {type(exc).__name__}"
        return out

    # Exactly one containing object should be a projection of another.
    pairs = [(i, j) for i in range(len(parents)) for j in range(len(parents))
             if i != j and _is_projection_of(parents[i], parents[j])]
    if not pairs:
        out["kind"] = DISTINCT_DATA
        out["why"] = (
            "same artifact and same value, but neither record is a field "
            "subset of the other -- they are different measurements that "
            "share a rounded value. Which one the prose means depends on "
            "the condition it states, and needs a human.")
        out["candidates"] = [
            {"json_pointer": c["json_pointer"],
             "distinguishing_fields": _distinguishers(parents, k)}
            for k, c in enumerate(cands)]
        return out

    # The SOURCE record -- the one that is not a projection of anything --
    # is the canonical pointer, because it is the record that identifies
    # the run rather than a view selected from it.
    projections = {i for i, _ in pairs}
    sources = [k for k in range(len(cands)) if k not in projections]
    out["kind"] = DUPLICATE_POINTER
    out["artifact"] = artifact
    out["proposed_pointer"] = cands[sources[0]]["json_pointer"] if sources \
        else cands[0]["json_pointer"]
    out["alias_pointers"] = [cands[i]["json_pointer"] for i in
                             sorted(projections)]
    out["why"] = (
        "both pointers reach the same quantity in the same artifact: one "
        "record is a field subset of the other and agrees on every shared "
        "field, i.e. a summary projection of it. The QUANTITY is not "
        "ambiguous -- only the path. The proposal is the fuller record, "
        "because it is the one that identifies which run the number came "
        "from.")
    if sources:
        extra = sorted(set(parents[sources[0]]) - set(parents[
            sorted(projections)[0]]))
        out["fields_only_in_the_proposed_record"] = extra
    return out


def _distinguishers(parents, k) -> dict:
    """Fields that differ between this record and the others."""
    me = parents[k]
    if not isinstance(me, dict):
        return {}
    others = [p for i, p in enumerate(parents) if i != k
              and isinstance(p, dict)]
    return {key: me[key] for key in sorted(me)
            if any(o.get(key) != me[key] for o in others)}


def run() -> dict:
    src = _load(SOURCE)

    def final(lit):
        return lit.get("human_verdict") or lit["tool_verdict"]

    unresolved = [x for x in src["literals"] if final(x) == UNCHANGED]
    results = [classify(x) for x in unresolved]

    counts: dict = {}
    for r in results:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1

    return {
        "schema": "csia.publication.duplicate_pointer_resolution/1",
        "source": SOURCE,
        "unresolved_in": len(unresolved),
        "counts": counts,
        "results": results,
        "nothing_is_applied": (
            "these bind into papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml, "
            "which the E1 freeze manifest hashes. Writing them would break "
            "the freeze they are recorded in. Merge at a deliberate "
            "re-freeze."),
        "a_duplicate_pointer_is_still_a_proposal": (
            "DUPLICATE_POINTER decides that two paths name the same "
            "quantity, which is mechanical. WHICH path a paper should cite "
            "is an editorial choice, and the recommendation here -- the "
            "record that identifies the run -- is a stated preference, not "
            "a derivation."),
        "what_is_deliberately_not_decided": (
            "DISTINCT_DATA and VALUE_TOO_COMMON_TO_BIND are left open. "
            "MX-013 records a tool getting two of five such bindings wrong; "
            "the response is to narrow what a tool claims, not to raise its "
            "confidence."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rep = run()
    if args.out:
        path = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")
    print(f"unresolved literals examined: {rep['unresolved_in']}")
    for kind, n in sorted(rep["counts"].items()):
        print(f"  {kind}: {n}")
    for r in rep["results"]:
        if r["kind"] == DUPLICATE_POINTER:
            print(f"    {r['literal']:<8s} -> {r['proposed_pointer']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
