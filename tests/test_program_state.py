"""The paper lock, enforced rather than asserted.

`docs/CURRENT_PROGRAM_STATE.md` says product development is frozen at v2
Phase C and that Forge is documentation only. A freeze that lives only in a
markdown file is a freeze until somebody is in a hurry. These tests make the
two mechanical parts of it mechanical:

  * no new v2 domain module appears
  * `forge/` contains no code

They do NOT try to police intent. A human deciding to lift the freeze edits
this file and the state document together, which is the point: the change
becomes visible in a diff rather than happening quietly.
"""

from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The six domains frozen at Phase C. Adding a seventh is the exact thing the
#: management decision forbids until both papers are submission-candidate.
FROZEN_V2_DOMAINS = {
    "__init__.py", "actuation.py", "communication.py", "compute.py",
    "navigation.py", "power.py", "timing.py",
}

FORBIDDEN_DOMAIN_NAMES = ("estimator", "energy", "thermal", "security",
                          "firmware", "storage")


def test_no_seventh_v2_domain_has_appeared():
    here = os.path.join(ROOT, "csia", "v2", "domains")
    found = {f for f in os.listdir(here) if f.endswith(".py")}
    extra = found - FROZEN_V2_DOMAINS
    assert not extra, (
        f"new v2 domain module(s) {sorted(extra)}. Product development is "
        f"FROZEN at v2 Phase C until BOTH papers reach submission-candidate "
        f"state -- see docs/CURRENT_PROGRAM_STATE.md and "
        f"engineering/v2/V2_PHASEC_FREEZE.md. If the lock has been released, "
        f"update FROZEN_V2_DOMAINS here in the same commit.")


def test_no_forbidden_domain_is_registered():
    """The core RESERVES ids for ESTIMATOR, THERMAL, STORAGE,
    FIRMWARE_CONFIGURATION and SECURITY_INTEGRITY -- that vocabulary is part
    of the frozen Phase-A contract and reserving an id is not implementing a
    domain. What the freeze governs is whether a profile REGISTERS a plugin
    for one, so that is what is checked.

    (The first version of this test asserted the ids were absent, which was
    simply wrong about the codebase and would have had to be deleted rather
    than fixed.)
    """
    from csia.v2.profiles import build_engine_for
    from csia.v2.profiles import SCENARIOS

    seen = set()
    for name in ("NOMINAL",):
        if name not in SCENARIOS:
            continue
        engine = build_engine_for(SCENARIOS[name])
        seen |= {d.domain_id for d in engine.registry.domains()}
    assert seen, "no engine could be built; the check would pass vacuously"
    for did in sorted(seen):
        assert not any(n in did.lower() for n in FORBIDDEN_DOMAIN_NAMES), (
            f"domain {did!r} is registered. Product development is FROZEN at "
            f"v2 Phase C -- see docs/CURRENT_PROGRAM_STATE.md.")


def test_forge_contains_no_code():
    forge = os.path.join(ROOT, "forge")
    assert os.path.isdir(forge), "forge/ should exist and hold the future docs"
    code = []
    for dirpath, _dirnames, filenames in os.walk(forge):
        for f in filenames:
            if os.path.splitext(f)[1] in (".py", ".c", ".cpp", ".h", ".rs",
                                          ".go", ".java", ".ts", ".js"):
                code.append(os.path.relpath(os.path.join(dirpath, f), ROOT))
    assert not code, (
        f"Forge production code found: {sorted(code)}. Forge is "
        f"DOCUMENTATION / PRIOR ART ONLY until both papers are "
        f"submission-candidate. See forge/README_FUTURE.md section 7.")


def test_the_program_state_document_says_what_the_freeze_is():
    """A state file that stopped saying 'FROZEN' would silently unlock the
    repository for every future agent that reads it first.

    The header block was reformatted during the 2026-09 repository
    finalization: the trailing colons went, `PRODUCT DEVELOPMENT` became
    `ENGINEERING`, `DUAL PAPER COMPLETION` became `DUAL PAPER FINALIZATION`,
    and per-paper status plus an explicit next-phase lock were added. The
    tokens below track that change. **The set did not shrink** -- every
    constraint the old list asserted is still asserted here, and three more
    are, so this is not a guard being loosened to fit a rewrite.
    """
    path = os.path.join(ROOT, "docs", "CURRENT_PROGRAM_STATE.md")
    text = open(path, encoding="utf-8").read()
    for required in ("CURRENT PRIORITY", "DUAL PAPER FINALIZATION",
                     "ENGINEERING", "FROZEN AT V2 PHASE C",
                     "SYSTEMS PAPER", "MATHEMATICAL PAPER", "FINALIZATION",
                     "FORGE", "DOCUMENTATION / PRIOR ART ONLY",
                     "HARDWARE", "NOT CURRENT GATE",
                     "NEXT PRODUCT PHASE",
                     "LOCKED UNTIL BOTH PAPER SUBMISSION-CANDIDATE TAGS EXIST"):
        assert required in text, f"{path} no longer states {required!r}"


def test_the_program_state_names_the_three_canonical_freezes():
    """The document's stated job is to let another engineer recover the state
    without conversation history. That is impossible without the commits."""
    path = os.path.join(ROOT, "docs", "CURRENT_PROGRAM_STATE.md")
    text = open(path, encoding="utf-8").read()
    for tag, commit in (
            ("csia-v1.0-research-final",
             "ec5acd189295dab9259d4989657d42184d6142a3"),
            ("csia-v2-phasec-frozen",
             "50c5d3576e9084e7c2789167628392c5de992b6f"),
            ("csia-dual-paper-evidence-freeze",
             "eb2577d6830208b26d33facb283aa5be0ddf7c86")):
        assert tag in text, f"{path} does not name the tag {tag!r}"
        assert commit in text, (
            f"{path} names {tag!r} without its commit; a tag can be moved, a "
            f"SHA cannot")


def test_the_phase_c_freeze_record_exists_and_names_its_commit():
    path = os.path.join(ROOT, "engineering", "v2", "V2_PHASEC_FREEZE.md")
    text = open(path, encoding="utf-8").read()
    assert "50c5d3576e9084e7c2789167628392c5de992b6f" in text
    assert "NO FURTHER V2 IMPLEMENTATION UNTIL PAPER LOCK RELEASE" in text


def test_neither_submission_candidate_tag_is_claimed_to_exist():
    """The gates are not met. A document claiming otherwise would be the
    worst possible failure of this file."""
    path = os.path.join(ROOT, "docs", "CURRENT_PROGRAM_STATE.md")
    text = open(path, encoding="utf-8").read()
    assert "SYSTEMS PAPER: BLOCKED" in text
    assert "MATHEMATICAL PAPER: BLOCKED" in text
