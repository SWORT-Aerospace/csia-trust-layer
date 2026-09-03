"""Regression for the systems paper's new evidence (brief B1-B4).

Three things are asserted and none of them is "the number is still the same":

  1. THE INDEPENDENT CHECKER IS INDEPENDENT. Run in a fresh interpreter, it
     must import no `csia` module and neither `support` nor `decompose`. This
     is the whole basis for the 378,000/378,000 agreement meaning anything --
     an agreement produced by reading production's answer proves nothing.

  2. THE COMMITTED VERDICTS ARE WHAT THE CHECKER PRODUCES. Re-run it against
     the committed active-set export and compare. A committed artifact that
     the code no longer produces is worse than no artifact.

  3. THE CLAIM REGISTER IS COMPLETE AND HONEST. Every row has every field,
     every artifact path that is not explicitly NONE exists, and no row
     claims a status its artifact cannot support.

Mechanism B's arms are re-derived rather than re-run: the full pipeline takes
minutes per arm, so the test checks internal consistency of the committed
result plus the one property that could silently rot -- the EW inversion
round-tripping.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SP = os.path.join(ROOT, "research", "systems-paper")
RESULTS = os.path.join(SP, "results")


def _checker():
    """Load the research module BY PATH rather than by name.

    `tests/test_ci_env.py` scans this directory's imports and requires every
    top-level module name to be provided by the CI dependency set --
    correctly, because that guard exists to stop an undeclared dependency
    reaching CI. `import independent_checker` looks exactly like one. Loading
    by path keeps the guard's semantics intact instead of allowlisting a
    local module into it.
    """
    spec = importlib.util.spec_from_file_location(
        "_sp_independent_checker", os.path.join(SP, "independent_checker.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated; run the scripts in {SP}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ============================================================ independence
def test_the_checker_imports_no_production_module():
    """THE PROPERTY THE WHOLE COMPARISON RESTS ON."""
    code = (
        "import sys, os\n"
        f"sys.path.insert(0, {SP!r})\n"
        "import independent_checker as C\n"
        "doc = C.run()\n"
        "bad = sorted(m for m in sys.modules "
        "if m.split('.')[0] == 'csia' or m in ('support', 'decompose'))\n"
        "print(repr(bad))\n")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]", (
        "the independent checker imported a production module: "
        f"{out.stdout.strip()}. It is then not independent and the agreement "
        f"result means nothing.")


def test_the_checker_reads_only_the_signature_table_and_the_active_sets():
    C = _checker()
    assert os.path.basename(C.SIGNATURES) == \
        "diagnostic_signature_matrix.yaml"
    assert os.path.basename(C.ACTIVE_SETS) == "active_sets.json"
    # The active-set export must carry no support analysis at all. Checked
    # over KEYS, not over the serialised blob: a substring scan matched the
    # scenario name DUAL_IMU_AMBIGUITY and would have had to be weakened
    # rather than fixed.
    data = _load("active_sets.json")
    forbidden = {"leader", "posterior", "support_state", "identifiable",
                 "ambiguity", "discriminating", "discriminating_terms"}

    def keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from keys(v)

    leaked = sorted(forbidden & {k.lower() for k in keys(data)})
    assert not leaked, (
        f"the active-set export carries {leaked}; the checker would then be "
        f"reading part of production's answer")


# =========================================================== reproducibility
def test_the_committed_verdicts_are_what_the_checker_produces():
    C = _checker()
    committed = _load("checker_verdicts.json")
    fresh = C.run()
    assert fresh["scenarios"] == committed["scenarios"], (
        "checker_verdicts.json no longer matches what independent_checker.py "
        "produces from the committed active sets. Regenerate it or fix the "
        "checker; do not edit the artifact.")


def test_the_agreement_artifact_reports_no_real_disagreement():
    doc = _load("checker_agreement.json")
    assert doc["verdict"] == "CHECKER_AGREES_WITH_PRODUCTION"
    assert doc["totals"]["real_disagreements"] == 0
    assert doc["blocks_submission"] is False
    # Agreement is only meaningful if a meaningful number were compared.
    assert doc["totals"]["agree"] > 100_000


def test_the_known_disagreement_class_is_counted_separately_not_hidden():
    """c == 0.5 makes the structural and numeric definitions differ. Folding
    those into the agreement count would hide the only place the two
    definitions actually disagree."""
    doc = _load("checker_agreement.json")
    assert "degenerate_only" in doc["totals"]
    assert "known_disagreement_class" in doc
    for row in doc["scenarios"].values():
        assert row["agree"] + row["real_disagreements"] \
            + row["degenerate_only"] == row["pairs_compared"]


# ================================================================ mechanism A
def test_only_the_target_pair_ever_collapses_in_this_catalogue():
    doc = _load("checker_verdicts.json")
    for label, scen in doc["scenarios"].items():
        for g in scen["groups"]:
            for pair in g["collapsed_pairs"]:
                assert pair == "gps_fault|nominal", (
                    f"{label}: an unexpected pair collapsed: {pair}")


def test_the_startup_window_is_present_in_every_scenario_including_clean():
    """SC-05. If this stopped being true of the clean arm, the metric would
    have become fault-triggered and the reading would change."""
    doc = _load("checker_verdicts.json")
    for label, scen in doc["scenarios"].items():
        first = scen["groups"][0]
        assert first["first_tick"] == 0
        assert first["target_distinguishable"] is False, label
        assert first["ticks"] == 76, (label, first["ticks"])


def test_only_the_fix_loss_scenario_has_a_second_blind_window():
    doc = _load("checker_verdicts.json")
    for label, scen in doc["scenarios"].items():
        blind = scen["ticks_target_pair_not_distinguishable"]
        if label == "GNSS_FIX_LOSS":
            assert blind == 276, blind
        else:
            assert blind == 76, (label, blind)


# ================================================================ mechanism B
def test_mechanism_b_reports_the_clean_arm_crossings_as_false_alarms():
    doc = _load("mechanism_b.json")
    clean = doc["arms"]["clean"]
    assert clean["ground_truth_faulted"] is False
    assert clean["crossings_are_false_alarms"] is True
    # The trust path and the CUSUM must NOT fire on an unfaulted arm.
    assert clean["crossing"]["trust_t_s"] is None
    assert clean["crossing"]["cusum_t_s"] is None


def test_mechanism_b_ew_inversion_round_trips():
    doc = _load("mechanism_b.json")
    for name, arm in doc["arms"].items():
        assert arm["ew_inversion_max_error"] <= 1e-9, name


def test_mechanism_b_smoothing_cuts_false_crossings():
    """SC-08. The direction is the claim; the exact counts are the artifact."""
    doc = _load("mechanism_b.json")
    for name, arm in doc["arms"].items():
        f = arm["false_alarms_in_clean_window"]
        assert f["smoothed_lambda_over_threshold"] \
            < f["instantaneous_lambda_over_threshold"], name
        assert f["trust_below_threshold"] == 0, name
        assert f["cusum_alarming"] == 0, name


def test_mechanism_b_claims_no_cusum_novelty():
    doc = _load("mechanism_b.json")
    assert "NONE CLAIMED" in doc["novelty"]
    assert "Page" in doc["novelty"]


# ============================================================== claim register
def test_every_claim_row_is_complete():
    path = os.path.join(SP, "CLAIMS.csv")
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    assert rows
    required = {"claim_id", "claim_text", "claim_type", "definition",
                "artifact", "commit", "source_code_location", "baseline",
                "counter_evidence", "alternative_explanation", "status"}
    assert required <= set(rows[0])
    for r in rows:
        for field in required:
            assert (r[field] or "").strip(), f"{r['claim_id']}: {field} empty"


def test_every_claim_status_is_from_the_declared_vocabulary():
    allowed = {"PROVED", "EMPIRICAL_ONLY", "PROVISIONAL", "KNOWN_SUBSUMED",
               "REFUTED", "WITHDRAWN"}
    path = os.path.join(SP, "CLAIMS.csv")
    for r in csv.DictReader(open(path, encoding="utf-8")):
        assert r["status"] in allowed, (r["claim_id"], r["status"])


def test_every_named_claim_artifact_exists():
    path = os.path.join(SP, "CLAIMS.csv")
    for r in csv.DictReader(open(path, encoding="utf-8")):
        art = r["artifact"].strip()
        if art in ("n/a", "") or art.startswith("NONE"):
            continue
        first = art.split(";")[0].split(" ")[0].strip()
        assert os.path.exists(os.path.join(ROOT, first)), \
            f"{r['claim_id']} names a missing artifact: {first}"


#: A PROVISIONAL row must say IN WORDS why it is not established. The
#: vocabulary is small on purpose: "blocked" and "inapplicable" and "not run"
#: are different reasons and all three are legitimate, but silence is not.
_NOT_ESTABLISHED_MARKERS = ("BLOCKED", "NOT DONE", "NOT RUN",
                            "0 trials run", "INAPPLICABLE", "Not faked",
                            "not faked")


def test_every_provisional_claim_says_why_it_is_not_established():
    """SC-22 (public logs) was NOT run; SC-23 (Mechanism A on the current
    stack) was NOT done; SC-25 is INAPPLICABLE with zero trials. If any of
    them ever reads EMPIRICAL_ONLY or PROVED, something has been written up
    that did not happen.

    (The first version of this test looked for the single word "BLOCKED",
    which broke the moment a claim was correctly reworded to INAPPLICABLE --
    a different and equally honest reason.)
    """
    path = os.path.join(SP, "CLAIMS.csv")
    rows = {r["claim_id"]: r for r in csv.DictReader(open(path,
                                                          encoding="utf-8"))}
    provisional = [r for r in rows.values() if r["status"] == "PROVISIONAL"]
    assert provisional, "no PROVISIONAL rows; the test would pass vacuously"
    for r in provisional:
        why = r["alternative_explanation"]
        assert any(m in why for m in _NOT_ESTABLISHED_MARKERS), (
            f"{r['claim_id']} is PROVISIONAL but does not say why it is not "
            f"established: {why!r}")
    # The three that must never quietly become established.
    for cid in ("SC-22", "SC-23", "SC-25"):
        assert rows[cid]["status"] == "PROVISIONAL", cid


def test_the_current_stack_replication_is_recorded_as_replicated():
    """The correction that mattered: Mechanism B IS replicated on ArduPilot
    4.8, by a preregistered campaign this session initially failed to find."""
    path = os.path.join(SP, "CLAIMS.csv")
    rows = {r["claim_id"]: r for r in csv.DictReader(open(path,
                                                          encoding="utf-8"))}
    assert rows["SC-24"]["status"] == "EMPIRICAL_ONLY"
    assert "ArduPilot 4.8" in rows["SC-24"]["claim_text"]
    art = os.path.join(ROOT, rows["SC-24"]["artifact"])
    assert os.path.exists(art), art
    doc = json.load(open(art, encoding="utf-8"))
    assert doc["platforms"]["ardupilot"]["verdict"] == "REPLICATED"
    assert doc["platforms"]["px4"]["verdict"] == "INAPPLICABLE"


# ============================================== the word that must not be used
def test_the_manuscript_never_calls_the_posterior_confidence():
    """A posterior with no discriminating support is not a confidence, and
    calling it one invites a reader to do arithmetic that is not licensed."""
    tex = open(os.path.join(ROOT, "papers", "csia_systems", "main.tex"),
               encoding="utf-8").read().lower()
    for phrase in ("posterior confidence", "confidence posterior",
                   "confidence of the posterior",
                   "posterior as confidence"):
        assert phrase not in tex, phrase
