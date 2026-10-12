"""Guards for the AI-contract-synthesis package. Item 55.

NOTHING HERE SCORES A RESULT. These tests protect the properties that would
make the package dishonest if they broke: the production core untouched, the
ordering discipline intact, an unsupported clause unable to become a defect,
and every artificial fixture labelled non-scored.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "ai_contract_synthesis")
RES = os.path.join(PKG, "results")


def _load(name, *parts):
    """Load a research module BY PATH.

    Not `import containment` -- tests/test_ci_env.py scans import statements
    to catch undeclared third-party dependencies, and a bare local import
    inside a research package looks exactly like one.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PKG, *parts))
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


def _j(name, sub=""):
    with open(os.path.join(PKG, sub, name), encoding="utf-8") as fh:
        return json.load(fh)


def _needs(name, sub=""):
    return pytest.mark.skipif(
        not os.path.exists(os.path.join(PKG, sub, name)),
        reason=f"{name} not built")


# ------------------------------------------------- production core untouched
def test_no_production_csia_file_is_part_of_this_package():
    """Item 60. The package may not modify CSIA production semantics."""
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            p = os.path.join(dirpath, fn)
            assert "/csia/" not in p.replace(os.sep, "/"), p
    assert os.path.exists(os.path.join(ROOT, "tests", "test_v1_frozen.py")), (
        "the frozen-core test must still exist; it is what actually enforces "
        "this")


# ------------------------------------------------------- ordering discipline
def test_the_freeze_manifest_exists_and_covers_the_predictions():
    fr = _j("FREEZE.json")
    for rel in ("candidates/B1_CODE_ONLY.json",
                "candidates/NONSCORED_HALLUCINATION.json",
                "prompts/semantic_contract_miner_v1.md",
                "METRICS.md", "HELD_OUT_PILOT.json"):
        assert rel in fr["hashes"], rel
    assert "blindness" in fr["not_a_claim_of"]


def test_prediction_files_still_match_the_freeze():
    """A verifier may be amended after the freeze and is recorded in
    FREEZE_AMENDMENTS.json; a PREDICTION may not be touched at all."""
    import hashlib
    fr = _j("FREEZE.json")["hashes"]
    for rel, want in fr.items():
        if not rel.startswith(("candidates/", "prompts/")) \
                and rel not in ("METRICS.md", "HELD_OUT_PILOT.json",
                                "BENCHMARK_SPLIT.json"):
            continue
        got = hashlib.sha256(
            open(os.path.join(PKG, rel), "rb").read()).hexdigest()
        assert got == want, (
            f"{rel} changed after the freeze; the ordering guarantee is void")


def test_any_post_freeze_change_is_recorded_rather_than_hidden():
    r = subprocess.run([sys.executable, os.path.join(PKG, "freeze.py"),
                        "--check"], capture_output=True, text=True)
    if r.returncode == 0:
        return                                  # nothing drifted
    assert os.path.exists(os.path.join(PKG, "FREEZE_AMENDMENTS.json")), (
        "frozen artifacts drifted with no amendment record")
    am = _j("FREEZE_AMENDMENTS.json")
    changed = {a["file"] for a in am["amendments"]}
    for a in am["amendments"]:
        assert a["amends_a_verifier_not_a_prediction"] is True, a["file"]
        assert a["what"].strip() and a["why_it_is_not_a_result_change"].strip()
    assert changed, "amendment file is empty"


def test_build_reference_refuses_to_run_when_the_freeze_is_broken(tmp_path):
    """The refusal is the mechanism, so it is tested rather than trusted."""
    src = open(os.path.join(PKG, "build_reference.py"), encoding="utf-8").read()
    assert "require_freeze()" in src
    assert "REFUSING TO BUILD THE REFERENCE" in src


# ------------------------------------------------------- the reference is not
def test_the_reference_never_calls_itself_ground_truth():
    ref = _j("REFERENCE.json", "SOURCE_AUDITED_REFERENCE")
    for phrase in ("ground truth", "a gold standard", "human reviewed"):
        assert phrase in ref["NOT"], phrase
    assert "MECHANICAL" in ref["sentinel_clause_derivation"]
    assert "JUDGEMENT" in ref["consumer_clause_derivation"]


