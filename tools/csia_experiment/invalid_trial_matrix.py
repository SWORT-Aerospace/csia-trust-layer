"""The twelve invalid-trial causes, and the detector for each.

WHY A MATRIX AND NOT MORE STATES
---------------------------------
`validity.py` defines EIGHT states. This file defines TWELVE CAUSES that map
onto them. The distinction is deliberate: a state is what a trial IS, a cause
is what went wrong, and adding a state per cause would grow an eight-word
vocabulary into a twenty-word one that nobody could apply consistently.

    cause                            -> state
    ---------------------------------------------------------------
    no-op injection                  -> INVALID_SCENARIO
    missing downstream confirmation  -> INVALID_SCENARIO
    late downstream confirmation     -> INVALID_SCENARIO
    missing required stream          -> INVALID_SCENARIO
    timebase corruption              -> INVALID_SCENARIO
    injector readback mismatch       -> INVALID_SCENARIO
    incomplete artifact              -> INVALID_SCENARIO
    artifact tamper                  -> (rejected at load, before adjudication)
    profile/deployment conflict      -> (rejected at validate, exit 3)
    wrong autopilot version          -> PREREG_VIOLATION
    wrong core SHA                   -> PREREG_VIOLATION
    aborted trial                    -> ABORTED_BY_OPERATOR

EVERY CAUSE MUST BE DETECTED WITHOUT MANUAL ADJUDICATION. A cause that needs a
human to look at it is not a check; it is a hope. `tests/test_invalid_trial_
matrix.py` drives all twelve and reports x/y.

THE THREE PREREGISTRATION-BOUND CAUSES
--------------------------------------
`wrong autopilot version`, `wrong core SHA` and `late downstream confirmation`
are only detectable against a DECLARED EXPECTATION. A trial that does not
declare what build it expected cannot be found to have run the wrong one, so
these predicates return None -- undecidable -- rather than False when the
expectation is absent. That is the same rule the eight states already follow:
"we cannot tell" is not "it did not happen".
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from tools.csia_experiment.validity import TrialState, adjudicate  # noqa: E402


@dataclass
class Cause:
    """One way a trial goes wrong, and how it is caught."""

    id: str
    describe: str
    #: record -> True (this cause is present) / False / None (undecidable)
    detect: Callable
    #: the TrialState a record with this cause must adjudicate to, or None
    #: when the cause is caught before adjudication (load or validate time).
    expected_state: Optional[TrialState]
    caught_by: str


# --------------------------------------------------------------- detectors

def _no_op_injection(rec):
    """A parameter was written and nothing downstream moved.

    THE ORIGINAL SIN this whole contract exists for: COMMAND ISSUED is not
    FAULT INJECTED. Scoring this as a detector miss manufactures evidence that
    a detector failed to see a fault that never existed.
    """
    inj = rec.get("measured_injection")
    if inj is None:
        return None
    if not inj.get("param"):
        return False                       # nothing was written; not this cause
    return inj.get("confirmed") is not True


def _missing_downstream_confirmation(rec):
    if "first_break" not in rec:
        return None
    return rec.get("first_break") in ("SENSOR_OUTPUT_CHANGED",
                                      "CSIA_RECEIVED_CHANGE")


def _late_downstream_confirmation(rec):
    """The effect arrived, but outside the window the trial declared.

    Undecidable without a declared bound: a trial that never said how long it
    would wait cannot be found to have waited too long.
    """
    observed = rec.get("downstream_confirmation_latency_s")
    bound = rec.get("downstream_confirmation_bound_s")
    if observed is None or bound is None:
        return None
    return observed > bound


def _missing_required_stream(rec):
    required = rec.get("required_streams")
    seen = rec.get("streams_seen")
    if required is None or seen is None:
        return None
    return bool(set(required) - set(seen))


def _timebase_corruption(rec):
    """Time ran backwards, or re-anchored mid-trial.

    A trial whose clock moved is a trial whose every latency is meaningless,
    and it must not be scored as a slow detection.
    """
    reanchors = rec.get("time_reanchors")
    monotonic = rec.get("timebase_monotonic")
    if reanchors is None and monotonic is None:
        return None
    if reanchors is not None and reanchors > 0:
        return True
    return monotonic is False


def _injector_readback_mismatch(rec):
    inj = rec.get("measured_injection")
    if inj is None or "readback" not in inj:
        return None
    return inj.get("readback") != inj.get("value")


def _incomplete_artifact(rec):
    """A required field is absent from the trial record itself."""
    required = rec.get("required_fields")
    if required is None:
        return None
    return bool([f for f in required if f not in rec])


def _wrong_autopilot_version(rec):
    expected = rec.get("expected_autopilot_commit")
    actual = rec.get("ardupilot_commit") or rec.get("autopilot_commit")
    if expected is None or actual is None:
        return None
    return not str(actual).startswith(str(expected)[:12])


def _wrong_core_sha(rec):
    expected = rec.get("expected_frozen_core_tag")
    actual = rec.get("frozen_core_tag")
    if expected is None or actual is None:
        return None
    return actual != expected


def _aborted(rec):
    return bool(rec.get("operator_abort"))


CAUSES = (
    Cause("NO_OP_INJECTION",
          "a parameter was written and nothing downstream moved",
          _no_op_injection, TrialState.INVALID_SCENARIO,
          "evidence chain: first_break at SIMULATOR_STATE_CHANGED"),
    Cause("MISSING_DOWNSTREAM_CONFIRMATION",
          "the sensor stream or the canonical sample never showed the effect",
          _missing_downstream_confirmation, TrialState.INVALID_SCENARIO,
          "evidence chain: first_break downstream of the command"),
    Cause("LATE_DOWNSTREAM_CONFIRMATION",
          "the effect arrived outside the declared confirmation window",
          _late_downstream_confirmation, TrialState.INVALID_SCENARIO,
          "declared bound vs observed latency"),
    Cause("MISSING_REQUIRED_STREAM",
          "a stream the trial declared it needed never arrived",
          _missing_required_stream, TrialState.INVALID_SCENARIO,
          "required_streams minus streams_seen"),
    Cause("TIMEBASE_CORRUPTION",
          "the clock re-anchored or ran backwards mid-trial",
          _timebase_corruption, TrialState.INVALID_SCENARIO,
          "time_reanchors > 0 or timebase_monotonic false"),
    Cause("INJECTOR_READBACK_MISMATCH",
          "the parameter read back as something other than what was written",
          _injector_readback_mismatch, TrialState.INVALID_SCENARIO,
          "readback != value"),
    Cause("INCOMPLETE_ARTIFACT",
          "a field the trial declared required is absent from the record",
          _incomplete_artifact, TrialState.INVALID_SCENARIO,
          "required_fields minus present keys"),
    Cause("ARTIFACT_TAMPER",
          "the manifest was edited after it was written",
          lambda rec: None, None,
          "manifest content hash, rejected at load before adjudication"),
    Cause("PROFILE_DEPLOYMENT_CONFLICT",
          "the vehicle profile and the deployment config disagree",
          lambda rec: None, None,
          "csia-edge validate, exit 3, reported never resolved"),
    Cause("WRONG_AUTOPILOT_VERSION",
          "the trial ran on a build other than the one it declared",
          _wrong_autopilot_version, TrialState.PREREG_VIOLATION,
          "expected_autopilot_commit vs recorded commit"),
    Cause("WRONG_CORE_SHA",
          "the frozen core was not the one the preregistration named",
          _wrong_core_sha, TrialState.PREREG_VIOLATION,
          "expected_frozen_core_tag vs recorded tag"),
    Cause("ABORTED_TRIAL",
          "a human stopped the run",
          _aborted, TrialState.ABORTED_BY_OPERATOR,
          "operator_abort flag"),
)


def classify(record: dict) -> dict:
    """Every cause present in a record, plus the adjudicated state.

    The two preregistration-bound causes are folded into the record's
    `prereg_deviations` so the eight-state adjudicator can see them -- a
    version mismatch IS a deviation from what was preregistered, and giving it
    its own state would duplicate PREREG_VIOLATION.
    """
    present, undecidable = [], []
    for cause in CAUSES:
        got = cause.detect(record)
        if got is None:
            undecidable.append(cause.id)
        elif got:
            present.append(cause.id)

    enriched = dict(record)
    prereg_causes = [c for c in present
                     if c in ("WRONG_AUTOPILOT_VERSION", "WRONG_CORE_SHA")]
    if prereg_causes:
        enriched["prereg_deviations"] = list(
            record.get("prereg_deviations") or []) + prereg_causes

    chain_causes = [c for c in present if c in (
        "NO_OP_INJECTION", "MISSING_DOWNSTREAM_CONFIRMATION",
        "LATE_DOWNSTREAM_CONFIRMATION", "MISSING_REQUIRED_STREAM",
        "TIMEBASE_CORRUPTION", "INJECTOR_READBACK_MISMATCH",
        "INCOMPLETE_ARTIFACT")]
    if chain_causes and not enriched.get("first_break"):
        enriched["first_break"] = "SIMULATOR_STATE_CHANGED"
        enriched["first_break_causes"] = chain_causes

    return {"causes_present": present, "undecidable": undecidable,
            "state": adjudicate(enriched).state}
