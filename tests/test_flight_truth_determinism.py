"""The scripted flight truth is deterministic, and `seed` does not change it.

WHY THIS FILE EXISTS
--------------------
`csia.sensors.truth.generate_flight` takes a `seed` parameter that has never
done anything. The truth is scripted -- every field is a closed-form function
of `t` with no noise term -- so two calls differing only in `seed` return
byte-identical output. That determinism is a FEATURE: it is what makes the
committed scenario artifacts reproducible.

The defect was that nothing said so, and a caller believed otherwise.
`csia.validation.monte_carlo` drew a fresh seed per trial:

    truth = generate_flight(seed=int(rng.integers(1, 2 ** 31)))

which reads as per-trial flight randomization and is not one. All 150 runs of
the committed campaign flew the SAME trajectory. The numbers are unaffected --
they were always produced this way, and `campaigns/monte_carlo.json` still
reproduces bit-identically -- but the campaign's variation is over fault class,
amplitude, onset and the clean/faulted split, NOT over the flight, and that
belongs in the open where a reader of the confidence intervals will see it.

WHAT IS PINNED HERE
-------------------
1. the behavioural property, over several seeds and both profiles;
2. the STRUCTURAL property, by AST -- `generate_flight` uses no randomness at
   all, so the behaviour cannot drift back without this test failing;
3. that no caller passes `seed=` to `generate_flight` again;
4. that `monte_carlo` still CONSUMES its per-iteration draw. That draw is
   deliberately retained: `rng` is one stream, and dropping a draw would shift
   every subsequent `rng.random()` and `rng.uniform()`, silently changing a
   committed regression artifact. Deleting the line is the tempting cleanup and
   it is the wrong one.
"""

from __future__ import annotations

import ast
import dataclasses
import os

import numpy as np
import pytest

from csia.sensors.truth import generate_flight

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRUTH_SRC = os.path.join(ROOT, "csia", "sensors", "truth.py")
VALIDATION_SRC = os.path.join(ROOT, "csia", "validation.py")


def _fields_equal(a, b) -> list[str]:
    """Names of the fields that DIFFER between two FlightTruth values."""
    out = []
    for f in dataclasses.fields(a):
        x, y = getattr(a, f.name), getattr(b, f.name)
        same = (np.array_equal(x, y) if isinstance(x, np.ndarray) else x == y)
        if not same:
            out.append(f.name)
    return out


@pytest.mark.parametrize("profile", ["hover_circle", "fast_cruise"])
def test_the_seed_changes_nothing(profile):
    base = generate_flight(profile=profile, seed=42)
    for seed in (0, 1, 7, 2**31 - 1, None):
        other = generate_flight(profile=profile, seed=seed)
        differing = _fields_equal(base, other)
        assert not differing, (
            f"profile {profile!r}: seed={seed!r} changed {differing}. Either "
            f"randomness was added to a generator every committed scenario "
            f"artifact depends on byte-for-byte, or this test is now wrong. "
            f"It is almost certainly the former.")


def test_the_generator_contains_no_randomness_at_all():
    """The structural half. Behaviour can coincide by luck across the seeds
    this file happens to try; an absent RNG call cannot."""
    tree = ast.parse(open(TRUTH_SRC, encoding="utf-8").read(), TRUTH_SRC)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "generate_flight"),
              None)
    assert fn is not None, "generate_flight not found in csia/sensors/truth.py"

    banned = ("default_rng", "random", "normal", "uniform", "standard_normal",
              "integers", "choice", "shuffle", "permutation")
    found = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = (f.attr if isinstance(f, ast.Attribute)
                else f.id if isinstance(f, ast.Name) else None)
        if name in banned:
            found.append(f"line {node.lineno}: {name}(...)")
    assert not found, (
        "generate_flight now calls a random-number routine:\n  "
        + "\n  ".join(found) +
        "\n\nThe scripted truth is deterministic by design and the committed "
        "scenario artifacts depend on it. If randomness is genuinely wanted, "
        "it belongs in the SENSOR layer (csia/sensors), not in the truth.")


def test_no_caller_passes_a_seed_to_generate_flight():
    """The mistake this file was written for, made unrepeatable.

    Passing `seed=` reads as a request for a different flight and cannot be
    one. Any caller that wants variation has to get it somewhere real.

    THIS FILE IS THE ONE EXEMPTION, and it is named rather than pattern-
    matched: `test_the_seed_changes_nothing` has to pass a seed in order to
    demonstrate that passing one changes nothing. A rule against a construct
    necessarily contains the construct; exempting the whole `tests/` tree
    instead would blind the guard to the callers most likely to acquire it.
    """
    exempt = {os.path.abspath(__file__)}
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", ".venv", "__pycache__", "build",
                                    "node_modules", ".pytest_cache"}]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            if os.path.abspath(path) in exempt:
                continue
            try:
                tree = ast.parse(open(path, encoding="utf-8").read(), path)
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                fname = (f.attr if isinstance(f, ast.Attribute)
                         else f.id if isinstance(f, ast.Name) else None)
                if fname != "generate_flight":
                    continue
                if any(k.arg == "seed" for k in node.keywords):
                    offenders.append(f"{os.path.relpath(path, ROOT)}:"
                                     f"{node.lineno}")
    assert not offenders, (
        "generate_flight(seed=...) called at:\n  " + "\n  ".join(offenders) +
        "\n\nThe seed does nothing. If the intent was a different flight, this "
        "does not deliver one; if the intent was reproducibility, it is "
        "already unconditional.")


def test_monte_carlo_still_consumes_its_per_iteration_draw():
    """DO NOT 'clean up' the bare rng.integers call in monte_carlo.

    It looks like a no-op and is not: `rng` is a single stream shared with the
    clean/faulted coin flip, the fault-class pick, the amplitude and the onset.
    Removing the draw shifts all of them and changes
    campaigns/monte_carlo.json, which reproduces bit-identically today.
    """
    tree = ast.parse(open(VALIDATION_SRC, encoding="utf-8").read(),
                     VALIDATION_SRC)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "monte_carlo"),
              None)
    assert fn is not None, "monte_carlo not found in csia/validation.py"

    draws = [n for n in ast.walk(fn)
             if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
             and isinstance(n.value.func, ast.Attribute)
             and n.value.func.attr == "integers"]
    assert len(draws) == 1, (
        f"expected exactly one bare `rng.integers(...)` stream draw in "
        f"monte_carlo, found {len(draws)}. That draw holds the random stream "
        f"in the position campaigns/monte_carlo.json was generated at. If it "
        f"is genuinely being removed, regenerate the campaign artifact and "
        f"say in the commit that the committed numbers moved and why.")
