"""Every digest in the E1 freeze manifest still describes the file it names.

A freeze manifest that is not recomputed is a claim about a past state that
nobody checks. This recomputes each digest and compares, so a file that moved
after the freeze fails here instead of silently invalidating the manifest.

WHAT IT CANNOT CHECK, AND SAYS SO
  * `head_commit` is the commit the manifest was generated at, which is by
    construction the commit BEFORE the manifest itself was committed. It is
    provenance, not a self-referential hash, and this file does not pretend
    otherwise.
  * `tests.collected` is passed in by the operator who ran the suite. The
    generator does not run pytest, so it cannot report a number it did not
    observe, and neither can this test verify one that was mistyped -- but
    `test_the_recorded_test_count_is_not_wildly_stale` catches a large drift.
"""

from __future__ import annotations

import os
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment.build_e1_freeze_manifest import (  # noqa: E402
    STATE_NAME, sha256_file, sha256_tree)

MANIFEST = os.path.join(ROOT, "research", "physical_validation",
                        "E1_FREEZE_MANIFEST.yaml")


@pytest.fixture(scope="module")
def doc():
    if not os.path.exists(MANIFEST):
        pytest.skip("E1_FREEZE_MANIFEST.yaml not present")
    with open(MANIFEST, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _flat_file_digests(doc):
    """Every (path, digest) pair the manifest records for a single file."""
    out = []
    for section in ("extractors", "claim_table", "results", "papers"):
        for rel, digest in (doc.get(section) or {}).items():
            out.append((section, rel, digest))
    for rel, digest in (doc.get("preregistrations", {}).get("digests")
                        or {}).items():
        out.append(("preregistrations", rel, digest))
    for rel, digest in (doc.get("frozen_core", {}).get("digests")
                        or {}).items():
        if isinstance(digest, str):
            out.append(("frozen_core", rel, digest))
    return out


def test_the_state_is_named_software_validation_not_physical(doc):
    """The name is load-bearing: a reader who sees only this file must not
    come away thinking hardware was involved."""
    assert doc["state"] == STATE_NAME
    assert "SOFTWARE" in doc["state"].upper()
    lowered = [s.lower() for s in doc["state_is_not"]]
    for denial in ("physical validation", "hardware validation",
                   "flight validation"):
        assert denial in lowered, f"the manifest no longer denies {denial!r}"


def test_every_single_file_digest_still_matches(doc):
    wrong, missing = [], []
    for section, rel, digest in _flat_file_digests(doc):
        path = os.path.join(ROOT, rel)
        if digest == "ABSENT":
            if os.path.exists(path):
                wrong.append(f"{section}:{rel} recorded ABSENT but exists")
            continue
        if not os.path.exists(path):
            missing.append(f"{section}:{rel}")
            continue
        got = sha256_file(path)
        if got != digest:
            wrong.append(f"{section}:{rel}\n      manifest {digest}"
                         f"\n      actual   {got}")
    assert not missing, ("files named in the freeze manifest are gone:\n  "
                         + "\n  ".join(missing))
    assert not wrong, ("files have changed since the E1 freeze:\n  "
                       + "\n  ".join(wrong))


def test_every_directory_digest_still_matches(doc):
    trees = []
    for rel, digest in (doc.get("frozen_core", {}).get("digests")
                        or {}).items():
        if isinstance(digest, dict):
            trees.append(("frozen_core", rel, digest))
    for rel, entry in (doc.get("raw_trace_archives") or {}).items():
        trees.append(("raw_trace_archives", rel, entry))
    for rel, entry in (doc.get("campaigns") or {}).items():
        if isinstance(entry, dict) and "tree" in entry:
            trees.append(("campaigns", rel, entry["tree"]))
    assert trees, "the manifest records no directory digests at all"

    wrong = []
    for section, rel, recorded in trees:
        if not os.path.isdir(os.path.join(ROOT, rel)):
            wrong.append(f"{section}:{rel} is not a directory any more")
            continue
        got = sha256_tree(rel)
        if got != recorded:
            wrong.append(
                f"{section}:{rel}\n      manifest {recorded}"
                f"\n      actual   {got}")
    assert not wrong, ("directories have changed since the E1 freeze:\n  "
                       + "\n  ".join(wrong))


def test_the_campaign_arithmetic_in_the_manifest_balances(doc):
    """planned = valid + invalid + not_attempted, per campaign, as recorded."""
    for rel, entry in (doc.get("campaigns") or {}).items():
        if "planned" not in entry:
            pytest.fail(f"{rel}: no counts recorded")
        total = entry["valid"] + entry["invalid"] + entry["not_attempted"]
        assert entry["planned"] == total, (
            f"{rel}: planned {entry['planned']} against "
            f"{total} = valid+invalid+not_attempted")
        assert entry["attempted"] + entry["not_attempted"] == entry["planned"]


def test_the_manifest_records_what_is_still_open(doc):
    """A freeze that lists no open items is a freeze nobody audited."""
    open_items = doc.get("known_open_at_freeze") or []
    assert len(open_items) >= 5, (
        "the freeze manifest lists fewer than five open items; the E1 state "
        "has at least FL-019, the local-only tags, the unverified "
        "bibliography, the unmapped literals and CONFIGURATION-02")
    joined = " ".join(open_items)
    assert "FL-019" in joined, "FL-019 is not recorded as open"


def test_the_next_tier_is_e2_and_is_blocked_on_hardware(doc):
    nxt = doc["next_tier"]
    assert nxt["tier"] == "E2"
    assert "frozen CSIA core" in nxt["objective"]
    assert "E3" in nxt["not_yet"], (
        "the manifest no longer says the physical GNSS fault is E3")
    assert os.path.exists(os.path.join(ROOT, nxt["packet"])), (
        f"the E2 build packet {nxt['packet']} does not exist")


def test_the_recorded_test_count_is_not_wildly_stale(doc):
    """Catches a manifest generated against a very different suite.

    Deliberately loose: this file cannot verify a count it did not observe,
    and a tight bound would fail on every ordinary test addition. It fails
    only on the case that matters -- a manifest carried over from a
    substantially different repository state.
    """
    recorded = (doc.get("tests") or {}).get("collected")
    if recorded is None:
        pytest.skip("no test count recorded")
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--co", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    total = sum(int(line.rsplit(": ", 1)[1])
                for line in proc.stdout.splitlines()
                if line.strip().endswith(tuple("0123456789"))
                and ": " in line and line.rsplit(": ", 1)[1].isdigit())
    assert abs(total - recorded) <= 50, (
        f"the manifest records {recorded} tests, the suite now collects "
        f"{total}. Regenerate the manifest with the observed count.")
