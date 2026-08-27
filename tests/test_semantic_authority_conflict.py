"""Guards for the semantic-authority-conflict package. Item 57.

NOTHING HERE SCORES A RESULT. These tests protect the properties that would
make the package dishonest if they broke: the frozen core untouched, the
baseline conflicts still reproducing, the authorities distinct and cited, no
weights anywhere, and no claim that a silence is a disagreement.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "research", "semantic_authority_conflict")
RES = os.path.join(PKG, "results")


def _load(name, *parts):
    """Load a research module BY PATH -- tests/test_ci_env.py scans import
    statements to catch undeclared dependencies, and a bare local import
    inside a research package looks exactly like one."""
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


def _csv(name, sub=""):
    p = os.path.join(PKG, sub, name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not built")
    return list(csv.DictReader(open(p, encoding="utf-8")))


# ------------------------------------------------- production core untouched
def test_the_package_contains_no_production_csia_file():
    for dirpath, _dirs, files in os.walk(PKG):
        for fn in files:
            p = os.path.join(dirpath, fn).replace(os.sep, "/")
            assert "/csia/" not in p, p
    assert os.path.exists(os.path.join(ROOT, "tests", "test_v1_frozen.py"))


# --------------------------------------------- baseline conflicts reproduce
def test_the_battery_three_way_split_still_reproduces():
    """5.00 / 0.00 / -1.00 A. If this stops reproducing, item 14's hard stop
    has fired and nothing downstream is valid."""
    rows = _csv("DECLARED_VS_EFFECTIVE_SEMANTICS.csv")
    bat = {r["authority"]: r for r in rows
           if r["case"] == "battery.current_not_measured"}
    assert bat["C_consumer_A"]["effective_value_at_core"] == "(5.0,)"
    assert bat["C_consumer_B"]["effective_value_at_core"] == "(0.0,)"
    assert bat["C_consumer_C"]["effective_value_at_core"] == "(-1.0,)"


def test_the_gnss_split_still_reproduces():
    rows = _csv("DECLARED_VS_EFFECTIVE_SEMANTICS.csv")
    g = {r["authority"]: r for r in rows if r["case"] == "gnss.no_3d_fix"}
    assert g["C_consumer_A"]["effective_token_at_core"] == "NOTHING_EMITTED"
    assert g["C_consumer_B"]["effective_token_at_core"] == "I"
    assert g["C_consumer_C"]["effective_token_at_core"] == "I"


# ------------------------------------------------ authorities stay distinct
def test_every_authority_citation_still_resolves():
    A = _load("_authorities", "authorities.py")
    bad = []
    for case in A.CASES:
        for name, a in case["authorities"].items():
            for c in a["support"]:
                ok, why = A.verify(c)
                if not ok:
                    bad.append((case["case"], name, c["locator"], why))
    assert not bad, bad


def test_the_authority_kinds_are_distinct_and_source_identified():
    """Item 58-I: every authority must correspond to an independently
    identifiable source, not to a label someone chose."""
    A = _load("_authorities", "authorities.py")
    allowed = {"PROTOCOL_SCHEMA", "PRODUCER_SOURCE", "CONSUMER_SOURCE"}
    for case in A.CASES:
        kinds = set()
        for name, a in case["authorities"].items():
            assert a["support_kind"] in allowed, (name, a["support_kind"])
            assert a["support"], name
            kinds.add(a["support_kind"])
        assert len(kinds) >= 2, (case["case"], kinds)


def test_no_authority_carries_a_weight():
    """Item 10 forbids inventing precedence numbers. Nothing in this package
    may introduce one."""
    A = _load("_authorities", "authorities.py")
    banned = ("weight", "prior", "confidence", "trust_score", "probability")
    for case in A.CASES:
        for name, a in case["authorities"].items():
            for k in a:
                assert not any(b in k.lower() for b in banned), (name, k)
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"):
            continue
        src = open(os.path.join(PKG, fn), encoding="utf-8").read()
        for m in re.finditer(r"weight\s*=\s*([0-9.]+)", src):
            raise AssertionError(f"{fn}: numeric authority weight {m.group(0)}")


# ------------------------------------- silence is not a disagreement
def test_silence_is_never_counted_as_conflict():
    rows = _csv("AUTHORITY_CONFLICTS.csv")
    A = _load("_authorities", "authorities.py")
    for r in rows:
        silent = (r["interpretation_a"] == A.SILENT
                  or r["interpretation_b"] == A.SILENT)
        if silent:
            assert r["status"] == "UNDERSPECIFICATION", r
        if r["status"] == "CONFLICT":
            assert not silent, r
            assert r["interpretation_a"] != r["interpretation_b"], r


def test_underspecification_is_reported_and_not_folded_into_conflict():
    rows = _csv("AUTHORITY_CONFLICTS.csv")
    assert any(r["status"] == "UNDERSPECIFICATION" for r in rows), (
        "the distinction the package turns on has vanished")
    assert any(r["status"] == "CONFLICT" for r in rows)


def test_no_spec_versus_producer_conflict_is_reported():
    """The headline finding. If a future edit makes one appear, the report's
    section 1 is wrong and must be rewritten, not the test relaxed."""
    rows = _csv("AUTHORITY_CONFLICTS.csv")
    bad = [r for r in rows
           if r["status"] == "CONFLICT"
           and r["conflict_type"] == "SPEC_VS_PRODUCER"]
    assert not bad, bad


# ----------------------------------------- equivalence is not numeric equality
def test_declared_and_effective_semantics_are_kept_in_separate_columns():
    rows = _csv("DECLARED_VS_EFFECTIVE_SEMANTICS.csv")
    assert rows
    for r in rows:
        assert "declared_semantics" in r and "effective_value_at_core" in r
        # a declared interpretation is a NAME, an effective value is a NUMBER
        assert not re.fullmatch(r"[-\d.,() ]+", r["declared_semantics"]), r


# --------------------------------------------- downstream results are honest
def test_every_level_carries_its_null_control():
    rows = _csv("DECISION_SENSITIVITY.csv")
    assert rows
    for r in rows:
        assert r["control_agrees"] in ("True", "False"), r
        if r["control_agrees"] == "False":
            assert r["verdict"] == "CONFOUNDED_BY_CONTROL", r
        if r["verdict"] == "SEMANTICALLY_AMBIGUOUS":
            assert r["control_agrees"] == "True", r


def test_downstream_results_come_from_identical_raw_traces():
    """Item 57: the authorities must be compared on the same word."""
    sv = _j("SET_VALUED_ASSURANCE_RESULTS.json")
    for case, d in sv["cases"].items():
        assert isinstance(d["word"], str) and d["word"], case
        assert len(d["authorities"]) >= 2, case


def test_the_set_valued_output_contains_every_source_supported_reading():
    """Item 57: no interpretation may be added that no authority supports,
    and none that one does may be dropped."""
    A = _load("_authorities", "authorities.py")
    sv = _j("SET_VALUED_ASSURANCE_RESULTS.json")
    by_case = {c["case"]: c for c in A.CASES}
    for case, d in sv["cases"].items():
        declared = {k for k, v in by_case[case]["authorities"].items()
                    if k.startswith("C_consumer")}
        assert set(d["authorities"]) == declared, (case, d["authorities"])


def test_no_conflict_is_claimed_to_reach_the_failsafe_action():
    """The verdict rests on this. If it ever becomes false the direction
    reopens and the report must be rewritten."""
    rows = _csv("CONFLICT_PROPAGATION.csv")
    assert rows
    for r in rows:
        assert r["disagreement_reaches_ACTION"] == "False", r


# ------------------------------------------------------------ honesty guards
def test_physical_hil_is_never_claimed():
    for fn in os.listdir(PKG):
        if not fn.endswith(".md"):
            continue
        t = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        if "hil" not in t and "hardware" not in t:
            continue
        assert ("no hardware" in t or "not executed" in t
                or "no physical hil" in t or "design only" in t), fn


def test_the_security_note_stays_conceptual():
    t = open(os.path.join(PKG, "SECURITY_IMPLICATIONS_NOTES.md"),
             encoding="utf-8").read().lower()
    assert "no exploit tooling" in t
    assert "conceptual" in t
    for fn in os.listdir(PKG):
        assert not fn.lower().startswith(("exploit", "attack", "poc")), fn


def test_the_ledger_records_no_surviving_novelty_claim():
    led = _j("CLAIM_LEDGER.json")
    assert led["novelty"] == "NOT ESTABLISHED"
    assert "PROVED - POSSIBLE NOVEL CONTRIBUTION" not in {
        c["status"] for c in led["claims"]}
    assert led["refuted_predictions"]
    for p in led["refuted_predictions"]:
        assert p["kept"] is True
    for c in led["claims"]:
        for k in ("statement", "evidence", "status", "assumptions",
                  "strongest_allowed_wording", "forbidden_stronger_wording",
                  "next_falsification_test"):
            assert c.get(k), (c["id"], k)


def test_prior_verdicts_are_preserved_and_not_renamed():
    led = _j("CLAIM_LEDGER.json")
    p = led["preserved_prior_verdicts"]
    assert p["generic semantic-equivalence checking"] == "KNOWN/SUBSUMED"
    assert p["dual operational/diagnostic admissibility"] == "KNOWN/SUBSUMED"
    assert "HEURISTICS_SUFFICIENT" in p["AI-assisted contract synthesis"]


def test_no_novelty_wording_anywhere_in_the_package():
    banned = ("first-ever", "unprecedented", "new paradigm", "new theorem",
              "breakthrough")
    denials = ("not ", "no ", "none", "never", "forbidden", "subsumed",
               "known/", "refuted", "cannot", "does not")
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".md"):
            continue
        raw = open(os.path.join(PKG, fn), encoding="utf-8").read().lower()
        text = re.sub(r"[.,;:!?)\]]", " ",
                      raw.replace("*", "").replace("`", ""))
        for w in banned:
            if w not in text:
                continue
            for i, line in enumerate(text.splitlines()):
                if w not in line or line.lstrip().startswith("#"):
                    continue
                window = " ".join(text.splitlines()[i:i + 3])
                assert any(k in window for k in denials), (fn, w, line[:120])
