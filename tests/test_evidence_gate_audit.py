"""Guards for the evidence-gate audit.

An audit whose classifier drifts reports a number nobody can act on, and the
drift is invisible because the output still looks like an audit. The
classifier is the thing under test here, not the repository's current counts:
those change as the repository does, and pinning them would turn every
ordinary commit into a failure.

What IS pinned is the direction of every error the classifier can make. It
got both directions wrong while being written -- first counting reads as
writes, which made three SHA256 manifests look EVIDENCE_GATED because
provenance_workflow.py reads them as a precondition; then missing writes
through a module constant, which made the one genuinely gated artifact look
ungated. Both are exercised below.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.assurance import evidence_gate_audit as a   # noqa: E402


# --------------------------------------------------- reads are not writes

def test_reading_an_artifact_does_not_count_as_writing_it():
    """The error that inflates the gated count, so it is tested first."""
    reader = '''
REQUIRED = ("research/phase4/SHA256_MANIFEST4.json",)

def check():
    doc = json.load(open(REQUIRED[0], encoding="utf-8"))
    return doc

def unrelated_write(path, payload):
    with open(path, "w") as fh:
        json.dump(payload, fh)
'''
    assert not a.mentions_as_writer(
        reader, ("SHA256_MANIFEST4.json",
                 "research/phase4/SHA256_MANIFEST4.json")), (
        "a script that only READS an artifact must not be credited as its "
        "generator; doing so reports the artifact as guarded by whatever "
        "gate the reader happens to carry")


def test_a_direct_write_counts():
    src = '''
def emit(payload):
    with open("research/x/results/THING.json", "w") as fh:
        json.dump(payload, fh)
'''
    assert a.mentions_as_writer(src, ("THING.json",))


# ------------------------------------------- writes through a module constant

def test_a_write_through_a_module_constant_counts():
    """The normal good pattern, and the one the proximity rule alone missed."""
    src = '''
OUT = os.path.join(ROOT, "research", "x", "results", "THING.json")

def emit(payload):
    with protected_write(OUT) as fh:
        fh.write(json.dumps(payload))
'''
    assert a.mentions_as_writer(src, ("THING.json",)), (
        "a path bound to a module constant and written far below is the "
        "ordinary way to write an artifact and must be recognised")


def test_a_write_through_a_multi_line_constant_counts():
    """The mention lands on a CONTINUATION line, not the assignment head."""
    src = '''
RECORD = os.path.join(ROOT, "research", "physical_validation", "results",
                      "BUILD_PROVENANCE.json")

def write_it(doc):
    with protected_write(RECORD, regenerate=True) as fh:
        fh.write(json.dumps(doc))
'''
    assert a.mentions_as_writer(src, ("BUILD_PROVENANCE.json",))


# ----------------------------------------------------- guard classification

def test_guard_levels_are_ordered_and_distinguished():
    gated = "ok, evidence = gather_evidence(suite)\nprotected_write(p)"
    accident = "with protected_write(OUT) as fh:\n    fh.write(x)"
    none = "with open(OUT, 'w') as fh:\n    fh.write(x)"

    assert a.classify_writer(gated) == a.EVIDENCE_GATED
    assert a.classify_writer(accident) == a.ACCIDENT_GUARDED
    assert a.classify_writer(none) == a.UNGUARDED
    assert (a.STRENGTH[a.EVIDENCE_GATED] > a.STRENGTH[a.ACCIDENT_GUARDED]
            > a.STRENGTH[a.UNGUARDED] > a.STRENGTH[a.NO_GENERATOR]), (
        "an accident guard must never rank as high as an evidence gate; "
        "they answer different questions")


def test_an_accident_guard_is_not_reported_as_an_evidence_gate():
    """protected_write refuses to clobber. It asks nothing about the tree."""
    assert a.classify_writer("protected_write(p, regenerate=True)") \
        != a.EVIDENCE_GATED


# ------------------------------------------------------------- pin detection

def test_pin_targets_finds_every_manifest_shape(tmp_path):
    h = "0" * 64
    found = set()
    a._pin_targets({"files": {"a/b.json": h},
                    "nested": {"deep": {"c/d.csv": {"sha256": h}}},
                    "listed": [{"path": "e/f.json", "sha256": h}],
                    "not_a_digest": {"g/h.json": "nope"}}, found)
    assert found == {"a/b.json", "c/d.csv", "e/f.json"}, found


# --------------------------------------------------- the audit runs and is sane

def test_the_audit_runs_and_classifies_the_one_gated_artifact():
    """Calibration against ground truth: exactly the provenance record is
    evidence-gated today, and it is attributed to the workflow that gates it.

    This does NOT pin the repository's counts -- those move with the tree.
    It pins that the classifier still recognises the one case we know the
    answer to. If a second artifact is gated later this still passes; if the
    known one stops being recognised, it fails.
    """
    doc = a.audit()
    assert doc["artifacts_examined"] > 100
    rows = {r["artifact"]: r for r in doc["rows"]}
    record = "research/physical_validation/results/BUILD_PROVENANCE.json"
    assert record in rows
    assert rows[record]["verdict"] == a.EVIDENCE_GATED, (
        f"the provenance record is gated by provenance_workflow.py; the "
        f"audit now says {rows[record]['verdict']}")
    assert "tools/assurance/provenance_workflow.py" in \
        rows[record]["generators_by_name_or_path"]


def test_the_audit_separates_prevention_from_detection():
    doc = a.audit()
    assert "manifest_pinned" in doc
    assert "not_gated_and_not_pinned" in doc
    assert doc["not_gated_and_not_pinned"] <= doc["not_evidence_gated"], (
        "the undetected set cannot exceed the ungated set")
    assert "DETECTED, not PREVENTED" in doc["what_pinning_means"]


def test_the_claim_backing_tier_is_populated():
    """If the artifact maps stop resolving, this tier silently reads zero and
    the audit's sharpest finding disappears without anyone noticing."""
    doc = a.audit()
    cb = doc["claim_backing"]
    assert cb["artifacts_cited_by_a_paper_artifact_map"] > 0, (
        "no paper-cited artifacts resolved; the artifact maps moved or the "
        "path regex stopped matching, and this tier is now vacuous")
    assert cb["of_those_not_evidence_gated"] <= \
        cb["artifacts_cited_by_a_paper_artifact_map"]