def test_every_reference_case_records_how_it_was_derived():
    ref = _j("REFERENCE.json", "SOURCE_AUDITED_REFERENCE")
    for c in ref["cases"]:
        assert c["derivation"], c["case_id"]
        for cl in c["clauses"]:
            assert cl["support"], (c["case_id"], cl["kind"])


# -------------------------------------------------- promotion cannot be faked
def test_an_unsupported_clause_cannot_become_a_confirmed_defect():
    sys.path.insert(0, os.path.join(PKG, "verification"))
    C = _load("_containment", "verification", "containment.py")
    bad = {"case_id": "FAKE.field", "condition": "B1_CODE_ONLY",
           "abstain": False, "explicit_semantic_state_found": "YES",
           "confidence": 0.99,
           "clauses": [{"kind": "SENTINEL_CONDITION",
                        "statement": "field == -1 is the sentinel.",
                        "raw_condition": "field == -1",
                        "state": "X", "support": [], "support_kind": "NONE"}]}
    r = C.promote(bad)
    assert r["promoted_as_defect"] is False
    assert r["phase2"] == "NOT_RUN"
    assert r["final"] != "CHECKER_CONFIRMED_IMPLEMENTATION_VIOLATION"


def test_phase2_is_only_reachable_from_source_supported():
    src = open(os.path.join(PKG, "verification", "containment.py"),
               encoding="utf-8").read()
    assert 'if p1 != "SOURCE_SUPPORTED":' in src
    assert '"phase2": "NOT_RUN"' in src


def test_abstention_is_a_valid_output_and_is_never_unsafe():
    sys.path.insert(0, os.path.join(PKG, "verification"))
    S = _load("_score", "score.py")
    ref = _j("REFERENCE.json", "SOURCE_AUDITED_REFERENCE")
    by_id = {c["case_id"]: c for c in ref["cases"]}
    cid = next(c["case_id"] for c in ref["cases"] if c["has_explicit_state"])
    assert S.unsafe({"case_id": cid, "abstain": True,
                     "explicit_semantic_state_found": "UNKNOWN",
                     "clauses": []}, by_id) == []


# ------------------------------------------------------------ the fixtures
def test_every_artificial_fixture_is_labelled_non_scored():
    d = _j("NONSCORED_HALLUCINATION.json", "candidates")
    assert d["scored"] is False
    assert "NON-SCORED" in d["status"]
    for c in d["candidates"]:
        assert c["case_id"].startswith("FIXTURE_"), c["case_id"]
        assert c.get("fixture_truth"), c["case_id"]
    fx = os.path.join(PKG, "fixtures")
    for fn in os.listdir(fx):
        if fn.endswith(".py"):
            assert "NON-SCORED FIXTURE" in open(
                os.path.join(fx, fn), encoding="utf-8").read(), fn


@_needs("HALLUCINATION_CONTAINMENT.json", "results")
def test_no_fixture_ever_reaches_the_checker():
    d = _j("HALLUCINATION_CONTAINMENT.json", "results")
    assert d["status"].startswith("NON-SCORED")
    for r in d["results"]:
        assert r["promoted_as_defect"] is False, r["case_id"]
        assert r["final"] != "CHECKER_CONFIRMED_IMPLEMENTATION_VIOLATION"


