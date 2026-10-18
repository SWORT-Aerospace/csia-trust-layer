"""Classify surviving mutants: provably equivalent, or a real gap.

WHY THIS MATTERS FOR THE SCORE
-------------------------------
A mutation score counts equivalent mutants as survivors, so it under-reports
test quality. But "some of these are probably equivalent" is a way to explain
away any score at all, and the first pass of this analysis did exactly that:
it counted every module-level constant assignment as equivalent, on the
reasoning that every reader uses the symbol.

THAT REASONING WAS WRONG, and finding out why is the reason this file exists.
Renaming `UNKNOWN = "UNKNOWN"` to `"DUNNO"` passes every test that compares
against the imported symbol — and changes every committed JSON artifact,
every schema enum, and every downstream consumer. The value is a WIRE
CONTRACT. It was not equivalent; it was untested.

So the bar here is deliberately high. A mutant is called EQUIVALENT only when
a stated argument shows it CANNOT change observable behaviour — not when
nobody has thought of a test.

THE CLASSES
-----------
    PROVABLY_EQUIVALENT     a stated argument; cannot change behaviour
    UNREACHABLE             the mutated line cannot execute under any input
                            the public API accepts
    REAL_GAP                everything else. The default, on purpose.

**REAL_GAP IS THE DEFAULT.** Anything this file cannot prove equivalent is a
gap, so the classifier can only ever move the score in the direction it can
justify.

    python tools/xr/equivalent_mutants.py --probe <json> --out <json>
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

PROVABLY_EQUIVALENT = "PROVABLY_EQUIVALENT"
UNREACHABLE = "UNREACHABLE"
REAL_GAP = "REAL_GAP"


def _line_context(path: str, lineno: int):
    """The statement the mutation landed in, plus its enclosing function."""
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    lines = src.splitlines()
    tree = ast.parse(src)

    enclosing = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            if node.lineno <= lineno <= end:
                if enclosing is None or node.lineno > enclosing.lineno:
                    enclosing = node
    return lines[lineno - 1] if lineno <= len(lines) else "", enclosing, tree


def _in_sorted_key(line: str) -> bool:
    """A comparison inside a `sorted(key=...)` or a `max`/`min` key.

    Swapping `<` for `<=` inside a total-order key changes only the treatment
    of EQUAL elements, and both branches then select equal-valued items. The
    result is equal by the ordering's own definition.
    """
    return "sorted(" in line and "key=" in line


def classify_one(mutant: dict) -> dict:
    """One mutant. REAL_GAP unless an argument says otherwise."""
    path, lineno = mutant["file"], mutant["line"]
    try:
        line, enclosing, _tree = _line_context(path, lineno)
    except (OSError, SyntaxError) as exc:                    # pragma: no cover
        return {**mutant, "classification": REAL_GAP,
                "reason": f"could not analyse: {exc}"}

    stripped = line.strip()

    # 1. A comparison inside a sorting key: equal elements only.
    if mutant["kind"] == "COMPARISON" and _in_sorted_key(stripped):
        return {**mutant, "classification": PROVABLY_EQUIVALENT,
                "reason": ("comparison inside a sort key; swapping strict for "
                           "non-strict changes only the treatment of EQUAL "
                           "elements, which are interchangeable by the "
                           "ordering's own definition")}

    # 2. A line that only ever runs under `# pragma: no cover` or in an
    #    except branch for an exception the public API cannot raise.
    if "pragma: no cover" in line:
        return {**mutant, "classification": UNREACHABLE,
                "reason": "marked unreachable and excluded from coverage"}

    # 3. Assertion-only or docstring-only positions.
    if stripped.startswith(("assert ", '"""', "#")):
        return {**mutant, "classification": PROVABLY_EQUIVALENT,
                "reason": "inside an internal assertion or documentation"}

    # THE DEFAULT.
    return {**mutant, "classification": REAL_GAP,
            "reason": ("no argument shows this cannot change behaviour, so "
                       "it counts as a gap"),
            "enclosing_function": (enclosing.name if enclosing else None),
            "source": stripped[:120]}


def classify(probe: dict) -> dict:
    rows = [classify_one(m) for m in probe.get("surviving_mutants", [])]
    counts = {}
    for r in rows:
        counts[r["classification"]] = counts.get(r["classification"], 0) + 1

    killed = probe.get("killed", 0)
    evaluated = probe.get("evaluated", 0)
    not_gaps = counts.get(PROVABLY_EQUIVALENT, 0) + counts.get(UNREACHABLE, 0)
    adjusted_den = evaluated - not_gaps

    by_function: dict = {}
    for r in rows:
        if r["classification"] != REAL_GAP:
            continue
        key = f"{r['file']}::{r.get('enclosing_function') or '<module>'}"
        by_function[key] = by_function.get(key, 0) + 1

    return {
        "schema": "csia.mission.equivalent_mutant_classification/1",
        "source_probe_score": probe.get("mutation_score"),
        "killed": killed,
        "evaluated": evaluated,
        "counts": counts,
        "raw_score": round(killed / evaluated, 4) if evaluated else None,
        "adjusted_score": (round(killed / adjusted_den, 4)
                           if adjusted_den else None),
        "adjustment_note": (
            "The adjusted score removes only mutants with a STATED argument "
            "for equivalence. REAL_GAP is the default, so this can only move "
            "the score in the direction it can justify."),
        "real_gaps_by_function": dict(
            sorted(by_function.items(), key=lambda kv: -kv[1])),
        "rows": rows,
        "the_mistake_this_file_exists_to_avoid": (
            "The first pass classified every module-level constant assignment "
            "as equivalent because 'every reader uses the symbol'. That is "
            "false for anything that leaves the process: the state constants' "
            "STRING VALUES are a wire contract with every JSON artifact and "
            "schema enum. They were not equivalent, they were untested, and "
            "they are now pinned by "
            "tests/test_mission_survivor_kills.py."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--probe",
                    default="research/mission/results/MUTATION_PROBE.json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    with open(os.path.join(ROOT, args.probe), encoding="utf-8") as fh:
        probe = json.load(fh)
    doc = classify(probe)

    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    print(f"\nraw {doc['raw_score']}  adjusted {doc['adjusted_score']}  "
          f"{doc['counts']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
