"""The DEA conformance regime, tested the only way that means anything.

A conformance runner that passes everything is indistinguishable from one that
tests nothing. So the load-bearing tests here are not "the good reference
passes" -- they are:

  1. every one of the eight bad references is REJECTED, and rejected for the
     requirement it was built to violate;
  2. every requirement DEA-1..DEA-10 is violated by at least one bad
     reference, so a requirement nobody can fail cannot quietly enter the
     profile;
  3. the conforming reference SHARES NO CODE WITH CSIA -- a profile validated
     only against its author's own system is a description of that system;
  4. the runner produces no score, because a percentage invites declaring
     requirements INAPPLICABLE to raise the denominator.

INCONCLUSIVE IS TESTED AS A FIRST-CLASS VERDICT. A regime that collapses "we
could not test this" into PASS is worse than one that has no such verdict,
because it looks complete.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.dea import conformance as C                     # noqa: E402
from tools.dea.references import good_minimal              # noqa: E402

PROFILE = os.path.join(ROOT, "standards", "dea", "DEA_PROFILE.md")
SCHEMA_DIR = os.path.join(ROOT, "standards", "dea", "schemas")

#: Which requirement each bad reference is built to violate. Read from the
#: module's own VIOLATES line so the map cannot drift from the file.
BAD_REFERENCES = [
    "bad_no_hypothesis_set", "bad_no_evidence_model", "bad_ignores_freshness",
    "bad_inapplicable_counts_as_pass", "bad_high_score_is_support",
    "bad_never_unassessable", "bad_decorative_witness",
    "bad_silence_reads_as_health",
]


def _violates(module_name: str) -> list:
    path = os.path.join(ROOT, "tools", "dea", "references",
                        module_name + ".py")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("VIOLATES:"):
                return [t.strip() for t in
                        line.split(":", 1)[1].split(",") if t.strip()]
    raise AssertionError(f"{module_name} declares no VIOLATES line")


def _load(module_name):
    import importlib
    return importlib.import_module(f"tools.dea.references.{module_name}")


# ------------------------------------------------------------------ scenario
#
# One script, driven through every implementation. Three probes, chosen so the
# scenario exercises the requirements rather than flattering anybody:
#
#   t=0  pump running, evidence separates FILTER_CLOGGED from everything
#   t=1  pump OFF -- dP and flow are INAPPLICABLE. Nothing is supported, so a
#        conforming layer must say unassessable and must not claim health.
#   t=2  pump running, but the level reading has aged out. Evidence is
#        present and STALE, which is not the same as absent.

SCRIPT = {
    0: {"pump_running": True,
        "obs": {"dP_across_filter": ("HIGH", 0.1),
                "flow_vs_command": ("LOW", 0.1),
                "reservoir_level_trend": ("NORMAL", 1.0)}},
    1: {"pump_running": False,
        "obs": {"dP_across_filter": ("NORMAL", 0.1),
                "flow_vs_command": ("NORMAL", 0.1),
                "reservoir_level_trend": ("NORMAL", 1.0)}},
    2: {"pump_running": True,
        "obs": {"dP_across_filter": ("NORMAL", 0.1),
                "flow_vs_command": ("NORMAL", 0.1),
                "reservoir_level_trend": ("NORMAL", 999.0)}},
}

#: The same script in the flat shape the bad references consume.
FLAT = {
    0: {"state": {"dP": {"outcome": "HIGH", "fresh": True, "applicable": True},
                  "flow": {"outcome": "LOW", "fresh": True,
                           "applicable": True},
                  "level": {"outcome": "NORMAL", "fresh": True,
                            "applicable": True}}},
    1: {"state": {"dP": {"outcome": "NORMAL", "fresh": True,
                         "applicable": False},
                  "flow": {"outcome": "NORMAL", "fresh": True,
                           "applicable": False},
                  "level": {"outcome": "NORMAL", "fresh": True,
                            "applicable": True}}},
    2: {"state": {"dP": {"outcome": "NORMAL", "fresh": True,
                         "applicable": True},
                  "flow": {"outcome": "NORMAL", "fresh": True,
                           "applicable": True},
                  "level": {"outcome": "NORMAL", "fresh": False,
                            "applicable": True}}},
}

PROBES = [
    C.Probe(0, "separating evidence present", expect_evidence_active=True),
    C.Probe(1, "pump off: dP and flow inapplicable",
            expect_evidence_active=False),
    C.Probe(2, "level reading aged out", expect_evidence_active=True),
]


# ================================================== the conforming reference

def test_the_non_csia_reference_conforms():
    impl = good_minimal.HydraulicLoop(SCRIPT)
    report = C.run(impl, PROBES)
    fails = [r for r in report.results if r.verdict is C.Verdict.FAIL]
    assert not fails, (
        "the conforming reference failed: "
        + "; ".join(f"{r.requirement}: {r.detail}" for r in fails))


def test_the_conforming_reference_shares_no_code_with_csia():
    """A profile validated only against its author's system is a description
    of that system wearing a standard's clothes."""
    path = os.path.join(ROOT, "tools", "dea", "references", "good_minimal.py")
    src = open(path, encoding="utf-8").read()
    assert "import csia" not in src and "from csia" not in src, \
        "the non-CSIA reference imports CSIA"
    assert good_minimal.SHARES_CODE_WITH_CSIA is False
    # And it is not even in the same domain. WORD BOUNDARIES: the first
    # version matched substrings and flagged "esc" inside "description",
    # which is a guard firing on ordinary English rather than on a domain leak.
    import re
    for avionics in ("imu", "gnss", "mag", "baro", "esc", "airframe",
                     "autopilot", "mavlink"):
        assert not re.search(rf"\b{avionics}\b", src, re.I), (
            f"{avionics!r} appears in the reference as a word; if the profile "
            f"were secretly avionics-shaped it would show up exactly here")


