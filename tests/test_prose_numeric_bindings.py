"""Every headline number in prose still matches the artifact it came from.

`research/PROSE_NUMERIC_BINDINGS.yaml` binds each one to an artifact and a
JSON pointer. This checks BOTH directions, because only the second catches the
failure that actually happens:

  1. the bound value equals what the artifact says today
  2. every rendering the prose uses is derivable from that value, AND at least
     one of them literally appears in every document the row names

Direction 2 is the point. A regeneration on a different host, a rerun after a
code change, or a typo leaves the prose confidently stating a number the
artifact no longer contains, and nothing else in this repository would notice.

A row naming no document, or naming a document that does not contain any of
its renderings, FAILS. A binding nobody quotes is not a binding.
"""

from __future__ import annotations

import json
import os
import re

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BINDINGS = os.path.join(ROOT, "research", "PROSE_NUMERIC_BINDINGS.yaml")


def _rows():
    with open(BINDINGS, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert doc["schema"] == "csia.research.prose_numeric_bindings/1"
    rows = doc["bindings"]
    assert rows, "no bindings; the test would pass vacuously"
    return rows


def _resolve(obj, pointer: str):
    """RFC-6901 JSON pointer, minus the escaping nobody here needs."""
    cur = obj
    for part in pointer.strip("/").split("/"):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            assert part in cur, f"pointer segment {part!r} missing"
            cur = cur[part]
    return cur


def _canonical(text: str) -> str:
    """Strip thousands separators and LaTeX group braces so "378,000",
    "378000" and "$378{,}000$" compare equal."""
    return re.sub(r"[,\s$]|\{,\}", "", text)


def _derivable(rendering: str, value) -> bool:
    """Is this rendering a faithful presentation of the artifact's value?

    Accepts thousands separators and rounding to fewer decimal places. Does
    NOT accept a different number: a rendering that is not derivable is a
    transcription error, and widening this function to admit it would defeat
    the file.
    """
    canon = _canonical(rendering)
    try:
        rendered = float(canon)
    except ValueError:
        return False
    if isinstance(value, bool) or value is None:
        return False
    value = float(value)
    if rendered == value:
        return True
    # Rounding: the rendering may carry fewer decimals than the artifact.
    if "." in canon:
        places = len(canon.split(".")[1])
    else:
        places = 0
    return round(value, places) == rendered


ROWS = _rows()
IDS = [r["id"] for r in ROWS]


def test_binding_ids_are_unique():
    assert len(IDS) == len(set(IDS)), "duplicate binding id"


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_the_artifact_still_says_what_the_binding_claims(row):
    path = os.path.join(ROOT, row["artifact"])
    assert os.path.exists(path), f"{row['id']}: missing {row['artifact']}"
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    value = _resolve(doc, row["pointer"])
    assert row["renderings"], f"{row['id']}: no renderings"
    for rendering in row["renderings"]:
        assert _derivable(rendering, value), (
            f"{row['id']}: prose renders {rendering!r} but "
            f"{row['artifact']}{row['pointer']} is {value!r}")


@pytest.mark.parametrize("row", ROWS, ids=IDS)
def test_every_document_still_quotes_the_number(row):
    docs = row.get("documents") or []
    assert docs, (
        f"{row['id']}: names no document. A binding nobody quotes is not a "
        f"binding -- delete the row or name where it is used.")
    for rel in docs:
        path = os.path.join(ROOT, rel)
        assert os.path.exists(path), f"{row['id']}: missing document {rel}"
        text = open(path, encoding="utf-8").read()
        if not any(r in text for r in row["renderings"]):
            raise AssertionError(
                f"{row['id']}: none of {row['renderings']} appears in {rel}. "
                f"Either the document drifted from "
                f"{row['artifact']}{row['pointer']}, or the row names a "
                f"document that never quoted it.")


def test_every_bound_artifact_is_a_committed_result():
    """A binding pointing at something untracked would silently stop being
    checkable on a fresh clone."""
    import subprocess
    for row in ROWS:
        r = subprocess.run(["git", "ls-files", "--error-unmatch",
                            row["artifact"]], cwd=ROOT,
                           capture_output=True, text=True)
        assert r.returncode == 0, \
            f"{row['id']}: {row['artifact']} is not tracked by git"
