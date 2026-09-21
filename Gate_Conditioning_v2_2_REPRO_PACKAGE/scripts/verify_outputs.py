#!/usr/bin/env python3
"""Compare every generated JSON against its expected output.

THE RULE
--------
A generated file must equal its expected counterpart EXACTLY, after canonical
JSON ordering, except at paths listed in ENVIRONMENT_SPECIFIC below. Anything
else -- a changed number, an added key, a removed key, a file that was not
generated, a file that was generated and is neither expected nor listed in
NOT_COMPARED -- is a FAIL.

Undeclared differences are rejected on purpose. The tempting design is to
compare floats with a tolerance and move on; that turns a reproduction check
into a plausibility check, and a reproduction that only has to be plausible
is not one. Floats are compared by exact equality of their canonical JSON
text. If a platform's arithmetic genuinely moves a digit, this FAILS and says
which path moved, which is the correct outcome: it is a real finding about
the environment, not noise to be absorbed.

ENVIRONMENT-SPECIFIC FIELDS
---------------------------
Three, each with a reason, each checked for TYPE and PRESENCE rather than
passed over:

  /commit                    the source revision. This package is not a git
                             checkout, so the upstream helper's fallback
                             "UNKNOWN" is the normal value here. Upstream the
                             same field is exempt by name in
                             `make proof-audit-check`.
  /symbolic/sympy_version    the installed sympy, recorded by the audit.
  /symbolic/available        false when sympy is absent. The package pins
                             sympy in requirements.txt so the symbolic pass
                             runs; a reader who skips it still gets a valid
                             numeric reproduction, and this field says which
                             of the two they have.

Nothing else is exempt. In particular every deviation, count, slack, seed,
trial count and verdict is compared exactly.

    python scripts/verify_outputs.py
    python scripts/verify_outputs.py --outputs some/dir
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
DEFAULT_OUTPUTS = os.path.join(PKG, "outputs")
EXPECTED = os.path.join(PKG, "expected_outputs")

#: JSON-pointer-style path -> (reason, accepted python types).
#: A field listed here is checked for presence and type, never for value.
ENVIRONMENT_SPECIFIC = {
    "/commit": ("source revision; this package is not a git checkout, so "
                "'UNKNOWN' is the expected value outside one", (str,)),
    "/symbolic/sympy_version": ("installed sympy version", (str,)),
    "/symbolic/available": ("false when sympy is not installed; the numeric "
                            "pass stands on its own either way", (bool,)),
}


#: Generated files that are deliberately NOT compared, with the reason.
#: Declaring them is the point: a file that simply went unmentioned would be
#: indistinguishable from one nobody noticed.
NOT_COMPARED = {
    "environment_record.json":
        "every field describes the machine that ran the reproduction, so "
        "there is no environment-independent expected value to compare it "
        "against. scripts/verify_environment.py checks it instead, against "
        "requirements.txt and PYTHON_VERSION.txt.",
}


def canonical(obj) -> str:
    """Canonical JSON: sorted keys, fixed separators, no ambiguity.

    Two documents that differ only in key order or whitespace produce the
    same text here, so a diff reported below is a diff in CONTENT.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def flatten(obj, prefix="") -> dict:
    """Every leaf, keyed by its path. Lists are indexed, so a reordered list
    is a difference rather than a silent pass."""
    out = {}
    if isinstance(obj, dict):
        for k in sorted(obj):
            out.update(flatten(obj[k], f"{prefix}/{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}/{i}"))
        out[prefix + "/__len__"] = len(obj)
    else:
        out[prefix] = obj
    return out


def compare(expected, got) -> tuple:
    """(ok, problems, exempted). Exact everywhere except declared paths."""
    fe, fg = flatten(expected), flatten(got)
    problems, exempted = [], []

    for path in sorted(set(fe) | set(fg)):
        declared = ENVIRONMENT_SPECIFIC.get(path)
        if declared is not None:
            reason, types = declared
            if path not in fg:
                problems.append(
                    f"{path}: declared environment-specific but ABSENT from "
                    f"the generated file; the declaration is stale")
            elif not isinstance(fg[path], types):
                problems.append(
                    f"{path}: declared environment-specific with type "
                    f"{[t.__name__ for t in types]}, got "
                    f"{type(fg[path]).__name__}")
            else:
                exempted.append((path, reason, fg[path]))
            continue
        if path not in fe:
            problems.append(f"{path}: present in the generated file, absent "
                            f"from expected -- an UNDECLARED addition")
        elif path not in fg:
            problems.append(f"{path}: expected but NOT generated")
        elif canonical(fe[path]) != canonical(fg[path]):
            problems.append(f"{path}: expected {canonical(fe[path])}, got "
                            f"{canonical(fg[path])}")
    return (not problems), problems, exempted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", default=DEFAULT_OUTPUTS)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    outputs = os.path.abspath(args.outputs)
    if not os.path.isdir(EXPECTED):
        print(f"FAIL: {EXPECTED} is missing; the package is incomplete",
              file=sys.stderr)
        return 2
    if not os.path.isdir(outputs):
        print(f"FAIL: {outputs} does not exist. Run scripts/reproduce.py and "
              f"scripts/srcattr_controls.py first.", file=sys.stderr)
        return 2

    want = sorted(f for f in os.listdir(EXPECTED) if f.endswith(".json"))
    have = sorted(f for f in os.listdir(outputs) if f.endswith(".json"))
    if not want:
        print(f"FAIL: expected_outputs/ contains no JSON; there is nothing "
              f"to verify and a vacuous pass is worse than a failure",
              file=sys.stderr)
        return 2

    failures = 0
    print("OUTPUT VERIFICATION -- canonical JSON, exact except where declared")
    print("=" * 70)

    for name in want:
        gen = os.path.join(outputs, name)
        if not os.path.exists(gen):
            print(f"[FAIL] {name}  -- expected but never generated")
            failures += 1
            continue
        try:
            expected = json.load(open(os.path.join(EXPECTED, name),
                                      encoding="utf-8"))
            got = json.load(open(gen, encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[FAIL] {name}  -- not valid JSON: {e}")
            failures += 1
            continue

        ok, problems, exempted = compare(expected, got)
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if exempted and not args.quiet:
            for path, reason, value in exempted:
                print(f"         declared environment-specific: {path} "
                      f"= {value!r}")
                print(f"           reason: {reason}")
        if not ok:
            failures += 1
            for p in problems:
                print(f"         {p}")

    declared_uncompared = [f for f in have if f in NOT_COMPARED]
    if declared_uncompared and not args.quiet:
        print()
        for name in sorted(declared_uncompared):
            print(f"[skip] {name}  -- declared not-compared")
            print(f"         reason: {NOT_COMPARED[name]}")

    extra = [f for f in have if f not in want and f not in NOT_COMPARED]
    if extra:
        print()
        for name in extra:
            print(f"[FAIL] {name}  -- generated but NOT declared in "
                  f"expected_outputs/ and not in NOT_COMPARED; an "
                  f"undeclared artifact is an unexplained difference")
        failures += len(extra)

    print("=" * 70)
    if failures:
        print(f"FAIL: {failures} file(s) did not match", file=sys.stderr)
        return 1
    print(f"PASS: {len(want)} file(s) matched expected_outputs/ exactly, "
          f"apart from {len(ENVIRONMENT_SPECIFIC)} declared "
          f"environment-specific field(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
