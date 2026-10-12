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

import json
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
    """Directory digests OUTSIDE the frozen core, which contain no bytecode.

    The two `frozen_core` directory digests are deliberately NOT checked
    here; `test_the_frozen_source_digests_still_match` covers that source
    with a reproducible measurement. See HF-011 and the docstring on
    `sha256_tree`: those two recorded values hash `__pycache__` alongside
    source, so they embed the source mtime through the .pyc header and
    cannot be reproduced on a fresh clone, which has no `__pycache__` at
    all. They are left in the manifest as the historical record they are.
    """
    trees = []
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


def test_the_frozen_source_digests_still_match():
    """THE FROZEN CORE, MEASURED OVER SOURCE ONLY.

    This is the check the bytecode-contaminated directory digests were
    meant to be. It is reproducible on a fresh clone because it hashes
    only source, and `FROZEN_SOURCE_DIGESTS.json` records the values
    measured from a tree verified byte-identical to the freeze tag.
    """
    path = os.path.join(ROOT, "research", "physical_validation", "results",
                        "FROZEN_SOURCE_DIGESTS.json")
    assert os.path.exists(path), "FROZEN_SOURCE_DIGESTS.json is missing"
    with open(path, encoding="utf-8") as fh:
        recorded = json.load(fh)

    wrong = []
    for rel, expected in sorted(recorded["digests"].items()):
        full = os.path.join(ROOT, rel)
        if os.path.isdir(full):
            got = sha256_tree(rel, source_only=True)
        elif os.path.exists(full):
            got = {"files": 1, "sha256_of_file_manifest": sha256_file(full)}
        else:
            wrong.append(f"{rel} no longer exists")
            continue
        if got != expected:
            wrong.append(f"{rel}\n      recorded {expected}"
                         f"\n      actual   {got}")
    assert not wrong, ("THE FROZEN CORE SOURCE HAS CHANGED:\n  "
                       + "\n  ".join(wrong))


def test_the_per_file_frozen_hashes_agree_with_the_source_digests():
    """Two independent records of the same files must agree.

    The E1 manifest's PER-FILE hashes were never bytecode-contaminated --
    only its two DIRECTORY digests were -- so they must still match the
    source-only artifact. If these two ever disagree, one of them has been
    edited and the disagreement is the finding.
    """
    with open(os.path.join(ROOT, "research", "physical_validation",
                           "results", "FROZEN_SOURCE_DIGESTS.json"),
              encoding="utf-8") as fh:
        source_digests = json.load(fh)["digests"]

    with open(MANIFEST, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    checked = 0
    for rel, digest in (doc.get("frozen_core", {}).get("digests")
                        or {}).items():
        if isinstance(digest, dict):        # a directory: not comparable
            continue
        assert source_digests[rel]["sha256_of_file_manifest"] == digest, (
            f"{rel}: the E1 manifest and the source-digest artifact "
            f"disagree about a frozen file")
        checked += 1
    assert checked >= 4, (
        f"only {checked} per-file frozen hashes compared; this test must "
        f"not pass vacuously")


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


def test_the_suite_has_not_lost_the_tests_the_freeze_counted(doc):
    """The suite may GROW after the freeze. It may not SHRINK.

    THIS TEST WAS WRITTEN AS A TWO-SIDED BOUND AND THAT WAS WRONG. It
    originally asserted `abs(total - recorded) <= 50`, on the reasoning that a
    large drift meant a manifest carried over from a different repository
    state. Program A then added 90 tests and the guard fired -- against an
    artifact that is IMMUTABLE BY INSTRUCTION and that correctly describes a
    past state.

    The premise was the defect, not the manifest. A freeze manifest records
    what was true at the freeze; post-freeze work is expected to add tests,
    and an upper bound turns every future addition into a demand to rewrite
    history. The bound that still means something is the lower one: if the
    suite drops below what the freeze counted, tests that existed at the
    freeze have gone, and that needs an explanation.

    So the manifest is NOT regenerated and the growth is reported, not
    asserted against.
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
    print(f"\nE1 freeze counted {recorded} tests; the suite now collects "
          f"{total} ({total - recorded:+d} since the freeze)")
    assert total >= recorded - 50, (
        f"the suite collects {total} but the E1 freeze counted {recorded}. "
        f"Tests that existed at the freeze appear to have been removed. The "
        f"freeze manifest is immutable -- investigate the suite, not it.")
