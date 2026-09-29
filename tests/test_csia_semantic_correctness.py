"""CSIA semantic correctness audit (research/csia_semantic_correctness/): guards.

Three kinds of check:

  * PACKAGE HONESTY. Exactly the declared deliverables exist; the CSVs are
    well formed; every finding has an allowed severity; exactly one gate
    decision is stated and no other gate token appears; headline numbers in
    the README are bound to the committed probe results.

  * CHARACTERIZATION (Feathers). The record-level reproductions are
    re-executed against frozen v2 and must still equal the committed results.
    These pin CURRENT frozen behaviour, including the defects. They are meant
    to FLIP when a successor semantics is authorized, and must never be
    edited to pass. They do not assert that the frozen behaviour is correct.

  * XSYS-001 COMPATIBILITY. The committed replay says every sealed slot was
    reproduced, and that no proposed correction changes a decision or an
    outcome.

The research probe is imported without writing bytecode into the package.
"""

import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D = REPO / "research" / "csia_semantic_correctness"
MD = ("README.md", "CURRENT_SEMANTICS_MAP.md", "MINIMAL_REPRODUCTIONS.md",
      "ATTRIBUTION_RELEVANCE_AUDIT.md", "MISSING_EVIDENCE_AUDIT.md",
      "EXCEPTION_SEMANTICS_AUDIT.md", "METAMORPHIC_TEST_PLAN.md",
      "SMALL_STATE_ENUMERATION.md", "XSYS_001_COMPATIBILITY.md",
      "MINIMAL_CORRECTION_DESIGN.md", "IMPLEMENTATION_GATE.md", "SOURCES.md")
CSV = ("SEMANTIC_PROPERTY_MATRIX.csv", "UNSUPPORTED_TRUTH_TABLE.csv",
       "LOCALIZATION_ATTRIBUTION_MATRIX.csv", "EXISTING_TEST_COVERAGE.csv",
       "FINDINGS.csv")
OTHER = ("semantic_probe.py", "semantic_probe_results.json")
GATE_TOKENS = ("SEMANTICS_CLEAN_NO_FIX_REQUIRED",
               "SEMANTICS_FIX_REQUIRED_BEFORE_ARCHITECTURE",
               "SEMANTICS_FIX_REQUIRED_BUT_NONBLOCKING",
               "SEMANTICS_REQUIRES_GOVERNANCE_REVIEW")


def _text(name):
    return (D / name).read_text(encoding="utf-8")


