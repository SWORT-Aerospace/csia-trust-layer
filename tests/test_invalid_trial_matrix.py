"""P6: all twelve invalid-trial causes, produced deliberately and detected.

The number this file exists to report is **x of y correctly classified**, with
NO MANUAL ADJUDICATION for any of the twelve. A cause that needs a human to
look at it is not a check.

Ten causes are detected from the trial record. Two are caught EARLIER than
adjudication and are demonstrated against the components that catch them:

  * `ARTIFACT_TAMPER` -- the manifest content hash, at load;
  * `PROFILE_DEPLOYMENT_CONFLICT` -- `csia-edge validate`, exit 3.

Those two are not weaker for being caught early. They are stronger: a tampered
manifest never reaches the adjudicator at all.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.csia_experiment import manifest as M                 # noqa: E402
from tools.csia_experiment.invalid_trial_matrix import (        # noqa: E402
    CAUSES, classify)
from tools.csia_experiment.validity import TrialState           # noqa: E402

AP_PROFILE = os.path.join(ROOT, "profiles", "reference_quad_ardupilot.yaml")


def _clean(**over):
    """A record with nothing wrong with it."""
    rec = {
        "attempted": True, "prereg_deviations": [], "operator_abort": False,
        "rig_faults": [], "null_controls": [{"name": "n", "quiet": True}],
        "first_break": None, "stages": {},
        "measured_injection": {"param": "SIM_GPS1_ENABLE", "value": 0,
                               "readback": 0, "confirmed": True},
        "downstream_confirmation_latency_s": 0.04,
        "downstream_confirmation_bound_s": 1.0,
        "required_streams": ["gnss.position", "imu0.accel"],
        "streams_seen": ["gnss.position", "imu0.accel", "baro.altitude"],
        "time_reanchors": 0, "timebase_monotonic": True,
        "required_fields": ["measured_injection", "stages"],
        "expected_autopilot_commit": "01a504b47225",
        "ardupilot_commit": "01a504b472259602e13df4cf07df7c0cdbb35993",
        "expected_frozen_core_tag": "csia-v1.0-research-final",
        "frozen_core_tag": "csia-v1.0-research-final",
    }
    rec.update(over)
    return rec


#: One deliberately-broken record per record-detectable cause.
BROKEN = {
    "NO_OP_INJECTION": _clean(
        measured_injection={"param": "SIM_GPS1_ENABLE", "value": 0,
                            "readback": 1, "confirmed": False}),
    "MISSING_DOWNSTREAM_CONFIRMATION": _clean(
        first_break="SENSOR_OUTPUT_CHANGED"),
    "LATE_DOWNSTREAM_CONFIRMATION": _clean(
        downstream_confirmation_latency_s=9.5),
    "MISSING_REQUIRED_STREAM": _clean(
        streams_seen=["imu0.accel"]),
    "TIMEBASE_CORRUPTION": _clean(time_reanchors=3),
    "INJECTOR_READBACK_MISMATCH": _clean(
        measured_injection={"param": "SIM_GPS1_ENABLE", "value": 0,
                            "readback": 1.401298464324817e-44,
                            "confirmed": True}),
    "INCOMPLETE_ARTIFACT": _clean(
        required_fields=["measured_injection", "a_field_that_is_absent"]),
    "WRONG_AUTOPILOT_VERSION": _clean(
        ardupilot_commit="e21b732a07ce2b632ea99b098ee6ab7ece0971ea"),
    "WRONG_CORE_SHA": _clean(frozen_core_tag="csia-v2-phasec-frozen"),
    "ABORTED_TRIAL": _clean(operator_abort=True),
}

#: Caught before adjudication, so demonstrated against their own component.
EARLY = ("ARTIFACT_TAMPER", "PROFILE_DEPLOYMENT_CONFLICT")


def test_the_matrix_covers_twelve_causes():
    assert len(CAUSES) == 12, f"the matrix defines {len(CAUSES)} causes"
    assert set(BROKEN) | set(EARLY) == {c.id for c in CAUSES}, (
        "every cause must have either a broken record or an early-detection "
        "demonstration; a cause with neither is undemonstrated")


@pytest.mark.parametrize("cause_id", sorted(BROKEN))
def test_each_cause_is_detected_from_the_record(cause_id):
    """No manual adjudication: the detector fires on the record alone."""
    result = classify(BROKEN[cause_id])
    assert cause_id in result["causes_present"], (
        f"{cause_id} was not detected. Present: {result['causes_present']}, "
        f"undecidable: {result['undecidable']}")


@pytest.mark.parametrize("cause_id", sorted(BROKEN))
def test_each_cause_lands_in_the_right_state(cause_id):
    expected = next(c.expected_state for c in CAUSES if c.id == cause_id)
    got = classify(BROKEN[cause_id])["state"]
    assert got is expected, (
        f"{cause_id} adjudicated {got.value}, expected {expected.value}")


def test_a_clean_record_triggers_no_cause_and_is_valid():
    """The negative control. Without it, a detector that fires on everything
    would pass every test above."""
    result = classify(_clean())
    assert not result["causes_present"], (
        f"a clean record triggered {result['causes_present']}")
    assert result["state"] is TrialState.VALID


def test_artifact_tamper_is_caught_at_load_before_adjudication(tmp_path):
    """Caught EARLIER than the adjudicator, which is stronger, not weaker."""
    dead = _clean(null_controls=[{"name": "no_injection", "quiet": False,
                                  "measured": 38.89, "tolerance": 0.5}])
    man = M.TrialManifest(trial_id="T1", campaign="C", scenario="s",
                          record=dead)
    path = man.write(str(tmp_path))
    body = json.loads(open(path, encoding="utf-8").read())
    assert body["adjudication"]["state"] == "INSTRUMENT_DEAD"

    body["record"]["null_controls"][0]["quiet"] = True
    body["adjudication"]["state"] = "VALID"
    open(path, "w", encoding="utf-8").write(json.dumps(body, indent=2,
                                                       sort_keys=True) + "\n")
    with pytest.raises(M.ManifestError, match="edited after it was written"):
        M.load(path)


def test_profile_deployment_conflict_is_caught_by_validate(tmp_path, capsys):
    import yaml

    from csia.deploy import edge

    conflicting = {"vehicle": {"id": "X"},
                   "autopilot": {"stack": "px4"},
                   "csia": {"mode": "SHADOW", "tick_hz": 25.0,
                            "profile": "FIELD_DERIVED_NOISE"}}
    path = tmp_path / "deployment.yaml"
    path.write_text(yaml.safe_dump(conflicting), encoding="utf-8")

    code = edge.main(["validate", "--profile", AP_PROFILE,
                      "--deployment", str(path), "--json"])
    assert code == 3, "a profile/deployment conflict must exit 3"
    out = json.loads(capsys.readouterr().out)
    assert any("autopilot" in c for c in out["config_conflicts"])


def test_every_cause_is_undecidable_when_the_record_is_silent():
    """"We cannot tell" is not "it did not happen".

    A bare record must not adjudicate every cause absent -- that would let a
    trial with no instrumentation at all read as clean.
    """
    result = classify({"attempted": True})
    record_detectable = {c.id for c in CAUSES
                         if c.expected_state is not None
                         and c.id != "ABORTED_TRIAL"}
    decided = set(result["causes_present"])
    undecidable = set(result["undecidable"])
    unaccounted = sorted(record_detectable - decided - undecidable)
    assert not unaccounted, (
        f"{unaccounted} silently read as absent on a bare record")


def test_the_matrix_reports_its_own_score():
    """The number the program asked for: x of y, no manual adjudication."""
    total = len(CAUSES)
    correct = 0
    for cause in CAUSES:
        if cause.id in EARLY:
            correct += 1        # demonstrated by its own test above
            continue
        result = classify(BROKEN[cause.id])
        if (cause.id in result["causes_present"]
                and result["state"] is cause.expected_state):
            correct += 1
    assert correct == total, f"{correct}/{total} causes correctly classified"
    print(f"\nINVALID-TRIAL MATRIX: {correct}/{total} correctly classified, "
          f"no manual adjudication")