def test_the_certificate_validates_against_its_schema():
    jsonschema = pytest.importorskip("jsonschema")
    with open(os.path.join(SCHEMA_DIR,
                           "conformance_certificate.schema.json")) as fh:
        schema = json.load(fh)
    cert = C.run(good_minimal.HydraulicLoop(SCRIPT), PROBES).certificate()
    jsonschema.validate(cert, schema)


def test_a_witness_validates_against_its_schema():
    jsonschema = pytest.importorskip("jsonschema")
    with open(os.path.join(SCHEMA_DIR, "support_witness.schema.json")) as fh:
        schema = json.load(fh)
    out = good_minimal.HydraulicLoop(SCRIPT).output(0)
    assert out["attribution"], "probe 0 must produce an attribution"
    jsonschema.validate(out["witness"], schema)


# ========================================== the eight, and what they prove

@pytest.mark.parametrize("module_name", BAD_REFERENCES)
def test_each_bad_reference_is_rejected(module_name):
    mod = _load(module_name)
    report = C.run(mod.Impl(FLAT), PROBES)
    assert not report.conformant, (
        f"{module_name} was accepted. A conformance runner that passes "
        f"everything is indistinguishable from one that tests nothing.")


@pytest.mark.parametrize("module_name", BAD_REFERENCES)
def test_each_bad_reference_fails_the_requirement_it_violates(module_name):
    """Rejected is not enough -- rejected FOR THE RIGHT REASON.

    A runner that failed everything on DEA-1 would pass the test above while
    testing nothing at all.
    """
    mod = _load(module_name)
    report = C.run(mod.Impl(FLAT), PROBES)
    bad = {r.requirement for r in report.results
           if r.verdict in (C.Verdict.FAIL, C.Verdict.INCONCLUSIVE)}
    declared = set(_violates(module_name))
    assert declared & bad, (
        f"{module_name} declares it violates {sorted(declared)}, but the "
        f"runner objected to {sorted(bad)}. Either the reference does not do "
        f"what it says or the runner is failing it for the wrong reason.")


def test_every_requirement_is_violated_by_some_reference():
    """A requirement nobody can fail is a requirement that means nothing.

    Fails CLOSED: add DEA-11 to the profile and this test names it until a bad
    reference exists that violates it.
    """
    covered = set()
    for module_name in BAD_REFERENCES:
        covered |= set(_violates(module_name))
    missing = sorted(set(C.REQUIREMENTS) - covered,
                     key=lambda r: int(r.split("-")[1]))
    assert not missing, (
        f"no bad reference violates {missing}. Either write one, or the "
        f"requirement is unfalsifiable and does not belong in the profile.")


def test_the_named_bad_implementation_from_the_brief_fails_on_support():
    """BAD_HIGH_SCORE_IS_SUPPORT: the shape most real implementations have.

    It computes a score, sorts, takes the top and calls it a diagnosis. The
    runner must object on DEA-5/DEA-6 specifically -- rank substituted for
    support -- and not merely on the decorative witness it also has.
    """
    mod = _load("bad_high_score_is_support")
    report = C.run(mod.Impl(FLAT), PROBES)
    by_req = {r.requirement: r for r in report.results}
    assert by_req["DEA-6"].verdict is C.Verdict.FAIL
    assert by_req["DEA-5"].verdict is C.Verdict.FAIL
    witness = by_req["DEA-6"].witness
    assert witness and witness["unentitled_attributions"], (
        "a FAIL without a witness is an opinion")
    first = witness["unentitled_attributions"][0]
    assert first["competitors_not_separated"], (
        "the witness must name WHICH competitors were not separated")


# ================================================== verdicts and scoring