def _rows(name):
    with open(D / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _results():
    return json.loads(_text("semantic_probe_results.json"))


def _probe():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("semantic_probe", D / "semantic_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ package honesty
def test_exactly_the_declared_deliverables_exist():
    names = sorted(p.name for p in D.iterdir() if p.name != "__pycache__")
    assert names == sorted(MD + CSV + OTHER)
    assert [p.name for p in D.glob("*.py")] == ["semantic_probe.py"]


def test_the_probe_is_research_only():
    """Nothing in production CSIA imports it, and it writes only its own
    results file."""
    for p in (REPO / "csia").rglob("*.py"):
        assert "semantic_probe" not in p.read_text(encoding="utf-8"), p
    src = _text("semantic_probe.py")
    assert src.count("write_text(") == 1 and "OUT.write_text(" in src
    assert "write_bytes(" not in src and "open(" not in src


def test_findings_have_allowed_severities_and_classes():
    rows = _rows("FINDINGS.csv")
    assert [r["ID"] for r in rows] == [f"SC-{i:02d}" for i in range(1, len(rows) + 1)]
    for r in rows:
        assert r["SEVERITY"] in ("S0", "S1", "S2", "S3", "S4"), r["ID"]
        assert r["CLASS"] in ("DEFECT", "LIMITATION", "DOCUMENTATION_GAP", "PROFILE_DATA"), r["ID"]
        assert r["FINDING"].strip() and r["MECHANISM"].strip(), r["ID"]
        assert r["XSYS_001_EFFECT"] in ("NO EFFECT ON XSYS-001", "CHANGES INTERNAL TRACE ONLY") \
            or r["XSYS_001_EFFECT"].startswith("NO EFFECT ON XSYS-001 ("), r["ID"]
    # Severity is not inflated: nothing is S4 while nothing downstream actuates.
    assert not [r for r in rows if r["SEVERITY"] == "S4"]
    counts = {s: sum(r["SEVERITY"] == s for r in rows) for s in ("S0", "S1", "S2", "S3")}
    assert f"{len(rows)}: **{counts['S3']} × S3**, {counts['S2']} × S2, " \
           f"{counts['S1']} × S1, {counts['S0']} × S0" in _text("README.md")


def test_property_matrix_is_complete_and_its_tally_is_the_readme_tally():
    rows = _rows("SEMANTIC_PROPERTY_MATRIX.csv")
    assert [r["ID"] for r in rows] == [f"P{i}" for i in range(1, len(rows) + 1)]
    findings = {r["ID"] for r in _rows("FINDINGS.csv")}
    for r in rows:
        assert r["PASS_FAIL"] in ("PASS", "FAIL"), r["ID"]
        for k in ("PRECONDITION", "TRANSFORMATION", "EXPECTED_INVARIANT", "CURRENT_RESULT"):
            assert r[k].strip(), (r["ID"], k)
        assert set(re.findall(r"SC-\d{2}", r["FINDINGS"])) <= findings, r["ID"]
        if r["PASS_FAIL"] == "FAIL":
            assert r["FINDINGS"].strip(), r["ID"]
    failed = sum(r["PASS_FAIL"] == "FAIL" for r in rows)
    readme = _text("README.md")
    assert f"| semantic properties tested | **{len(rows)}** |" in readme
    assert f"| failed by frozen v2 | **{failed}**." in readme
    shadow_fail = sum(r["SHADOW_SUCCESSOR_RESULT"].startswith("FAIL") for r in rows)
    assert f"| failed by the shadow successor | {shadow_fail}." in readme


def test_other_csvs_are_well_formed():
    for name, key in (("UNSUPPORTED_TRUTH_TABLE.csv", "ID"),
                      ("LOCALIZATION_ATTRIBUTION_MATRIX.csv", "CLASSIFICATION"),
                      ("EXISTING_TEST_COVERAGE.csv", "COVERAGE")):
        rows = _rows(name)
        assert rows, name
        for r in rows:
            assert r[key].strip(), (name, r)
    for r in _rows("LOCALIZATION_ATTRIBUTION_MATRIX.csv"):
        assert r["CLASSIFICATION"] in ("INTENDED SEMANTIC DISTINCTION", "POTENTIAL DEFECT",
                                       "DOCUMENTATION GAP", "CONSISTENT"), r
    cov = {r["ID"] for r in _rows("EXISTING_TEST_COVERAGE.csv")}
    assert {f"P{i}" for i in range(1, 21)} <= cov


def test_exactly_one_gate_decision_and_no_other_token_anywhere():
    gate = _text("IMPLEMENTATION_GATE.md")
    lines = [ln for ln in gate.splitlines() if ln.startswith("**Decision:**")]
    assert len(lines) == 1
    chosen = [t for t in GATE_TOKENS if t in lines[0]]
    assert len(chosen) == 1
    for name in MD + CSV:
        others = [t for t in GATE_TOKENS if t != chosen[0] and t in _text(name)]
        assert not others, (name, others)
    assert f"**Decision:** {chosen[0]}" in _text("README.md")


def test_readme_headline_numbers_are_the_probe_results():
    j = _results()
    readme = _text("README.md")
    single = j["E"]["tick_census"]["single_candidate_ticks_by_verdict"]
    assert single["AMBIGUOUS"] == 0
    assert f"{single['UNIQUE']} of {single['UNIQUE']} ticks" in readme
    p9 = j["P"]["P9"]
    assert f"{p9['frozen_violations']} of {p9['unique_ticks']} UNIQUE ticks" in readme
    assert f"{j['E']['tick_census']['ticks']:,}" in readme
    x = j["X"]
    assert f"{x['slots']:,} / {x['slots']:,}" in readme
    ticks = j["SH"]["ALL_TICKS"]["by_fix"]
    for fx in ("C1", "C2", "C4", "C6"):
        assert sum(ticks[fx].values()) == 0, fx
    assert f"F2 changes {ticks['F2']['ticks_with_attribution_change']} attribution ticks" in readme
    assert f"C3 changes {ticks['C3']['ticks_with_localization_change']} localization ticks" in readme


def test_the_shadow_reproduces_frozen_v2_when_every_fix_is_off():
    ident = _results()["SH"]["IDENTITY_CHECK"]
    assert ident["ticks"] > 0 and ident["mismatches_with_no_fix"] == 0


# ------------------------------------------------------------ XSYS-001
def test_xsys_001_replay_is_exact_and_no_correction_changes_it():
    x = _results()["X"]
    assert x["stage1_sha256_matches_seal"] is True
    assert x["frozen_replay_identical_to_sealed"] == x["slots"] == 3872
    assert set(x["shadow_decision_diffs_by_fix"].values()) == {0}
    assert set(x["shadow_motor0_outcome_diffs_by_fix"].values()) == {0}
    assert x["predicate_raises"] == 0 and x["predicate_non_bool_returns"] == 0
    assert x["primary_record"]["PRIMARY_SUPPORTED"] == "YES"
    assert x["confirm_and_refute_all_slots"]["specific_confirmer"] == 0


# ------------------------------------------------------------ characterization
def test_record_level_reproductions_still_characterize_frozen_v2():
    """CHARACTERIZATION of CURRENT frozen behaviour, defects included. If this
    fails, frozen v2 or the probe changed: find out which before touching the
    committed results."""
    probe = _probe()
    got = json.loads(json.dumps(probe.section_R(), sort_keys=True, default=str))
    assert got == _results()["R"]


def test_the_central_reproductions_say_what_the_package_says():
    r = _results()["R"]
    # Part 1: one unrelated NOMINAL record turns AMBIGUOUS into UNIQUE.
    assert r["R1A"]["frozen"]["attr"]["verdict"] == "AMBIGUOUS"
    assert r["R1B"]["frozen"]["attr"]["verdict"] == "UNIQUE"
    assert r["R1B"]["frozen_trace"]["attr"]["discriminators"] == ["COMPUTE/cpu:compute.resource_headroom"]
    # Missing evidence becomes a different confident cause.
    assert r["R8E"]["frozen"]["loc"]["OUTPUT_STALE|nav_solution"]["supported"] == ["COMPUTE/processing_delay"]
    assert r["R8E"]["frozen"]["loc"]["OUTPUT_STALE|nav_solution"]["verdict"] == "SUPPORTED"
    # Container order decides.
    assert r["R6A"]["frozen"]["loc"]["OUTPUT_STALE|nav_solution"]["verdict"] == "UNSUPPORTED"
    assert r["R6B"]["frozen"]["loc"]["OUTPUT_STALE|nav_solution"]["verdict"] == "SUPPORTED"
    # A raising refuter creates SUPPORTED.
    rows = {x["Q"]: x["frozen"]["verdict"] for x in r["R9B"]["rows"]}
    assert rows["True"] == "UNSUPPORTED" and rows["raises KeyError"] == "SUPPORTED"
    # The shadow successor fixes each of them and keeps the control.
    assert r["R1B"]["shadow"]["attr"]["verdict"] == "AMBIGUOUS"
    assert r["R4"]["shadow"]["attr"]["verdict"] == "UNIQUE"
    assert r["R8E"]["shadow"]["loc"]["OUTPUT_STALE|nav_solution"]["verdict"] == "AMBIGUOUS"
    assert r["R6A"]["shadow"]["loc"] == r["R6B"]["shadow"]["loc"]


# ------------------------------------------------------------ language
def test_no_unqualified_novelty_or_priority_language():
    banned = ("no prior work exists", "we are the first", "is the first to", "first ever",
              "no one has", "never been studied", "has never been", "no prior art exists")
    for name in MD + CSV:
        low = _text(name).lower()
        assert not [b for b in banned if b in low], name
        stripped = re.sub(r"`[^`\n]*`", "", low)
        stripped = re.sub(r'"[^"\n]*"', "", stripped)
        assert not re.search(r"\bnovel\b", stripped), name
