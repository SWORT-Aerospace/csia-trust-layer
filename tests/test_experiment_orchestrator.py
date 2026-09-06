"""The campaign orchestrator: the denominator, the eight states, immutability.

WHAT THIS FILE IS ACTUALLY GUARDING
------------------------------------
Not "does the code run". Three properties, each of which has ruined somebody's
campaign:

  1. THE DENOMINATOR IS FIXED BEFORE THE TRIALS. A campaign that decides how
     many trials it ran after it ran them reports whatever survived.
  2. A TRIAL RECORD IS WRITTEN ONCE. A manifest that can be edited later is a
     note, not evidence, and the edit that gets made is never malicious -- it
     is "fix the scenario name", three weeks later.
  3. VALID DOES NOT MEAN ADMISSIBLE. The simulated backend produces records
     that adjudicate VALID and measure nothing. The report must say so loudly
     enough that nobody quotes them.

The nine invalid-trial demonstrations at the bottom are the P6 dry run: every
non-VALID outcome the vocabulary can produce, produced deliberately, so that
"we would have caught it" is a demonstration rather than a belief.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment import manifest as M            # noqa: E402
from tools.csia_experiment import orchestrator as O        # noqa: E402
from tools.csia_experiment.validity import (               # noqa: E402
    INVALID_STATES, PRECEDENCE, TrialState, adjudicate, from_contract_verdict,
    reconcile)

AP_PROFILE = os.path.join(ROOT, "profiles", "reference_quad_ardupilot.yaml")


def _clean_record(**over):
    rec = {"attempted": True, "prereg_deviations": [], "operator_abort": False,
           "rig_faults": [], "null_controls": [{"name": "n", "quiet": True}],
           "first_break": None, "stages": {}}
    rec.update(over)
    return rec


# =========================================================== the vocabulary

def test_the_eight_states_extend_the_contract_rather_than_forking_it():
    """The three contract verdicts must survive by name into the eight.

    If they ever stop matching, the orchestrator is speaking a different
    language from csia/simulation/contract.py while using the same words --
    which is worse than an outright incompatibility, because it type-checks.
    """
    from csia.simulation.contract import TrialVerdict
    for verdict in TrialVerdict:
        assert from_contract_verdict(verdict.value).value == verdict.value
    assert len(TrialState) == 8


def test_every_state_except_valid_and_not_attempted_is_counted_as_invalid():
    """The arithmetic depends on this partition being complete.

    A state added to TrialState and forgotten in INVALID_STATES makes
    reconcile() raise rather than miscount -- but only if this test notices
    the omission first, with a message that says which one.
    """
    partitioned = set(INVALID_STATES) | {TrialState.VALID,
                                         TrialState.NOT_ATTEMPTED}
    missing = sorted(s.value for s in set(TrialState) - partitioned)
    assert not missing, (
        f"{missing} belong to no bucket. planned == valid + invalid + "
        f"not_attempted silently stops holding.")


def test_a_silent_record_is_undecidable_and_not_false():
    """"We cannot tell whether the rig faulted" is not "the rig did not fault".

    A predicate that defaulted None to False would let a record with no rig
    instrumentation at all adjudicate VALID while claiming the rig was fine.
    """
    adj = adjudicate({"attempted": True})
    undecided = {u["state"] for u in adj.undecidable}
    assert TrialState.HARDWARE_FAULT.value in undecided
    assert TrialState.PREREG_VIOLATION.value in undecided
    assert adj.state is TrialState.VALID, (
        "with nothing ruled in, VALID is the residual -- but the undecidable "
        "list must carry what was never established")
    assert adj.undecidable, "a bare record cannot be fully adjudicated"


def test_every_predicate_declares_what_the_record_must_carry():
    for pred in PRECEDENCE:
        assert pred.describe and pred.fn
        result = pred.evaluate({})
        if pred.requires:
            assert result["holds"] is None and result["missing"], (
                f"{pred.state.value} claims to require {pred.requires} but "
                f"adjudicated an empty record anyway")


def test_the_arithmetic_refuses_to_be_open():
    records = [_clean_record(), {"attempted": False},
               _clean_record(operator_abort=True)]
    summary = reconcile(records)
    assert summary["planned"] == 3
    assert (summary["valid"] + summary["invalid"]
            + summary["not_attempted"] == summary["planned"])
    assert summary["attempted"] == 2


def test_both_denominators_are_reported_so_a_rate_can_be_checked():
    """A quoted "95% valid" is meaningless without which denominator it used."""
    summary = reconcile([_clean_record(), {"attempted": False}])
    assert summary["planned"] == 2 and summary["attempted"] == 1
    assert "valid / attempted" in summary["scorable_fraction_note"]


# ============================================================ the denominator

def test_a_campaign_without_a_plan_has_no_denominator(tmp_path):
    with pytest.raises(O.OrchestratorError, match="no denominator"):
        O.report(str(tmp_path))


def test_a_trial_outside_the_plan_is_refused(tmp_path):
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 2)
    with pytest.raises(O.OrchestratorError, match="not in the plan"):
        O.run_trial(str(tmp_path), "C-099", "simulated")


def test_replanning_a_campaign_is_refused(tmp_path):
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 2)
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 2)      # identical: ok
    with pytest.raises(O.OrchestratorError, match="different plan"):
        O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 20)


def test_an_unrun_planned_trial_counts_as_not_attempted(tmp_path):
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 4)
    O.run_trial(str(tmp_path), "C-001", "simulated")
    summary = O.report(str(tmp_path))
    assert summary["planned"] == 4
    assert summary["not_attempted"] == 3, (
        "three planned trials produced no manifest and must appear in the "
        "denominator, not vanish")


def test_a_manifest_for_an_unplanned_trial_is_caught_at_report_time(tmp_path):
    """Belt and braces: the plan check can be bypassed by writing a file."""
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 1)
    M.TrialManifest(trial_id="C-777", campaign="C", scenario="x",
                    record=_clean_record()).write(str(tmp_path))
    with pytest.raises(O.OrchestratorError, match="not in the plan"):
        O.report(str(tmp_path))


# ============================================================== immutability

def test_a_manifest_is_written_once(tmp_path):
    man = M.TrialManifest(trial_id="T1", campaign="C", scenario="s",
                          record=_clean_record())
    man.write(str(tmp_path))
    man.write(str(tmp_path))                       # identical content: no-op
    man.notes.append("edited afterwards")
    with pytest.raises(M.ManifestError, match="written once"):
        man.write(str(tmp_path))


def test_there_is_no_force_parameter_anywhere():
    """A force flag would make the immutability decorative.

    Checked against the PARSED CODE, not the text. The first version grepped
    for the word and failed on the docstring sentence "No force flag exists."
    -- a guard firing on its own documentation, which this repository has now
    hit three times (tests/test_ci_env.py carries two of them).
    """
    import ast
    for rel in ("tools/csia_experiment/manifest.py",
                "tools/csia_experiment/orchestrator.py"):
        tree = ast.parse(open(os.path.join(ROOT, rel), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [a.arg for a in node.args.args + node.args.kwonlyargs]
                assert not any("force" in n.lower() for n in names), (
                    f"{rel}:{node.name} takes a force parameter")
            if isinstance(node, ast.Call) and isinstance(node.func,
                                                         ast.Attribute):
                if node.func.attr == "add_argument":
                    for arg in node.args:
                        if (isinstance(arg, ast.Constant)
                                and "force" in str(arg.value).lower()):
                            raise AssertionError(f"{rel} exposes {arg.value}")


def test_an_edited_manifest_is_detected_on_load(tmp_path):
    man = M.TrialManifest(trial_id="T1", campaign="C", scenario="s",
                          record=_clean_record())
    path = man.write(str(tmp_path))
    body = json.loads(open(path, encoding="utf-8").read())
    body["scenario"] = "something_else"
    open(path, "w", encoding="utf-8").write(json.dumps(body))
    with pytest.raises(M.ManifestError, match="edited after it was written"):
        M.load(path)


def test_the_manifest_pins_the_conditions_that_decide_what_it_means(tmp_path):
    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    prov = M.provenance(AP_PROFILE, None, ArduPilotAdapter())
    assert prov["head"] and len(prov["head"]) == 40
    assert prov["profile_sha256"]
    assert prov["adapter"]["platform"] == "ardupilot"
    assert "frozen_core_tag_resolves" in prov, (
        "the freeze tags are LOCAL ONLY in this repository -- a manifest that "
        "omitted whether the tag resolves would let a trial claim the frozen "
        "core with nothing having checked")


# ================================================ VALID is not ADMISSIBLE

def test_the_simulated_backend_marks_itself_inadmissible():
    rec = O.backend_simulated("T1", "s")
    assert adjudicate(rec).state is TrialState.VALID
    assert rec["admissible_as_evidence"] is False
    assert rec["evidence_tier"] == "E0"


def test_the_report_warns_when_valid_trials_measured_nothing(tmp_path):
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 1)
    O.run_trial(str(tmp_path), "C-001", "simulated")
    summary = O.report(str(tmp_path))
    assert summary["valid"] == 1
    assert "admissibility_warning" in summary
    assert "measured nothing" in summary["admissibility_warning"]


def test_the_hardware_backend_refuses_rather_than_stubbing():
    """A stub returning plausible readings is the most dangerous thing this
    module could contain: E2 numbers from nothing, indistinguishable from
    measurements everywhere downstream."""
    with pytest.raises(O.OrchestratorError) as exc:
        O.backend_hardware("T1", "s")
    text = str(exc.value)
    assert "not implemented" in text
    assert "USER_ACTION_REQUIRED.md" in text
    assert "NOT_STARTED" in text


# ======================================== P6: the nine invalid demonstrations
#
# Every non-VALID outcome, produced deliberately. "We would have caught it" is
# a belief; this is a demonstration.

DEMONSTRATIONS = [
    ("NOT_ATTEMPTED", {"attempted": False}, TrialState.NOT_ATTEMPTED),
    ("PREREG_VIOLATION",
     _clean_record(prereg_deviations=["ran 19 of the 20 preregistered trials"]),
     TrialState.PREREG_VIOLATION),
    ("ABORTED_BY_OPERATOR", _clean_record(operator_abort=True),
     TrialState.ABORTED_BY_OPERATOR),
    ("HARDWARE_FAULT",
     _clean_record(rig_faults=["injector relay stuck closed"]),
     TrialState.HARDWARE_FAULT),
    ("INSTRUMENT_DEAD",
     _clean_record(null_controls=[{"name": "no_injection", "quiet": False,
                                   "measured": 38.89, "tolerance": 0.5}]),
     TrialState.INSTRUMENT_DEAD),
    ("INVALID_SCENARIO", _clean_record(first_break="SENSOR_OUTPUT_CHANGED"),
     TrialState.INVALID_SCENARIO),
    ("TIMING_INSUFFICIENT",
     _clean_record(timing_budget={"p99_tick_us": 40000.0},
                   timing_observed={"p99_tick_us": 91000.0}),
     TrialState.TIMING_INSUFFICIENT),
]


@pytest.mark.parametrize("name,record,expected", DEMONSTRATIONS,
                         ids=[d[0] for d in DEMONSTRATIONS])
def test_each_invalid_state_can_actually_be_produced(name, record, expected):
    adj = adjudicate(record)
    assert adj.state is expected, (
        f"{name}: adjudicated {adj.state.value}. A state the vocabulary "
        f"defines but no record can reach is decoration.")
    assert not adj.state.scorable or expected is TrialState.VALID


def test_demonstration_eight_a_tampered_manifest(tmp_path):
    """The eighth: not a trial state, a trial RECORD failure.

    The realistic tamper, and the one worth demonstrating: take a trial whose
    null control MOVED -- INSTRUMENT_DEAD, unusable -- and quietly edit it into
    a VALID one. That is the edit somebody makes at 2am with one arm left to
    salvage, and it is exactly what the content hash exists to refuse.

    The first version of this test edited a field to the value it already had
    and asserted a raise. It passed nothing and would have kept passing with
    the hash check deleted.
    """
    dead = _clean_record(null_controls=[{"name": "no_injection",
                                         "quiet": False, "measured": 38.89,
                                         "tolerance": 0.5}])
    man = M.TrialManifest(trial_id="T1", campaign="C", scenario="s",
                          record=dead)
    path = man.write(str(tmp_path))
    body = json.loads(open(path, encoding="utf-8").read())
    assert body["adjudication"]["state"] == "INSTRUMENT_DEAD"

    body["record"]["null_controls"][0]["quiet"] = True
    body["record"]["null_controls"][0]["measured"] = 0.01
    body["adjudication"]["state"] = "VALID"
    body["adjudication"]["scorable"] = True
    open(path, "w", encoding="utf-8").write(json.dumps(body, indent=2,
                                                       sort_keys=True) + "\n")
    with pytest.raises(M.ManifestError, match="edited after it was written"):
        M.load(path)


def test_demonstration_nine_a_campaign_that_grew_an_extra_arm(tmp_path):
    """The ninth: the failure that has no state because it is a CAMPAIGN
    failure. Two ways in, both closed."""
    O.plan_campaign(str(tmp_path), "C", "gps_fix_loss", 2)
    with pytest.raises(O.OrchestratorError, match="not in the plan"):
        O.run_trial(str(tmp_path), "C-003", "simulated")
    M.TrialManifest(trial_id="C-003", campaign="C", scenario="gps_fix_loss",
                    record=_clean_record()).write(str(tmp_path))
    with pytest.raises(O.OrchestratorError, match="not in the plan"):
        O.report(str(tmp_path))


def test_the_dry_run_covers_every_invalid_state_in_the_vocabulary():
    """A negative control for the list above: no state may go undemonstrated.

    Without this, adding a ninth state and forgetting to demonstrate it leaves
    the suite green and the claim "every invalid outcome is demonstrated"
    false.
    """
    demonstrated = {expected for _n, _r, expected in DEMONSTRATIONS}
    undemonstrated = sorted(
        s.value for s in set(INVALID_STATES) | {TrialState.NOT_ATTEMPTED}
        if s not in demonstrated)
    assert not undemonstrated, (
        f"these states are defined and never demonstrated: {undemonstrated}")


# =============================================== the whole loop, end to end

def test_a_full_campaign_reconciles(tmp_path):
    O.plan_campaign(str(tmp_path), "DRY", "gps_fix_loss", 9,
                    prereg_path=None)
    states = []
    for i, (_name, record, expected) in enumerate(DEMONSTRATIONS, start=1):
        if expected is TrialState.NOT_ATTEMPTED:
            continue                    # by definition, no manifest is written
        O.run_trial(str(tmp_path), f"DRY-{i:03d}", "simulated",
                    record_override=record)
        states.append(expected)

    summary = O.report(str(tmp_path))
    assert summary["planned"] == 9
    assert summary["valid"] == 0, (
        "every demonstration is an invalid outcome; a VALID here means a "
        "predicate stopped firing")
    assert summary["invalid"] == len(states)
    assert summary["not_attempted"] == 9 - len(states)
    assert (summary["valid"] + summary["invalid"]
            + summary["not_attempted"] == 9)
