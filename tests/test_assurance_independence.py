"""The firewall does not import the thing it is meant to check.

A firewall that reached into `csia.diagnosis` for its support helpers would be
the production implementation wearing a hat: it would agree with itself, and
the agreement would establish nothing. The docstring in `csia_assurance`
promises independence; a docstring is not independence, so this measures it.

HOW IT MEASURES
---------------
A FRESH interpreter imports `csia_assurance`, then reports every module in
`sys.modules`. Fresh, because this test session has already imported half the
repository and an in-process check would pass on modules somebody else loaded.

WHAT IS ALLOWED
---------------
The standard library, and `structural_reference` -- the clean-room module,
itself standard-library-only and written from the definition rather than from
the production code. Nothing else from this repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Repository modules the firewall may import. One entry, and it is the
#: clean-room reference the design deliberately builds on.
ALLOWED_REPO_MODULES = {"structural_reference"}

#: Top-level names that are repository packages rather than stdlib.
REPO_TOP_LEVEL = {"csia", "tools", "research", "engineering", "csia_assurance"}

PROBE = r"""
import json, sys
before = set(sys.modules)
import csia_assurance
after = set(sys.modules)
print(json.dumps(sorted(after - before)))
"""


def _imported_modules():
    proc = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT,
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, (
        f"importing csia_assurance in a fresh interpreter failed:\n"
        f"{proc.stderr[-2000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_the_firewall_imports_nothing_from_the_production_core():
    mods = _imported_modules()
    tops = {m.split(".")[0] for m in mods}
    forbidden = sorted(
        t for t in tops
        if t in REPO_TOP_LEVEL and t != "csia_assurance")
    assert not forbidden, (
        f"csia_assurance imported repository packages it must not touch: "
        f"{forbidden}\nfull import set: {sorted(mods)}")


def test_the_only_repository_module_is_the_cleanroom_reference():
    mods = set(_imported_modules())
    repo_like = {m for m in mods
                 if m in ALLOWED_REPO_MODULES
                 or m.split(".")[0] in REPO_TOP_LEVEL}
    unexpected = sorted(
        m for m in repo_like
        if not m.startswith("csia_assurance")
        and m not in ALLOWED_REPO_MODULES)
    assert not unexpected, f"unexpected repository imports: {unexpected}"
    assert "structural_reference" in mods, (
        "the firewall no longer uses the clean-room reference; if that is "
        "deliberate, this test and the design note both need updating")


def test_it_imports_no_third_party_package():
    """No numpy, no yaml. A dependency here is a dependency in the layer that
    is supposed to still work when things are going wrong."""
    mods = {m.split(".")[0] for m in _imported_modules()}
    third_party = sorted(mods & {"numpy", "yaml", "scipy", "pandas",
                                 "pymavlink", "z3", "hypothesis"})
    assert not third_party, f"third-party imports: {third_party}"


def test_the_cleanroom_reference_itself_stays_independent():
    """It is load-bearing for the firewall now, so its own independence is
    part of the firewall's independence."""
    probe = ("import json, sys\n"
             "sys.path.insert(0, 'research/physical_validation/cleanroom')\n"
             "before = set(sys.modules)\n"
             "import structural_reference\n"
             "print(json.dumps(sorted(set(sys.modules) - before)))\n")
    proc = subprocess.run([sys.executable, "-c", probe], cwd=ROOT,
                          capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr[-2000:]
    mods = json.loads(proc.stdout.strip().splitlines()[-1])
    tops = {m.split(".")[0] for m in mods}
    assert not (tops & REPO_TOP_LEVEL), (
        f"the clean-room reference imported repository code: {sorted(mods)}")


def test_the_firewall_lives_outside_the_frozen_core_directory():
    """Absolute rule 2: protective components sit OUTSIDE the frozen core.

    Checked as a path fact, because it is one.
    """
    assert os.path.isdir(os.path.join(ROOT, "csia_assurance"))
    assert not os.path.exists(os.path.join(ROOT, "csia", "assurance")), (
        "an assurance package has appeared inside csia/. The firewall is "
        "experimental and may not become core semantics without the review "
        "gate in docs/ASSURANCE_REFERENCE_SEMANTICS.md")


def test_no_frozen_core_module_imports_the_firewall():
    """The dependency may not run the other way either.

    If the frozen core imported the firewall, the firewall would be part of
    the core in everything but name, and the freeze would be broken by a
    change to a file outside it.
    """
    import re
    frozen = ["csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
              "csia/runtime/failsafe.py", "csia/scenarios.py",
              "csia/profiles.py"]
    hits = []
    for rel in frozen:
        path = os.path.join(ROOT, rel)
        files = ([path] if os.path.isfile(path) else
                 [os.path.join(b, n) for b, _d, ns in os.walk(path)
                  for n in ns if n.endswith(".py")])
        for f in files:
            body = open(f, encoding="utf-8", errors="replace").read()
            if re.search(r"\bcsia_assurance\b", body):
                hits.append(os.path.relpath(f, ROOT))
    assert not hits, f"frozen core references the firewall: {hits}"