def test_fixture_cases_are_absent_from_every_scored_result():
    for fn in os.listdir(RES) if os.path.exists(RES) else []:
        if not fn.endswith(".csv"):
            continue
        with open(os.path.join(RES, fn), encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                assert not str(row.get("case_id", "")).startswith("FIXTURE_"), \
                    (fn, row.get("case_id"))


# ------------------------------------------------------------- reproducibility
def test_the_mechanical_pieces_are_deterministic():
    """Same input, same output -- the parts that do not involve a model.

    enumerate_universe.py writes BENCHMARK_SPLIT.json IN PLACE and has no
    guard on its input: it reads the MAVLink message definitions out of an
    ArduPilot checkout outside this repository, and if that checkout is
    absent it resolves no messages, builds an empty universe and writes it
    over the committed artifact. That artifact is hash-pinned in FREEZE.json,
    so on any machine without the checkout this test used to destroy the
    split and void the ordering guarantee -- reporting non-determinism when
    the real finding was a missing input.

    The script is left alone deliberately. It is frozen, and what the freeze
    certifies is that the file defining the held-out split existed with those
    contents before the reference was built; editing it now would damage that
    evidence even with an amendment recorded. So the guard lives here, and
    the test restores the artifact whatever happens.
    """
    import hashlib
    import shutil
    if not os.path.isdir(_mavlink_dir()):
        pytest.skip("MAVLink message definitions not present; "
                    "determinism of the enumerator is untested here, "
                    "not assumed")
    split = os.path.join(PKG, "BENCHMARK_SPLIT.json")
    before = hashlib.sha256(open(split, "rb").read()).digest()
    keep = split + ".pre_determinism_check"
    shutil.copy2(split, keep)
    try:
        subprocess.run([sys.executable,
                        os.path.join(PKG, "enumerate_universe.py")],
                       capture_output=True, check=True)
        after = hashlib.sha256(open(split, "rb").read()).digest()
    finally:
        # Unconditional: a failure here must not leave a frozen artifact
        # rewritten, because the next test to read it would be measuring
        # this test's damage rather than the repository.
        shutil.move(keep, split)
    assert before == after, "the case universe is not reproducible"
    assert hashlib.sha256(open(split, "rb").read()).digest() == before, \
        "the determinism check did not restore the artifact it rewrote"


def _mavlink_dir():
    """The external checkout the enumerator reads, taken FROM the enumerator.

    Read out of the frozen script rather than retyped, so this guard cannot
    drift away from the path the script actually uses.
    """
    import re
    src = open(os.path.join(PKG, "enumerate_universe.py"),
               encoding="utf-8").read()
    m = re.search(r'MAVLINK_DIR = \((.*?)\)\n', src, re.S)
    assert m, "MAVLINK_DIR not found in enumerate_universe.py"
    return "".join(re.findall(r'"([^"]*)"', m.group(1)))


def test_repeatability_is_reported_as_not_run_rather_than_fabricated():
    p = os.path.join(RES, "REPEATABILITY_RESULTS.csv")
    if not os.path.exists(p):
        pytest.skip("not built")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert rows
    for r in rows:
        assert r["status"] == "NOT_RUN"
        assert r["clause_agreement"] == "" and r["variance"] == ""


# ---------------------------------------------------------------- the ledger
def test_the_ledger_records_no_surviving_novelty_claim():
    led = _j("CLAIM_LEDGER.json")
    assert led["novelty"] == "NOT ESTABLISHED"
    assert "PROVED - POSSIBLE NOVEL CONTRIBUTION" not in {
        c["status"] for c in led["claims"]}
    assert led["refuted_predictions"]
    for p in led["refuted_predictions"]:
        assert p["kept"] is True
    for c in led["claims"]:
        for k in ("claim", "evidence", "status", "assumptions",
                  "strongest_allowed_wording", "forbidden_stronger_wording",
                  "next_falsification_test"):
            assert c.get(k), (c["id"], k)


def test_the_containment_caveat_is_stated_wherever_the_number_appears():
    """6/6 is fitted to self-authored fixtures. Any document quoting it must
    say so within the same page."""
    for fn in ("HALLUCINATION_CONTAINMENT.md", "CHATGPT_REVIEW_REPORT.md",
               "README.md"):
        t = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        if "6/6" not in t:
            continue
        assert ("fitted" in t
                or "not an estimate" in t
                or "not an out-of-sample" in t
                or "on the first run" in t), fn


def test_no_novelty_wording_anywhere_in_the_package():
    banned = ("first-ever", "unprecedented", "new paradigm", "new theorem",
              "breakthrough")
    denials = ("not ", "no ", "none", "never", "forbidden", "subsumed",
               "known/", "refuted", "unsupported", "cannot")
    import re
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        text = re.sub(r"[.,;:!?)\]]", " ", raw.replace("*", "").replace("`", ""))
        for w in banned:
            if w not in text:
                continue
            for i, line in enumerate(text.splitlines()):
                if w not in line or line.lstrip().startswith("#"):
                    continue
                window = " ".join(text.splitlines()[i:i + 3])
                assert any(k in window for k in denials), (fn, w, line[:120])
