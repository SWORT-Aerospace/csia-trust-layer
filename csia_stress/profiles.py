"""Simultaneous multi-sensor degradation profiles, and the honest gaps.

WHAT THIS IS
------------
The frozen scenario catalog (`csia/scenarios.py`) ships nine scenarios,
seven of which inject a single fault kind. Two already compose several --
`power_sag` (battery + ESC) and `dual_imu_failure` (imu0 + imu1) -- which
is what establishes that `run_pipeline(faults=...)` takes a SEQUENCE and
that multi-fault composition needs no change to the frozen core.

This module composes ACROSS SENSOR CLASSES: navigation, attitude, heading,
power and structure degrading at once, with staggered onsets so the layer
must attribute several concurrent causes rather than one.

WHAT IT IS NOT
--------------
**These are simulated sensor-degradation profiles. Nothing here transmits
anything.** There is no jammer and no spoofing transmitter; a "GNSS-denied"
profile is a `dropout` fault on the GPS sensor model, which is what the
frozen core already ships as `gps_dropout`.

**No profile may claim a phenomenon the sensor model does not implement.**
The frozen `KNOWN_KINDS` has exactly six kinds. Anything outside them is
recorded in `UNMODELLED` as a declared gap with the reason -- not
approximated by the nearest available signature and quietly relabelled.
An urban-canyon multipath profile built out of `gps_spoof` would be a
lie about what was tested: multipath is a bounded, geometry-dependent,
oscillatory position error, and `gps_spoof` is a monotonic drift ramp.
They are different signatures and a detector that catches one need not
catch the other.

CONSTRUCTION REFUSES INERT FAULTS
---------------------------------
Every fault is checked against the MEASURED applicability matrix. A
profile containing a pair the sensors ignore raises `VacuousFault` rather
than running and reporting clean. See `applicability.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from csia.sensors.faults import Fault

from .applicability import ApplicabilityMatrix, matrix

#: Flight profiles the frozen truth model implements. There are exactly two.
#: `fast_cruise` is the closest thing to "high throttle" that exists, and the
#: frozen catalog describes it as a KINEMATIC high-speed envelope with
#: "aerodynamic drag NOT modeled, sensor tolerances quad-tuned". It is not an
#: aerodynamic maneuver model and is not described as one here.
FLIGHT_PROFILES = ("hover_circle", "fast_cruise")


@dataclass(frozen=True)
class StressProfile:
    """A named combination of simultaneous sensor degradations."""

    id: str
    summary: str
    faults: tuple
    flight_profile: str = "hover_circle"
    #: Flight length. Extended past the 60 s default when the faults clear
    #: too late for a recovery to be OBSERVABLE within the run -- the
    #: failsafe's de-escalation dwell is 5 s, so a run ending 5 s after the
    #: last fault cannot show a recovery whether or not one would occur.
    #: The stimulus is never shortened to fit the window; the window is
    #: lengthened to fit the stimulus.
    duration: float = 60.0
    #: Sensor classes this profile degrades, for reporting.
    classes: tuple = ()
    #: What the profile genuinely represents, in plain terms.
    represents: str = ""
    #: What it must NOT be read as. Empty is allowed; vagueness is not.
    does_not_represent: str = ""

    def __post_init__(self):
        if self.flight_profile not in FLIGHT_PROFILES:
            raise ValueError(
                f"{self.id}: unknown flight profile "
                f"{self.flight_profile!r}; the frozen truth model implements "
                f"{list(FLIGHT_PROFILES)} and this module does not invent "
                f"new flight dynamics")
        if not self.faults:
            raise ValueError(f"{self.id}: a stress profile with no faults "
                             f"stresses nothing")
        # Refuse a profile that cannot answer its own recovery question.
        # 5.0 s is FailsafeConfig.dwell_down; it is read at runtime rather
        # than hardcoded here so a frozen-core change would surface.
        from csia.runtime.failsafe import FailsafeConfig
        clear = max(f.start + f.duration for f in self.faults)
        window = self.duration - clear
        if window <= FailsafeConfig().dwell_down:
            raise ValueError(
                f"{self.id}: faults clear at {clear:.1f} s of a "
                f"{self.duration:.1f} s flight, leaving {window:.1f} s -- "
                f"not longer than the failsafe's {FailsafeConfig().dwell_down}"
                f" s de-escalation dwell, so a recovery could not be observed "
                f"even if it happened. Lengthen `duration`; do not shorten "
                f"the faults to fit.")

    def validate(self, mtx: ApplicabilityMatrix | None = None) -> None:
        """Refuse any fault the sensors would silently ignore."""
        mtx = mtx or matrix()
        for f in self.faults:
            mtx.require_live(f.kind, f.target, where=f"profile {self.id!r}")

    @property
    def targets(self) -> tuple:
        return tuple(sorted({f.target for f in self.faults}))

    @property
    def concurrent(self) -> bool:
        """True if any two fault windows overlap in time."""
        spans = sorted((f.start, f.start + f.duration) for f in self.faults)
        return any(spans[i][1] > spans[i + 1][0] for i in range(len(spans) - 1))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "summary": self.summary,
            "flight_profile": self.flight_profile,
            "classes": list(self.classes),
            "targets": list(self.targets),
            "concurrent": self.concurrent,
            "represents": self.represents,
            "does_not_represent": self.does_not_represent,
            "faults": [{"kind": f.kind, "target": f.target,
                        "start": f.start, "duration": f.duration,
                        "params": {k: list(v) if isinstance(v, tuple) else v
                                   for k, v in f.params.items()}}
                       for f in self.faults],
        }


# ---------------------------------------------------------------------------
# DECLARED GAPS. Phenomena requested of this layer that the frozen sensor
# model has no primitive for. They are DATA, not prose, so a report can list
# what was NOT tested next to what was.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UnmodelledPhenomenon:
    id: str
    why_not: str
    nearest_available: str
    why_the_nearest_is_not_it: str


UNMODELLED = (
    UnmodelledPhenomenon(
        id="rf_jamming_as_rf",
        why_not=(
            "The frozen sensor models have no RF front-end, no carrier-to-"
            "noise-density channel and no interference model. KNOWN_KINDS "
            "has six kinds and none of them is RF."),
        nearest_available="dropout on gps (loss of fix)",
        why_the_nearest_is_not_it=(
            "Dropout is the OBSERVABLE CONSEQUENCE of a jammer strong enough "
            "to deny the fix, and this repository does test that. It is not "
            "jamming: it omits the degraded-but-present regime a real jammer "
            "produces first -- rising noise, falling satellite count, a fix "
            "that is still reported and increasingly wrong. A layer that "
            "handles a clean dropout has NOT been shown to handle that."),
    ),
    UnmodelledPhenomenon(
        id="urban_canyon_multipath",
        why_not=(
            "Multipath is a geometry-dependent, bounded, oscillatory "
            "position error driven by reflectors around the vehicle. The "
            "frozen GPS model has a Gauss-Markov error and two fault kinds; "
            "it carries no reflector geometry."),
        nearest_available="gps_spoof (monotonic drift ramp)",
        why_the_nearest_is_not_it=(
            "A spoof drift is monotonic and unbounded; multipath is bounded "
            "and oscillatory, and correlates with heading and position "
            "rather than growing with time. Building a 'multipath' profile "
            "out of gps_spoof would test the drift detector and label the "
            "result multipath. THE DETECTOR THAT CATCHES ONE NEED NOT CATCH "
            "THE OTHER."),
    ),
    UnmodelledPhenomenon(
        id="control_surface_flutter",
        why_not=(
            "The frozen sensor suite is quad-tuned (eight nodes, no control-"
            "surface instrumentation) and the truth model has no "
            "aeroelastic state. Flutter is a structural-dynamic mode, not a "
            "sensor fault."),
        nearest_available="vibration_anomaly on the vibration node",
        why_the_nearest_is_not_it=(
            "vibration_anomaly is a prop/blade damage signature: amplitude "
            "growth plus a sub-harmonic. Flutter is a divergent oscillation "
            "at a structural mode frequency with a different spectral "
            "signature and a different time constant. The vibration profile "
            "below is labelled as the prop signature it is."),
    ),
    UnmodelledPhenomenon(
        id="high_throttle_maneuvering",
        why_not=(
            "The frozen truth model implements two flight profiles, "
            "hover_circle and fast_cruise. fast_cruise is a KINEMATIC "
            "high-speed envelope; its own catalog entry states that "
            "aerodynamic drag is NOT modelled."),
        nearest_available="fast_cruise (~55 m/s)",
        why_the_nearest_is_not_it=(
            "It is a high-SPEED profile, not a high-THROTTLE maneuvering "
            "one: there is no thrust model, no load factor and no control "
            "input. Profiles below that use it say 'fast_cruise', not "
            "'high-throttle maneuver'. Inventing a maneuver profile would "
            "mean inventing flight dynamics this repository has not "
            "validated."),
    ),
)


# ---------------------------------------------------------------------------
# THE CATALOG
# ---------------------------------------------------------------------------

def _msrd() -> tuple:
    """Simultaneous degradation across SENSOR CLASSES."""
    return (
        # The explicitly requested case: navigation spoof concurrent with a
        # heading-reference drift, flown on the fast profile.
        StressProfile(
            id="msrd_gps_spoof_mag_drift_fast",
            summary=("GPS spoof 20-35 s concurrent with magnetometer bias "
                     "drift 22-40 s, flown on fast_cruise"),
            flight_profile="fast_cruise",
            classes=("navigation", "heading"),
            faults=(
                Fault("gps_spoof", "gps", 20.0, 15.0,
                      {"drift": (3.0, 1.0, 0.0)}),
                Fault("bias_drift", "mag", 22.0, 18.0,
                      {"axis": 2, "rate": 0.05}),
            ),
            represents=("two independent references degrading at once, with "
                        "overlapping but not identical windows, so "
                        "attribution cannot be a single-cause answer"),
            does_not_represent=(
                "a high-throttle maneuver: fast_cruise is a kinematic "
                "high-speed envelope with no drag or thrust model"),
        ),
        StressProfile(
            id="msrd_gnss_denied_imu_drift",
            summary=("GNSS denied 20-40 s while imu0 accel-z bias drifts "
                     "25-45 s"),
            classes=("navigation", "attitude"),
            faults=(
                Fault("dropout", "gps", 20.0, 20.0),
                Fault("bias_drift", "imu0", 25.0, 20.0,
                      {"axis": 2, "rate": 0.05, "channel": "accel"}),
            ),
            represents=("loss of the navigation anchor while the dead-"
                        "reckoning reference is itself degrading -- the "
                        "case where holding on GPS loss is least safe"),
        ),
        StressProfile(
            id="msrd_power_and_structure",
            summary="Power sag 28-36 s with a prop-damage vibration signature 26-42 s",
            classes=("power", "structure"),
            faults=(
                Fault("power_sag", "battery", 28.0, 8.0, {"depth_v": 1.2}),
                Fault("power_sag", "motor_esc", 28.0, 8.0,
                      {"rpm_loss": 350.0}),
                Fault("vibration_anomaly", "vibration", 26.0, 16.0,
                      {"gain": 3.0}),
            ),
            represents=("a mechanical fault and its electrical consequence "
                        "presenting together, which is the physically "
                        "plausible pairing"),
            does_not_represent="control-surface flutter (see UNMODELLED)",
        ),
        StressProfile(
            id="msrd_four_class_cascade",
            summary=("Staggered four-class cascade: heading 18 s, navigation "
                     "22 s, attitude 26 s, power 30 s"),
            classes=("heading", "navigation", "attitude", "power"),
            faults=(
                Fault("emi_spike", "mag", 18.0, 24.0,
                      {"amplitude": 10.0, "rate_hz": 12.0}),
                Fault("gps_spoof", "gps", 22.0, 20.0,
                      {"drift": (2.0, 2.0, 0.0)}),
                Fault("bias_drift", "imu1", 26.0, 16.0,
                      {"axis": 2, "rate": 0.08, "channel": "accel"}),
                Fault("power_sag", "battery", 30.0, 10.0, {"depth_v": 1.0}),
            ),
            represents=("progressive degradation where each new fault "
                        "arrives while the previous is unresolved -- the "
                        "hardest attribution case this sensor suite can "
                        "express"),
        ),
        StressProfile(
            id="msrd_dual_imu_with_gnss_denied",
            summary=("Both IMUs drifting in opposite directions while GNSS "
                     "is denied"),
            classes=("attitude", "navigation"),
            # The IMU windows mirror the frozen dual_imu_failure scenario
            # exactly (25/30 and 27/28) and so clear at 55 s. The flight is
            # extended rather than the faults trimmed, so the stimulus stays
            # comparable to the frozen scenario and the recovery question
            # becomes answerable.
            duration=90.0,
            faults=(
                Fault("bias_drift", "imu0", 25.0, 30.0,
                      {"axis": 2, "rate": 0.18, "channel": "accel"}),
                Fault("bias_drift", "imu1", 27.0, 28.0,
                      {"axis": 2, "rate": -0.15, "channel": "accel"}),
                Fault("dropout", "gps", 24.0, 20.0),
            ),
            represents=("the frozen dual_imu_failure scenario with the "
                        "navigation anchor removed as well: attitude "
                        "redundancy is exhausted and there is no position "
                        "reference to cross-check against"),
        ),
    )


def _degraded_environment() -> tuple:
    """Environmental degradation, each labelled for what it actually is."""
    return (
        StressProfile(
            id="env_gnss_denied",
            summary="GNSS denied 20-40 s (loss of fix)",
            classes=("navigation",),
            faults=(Fault("dropout", "gps", 20.0, 20.0),),
            represents=("complete loss of GNSS fix, however caused -- the "
                        "observable end state of denial"),
            does_not_represent=(
                "RF jamming as such. There is no RF model; the "
                "degraded-but-present regime a real jammer produces first "
                "is NOT covered. See UNMODELLED['rf_jamming_as_rf']"),
        ),
        StressProfile(
            id="env_gnss_denied_intermittent",
            summary="Intermittent GNSS: four 3 s denials between 20 s and 44 s",
            classes=("navigation",),
            faults=tuple(
                Fault("dropout", "gps", 20.0 + 8.0 * i, 3.0) for i in range(4)),
            represents=("repeated acquire/lose cycles, which exercise "
                        "re-acquisition and the de-escalation dwell rather "
                        "than a single sustained loss"),
            does_not_represent=(
                "urban-canyon multipath: an intermittent FIX is not a "
                "systematically WRONG fix. See "
                "UNMODELLED['urban_canyon_multipath']"),
        ),
        StressProfile(
            id="env_motor_thrust_loss",
            summary="Motor/ESC thrust loss 30-42 s (RPM sag) with pack sag",
            classes=("power", "propulsion"),
            faults=(
                Fault("power_sag", "motor_esc", 30.0, 12.0,
                      {"rpm_loss": 500.0}),
                Fault("power_sag", "battery", 30.0, 12.0, {"depth_v": 1.5}),
            ),
            represents=("partial propulsion loss as it appears to the trust "
                        "layer: ESC RPM sag with correlated pack voltage dip"),
            does_not_represent=(
                "an airframe or actuator dynamics failure. CSIA observes "
                "sensors; a thrust loss enters only through its telemetry "
                "signature"),
        ),
        StressProfile(
            id="env_prop_damage_vibration",
            summary="Prop-damage vibration signature 28-46 s",
            classes=("structure",),
            faults=(Fault("vibration_anomaly", "vibration", 28.0, 18.0,
                          {"gain": 3.0}),),
            represents="the prop/blade damage signature the model implements",
            does_not_represent=(
                "control-surface flutter, which is a different spectral "
                "signature. See UNMODELLED['control_surface_flutter']"),
        ),
        StressProfile(
            id="env_gnss_denied_fast_cruise",
            summary="GNSS denied 20-40 s flown on fast_cruise",
            flight_profile="fast_cruise",
            classes=("navigation",),
            faults=(Fault("dropout", "gps", 20.0, 20.0),),
            represents=("the same denial at ~55 m/s, where dead-reckoning "
                        "error accumulates faster per second of outage"),
            does_not_represent=(
                "high-throttle maneuvering. See "
                "UNMODELLED['high_throttle_maneuvering']"),
        ),
    )


def catalog(validate: bool = True) -> tuple:
    """Every stress profile, validated against the measured matrix."""
    profiles = _msrd() + _degraded_environment()
    ids = [p.id for p in profiles]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate profile ids: {ids}")
    if validate:
        mtx = matrix()
        for p in profiles:
            p.validate(mtx)
    return profiles


def by_id(profile_id: str) -> StressProfile:
    for p in catalog():
        if p.id == profile_id:
            return p
    raise KeyError(f"unknown stress profile {profile_id!r}; "
                   f"available: {[p.id for p in catalog()]}")
