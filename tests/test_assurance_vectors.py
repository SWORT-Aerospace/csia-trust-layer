"""The published conformance vectors, and the five verdicts they must cover.

`csia_assurance/vectors/` is what `docs/ASSURANCE_REFERENCE_SEMANTICS.md` §7
offers to a second implementer: build from the document, run these, pass.

WHAT THESE VECTORS ARE, AND WHAT THEY ARE NOT
----------------------------------------------
Their expected values were produced BY THIS IMPLEMENTATION. That makes them a
CONFORMANCE TARGET, not an independent oracle: a shared misreading of the
document would be baked into both the vectors and the implementation, and
these tests could not tell. The independence that is available comes from
elsewhere -- the bounded verification's 4096-case cross-check against the
definition, and the clean-room reference that the firewall is built on. This
file is honest about which of the three it is.

What it does establish: the vectors stay in step with the implementation, they
exercise every verdict, and they cannot silently lose a case.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_assurance import qualify                          # noqa: E402
from csia_assurance.firewall import VERDICTS                # noqa: E402

VECTOR_DIR = os.path.join(ROOT, "csia_assurance", "vectors")


def _vectors():
    if not os.path.isdir(VECTOR_DIR):
        return []
    out = []
    for name in sorted(os.listdir(VECTOR_DIR)):
        if name.endswith(".json") and name != "INDEX.json":
            with open(os.path.join(VECTOR_DIR, name), encoding="utf-8") as fh:
                out.append(json.load(fh))
    return out


ALL = _vectors()


@pytest.mark.parametrize("vec", ALL, ids=[v["id"] for v in ALL])
def test_each_vector_reproduces_its_expected_verdict(vec):
    v = qualify(vec["record"], vec.get("prior"))
    exp = vec["expected"]
    assert v.state == exp["state"], f"{vec['id']}: {vec['why']}"
    assert v.reason == exp["reason"]
    assert list(v.competitors_without_witness) == exp[
        "competitors_without_witness"]
    assert {k: list(x) for k, x in v.witnesses.items()} == exp["witnesses"]


def test_every_verdict_is_covered_by_some_vector():
    """A suite that never produces UNKNOWN would leave that path untested."""
    covered = {v["expected"]["state"] for v in ALL}
    missing = sorted(set(VERDICTS) - covered)
    assert not missing, f"no vector produces: {missing}"


def test_the_index_matches_the_files_on_disk():
    index_path = os.path.join(VECTOR_DIR, "INDEX.json")
    if not os.path.exists(index_path):
        pytest.skip("no vector index")
    with open(index_path, encoding="utf-8") as fh:
        index = json.load(fh)
    listed = {e["id"] for e in index["vectors"]}
    on_disk = {v["id"] for v in ALL}
    assert listed == on_disk, (
        f"index and directory disagree: only in index {sorted(listed - on_disk)}, "
        f"only on disk {sorted(on_disk - listed)}")


def test_the_index_says_these_are_not_an_independent_oracle():
    """The caveat is load-bearing and may not be dropped."""
    index_path = os.path.join(VECTOR_DIR, "INDEX.json")
    if not os.path.exists(index_path):
        pytest.skip("no vector index")
    with open(index_path, encoding="utf-8") as fh:
        note = json.load(fh)["note"]
    assert "NOT an independent oracle" in note


def test_every_vector_explains_why_it_exists():
    for v in ALL:
        assert v.get("why", "").strip(), f"{v['id']} has no rationale"
