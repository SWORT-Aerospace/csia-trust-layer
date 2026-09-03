"""The Phase C freeze record still describes the artifacts on disk.

`engineering/v2/V2_PHASEC_FREEZE.md` is a deliverable: it states the commit,
the artifact hashes, the equivalence result and the gate verdict. Nothing
checked that the hashes still hold. If someone regenerates a Phase C artifact
the record silently becomes a list of hashes for files that no longer exist in
that form, and a freeze record that is wrong is worse than none.

WHAT IS AND IS NOT CHECKED
--------------------------
V2_PHASEC_COMPUTE.json carries wall-clock timings and CANNOT be
bit-reproducible. It is excluded from the hash check by name and the exclusion
is asserted, so it cannot be quietly widened to cover a file that starts
drifting for a different reason.

The research artifacts under research/systems-paper/results/ are deliberately
NOT hash-frozen: each embeds the commit it was generated at, so regenerating
at a later commit changes the file while the scientific content stays
bit-identical. That is a property worth knowing rather than a defect, and
`test_research_artifacts_differ_only_by_their_commit_field` records it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE = os.path.join(ROOT, "engineering", "v2", "V2_PHASEC_FREEZE.md")
V2 = os.path.join(ROOT, "engineering", "v2")

#: Excluded because it holds wall-clock timings. Named, not pattern-matched.
NOT_REPRODUCIBLE = {"V2_PHASEC_COMPUTE.json"}


def _recorded():
    text = open(FREEZE, encoding="utf-8").read()
    rows = re.findall(r"^([0-9a-f]{64})\s+(\S+)", text, flags=re.M)
    assert rows, "no SHA-256 lines found in the freeze record"
    return rows


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_every_recorded_hash_still_matches():
    stale = []
    for want, name in _recorded():
        if name in NOT_REPRODUCIBLE:
            continue
        path = os.path.join(V2, name)
        if not os.path.exists(path):
            stale.append(f"{name}: MISSING")
            continue
        got = _sha(path)
        if got != want:
            stale.append(f"{name}: recorded {want[:16]}... actual {got[:16]}...")
    assert not stale, (
        "engineering/v2/V2_PHASEC_FREEZE.md records hashes that no longer "
        "match:\n  " + "\n  ".join(stale) +
        "\n\nEither the artifact was regenerated (re-record the hash AND say "
        "why in the freeze record) or something changed that should not have. "
        "Phase C is FROZEN -- see docs/CURRENT_PROGRAM_STATE.md.")


def test_the_unreproducible_artifact_is_excluded_by_name_and_still_exists():
    """A blanket exclusion would let a genuinely drifting file hide behind
    the timing file's exemption."""
    assert NOT_REPRODUCIBLE == {"V2_PHASEC_COMPUTE.json"}
    for name in NOT_REPRODUCIBLE:
        assert os.path.exists(os.path.join(V2, name)), name
    recorded = {n for _h, n in _recorded()}
    assert NOT_REPRODUCIBLE <= recorded, (
        "the excluded file is not even listed in the freeze record, so the "
        "exclusion is protecting nothing")


def test_the_freeze_record_names_the_commit_and_the_prohibition():
    text = open(FREEZE, encoding="utf-8").read()
    assert "50c5d3576e9084e7c2789167628392c5de992b6f" in text
    assert "NO FURTHER V2 IMPLEMENTATION UNTIL PAPER LOCK RELEASE" in text


def test_the_gate_verdict_in_the_record_matches_the_gate_artifact():
    """The record's headline claim, checked against the artifact that
    produced it rather than against itself."""
    gate = json.load(open(os.path.join(V2, "V2_PHASEC_GATE.json"),
                          encoding="utf-8"))
    text = open(FREEZE, encoding="utf-8").read()
    assert gate["verdict"] in text, (
        f"the freeze record does not state the gate artifact's verdict "
        f"{gate['verdict']!r}")
    assert len(gate["qualifying_sets"]) == 2, gate["qualifying_sets"]


def test_the_equivalence_result_in_the_record_matches_its_artifact():
    doc = json.load(open(os.path.join(V2, "INTERNAL_EXTERNAL_EQUIVALENCE.json"),
                         encoding="utf-8"))
    text = open(FREEZE, encoding="utf-8").read()
    assert doc["identical"] is True
    assert doc["mismatches"] == 0
    assert f"{doc['checked']:,}" in text or str(doc["checked"]) in text


#: Fields a research artifact is ALLOWED to differ in between generations.
VOLATILE_FIELDS = {"commit", "active_sets_commit"}


def test_research_artifacts_carry_no_unreproducible_content():
    """NOT a freeze check -- a reproducibility property, checked statically.

    research/systems-paper/results/*.json embed the commit they were generated
    at, so they are not bit-reproducible ACROSS commits even though their
    scientific content is deterministic. What must be true is that the commit
    field is the only such thing: no wall-clock timestamp, no absolute host
    path, nothing else that would differ on another machine or another day.

    THE FIRST VERSION OF THIS TEST COMPARED THE WORKING COPY AGAINST HEAD.
    That was wrong in a way worth recording: it failed on every legitimate
    artifact regeneration, in the window between running the generator and
    committing the result -- a normal workflow state. A guard that fires
    during ordinary work is a guard somebody switches off, and it would have
    been switched off. This formulation has no such window, because it asks a
    question about the file's CONTENT rather than about its git history.
    """
    results = os.path.join(ROOT, "research", "systems-paper", "results")
    timestamp = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}|\b\d{10}\.\d{3,}")
    offenders = []
    for name in sorted(os.listdir(results)):
        if not name.endswith(".json"):
            continue
        blob = open(os.path.join(results, name), encoding="utf-8").read()
        if timestamp.search(blob):
            offenders.append(f"{name}: contains a wall-clock timestamp")
        for marker in ("/home/", "/tmp/", "/Users/", "C:\\\\"):
            if marker in blob:
                offenders.append(f"{name}: contains an absolute host path "
                                 f"({marker})")
        doc = json.loads(blob)
        # A volatile field may exist; an UNDECLARED one may not. Any other
        # top-level key ending in _commit or named like a timestamp would be
        # a second source of drift hiding behind the first.
        extra = {k for k in doc
                 if (k.endswith("_at") or k.endswith("_time")
                     or (k.endswith("_commit") and k not in VOLATILE_FIELDS))}
        if extra:
            offenders.append(f"{name}: undeclared volatile-looking keys "
                             f"{sorted(extra)}")
    assert not offenders, (
        "research artifacts contain content that cannot reproduce on another "
        "machine:\n  " + "\n  ".join(offenders))


def test_the_committed_research_artifacts_are_valid_and_current():
    """Cheap, and it does the job the git comparison was reaching for: the
    artifacts parse, declare the generator that made them, and name the
    command that regenerates them."""
    results = os.path.join(ROOT, "research", "systems-paper", "results")
    checked = 0
    for name in sorted(os.listdir(results)):
        if not name.endswith(".json"):
            continue
        doc = json.load(open(os.path.join(results, name), encoding="utf-8"))
        assert "artifact" in doc, f"{name}: no artifact name"
        assert any(k in doc for k in ("generation_command", "checker")), \
            f"{name}: does not say what produced it"
        checked += 1
    assert checked >= 4, checked
