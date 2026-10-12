"""Phase 6 — the cross-architecture audit of PX4 and ArduPilot source.

Two kinds of test live here, and the split is deliberate.

The first kind runs everywhere: it checks the audit's own discipline -- that
the vocabulary is the preregistered one, that nothing claims a runtime
classification while nothing has been run, and that the committed artifact
still says what the module says.

The second kind needs the PX4 and ArduPilot checkouts and SKIPS without them.
Those tests re-read every anchor in the real source. A skip is not a pass and
the artifact records the commit of each tree, so a reader can tell which
happened.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "consequence"))

import crossarch_audit as ca                              # noqa: E402

ARTIFACT = ROOT / "research" / "consequence" / "results" / "CROSSARCH_AUDIT.json"

TREES_PRESENT = all(os.path.isdir(p) for p in ca.DEFAULT_TREES.values())
needs_trees = pytest.mark.skipif(
    not TREES_PRESENT,
    reason=f"needs the PX4 and ArduPilot checkouts: {ca.DEFAULT_TREES}")


# --- discipline, checkable anywhere ---------------------------------------

def test_the_classification_vocabulary_is_the_preregistered_one():
    prereg = ROOT / "research" / "consequence" / "PREREGISTRATION.md"
    text = prereg.read_text(encoding="utf-8")
    for value in ca.CLASSIFICATIONS:
        assert value in text, f"{value} is not in the preregistration"


def test_no_finding_claims_a_runtime_classification():
    """Nothing in this phase executes an autopilot, so nothing may claim to."""
    runtime = {ca.RUNTIME_REPRODUCED, ca.RUNTIME_NOT_REPRODUCED}
    offenders = [f.fid for f in ca.FINDINGS if f.classification in runtime]
    assert offenders == [], offenders


def test_every_finding_is_source_analysis():
    assert {f.as_dict()["evidence_level"] for f in ca.FINDINGS} == \
        {"SOURCE_ANALYSIS"}


def test_finding_ids_are_unique():
    ids = [f.fid for f in ca.FINDINGS]
    assert len(ids) == len(set(ids)), ids


@pytest.mark.parametrize("kwarg,bad", [
    ("classification", "PROBABLY_THERE"),
    ("gate_kind", "VIBES"),
    ("coverage", "SOMETHING_ELSE"),
])
def test_an_undefined_vocabulary_value_is_refused(kwarg, bad):
    good = dict(fid="X", stack=ca.PX4, path="a.cpp", line=1, anchor="x",
                regime="r", gate_kind=ca.VEHICLE_STATE, relation_lost="l",
                independent_path="p", coverage=ca.NONE_FOUND,
                classification=ca.STRUCTURALLY_PRESENT, note="n")
    good[kwarg] = bad
    with pytest.raises(ValueError):
        ca.Finding(**good)


def test_the_audit_imports_no_csia_module():
    """Independence, asserted the way `independent_checker.py` asserts it:
    in a fresh interpreter, by inspecting sys.modules after the import."""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import crossarch_audit;"
        "leaked = sorted(m for m in sys.modules"
        " if m == 'csia' or m.startswith('csia'));"
        "print(leaked)" % str(ROOT / "research" / "consequence"))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


# --- the committed artifact -----------------------------------------------

def _artifact():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_artifact_exists_and_declares_it_ran_nothing():
    doc = _artifact()
    assert doc["schema"] == "csia.consequence.crossarch_audit/1"
    assert doc["evidence_level"] == "SOURCE_ANALYSIS"
    assert doc["executed_anything"] is False


def test_the_artifact_matches_the_module():
    doc = _artifact()
    assert [f["id"] for f in doc["findings"]] == [f.fid for f in ca.FINDINGS]
    assert {f["id"]: f["classification"] for f in doc["findings"]} == \
        {f.fid: f.classification for f in ca.FINDINGS}
    assert doc["counts"]["total"] == len(ca.FINDINGS)


def test_the_artifact_names_a_commit_for_every_tree():
    doc = _artifact()
    assert set(doc["source_trees"]) == set(ca.DEFAULT_TREES)
    for stack, info in doc["source_trees"].items():
        sha = info["commit"]
        assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha), \
            (stack, sha)


def test_the_artifact_does_not_claim_prevalence_or_novelty():
    """The preregistration forbids both.

    A flat keyword ban does not work here and the first version of this test
    was wrong because of it: `h5_outcome` has to be able to say "it predicted
    nothing about prevalence", and a blacklist failed on the denial. So the
    descriptive field is scanned for the words, and the two claim-bearing
    fields are required to carry the denials verbatim.
    """
    doc = _artifact()
    for banned in ("universal", "prevalen", "novel", "first to",
                   "airworthin", "certifi"):
        assert banned not in doc["subsystem_audited"].lower(), banned

    outcome = doc["h5_outcome"].lower()
    assert "predicted nothing about prevalence" in outcome
    assert "none is reported" in outcome
    assert "universal" not in outcome

    denials = doc["what_this_is_not"].lower()
    for required in ("not a prevalence measurement",
                     "not a universality claim", "not a novelty claim",
                     "not a bug report"):
        assert required in denials, required

    assert "flight validation" not in json.dumps(doc).lower()


def test_the_acknowledged_in_source_finding_is_present_and_first():
    """The one finding that cuts against novelty is reported first, and a
    later edit that quietly demotes it should fail here."""
    doc = _artifact()
    assert doc["findings"][0]["id"] == "AP-COMMENT"
    assert doc["findings"][0]["annotation"] == "ACKNOWLEDGED_IN_SOURCE"


# --- against the real source trees ----------------------------------------

@needs_trees
def test_every_anchor_is_still_at_its_recorded_line():
    verdicts = ca.verify()
    assert set(verdicts.values()) == {"AT_RECORDED_LINE"}, verdicts
    assert len(verdicts) == len(ca.FINDINGS)


@needs_trees
def test_the_committed_artifact_was_built_from_these_commits():
    """If the trees have moved on, this fails and the artifact is stale --
    which is a finding about the artifact, not something to paper over."""
    doc = _artifact()
    for stack, path in ca.DEFAULT_TREES.items():
        assert doc["source_trees"][stack]["commit"] == ca.tree_sha(path), \
            f"{stack} tree has moved; regenerate CROSSARCH_AUDIT.json"


@needs_trees
def test_a_moved_anchor_is_refused_rather_than_searched_for():
    """The check must not 'helpfully' find the text elsewhere and pass."""
    real = ca.FINDINGS[1]
    moved = ca.Finding(real.fid, real.stack, real.path, real.line + 3,
                       real.anchor, real.regime, real.gate_kind,
                       real.relation_lost, real.independent_path,
                       real.coverage, real.classification, real.note)
    original = ca.FINDINGS
    ca.FINDINGS = (moved,)
    try:
        with pytest.raises(ca.AnchorMoved, match="not"):
            ca.verify()
    finally:
        ca.FINDINGS = original


def test_an_absent_tree_is_an_error_not_an_empty_report():
    with pytest.raises(ca.AnchorMoved, match="absent"):
        ca.verify({ca.PX4: "/nonexistent/px4",
                   ca.ARDUPILOT: "/nonexistent/ardupilot"})
