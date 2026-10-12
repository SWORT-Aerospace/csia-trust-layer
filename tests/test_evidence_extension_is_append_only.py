"""`scientific_core_changed: false` is a measurement, not a promise.

The physical-validation program's whole defensibility rests on one sentence:
the frozen diagnostic core was not touched to make a validation result come
out. A YAML field asserting that is worth nothing -- it is exactly the field
somebody edits at 2am when a trial will not reproduce.

So this re-derives it from git on every run. If any path the extension calls
forbidden differs from the frozen tag, the test fails and names the file.

WHY THIS IS THE MOST IMPORTANT TEST IN THE PROGRAM
--------------------------------------------------
Every other guard here checks that we measured something correctly. This one
checks that we did not move the thing we were measuring. A physical-validation
campaign that quietly retuned a threshold would produce beautiful, worthless
evidence, and no amount of trial-count or hardware realism would recover it.

The `git diff` is against the TAG, not against a parent commit, so a change
that is made and then reverted still shows as clean -- which is correct: the
question is whether the core the trials ran against is the frozen core, not
whether the working tree took a detour.
"""

from __future__ import annotations

import os
import subprocess

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = os.path.join(ROOT, "research", "physical_validation",
                   "EVIDENCE_EXTENSION.yaml")

pytestmark = pytest.mark.skipif(
    not os.path.exists(EXT),
    reason="the physical-validation extension does not exist on this branch")


def _ext():
    with open(EXT, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True)


def _tag_exists(ref):
    return _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") \
        .returncode == 0


def test_the_extension_declares_the_core_unchanged():
    """The field itself. If somebody flips it to true, that is a disclosure,
    and the program's conclusions have to be re-read in that light -- so the
    test says so loudly rather than passing quietly."""
    ext = _ext()
    assert ext["scientific_core_changed"] is False, (
        "EVIDENCE_EXTENSION.yaml now declares the frozen scientific core "
        "CHANGED. That is not a test failure to route around: every physical "
        "result in this program was supposed to run against the frozen core, "
        "and if the core moved, the results describe something else. Say what "
        "changed and why in the extension file, and re-read the program's "
        "conclusions before touching this test.")


def test_no_forbidden_path_differs_from_the_frozen_core():
    """The measurement behind the field."""
    ext = _ext()
    tag = ext["scientific_core_sha"]
    if not _tag_exists(tag):
        pytest.skip(f"frozen core commit {tag[:8]} not present in this clone "
                    f"(shallow?); nothing to compare against")

    dirty = []
    for path in ext["forbidden_paths"]:
        if not os.path.exists(os.path.join(ROOT, path)):
            dirty.append(f"{path}: MISSING FROM THE WORKING TREE")
            continue
        proc = _git("diff", "--stat", tag, "--", path)
        if proc.returncode != 0:
            dirty.append(f"{path}: git diff failed -- {proc.stderr.strip()}")
        elif proc.stdout.strip():
            dirty.append(f"{path}:\n    "
                         + "\n    ".join(proc.stdout.strip().split("\n")))

    assert not dirty, (
        "the physical-validation extension has modified the FROZEN SCIENTIFIC "
        "CORE:\n\n  " + "\n  ".join(dirty) + "\n\n"
        "Rule 1 of the program: do not modify the frozen core to make a test "
        "pass, and do not retune thresholds, weights, priors, signatures, "
        "freshness limits, smoothing or gate definitions after seeing a "
        "validation outcome. If a validation trial fails, REPORT THE FAILURE "
        "in research/physical_validation/FAILURE_LEDGER.yaml.")


def test_the_parent_freeze_is_named_and_reachable():
    """An extension whose parent cannot be resolved is not append-only to
    anything in particular."""
    ext = _ext()
    parent = ext["parent_evidence_freeze"]["commit"]
    if not _tag_exists(parent):
        pytest.skip(f"parent freeze {parent[:8]} not present in this clone")
    assert len(parent) == 40, "the parent freeze must be a full 40-char SHA"


def test_every_allowed_path_is_outside_every_forbidden_path():
    """A path list that permits and forbids the same directory decides
    nothing. Checked mechanically because the two lists are edited by hand and
    a nested overlap is invisible on inspection."""
    ext = _ext()
    overlaps = []
    for allowed in ext["allowed_paths"]:
        for forbidden in ext["forbidden_paths"]:
            a = allowed.rstrip("/") + "/"
            f = forbidden.rstrip("/") + "/"
            if a.startswith(f) or f.startswith(a):
                overlaps.append(f"allowed {allowed!r} overlaps forbidden "
                                f"{forbidden!r}")
    assert not overlaps, "\n  ".join([""] + overlaps)