def test_a_missing_capability_is_inconclusive_not_a_failure():
    """"We could not test this" is not "this was violated"."""
    class Opaque:
        NAME = "opaque"

    report = C.run(Opaque(), PROBES)
    verdicts = {r.verdict for r in report.results}
    assert C.Verdict.INCONCLUSIVE in verdicts
    assert not report.conformant, (
        "an untested requirement is not a satisfied one")


def test_inconclusive_blocks_conformance():
    class Opaque:
        NAME = "opaque"

    report = C.run(Opaque(), PROBES)
    counts = report.counts
    assert counts["INCONCLUSIVE"] > 0
    assert report.conformant is False


def test_the_runner_produces_no_score():
    """A percentage invites declaring requirements INAPPLICABLE to raise the
    denominator, and shrinking the hypothesis set to make DEA-6 easier. Both
    raise the number and lower what it means."""
    cert = C.run(good_minimal.HydraulicLoop(SCRIPT), PROBES).certificate()
    flat = json.dumps(cert).lower()
    for banned in ("score", "percent", "grade", "rating", "conformance_level"):
        assert banned not in flat, f"the certificate carries a {banned!r}"
    assert "counts" in cert and "results" in cert


def test_the_certificate_records_the_hypothesis_set_size():
    """Conformance is relative to the declared set. An implementation with two
    hypotheses conforms more easily than one with twenty, so the certificate
    must carry the number that makes two certificates incomparable."""
    cert = C.run(good_minimal.HydraulicLoop(SCRIPT), PROBES).certificate()
    assert cert["hypothesis_set_size"] == 4
    assert any("not comparable" in c or "conforms more easily" in c
               for c in cert["caveats"])


def test_the_certificate_says_what_it_does_not_mean():
    cert = C.run(good_minimal.HydraulicLoop(SCRIPT), PROBES).certificate()
    joined = " ".join(cert["caveats"]).lower()
    for required in ("not correctness", "not safety", "not certification"):
        assert required in joined, f"caveats omit {required!r}"


# ============================================ the profile document itself

def test_the_profile_does_not_standardise_the_naive_rule():
    """"Gate closure shall lower trust" would fail a correct implementation.

    On both current-stack platforms the gate weight collapses and trust RISES
    -- 0.9213 to 0.9300 on ArduPilot, 0.9856 to 0.9875 on PX4 -- because
    removing an inconsistent comparison removes a source of disagreement. A
    profile containing that rule would be met by implementations that
    special-case it.
    """
    text = open(PROFILE, encoding="utf-8").read()
    assert "deliberately NOT in this profile" in text
    assert "0.9213" in text and "0.9300" in text, \
        "the measurement that justifies the exclusion must be in the document"
    # STRUCTURAL, NOT TEXTUAL. The first version asserted the phrase "shall
    # lower trust" appeared nowhere -- and fired on section 2.1, which is the
    # paragraph EXPLAINING why the rule is excluded. That is the fourth guard
    # in this repository to fire on its own documentation
    # (tests/test_ci_env.py carries two more). The rule is about where the
    # phrase may appear, so check the section it may not appear in.
    requirements_section = text.split("## 4. Requirements", 1)[1].split(
        "## 5. Conformance verdicts", 1)[0]
    assert "trust" not in requirements_section.lower(), (
        "the requirements section mentions trust. DEA constrains what may be "
        "ASSERTED, not what any quantity must do -- a requirement about trust "
        "would fail a correct implementation for doing the arithmetic right.")
    rationale = text.split("### 2.1", 1)[1].split("## 3.", 1)[0]
    assert "shall lower trust" in rationale, (
        "the excluded rule must be named in the rationale, or a reader cannot "
        "tell it was considered and rejected rather than overlooked")


def test_the_profile_forbids_the_words_that_make_a_claim_uncheckable():
    text = open(PROFILE, encoding="utf-8").read()
    assert "confidence" in text and "forbids" in text
    assert "normalised hypothesis weight" in text, (
        "the profile must name what CSIA calls its own output, or the "
        "terminology rule has no worked example")


def test_every_requirement_in_the_profile_is_known_to_the_runner():
    """The document and the code must not drift into two different profiles."""
    text = open(PROFILE, encoding="utf-8").read()
    import re
    documented = set(re.findall(r"^### (DEA-\d+)", text, re.M))
    assert documented == set(C.REQUIREMENTS), (
        f"profile documents {sorted(documented)}; runner knows "
        f"{sorted(C.REQUIREMENTS)}")


def test_the_profile_records_its_open_questions():
    """A draft that hides its unresolved parts wastes its reviewers' time."""
    text = open(PROFILE, encoding="utf-8").read()
    assert "## 10. Open questions" in text
    assert text.count("unresolved") >= 3
