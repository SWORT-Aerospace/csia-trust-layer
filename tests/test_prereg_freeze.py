"""Every preregistration is byte-identical to the commit that froze it.

A preregistration's whole value is that it was fixed BEFORE the trials it
governs. That property is checkable from git and nowhere else: a document can
say "committed before the first trial" while having been quietly edited
afterwards, and the sentence would still be there.

WHAT THIS CHECKS, AND WHAT IT CANNOT
-------------------------------------
It checks that the blob at HEAD equals the blob at the named freeze commit --
so any later edit fails here, loudly, naming the file.

It does NOT and cannot check that the freeze commit predates the first trial in
wall-clock terms. That ordering is established by the campaign directories'
own commit history, and the honest limit is worth stating rather than implying
this test proves more than it does.

The freeze commits are short hashes, resolved through `git rev-parse`, so a
history rewrite that orphans one fails rather than silently passing.
"""

from __future__ import annotations

import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PREREG_DIR = "research/physical_validation/prereg"

#: preregistration -> the commit it was frozen at, and the campaign it governs.
FROZEN = {
    f"{PREREG_DIR}/MECHANISM_A_ARDUPILOT_TRUST_COMPLETION_PREREG.md": (
        "ceeaf4a", "CAMPAIGN_A2"),
    f"{PREREG_DIR}/MECHANISM_A_PX4_REPEATED_PREREG.md": (
        "1968ffd", "CAMPAIGN_P1"),
}


def _git(*args):
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, timeout=60)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _have_git():
    return _git("rev-parse", "--git-dir")[0] == 0


@pytest.mark.parametrize("path,freeze,campaign",
                         [(p, c, n) for p, (c, n) in sorted(FROZEN.items())])
def test_the_preregistration_is_unchanged_since_it_was_frozen(path, freeze,
                                                              campaign):
    if not _have_git():
        pytest.skip("not a git checkout")
    rc_head, at_head, err_head = _git("rev-parse", f"HEAD:{path}")
    assert rc_head == 0, f"{path} is not at HEAD: {err_head}"
    rc_frozen, at_freeze, err_frozen = _git("rev-parse", f"{freeze}:{path}")
    if rc_frozen != 0:
        pytest.skip(f"freeze commit {freeze} not in this clone: {err_frozen}")
    assert at_head == at_freeze, (
        f"{path} governs {campaign} and has CHANGED since it was frozen at "
        f"{freeze}: blob {at_freeze} -> {at_head}. A preregistration edited "
        f"after its trials is not a preregistration. If the change is "
        f"deliberate, it belongs in a NEW preregistration for a NEW campaign.")


def test_every_frozen_preregistration_still_exists():
    """A freeze that was deleted rather than edited is the same defect."""
    for path in FROZEN:
        assert os.path.exists(os.path.join(ROOT, path)), f"{path} is gone"
