"""No number reaches a referee without having been looked at once.

Peer-review hardening campaign, section 15.

WHY THIS FILE EXISTS
--------------------
`papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` binds the figures, the tables
and thirteen headline scalars. Everything else in running prose is unbound by
construction -- `artifact_map_check.py` reports it as
``unmapped prose numerics`` and, without `--strict-numbers`, only as a note.
A note is not a guard. `papers/csia_systems/NUMERIC_LITERAL_AUDIT.csv` is the
record that each of those literals was read by a human eye and classified.

That audit found exactly one wrong number:

    "S_0(T_0 - T*) = 125 against M(T* - e_f) = 1.0"

125 came from the generating script's own docstring, which illustrates the
term at the theoretical cap. The measured value is 118.82. The manuscript had
transcribed an illustration as a result, and nothing in the repository would
have noticed.

THE FAILURE THIS PREVENTS
-------------------------
The audit was a one-off. The next edit that adds a number to prose -- a new
paragraph, a corrected figure, a reviewer response -- adds it BELOW the audit,
and the CSV silently stops being a complete record of what was checked. This
test closes that: the set of unmapped prose literals must equal the set the
CSV audits, in both directions.

  * a literal in the manuscript but not in the CSV  -> a number nobody read
  * a literal in the CSV but not in the manuscript  -> a stale audit row,
    which is how a CSV starts describing a document that no longer exists

Adding a number to the paper therefore costs one CSV row. That is the price,
and it is the right price: it is exactly the moment to say where the number
came from.

The extraction below deliberately MIRRORS `artifact_map_check.py` rather than
importing it, because the two are checking each other. If they drift, the
mirror test at the bottom fails and says so.
"""

from __future__ import annotations

import csv
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDIR = os.path.join(ROOT, "papers", "csia_systems")
TEX = os.path.join(PDIR, "main.tex")
MAP = os.path.join(PDIR, "PAPER1_ARTIFACT_MAP.yaml")
AUDIT = os.path.join(PDIR, "NUMERIC_LITERAL_AUDIT.csv")

LITERAL_RE = re.compile(r"(?<![\w\\.])\d+(?:\.\d+)?(?![\w])")
TABULAR_RE = re.compile(r"\\begin\{tabular\}.*?\\end\{tabular\}", re.S)


def _unmapped_prose_literals():
    """The literals a human still has to account for.

    A number inside a `tabular` belongs to that table, and the table is bound
    to an artifact in the map, so table cells are excluded. What is left is
    prose: a claim in the author's own voice.
    """
    with open(TEX, encoding="utf-8") as fh:
        tex = fh.read()
    with open(MAP, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    allow = [re.compile(p) for p in (doc.get("non_empirical") or [])]
    mapped = {str(s.get("value")) for s in (doc.get("scalars") or [])}
    for table in (doc.get("tables") or []):
        mapped.update(str(v) for v in (table.get("values") or []))

    prose = TABULAR_RE.sub(" ", tex)
    lits = set(LITERAL_RE.findall(prose))
    return {x for x in lits
            if x not in mapped and not any(a.fullmatch(x) for a in allow)}


def _audited_literals():
    with open(AUDIT, encoding="utf-8", newline="") as fh:
        return {r["literal"].strip() for r in csv.DictReader(fh)}


def test_every_unmapped_prose_number_has_an_audit_row():
    """A number in the paper that nobody classified."""
    missing = sorted(_unmapped_prose_literals() - _audited_literals())
    assert not missing, (
        f"{len(missing)} numeric literals appear in papers/csia_systems/"
        f"main.tex prose with no row in NUMERIC_LITERAL_AUDIT.csv: {missing}\n\n"
        f"Each needs a row saying what it is and where it came from. If it is "
        f"a result, name the artifact; if it is a declared constant or a "
        f"version number, say so. This is the check that caught 125.")


def test_no_audit_row_describes_a_number_the_paper_no_longer_states():
    """The other direction. A stale row is an audit of a document that has
    moved on, and it makes the CSV's coverage look better than it is."""
    stale = sorted(_audited_literals() - _unmapped_prose_literals())
    assert not stale, (
        f"NUMERIC_LITERAL_AUDIT.csv audits {stale}, which no longer appear as "
        f"unmapped prose literals in main.tex. Either the number was removed "
        f"(delete the row) or it became mapped in PAPER1_ARTIFACT_MAP.yaml "
        f"(delete the row -- the map now owns it).")


def test_every_audit_row_is_complete():
    with open(AUDIT, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "the audit is empty"
    allowed = {"SCIENTIFIC_RESULT", "DECLARED_CONSTANT", "VERSION_OR_YEAR"}
    for r in rows:
        for field in ("literal", "line", "classification", "action_required",
                      "context"):
            assert (r.get(field) or "").strip(), \
                f"literal {r.get('literal')!r}: {field} is empty"
        assert r["classification"] in allowed, (
            f"literal {r['literal']!r} has classification "
            f"{r['classification']!r}, which is not one of {sorted(allowed)}. "
            f"Add it here deliberately or fix the row.")


def test_this_extraction_still_matches_the_publication_guard():
    """The mirror check.

    `tools/publication/artifact_map_check.py` computes the same set with its
    own copy of this logic and prints the count. If the two implementations
    ever disagree, this test is auditing a different set of numbers than the
    guard reports, and the disagreement is worth more than either number.
    """
    import importlib.util
    path = os.path.join(ROOT, "tools", "publication", "artifact_map_check.py")
    spec = importlib.util.spec_from_file_location("_amc", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.LITERAL_RE.pattern == LITERAL_RE.pattern, (
        "tools/publication/artifact_map_check.py changed how it finds numeric "
        "literals; this test's copy must be updated to match, or the audit "
        "and the guard are describing different sets.")
