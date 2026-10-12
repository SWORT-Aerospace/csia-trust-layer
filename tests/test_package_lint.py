"""The shipped package carries no dead code, and the one exemption is frozen.

WHY THIS FILE EXISTS
--------------------
`csia/` is what a customer installs. Dead imports, unused locals and spurious
f-strings in it are not style opinions: each one is a statement that was
written to do something and does not, and at least one in this repository was
hiding a real defect. `csia/validation.py` computed a fresh random seed per
Monte Carlo trial and passed it to a generator that ignores seeds --- the
campaign's 150 runs all flew the same trajectory. The dead value was the only
visible symptom, and nothing was looking for it.

So the invariant is: **the shipped package is pyflakes-clean.**

THE ONE EXEMPTION, AND WHY IT CANNOT BE FIXED
---------------------------------------------
`csia/diagnosis/` is the FROZEN v1 diagnostic core (`tests/test_v1_frozen.py`,
tag `csia-v1.0-research-final`, zero diff permitted). Its `__init__.py`
re-exports names for the public API without an `__all__`, which pyflakes reads
as unused imports, and `baselines.py` has one unused import. The correct fix is
a two-line `__all__` --- and applying it would break the freeze, which is worth
more than the lint. The exemption is therefore a DIRECTORY NAME, listed here,
asserted to be exactly the frozen path, and re-checked against the freeze test
so it cannot quietly widen into cover for a file that starts rotting.

Scope is `csia/` only. `tools/` and `research/` are development and research
code, not the shipped artifact, and holding them to the same bar would mean
editing SITL scripts that cannot be exercised from here.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "csia")

#: Frozen, therefore un-fixable. A path prefix, relative to the repo root.
FROZEN_EXEMPT = ("csia/diagnosis/",)


def test_pyflakes_is_a_declared_dependency_not_a_lucky_local_install():
    """The gate below skips when pyflakes is missing. That is only acceptable
    while pyflakes is part of the dependency set CI installs -- otherwise the
    skip is permanent and the gate checks nothing, anywhere."""
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        dev = tomllib.load(fh)["project"]["optional-dependencies"]["dev"]
    assert any(d.split(">")[0].split("=")[0].strip() == "pyflakes"
               for d in dev), (
        f"pyflakes is not in the [dev] extra ({dev}); "
        f"test_the_shipped_package_is_clean would skip in CI too")


def test_the_exemption_matches_the_actual_freeze():
    """A hand-written exemption list drifts. This one is checked against the
    freeze test's own definition of what is frozen."""
    frozen_src = open(os.path.join(ROOT, "tests", "test_v1_frozen.py"),
                      encoding="utf-8").read()
    for path in FROZEN_EXEMPT:
        stem = path.rstrip("/")
        assert f'"{stem}"' in frozen_src, (
            f"{stem!r} is exempted from lint as 'frozen' but does not appear "
            f"in tests/test_v1_frozen.py's FROZEN_PATHS. Either it is not "
            f"frozen and the lint must be fixed, or the freeze list moved.")
        assert os.path.isdir(os.path.join(ROOT, stem)), stem


def test_the_shipped_package_is_clean():
    try:
        import pyflakes                                    # noqa: F401
    except ImportError:                                    # pragma: no cover
        pytest.skip('pyflakes not installed; pip install -e ".[dev]"')

    proc = subprocess.run([sys.executable, "-m", "pyflakes", PACKAGE],
                          capture_output=True, text=True, cwd=ROOT)
    # pyflakes exits 1 when it reports anything, 0 when clean; anything else
    # (a crash, a bad path) must not be read as a pass.
    assert proc.returncode in (0, 1), (
        f"pyflakes exited {proc.returncode}: {proc.stderr.strip()}")

    findings = []
    for line in proc.stdout.splitlines():
        rel = os.path.relpath(line.split(":", 1)[0], ROOT) \
            if line[:1] not in ("", " ") else line
        if any(rel.startswith(p) for p in FROZEN_EXEMPT):
            continue
        findings.append(line.replace(ROOT + os.sep, ""))

    assert not findings, (
        f"{len(findings)} pyflakes finding(s) in the shipped package:\n  "
        + "\n  ".join(findings) +
        "\n\nEach one is code that says it does something and does not. Fix "
        "it rather than widening FROZEN_EXEMPT -- that list is for the frozen "
        "v1 core alone and is checked against the freeze.")


def test_the_exemption_is_not_hiding_an_empty_set():
    """If csia/diagnosis ever became clean, the exemption should go rather
    than sit there granting cover to a directory that no longer needs it."""
    try:
        import pyflakes                                    # noqa: F401
    except ImportError:                                    # pragma: no cover
        pytest.skip("pyflakes not installed")
    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes",
         os.path.join(ROOT, "csia", "diagnosis")],
        capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode in (0, 1), proc.stderr
    if proc.returncode == 0:
        pytest.fail(
            "csia/diagnosis is now pyflakes-clean, so FROZEN_EXEMPT is "
            "granting cover to nothing. Remove the exemption.")
