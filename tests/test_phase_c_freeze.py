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


def test_research_artifacts_differ_only_by_their_commit_field():
    """NOT a freeze check -- a recorded property.

    research/systems-paper/results/*.json embed the commit they were
    generated at, so they are not bit-reproducible across commits even though
    their scientific content is deterministic. This asserts the commit field
    is the ONLY such field, so that a future non-determinism cannot hide
    behind the same explanation.
    """
    import subprocess
    results = os.path.join(ROOT, "research", "systems-paper", "results")
    volatile = {"commit", "active_sets_commit"}
    for name in sorted(os.listdir(results)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(results, name)
        head = subprocess.run(["git", "show", f"HEAD:{os.path.relpath(path, ROOT)}"],
                              cwd=ROOT, capture_output=True, text=True)
        if head.returncode != 0:
            continue          # not yet committed
        committed = json.loads(head.stdout)
        current = json.load(open(path, encoding="utf-8"))
        for key in volatile:
            committed.pop(key, None)
            current.pop(key, None)
            if isinstance(committed.get("inputs"), dict):
                committed["inputs"].pop(key, None)
            if isinstance(current.get("inputs"), dict):
                current["inputs"].pop(key, None)
        assert committed == current, (
            f"{name} differs from its committed form in more than the commit "
            f"field. Regenerate and commit it, or find out what became "
            f"non-deterministic.")
