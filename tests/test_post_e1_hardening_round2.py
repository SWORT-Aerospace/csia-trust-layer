"""Guards for A16, A17, A18, A19 and the E2 preregistration template.

Each test pins the thing the corresponding tool could most plausibly lose:

    A16   that a forbidden transition is still forbidden
    A17   that the STRICT gate refuses all six forms AND accepts the real one
    A18   that the provenance record still describes this checkout
    A19   that five implementations still agree, and that the harness cannot
          silently read a non-answer as an answer again
    B5    that the template stays a template until hardware exists
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, "research", "physical_validation", "results")


def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ A16

def test_an_exception_never_becomes_a_nominal_verdict():
    """The first of the two transitions the programme forbids by name."""
    from csia_assurance import qualify

    class Exploding(dict):
        def get(self, *a, **k):
            raise RuntimeError("boom")

    v = qualify(Exploding())
    assert v.state == "NOT_EVALUABLE"
    assert v.reason.startswith("FIREWALL_INTERNAL_EXCEPTION")
    assert not v.supported


def test_an_expired_certificate_is_never_honoured():
    """The second forbidden transition, in its most direct form."""
    from csia_assurance import qualify
    with open(os.path.join(ROOT, "csia_assurance", "vectors",
                           "V01_supported_unique.json"),
              encoding="utf-8") as fh:
        rec = json.load(fh)["record"]
    ts = rec.get("timestamp", 0.0)
    v = qualify(rec, {"config_hash": rec.get("config_hash"),
                      "software_hash": rec.get("software_hash"),
                      "timestamp": ts - 10.0,
                      "valid_until": ts - 1.0})
    assert v.reason == "STALE_SUPPORT_CERTIFICATE"
    assert not v.supported


def test_the_recovery_campaign_records_no_forbidden_transition():
    doc = _load("PROCESS_RECOVERY.json")
    assert doc["verdict"] == "NO_FORBIDDEN_TRANSITION", doc["failures"]
    # A campaign whose scenarios all vanished would also pass the line above.
    assert len(doc["runs"]) >= 6
    assert doc["not_tested_here"], (
        "the campaign no longer records what it could not test; a recovery "
        "report with no stated limit is the one nobody should trust")


def test_a_dead_telemetry_source_does_not_read_as_health():
    from csia_assurance import qualify
    with open(os.path.join(ROOT, "csia_assurance", "vectors",
                           "V01_supported_unique.json"),
              encoding="utf-8") as fh:
        rec = dict(json.load(fh)["record"])
    assert qualify(rec).supported, "the control vector is no longer supported"
    rec["canonical_sample_present"] = False
    v = qualify(rec)
    assert v.state == "NOT_EVALUABLE"
    assert v.reason == "MISSING_CANONICAL_SAMPLE"


# ------------------------------------------------------------------ A17

def test_the_strict_config_gate_accepts_the_committed_reference():
    """Without this, six refusals would prove only that the gate says no."""
    import yaml
    from csia_assurance import config_gate
    path = os.path.join(ROOT, "configs", "vehicle",
                        "reference_quad_ardupilot_v2.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert config_gate.check(doc, environ={}) == []


@pytest.mark.parametrize("mutate,expected", [
    (lambda d: d["csia"].__setitem__("tick_hz_override", 50.0),
     "UNKNOWN_KEY"),
    (lambda d: d["csia"].__setitem__("tickHz", 50.0),
     "ALIAS_OF_KNOWN_KEY"),
    (lambda d: d["csia"].__setitem__("TICK_HZ", 50.0),
     "CASE_VARIANT_OF_KNOWN_KEY"),
    (lambda d: d["csia"].__setitem__("tick-hz", 50.0),
     "SEPARATOR_VARIANT_OF_KNOWN_KEY"),
    (lambda d: d.__setitem__("overrides", {"csia": {"tick_hz": 50.0}}),
     "NESTED_OVERRIDE_BLOCK"),
])
def test_each_smuggling_form_is_refused_with_its_own_reason(mutate, expected):
    import copy

    import yaml
    from csia_assurance import config_gate
    path = os.path.join(ROOT, "configs", "vehicle",
                        "reference_quad_ardupilot_v2.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = copy.deepcopy(yaml.safe_load(fh))
    mutate(doc)
    reasons = {r["reason"] for r in config_gate.check(doc, environ={})}
    assert expected in reasons, reasons


def test_an_environment_override_is_refused():
    import yaml
    from csia_assurance import config_gate
    path = os.path.join(ROOT, "configs", "vehicle",
                        "reference_quad_ardupilot_v2.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    reasons = {r["reason"] for r in
               config_gate.check(doc, environ={"CSIA_TICK_HZ": "50"})}
    assert "ENVIRONMENT_OVERRIDE_PRESENT" in reasons


def test_the_strict_gate_never_guesses_a_correction():
    """A refusal names what the key resembles. It must not offer a value a
    caller could apply -- one refactor from a self-correcting config loader.

    THIS GUARD FIRED ON ITS OWN DOCUMENTATION FIRST. `config_gate.py`'s
    docstring says "there is no 'did you mean'", and a naive substring scan
    read that promise as the violation. It is the seventh guard in this
    repository to trip over prose that states the very rule it enforces.

    So the scan is over CODE, with docstrings and comments stripped. A
    forbidden-word check that cannot tell a claim from its denial produces a
    failure whose only fix is to stop writing the denial down, and that is a
    guard making the repository worse.
    """
    import ast
    import io
    import tokenize

    path = os.path.join(ROOT, "csia_assurance", "config_gate.py")
    src = open(path, encoding="utf-8").read()

    # Drop comments.
    kept = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT:
            kept.append(tok)
    stripped = tokenize.untokenize(kept)

    # Drop docstrings.
    tree = ast.parse(stripped)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                body.pop(0)
    code = ast.unparse(tree).lower()

    for banned in ("did you mean", "autocorrect", "def fix", "def repair",
                   "difflib", "get_close_matches"):
        assert banned not in code, (
            f"config_gate.py's CODE now contains {banned!r}; a gate that "
            f"suggests a correction is one edit from applying it")


def test_nothing_was_smuggled_into_the_frozen_core():
    doc = _load("CONFIG_PROOF.json")
    assert doc["control"]["control_holds"], doc["control"]
    assert doc["verdict"] == "NOTHING_SMUGGLED_INTO_THE_CORE"
    assert doc["strict_gate_verdict"] == "ALL_SIX_REFUSED"
    assert doc["totals"]["forms_tried"] == 6


def test_the_config_proof_still_reports_the_environment_path_it_found():
    """CSIA_MODE is read. The artifact must keep saying so.

    The ENV_VAR row proves CSIA_TICK_HZ is inert; it does not prove there is
    no environment path. Deleting this record would upgrade the weaker true
    statement into the stronger false one.
    """
    doc = _load("CONFIG_PROOF.json")
    env = doc["environment_paths"]
    assert "CSIA_MODE" in env["variables_read_by_csia"]
    assert "NOT DATAFLOW" in env["check_performed"]


# ------------------------------------------------------------------ A18

def test_the_build_provenance_describes_this_checkout():
    doc = _load("BUILD_PROVENANCE.json")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    # The record is written before the commit that carries it, so it names
    # the parent. Either is acceptable; a THIRD commit is not.
    parents = subprocess.run(["git", "rev-list", "--max-count=3", "HEAD"],
                             cwd=ROOT, capture_output=True,
                             text=True).stdout.split()
    assert doc["source"]["commit"] in parents or doc["source"]["commit"] == head


def test_the_provenance_record_does_not_claim_to_be_signed():
    doc = _load("BUILD_PROVENANCE.json")
    text = json.dumps(doc).lower()
    assert "nothing here is signed" in doc["what_this_is_not"].lower()
    for overclaim in ("slsa level", "attested", "notarized"):
        assert overclaim not in text, (
            f"the provenance record now says {overclaim!r}; nothing here is "
            f"signed and it must not imply otherwise")


def test_the_frozen_core_still_matches_the_freeze_manifest():
    doc = _load("BUILD_PROVENANCE.json")
    core = doc["frozen_core"]
    assert core.get("identical_to_the_freeze") is True, (
        f"frozen-core drift since the E1 freeze: {core.get('paths_that_differ')}")


def test_every_third_party_import_is_declared():
    doc = _load("BUILD_PROVENANCE.json")
    dep = doc["undeclared_dependency_check"]
    assert dep.get("clean") is True, dep.get(
        "imported_but_not_installed_by_ci")


# ------------------------------------------------------------------ A19

def test_five_implementations_still_agree():
    doc = _load("ASSURANCE_DIFFERENTIAL.json")
    t = doc["totals"]
    assert t["comparisons"] > 1000, t
    assert t["real_disagreements"] == 0, doc["disagreements"][:3]
    assert doc["verdict"] == "FIVE_IMPLEMENTATIONS_AGREE"


def test_the_differential_says_what_agreement_does_not_prove():
    doc = _load("ASSURANCE_DIFFERENTIAL.json")
    assert "wrong definition agree" in doc["what_agreement_does_not_prove"]


def test_the_firewall_column_refuses_to_answer_when_nothing_was_computed():
    """The harness bug this campaign found, pinned from the outside.

    Its first version set `ranking` -- which the firewall deliberately does
    not read -- so every call returned UNKNOWN with an EMPTY
    `competitors_without_witness`, and `b not in ()` reported every pair as
    distinguishable. A silence read as a yes.
    """
    from tools.assurance import differential

    assert differential._FIREWALL_ANSWERED == (
        "SUPPORTED_UNIQUE", "AMBIGUOUS", "NON_IDENTIFIABLE"), (
        "the set of states in which competitors_without_witness is a computed "
        "answer has changed; re-derive it from firewall.qualify before "
        "widening it")

    low = {"a": frozenset({"x"}), "b": frozenset()}
    ok, state = differential._firewall_answer(
        low, "a", "b", frozenset({"x"}), ["x"])
    assert ok is True and state == "SUPPORTED_UNIQUE", (ok, state)


def test_a_firewall_state_that_computed_nothing_yields_no_answer():
    """The exact regression: an UNKNOWN verdict must not read as `True`.

    `qualify` returns UNKNOWN / NO_LEADER_ASSERTED with an EMPTY
    `competitors_without_witness` when no leader is asserted. `b not in ()` is
    True, so a harness that reads the field without checking the state reports
    every pair as distinguishable.
    """
    import csia_assurance
    from csia_assurance.firewall import SCHEMA
    from tools.assurance import differential

    leaderless = {
        "schema": SCHEMA, "canonical_sample_present": True,
        "config_hash": "c", "software_hash": "s", "timestamp": 0.0,
        "signatures": {"a": ["x"], "b": []},
        "gates": {"x": 1.0},
        "evidence_states": {"x": "ACTIVE"},
    }
    v = csia_assurance.qualify(leaderless)
    assert v.state == "UNKNOWN" and v.reason == "NO_LEADER_ASSERTED"
    assert v.competitors_without_witness == (), (
        "the empty field is the whole hazard; if it is no longer empty here, "
        "re-derive the harness rule")
    assert v.state not in differential._FIREWALL_ANSWERED, (
        "UNKNOWN is now treated as an answered state, which is exactly the "
        "defect this test exists to prevent")


def test_the_firewall_column_returns_none_on_a_contract_failure():
    """A refused record is not an answer either, and must not become one."""
    import csia_assurance
    from csia_assurance.firewall import SCHEMA
    from tools.assurance import differential

    bad = {
        "schema": SCHEMA, "canonical_sample_present": True,
        "config_hash": "c", "software_hash": "s", "timestamp": 0.0,
        "leader": "a",
        "signatures": {"a": ["x"], "b": []},
        "gates": {"x": float("nan")},
        "evidence_states": {"x": "ACTIVE"},
    }
    v = csia_assurance.qualify(bad)
    assert v.state == "NOT_EVALUABLE"
    assert v.state not in differential._FIREWALL_ANSWERED

    # And the control still answers, so the check above is not vacuous.
    ok, _state = differential._firewall_answer(
        {"a": frozenset({"x"}), "b": frozenset()}, "a", "b",
        frozenset({"x"}), ["x"])
    assert ok is True


# ------------------------------------------------------------------ B5

PREREG = os.path.join(ROOT, "research", "physical_validation", "prereg",
                      "E2_HARDWARE_BOUNDARY_PREREG.md")


def test_the_e2_preregistration_is_still_marked_a_template():
    text = open(PREREG, encoding="utf-8").read()
    assert "TEMPLATE, NOT A COMMITTED PREREGISTRATION" in text
    assert "E2_STATUS: NOT_RUN" in text


def test_the_e2_preregistration_still_has_unfilled_fields():
    """If every [FILL:] were gone, the file would read as a real
    preregistration for a campaign that never ran."""
    text = open(PREREG, encoding="utf-8").read()
    assert text.count("[FILL:") >= 15, (
        "the E2 preregistration has been filled in. If hardware really "
        "arrived, remove this test deliberately and record why; if it did "
        "not, the file is now claiming an environment nobody measured")


def test_the_e2_preregistration_forbids_the_words_e1_forbids():
    """The banned words may appear ONLY inside the sentence banning them.

    Checked over a WINDOW of flattened text rather than per line, because the
    prohibition wraps across lines and a line-by-line scan reported the second
    half of its own prohibition as a violation -- the same wrapping mistake
    the manuscript hygiene guard already made once.
    """
    text = open(PREREG, encoding="utf-8").read()
    flat = " ".join(text.split())
    assert "repeated under the tested conditions" in flat

    for banned in ("prevalence", "population probability"):
        start = 0
        while True:
            i = flat.lower().find(banned, start)
            if i < 0:
                break
            window = flat[max(0, i - 300):i + 200].lower()
            assert ("not permitted" in window
                    or "nothing about" in window
                    or "cannot establish" in window), (
                f"{banned!r} appears outside a prohibition: "
                f"...{flat[max(0, i - 120):i + 120]}...")
            start = i + len(banned)


def test_the_e2_preregistration_keeps_rule_a_and_the_abort_that_matters():
    text = open(PREREG, encoding="utf-8").read()
    assert "RULE A APPLIES WITHOUT EXCEPTION" in text
    assert "COMMAND ISSUED" in text and "FAULT INJECTED" in text
    assert "Ledger first. Workaround never." in text
