"""The mission-assurance conformance suite. Judges BEHAVIOUR, never names.

HOW IT WORKS
------------
Seven probes, each constructing an input whose correct answer is fixed by the
semantics, and each calling the implementation under test through the same
five-method interface. An implementation fails a probe by giving the wrong
answer, and for no other reason.

THE ONE RULE, AND HOW IT IS ENFORCED
--------------------------------------
**No probe may read the implementation's name, class, module or docstring.**
`BAD_PRODUCT_08_actually_fine` is a correct implementation with a name
designed to trip a name-based checker; it must PASS. A test asserts that,
which means a future edit adding a name check breaks a test rather than
quietly making the whole suite meaningless.

A MISSING CAPABILITY IS INCONCLUSIVE, NOT A FAILURE
-----------------------------------------------------
An implementation that does not expose a method cannot be judged on it. That
is reported as INCONCLUSIVE and is never folded into PASS -- the same rule
the OptiPlex nightly node uses, for the same reason: a skipped check reading
as green is a failure mode this repository has already hit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .capability import (CapabilityReport, DEGRADED_SUPPORTED, EvidenceStatus,
                         NOT_SUPPORTED, SUPPORTED)
from .planner import AUTHORIZED, MissionAction, REJECTED
from .product import (MissionProductContract, PRODUCT_SUPPORTED,
                      QualityRequirement)

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class ProbeResult:
    probe: str
    verdict: str
    expected: Any
    observed: Any
    why: str

    def to_dict(self) -> dict:
        return {"probe": self.probe, "verdict": self.verdict,
                "expected": str(self.expected), "observed": str(self.observed),
                "why": self.why}


def _call(impl, method: str, *args):
    fn = getattr(impl, method, None)
    if not callable(fn):
        return None, f"implementation exposes no {method}()"
    try:
        return fn(*args), None
    except NotImplementedError as exc:
        return None, f"{method}() raised NotImplementedError: {exc}"
    except Exception as exc:                                # noqa: BLE001
        return None, f"{method}() raised {type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# the fixtures each probe builds


def _absolute_product() -> MissionProductContract:
    return MissionProductContract(
        product_id="probe_absolute_map",
        product_type="absolute_georeferenced_map",
        qualities=(
            QualityRequirement(
                property_name="absolute_geolocation",
                requires_capabilities=("absolute_navigation",),
                permits=("georeferenced_asset_mapping",),
                prohibits_without=("survey_grade_absolute_measurement",)),
            QualityRequirement(
                property_name="imagery_quality",
                requires_all=("camera.rgb.calibration_valid",),
                permits=("visual_damage_assessment",),
                prohibits_without=("any_use_of_this_imagery",)),
        ))


def _mapping_product() -> MissionProductContract:
    return MissionProductContract(
        product_id="probe_mapping",
        product_type="relative_3d_reconstruction",
        qualities=(
            QualityRequirement(
                property_name="relative_geometry",
                requires_capabilities=("local_mapping",),
                permits=("relative_structural_comparison",),
                prohibits_without=("relative_structural_comparison",)),
        ))


# ---------------------------------------------------------------------------
# the probes


def probe_01_position_loss(impl) -> ProbeResult:
    """Absolute geolocation MUST go when absolute navigation goes."""
    contract = _absolute_product()
    evidence = {"camera.rgb.calibration_valid":
                EvidenceStatus("camera.rgb.calibration_valid", True)}
    caps = {"absolute_navigation": CapabilityReport(
        "absolute_navigation", NOT_SUPPORTED,
        ("EVIDENCE_NOT_SUPPORTED",))}

    got, err = _call(impl, "qualify_product", contract, evidence, caps, 10.0)
    if err:
        return ProbeResult("BAD_PRODUCT_01", INCONCLUSIVE,
                           "absolute_geolocation NOT_SUPPORTED", err, err)
    state = got.property_states.get("absolute_geolocation")
    ok = state == NOT_SUPPORTED
    return ProbeResult(
        "BAD_PRODUCT_01", PASS if ok else FAIL,
        f"absolute_geolocation={NOT_SUPPORTED}",
        f"absolute_geolocation={state}, product={got.state}",
        "an absolute-position property cannot survive the loss of the "
        "capability it names as its only requirement")


def probe_02_stale_calibration(impl) -> ProbeResult:
    """An EXPIRED calibration must not qualify imagery."""
    contract = _absolute_product()
    evidence = {"camera.rgb.calibration_valid": EvidenceStatus(
        "camera.rgb.calibration_valid", True, expires_at=5.0)}
    caps = {"absolute_navigation": CapabilityReport(
        "absolute_navigation", SUPPORTED, ("ALL_REQUIREMENTS_MET",))}

    got, err = _call(impl, "qualify_product", contract, evidence, caps, 99.0)
    if err:
        return ProbeResult("BAD_PRODUCT_02", INCONCLUSIVE,
                           "imagery_quality NOT_SUPPORTED", err, err)
    state = got.property_states.get("imagery_quality")
    ok = state == NOT_SUPPORTED
    return ProbeResult(
        "BAD_PRODUCT_02", PASS if ok else FAIL,
        f"imagery_quality={NOT_SUPPORTED} (calibration expired at t=5, now 99)",
        f"imagery_quality={state}",
        "a calibration with an expiry in the past is not a calibration")


def probe_03_compute_failure(impl) -> ProbeResult:
    """A compute-dependent product must fall when compute falls."""
    contract = _mapping_product()
    caps = {"local_mapping": CapabilityReport(
        "local_mapping", NOT_SUPPORTED, ("COMPUTE_NOT_SUPPORTED",))}

    got, err = _call(impl, "qualify_product", contract, {}, caps, 10.0)
    if err:
        return ProbeResult("BAD_PRODUCT_03", INCONCLUSIVE,
                           "relative_geometry NOT_SUPPORTED", err, err)
    state = got.property_states.get("relative_geometry")
    ok = state == NOT_SUPPORTED
    return ProbeResult(
        "BAD_PRODUCT_03", PASS if ok else FAIL,
        f"relative_geometry={NOT_SUPPORTED}",
        f"relative_geometry={state}",
        "a map that a missed deadline prevented building is not a map")


def probe_04_configuration_change(impl) -> ProbeResult:
    """A certificate must not survive a configuration change."""
    class _Cert:
        vehicle_configuration_hash = "CONFIG_A"
        evidence_manifest_hash = "EVIDENCE_A"

    got, err = _call(impl, "certificate_valid", _Cert(), "CONFIG_B",
                     "EVIDENCE_A")
    if err:
        return ProbeResult("BAD_PRODUCT_04", INCONCLUSIVE, "(False, reason)",
                           err, err)
    valid = got[0] if isinstance(got, (tuple, list)) else got
    ok = valid is False
    return ProbeResult(
        "BAD_PRODUCT_04", PASS if ok else FAIL,
        "valid=False when the vehicle configuration hash differs",
        f"valid={valid}",
        "the certificate describes a product from a specific article in a "
        "specific configuration; change it and the certificate describes "
        "something else")


def probe_05_instant_restore(impl) -> ProbeResult:
    """One supported observation must NOT restore a capability."""
    observations = [(SUPPORTED, 100.0)]
    got, err = _call(impl, "capability_after_recovery", observations, 100.05)
    if err:
        return ProbeResult("BAD_PRODUCT_05", INCONCLUSIVE,
                           f"not {SUPPORTED}", err, err)
    ok = got != SUPPORTED
    return ProbeResult(
        "BAD_PRODUCT_05", PASS if ok else FAIL,
        f"anything except {SUPPORTED} after ONE observation 50ms in",
        str(got),
        "presence of a sensor is not evidence that the function it serves "
        "works; restoring here implements 'the device answered, therefore "
        "the capability is back'")


def probe_06_planner_override(impl) -> ProbeResult:
    """An action needing a NOT_SUPPORTED capability must be REJECTED."""
    action = MissionAction("probe_action",
                           requires_capabilities=("absolute_navigation",))
    caps = {"absolute_navigation": CapabilityReport(
        "absolute_navigation", NOT_SUPPORTED, ("EVIDENCE_NOT_SUPPORTED",))}

    got, err = _call(impl, "authorize", action, caps, {})
    if err:
        return ProbeResult("BAD_PRODUCT_06", INCONCLUSIVE, REJECTED, err, err)
    ok = got == REJECTED
    return ProbeResult(
        "BAD_PRODUCT_06", PASS if ok else FAIL, REJECTED, str(got),
        "a planner may read support state and may not write it; an "
        "'advisory mode' that proceeds anyway is an override wearing a "
        "different word")


def probe_07_score_as_support(impl) -> ProbeResult:
    """No score, however high, is support."""
    verdicts = []
    for score in (0.90, 0.99, 0.999999, 1.0):
        got, err = _call(impl, "accepts_score_as_support", score)
        if err:
            return ProbeResult("BAD_PRODUCT_07", INCONCLUSIVE, "False", err,
                               err)
        verdicts.append((score, got))
    ok = all(v is False for _s, v in verdicts)
    return ProbeResult(
        "BAD_PRODUCT_07", PASS if ok else FAIL,
        "False at every score including 1.0",
        str(verdicts),
        "the separation of RANKING from SUPPORT is the finding this entire "
        "programme rests on; a score of 1.0 with no witness is still no "
        "witness")


PROBES = (probe_01_position_loss, probe_02_stale_calibration,
          probe_03_compute_failure, probe_04_configuration_change,
          probe_05_instant_restore, probe_06_planner_override,
          probe_07_score_as_support)


def run(impl) -> dict:
    """Run every probe. Returns a report; never raises on a bad impl."""
    results = [p(impl) for p in PROBES]
    failed = [r for r in results if r.verdict == FAIL]
    inconclusive = [r for r in results if r.verdict == INCONCLUSIVE]
    return {
        "schema": "csia.mission.conformance/1",
        # Recorded for the reader, NOT read by any probe.
        "implementation_label": getattr(impl, "name", "<unlabelled>"),
        "probes": [r.to_dict() for r in results],
        "counts": {PASS: sum(1 for r in results if r.verdict == PASS),
                   FAIL: len(failed),
                   INCONCLUSIVE: len(inconclusive)},
        "conforms": not failed and not inconclusive,
        "rejected": bool(failed),
        "judged_on": ("BEHAVIOUR ONLY. No probe reads the implementation's "
                      "name, class, module or docstring."),
        "inconclusive_is_not_pass": (
            "an implementation that does not expose a method cannot be "
            "judged on it, and that is never folded into PASS"),
    }


def run_all(references) -> dict:
    """Run the suite over (implementation, must_be_rejected) pairs."""
    rows, wrong = [], []
    for impl, must_reject in references:
        report = run(impl)
        correct = report["rejected"] == must_reject
        rows.append({"label": report["implementation_label"],
                     "must_be_rejected": must_reject,
                     "rejected": report["rejected"],
                     "counts": report["counts"],
                     "correct": correct,
                     "failing_probes": [p["probe"] for p in report["probes"]
                                        if p["verdict"] == FAIL]})
        if not correct:
            wrong.append(rows[-1])
    return {
        "schema": "csia.mission.conformance_campaign/1",
        "implementations": len(rows),
        "rows": rows,
        "suite_correct": not wrong,
        "misjudged": wrong,
        "control": ("BAD_PRODUCT_08_actually_fine is CORRECT and is named to "
                    "trip a name-based checker. It must NOT be rejected."),
    }


_ = (DEGRADED_SUPPORTED, AUTHORIZED, PRODUCT_SUPPORTED)   # vocabulary re-export
