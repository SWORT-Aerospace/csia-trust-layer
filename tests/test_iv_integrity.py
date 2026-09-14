"""The integrity artifacts, actually verified.

Two checksum manifests exist in this line of work and **neither was ever
read by anything**.

The prior phase's `RAW_CHECKSUMS.sha256` mixes immutable raw output with living
source files, so it fails on 9 of 18 entries and has failed since MX-040
(`COUNTEREXAMPLE_LOG.md` IV-5). That one is frozen evidence and is not repaired
here.

This phase's `RAW_CHECKSUMS.sha256` has the opposite defect and it is mine:
`tools/research/iv_manifest.py` writes it and no test, tool or guard has ever
checked a single line of it. A manifest nobody runs is not weaker than a
manifest that always fails -- it is the same thing, a check that cannot fire,
which is IV-1 and IV-19 wearing a third hat.

The same is true of the locked campaign's digest: `BASE_PROVENANCE.json` records
`sha256 = 14b9147e...` for the 13 MB artifact every §1 verification was
performed against, and nothing compares it to the file.

These tests read both. They fail if a pinned artifact changes by one byte, and
they fail if an immutable artifact appears that the manifest does not list --
because a manifest that silently omits a file is the other way for this to stop
meaning anything.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "research/active_evidence/independent_validation"
RESULTS = BASE / "results"
CHECKSUMS = BASE / "RAW_CHECKSUMS.sha256"
MANIFEST = BASE / "EXPERIMENT_MANIFEST.json"
PROVENANCE = BASE / "BASE_PROVENANCE.json"
LOCKED = (ROOT / "research/active_evidence/realized_current/results"
          / "RCEC_LOCKED_CAMPAIGN.json")


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tracked(path: pathlib.Path) -> bool:
    result = subprocess.run(("git", "ls-files", "--error-unmatch", str(path)),
                            cwd=ROOT, capture_output=True)
    return result.returncode == 0


def _entries():
    for line in CHECKSUMS.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        digest, _, relative = line.partition("  ")
        yield digest, ROOT / relative


# --- this phase's manifest, in both directions ---------------------------

def test_the_checksum_file_is_not_empty():
    entries = list(_entries())
    assert entries, "RAW_CHECKSUMS.sha256 has no entries to verify"
    assert len(entries) >= 8


@pytest.mark.parametrize("digest,path", list(_entries()),
                         ids=lambda value: (pathlib.Path(value).name
                                            if isinstance(value, pathlib.Path)
                                            else value[:8]))
def test_every_pinned_artifact_still_has_its_recorded_digest(digest, path):
    assert path.is_file(), f"{path.relative_to(ROOT)} is pinned but missing"
    assert _sha256(path) == digest, (
        f"{path.relative_to(ROOT)} changed. If that was deliberate, "
        "regenerate the manifest in the same commit and explain the diff; "
        "immutable raw output is not supposed to move.")


def test_every_pinned_artifact_is_actually_tracked_by_git():
    """A manifest pinning an ignored local file fails for everyone who clones."""
    for _, path in _entries():
        assert _tracked(path), (
            f"{path.relative_to(ROOT)} is pinned but not tracked by git")


def test_no_tracked_raw_artifact_is_missing_from_the_manifest():
    """The other direction. A manifest that omits a file cannot fire on it."""
    pinned = {path.resolve() for _, path in _entries()}
    for path in sorted(RESULTS.glob("*.json")):
        if not _tracked(path):
            continue
        assert path.resolve() in pinned, (
            f"{path.relative_to(ROOT)} is a tracked raw artifact and is not "
            "in RAW_CHECKSUMS.sha256; regenerate the manifest")


def test_the_experiment_manifest_agrees_with_the_checksum_file():
    manifest = json.loads(MANIFEST.read_text())
    pinned = {str(path.relative_to(ROOT)): digest
              for digest, path in _entries()}
    recorded = {key: value["sha256"]
                for key, value in manifest["raw_outputs"].items()}
    assert recorded == pinned


def test_the_manifest_still_reports_layer_a_clean():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["layers"]["layer_a_leaks"] == {}


# --- the prior phase's locked campaign ------------------------------------

def test_the_locked_campaign_matches_the_digest_recorded_for_it():
    """Every section-1 verification was performed against this exact file."""
    provenance = json.loads(PROVENANCE.read_text())
    recorded = provenance["locked_campaign"]["sha256"]
    assert recorded == "14b9147e15d2c75b1588b81c787eb6b4b011ca77f3a4975aa98185995ee44a01"
    assert _sha256(LOCKED) == recorded, (
        "the locked campaign artifact changed. It is frozen evidence from the "
        "prior phase and nothing in this phase may edit it.")


def test_the_prior_phase_checksum_file_is_still_stale_and_that_is_recorded():
    """Not repaired. Pinned so its staleness stays a documented fact.

    It lists nine living source files alongside its immutable raw JSON, so it
    fails on those nine and will keep failing. The raw JSON entry still
    verifies, which is the part that matters.
    """
    prior = (ROOT / "research/active_evidence/realized_current"
             / "RAW_CHECKSUMS.sha256")
    failures = []
    raw_json_ok = False
    for line in prior.read_text().splitlines():
        digest, _, relative = line.strip().partition("  ")
        path = ROOT / relative
        if not path.is_file():
            continue
        if _sha256(path) != digest:
            failures.append(relative)
        elif relative.endswith("RCEC_CAMPAIGN.json"):
            raw_json_ok = True
    assert len(failures) == 9, (
        f"expected the nine documented failures, got {len(failures)}: "
        f"{failures}")
    assert raw_json_ok, "the prior phase's immutable raw JSON no longer verifies"
