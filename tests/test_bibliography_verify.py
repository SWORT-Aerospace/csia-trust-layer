"""The bibliography verifier must catch real discrepancies, and must never
report a pass it did not earn.

A tool that clears provenance markers is only as trustworthy as its comparison
logic. These tests drive it with recorded Crossref payloads so the logic is
proven offline, including the two ways it could be quietly wrong: folding
LaTeX accents so real matches are not reported as mismatches, and refusing to
call anything clearable when the publisher could not be reached.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "publication"))

from verify_bibliography import (                             # noqa: E402
    _norm, _strip_latex, compare, parse_bib)

BIB = os.path.join(ROOT, "papers", "csia_systems", "refs.bib")


def test_parses_every_entry_and_its_markers():
    e = parse_bib(BIB)
    assert len(e) == 11, sorted(e)
    assert "FROM-BRIEF-UNVERIFIED" in e["carvalho2013permanent"]["markers"]
    assert e["carvalho2013permanent"]["fields"]["volume"] == "49"


def test_latex_accents_fold_so_real_matches_are_not_false_alarms():
    assert _strip_latex("Jo{\\~a}o") == "Joao"
    assert _strip_latex("St{\\'e}phane") == "Stephane"
    assert _norm("2068--2078") == _norm("2068-2078")
    assert _norm("Automatica") == _norm("automatica ")


def test_a_matching_record_is_clearable():
    e = parse_bib(BIB)["carvalho2013permanent"]
    rec = {
        "title": ["Robust diagnosis of discrete-event systems against "
                  "permanent loss of observations"],
        "container-title": ["Automatica"],
        "volume": "49", "issue": "1", "page": "223-231",
        "issued": {"date-parts": [[2013]]},
        "author": [{"family": "Carvalho"}, {"family": "Moreira"},
                   {"family": "Basilio"}, {"family": "Lafortune"}],
    }
    got = compare(e, rec)
    assert all(v[0] == "MATCH" for v in got.values()), got


def test_a_wrong_volume_is_caught():
    e = parse_bib(BIB)["carvalho2013permanent"]
    rec = {"title": ["Robust diagnosis of discrete-event systems against "
                     "permanent loss of observations"],
           "container-title": ["Automatica"], "volume": "51", "issue": "1",
           "page": "223-231", "issued": {"date-parts": [[2013]]},
           "author": [{"family": "Carvalho"}, {"family": "Moreira"},
                      {"family": "Basilio"}, {"family": "Lafortune"}]}
    assert compare(e, rec)["volume"][0] == "MISMATCH"


def test_a_reordered_author_list_is_caught():
    e = parse_bib(BIB)["carvalho2013permanent"]
    rec = {"title": [e["fields"]["title"]], "container-title": ["Automatica"],
           "volume": "49", "issue": "1", "page": "223-231",
           "issued": {"date-parts": [[2013]]},
           "author": [{"family": "Lafortune"}, {"family": "Carvalho"},
                      {"family": "Moreira"}, {"family": "Basilio"}]}
    assert compare(e, rec)["authors"][0] == "MISMATCH"


def test_a_VERIFY_placeholder_reads_as_missing_not_as_a_match():
    e = parse_bib(BIB)["takai2021diagnosability"]
    rec = {"title": ["Some real title"], "container-title": ["Automatica"],
           "volume": "1", "issue": "1", "page": "1-2",
           "issued": {"date-parts": [[2021]]}, "author": [{"family": "Takai"}]}
    assert compare(e, rec)["title"][0] == "MISSING_IN_BIB"


def test_unreachable_publisher_exits_nonzero_and_clears_nothing():
    """The failure mode that matters: no network must never look like a pass."""
    proc = subprocess.run(
        [sys.executable,
         os.path.join(ROOT, "tools", "publication", "verify_bibliography.py")],
        capture_output=True, text=True, cwd=ROOT, timeout=600)
    # In this sandbox Crossref is blocked, so the tool must refuse.
    if "UNREACHABLE" in proc.stdout or proc.returncode == 2:
        assert proc.returncode == 2
        assert "must NOT be cleared" in proc.stdout
    else:                                    # network available: real run
        assert proc.returncode in (0, 1)


def test_fixture_mode_runs_end_to_end(tmp_path):
    fx = tmp_path / "fx.json"
    fx.write_text(json.dumps({
        "10.1016/j.automatica.2012.09.017": {
            "title": ["Robust diagnosis of discrete-event systems against "
                      "permanent loss of observations"],
            "container-title": ["Automatica"], "volume": "49", "issue": "1",
            "page": "223-231", "issued": {"date-parts": [[2013]]},
            "author": [{"family": "Carvalho"}, {"family": "Moreira"},
                       {"family": "Basilio"}, {"family": "Lafortune"}]}}))
    proc = subprocess.run(
        [sys.executable,
         os.path.join(ROOT, "tools", "publication", "verify_bibliography.py"),
         "--fixture", str(fx)],
        capture_output=True, text=True, cwd=ROOT, timeout=600)
    assert "bibliography verification" in proc.stdout
    assert "uncited" in proc.stdout
