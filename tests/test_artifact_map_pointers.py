"""Every artifact-map `json_pointer` resolves, and to the value it claims.

The map's pointers were documentation: nothing dereferenced them. A pointer
that no longer resolves, or that resolves to a different number than the one
printed in the manuscript, would have been invisible -- which is the same shape
as the stale-artifact defect the mutation campaign found (EVIDENCE-05).

WHAT IT CHECKS
  * the pointer resolves in the artifact it names;
  * the resolved value ROUNDS to the value the manuscript prints, at the
    precision the manuscript prints it to.

Rounding is checked at the printed precision rather than against a fixed
tolerance, because the manuscript's own precision is the claim: "0.0206"
asserts four decimals and nothing about the fifth.

WHAT IT DOES NOT CHECK: entries with no `json_pointer`. Four Phase-I scalars
have none (S05, S10, S11, S12 -- one of which cites a source file rather than a
result). Those remain unchecked, and this test reports how many rather than
implying full coverage.
"""

from __future__ import annotations

import json
import os
import re

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAPS = [
    "papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml",
    "papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml",
]

#: `.a.b[0].c` -- dotted keys with optional integer indices.
TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _deref(obj, pointer):
    cur = obj
    for m in TOKEN.finditer(pointer):
        key, idx = m.group(1), m.group(2)
        cur = cur[int(idx)] if idx is not None else cur[key]
    return cur


def _entries():
    out = []
    for rel in MAPS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        for s in doc.get("scalars") or []:
            if s.get("json_pointer") and str(s.get("artifact", "")).endswith(
                    ".json"):
                out.append((rel, s))
    return out


def _decimals(value: str) -> int:
    return len(value.split(".")[1]) if "." in value else 0


@pytest.mark.parametrize(
    "rel,entry", [(r, e) for r, e in _entries()],
    ids=[f"{r.split('/')[1]}:{e['id']}" for r, e in _entries()])
def test_the_pointer_resolves_to_the_printed_value(rel, entry):
    artifact = os.path.join(ROOT, entry["artifact"])
    if not os.path.exists(artifact):
        pytest.skip(f"{entry['artifact']} not present")
    with open(artifact, encoding="utf-8") as fh:
        doc = json.load(fh)
    try:
        got = _deref(doc, entry["json_pointer"])
    except (KeyError, IndexError, TypeError) as exc:
        pytest.fail(f"{entry['id']}: pointer {entry['json_pointer']!r} does "
                    f"not resolve in {entry['artifact']}: "
                    f"{type(exc).__name__}: {exc}")
    printed = str(entry["value"])
    nd = _decimals(printed)
    assert f"{float(got):.{nd}f}" == f"{float(printed):.{nd}f}", (
        f"{entry['id']}: the manuscript prints {printed!r} but "
        f"{entry['artifact']}{entry['json_pointer']} holds {got!r}")


def test_the_uncovered_entries_are_counted_not_implied():
    """Say how many scalars this file does NOT check, rather than implying 0."""
    total = unpointered = 0
    for rel in MAPS:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for s in yaml.safe_load(fh).get("scalars") or []:
                total += 1
                if not (s.get("json_pointer")
                        and str(s.get("artifact", "")).endswith(".json")):
                    unpointered += 1
    checked = total - unpointered
    print(f"\nartifact-map scalars: {total} total, {checked} dereferenced "
          f"here, {unpointered} carry no JSON pointer and are NOT checked")
    assert checked > 0
