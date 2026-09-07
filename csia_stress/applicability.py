"""Which (fault kind, sensor) pairs ACTUALLY DO SOMETHING.

WHY THIS MODULE EXISTS BEFORE ANY STRESS PROFILE
------------------------------------------------
`Fault.__post_init__` rejects an unknown *kind*, and `sample_streams`
rejects an unknown *target*. Neither checks the PAIR. Each sensor model
applies only the kinds it implements and silently ignores the rest, so

    Fault("gps_spoof", "mag", 20.0, 10.0)

is accepted by every guard in the frozen core and changes nothing at all.
A stress profile built on pairs like that runs, produces output, and
stresses NOTHING -- while reporting a clean result.

MEASURED, NOT ASSUMED: of the 48 (kind, target) combinations the frozen
core will accept, **19 do something and 29 are silently ignored.** Most
syntactically valid faults are inert. That is not a defect in the core --
a magnetometer has no meaningful response to a GPS spoof -- but it is a
trap for anything that composes faults programmatically.

This repository has already recorded that shape once: MX-004, where two
checks "passed" from ZERO cases because frozen dataclasses rejected every
setattr, so the loop body never ran. A vacuous pass is worse than a
failure because nobody investigates it.

SO THE MATRIX IS DERIVED BY INJECTION, NOT BY READING THE SOURCE.
`derive_matrix()` samples each pair against an unfaulted baseline with the
same fixed seeds and asks whether any channel actually moved. A pair is
APPLIED only if the streams differ. Profiles are then validated against
that measured matrix, and a profile containing an inert pair is REFUSED
at construction -- it never gets the chance to report a clean run.

Nothing here modifies the frozen core. It only calls it.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from csia.scenarios import make_sensors, sample_streams
from csia.sensors import generate_flight
from csia.sensors.faults import KNOWN_KINDS, Fault

#: Representative parameters per kind, used ONLY to decide whether a pair is
#: live. These are the values the frozen scenario catalog itself uses, so the
#: probe asks the same question the shipped scenarios do.
PROBE_PARAMS: dict[str, dict] = {
    "bias_drift": {"axis": 2, "rate": 0.05, "channel": "accel"},
    "dropout": {},
    "emi_spike": {"amplitude": 10.0, "rate_hz": 12.0},
    "gps_spoof": {"drift": (3.0, 1.0, 0.0)},
    "vibration_anomaly": {"gain": 3.0},
    "power_sag": {"depth_v": 1.2, "rpm_loss": 350.0},
}

APPLIED = "APPLIED"
IGNORED = "IGNORED"
ERROR = "ERROR"


class VacuousFault(ValueError):
    """A fault the frozen core accepts but no sensor acts on.

    Raised at profile construction so an inert stimulus can never reach a
    result artifact and be read as a passing stress test.
    """


@dataclass(frozen=True)
class PairResult:
    kind: str
    target: str
    effect: str
    channels: tuple = ()
    max_delta: float = 0.0
    cross_talk: tuple = ()
    #: Whether the perturbation SURVIVES INTO THE EVENT STREAM the online
    #: layer actually consumes. None when not checked (stream-inert pairs
    #: are not worth transporting).
    transport: str | None = None

    @property
    def live(self) -> bool:
        """Live means the fault reaches the layer, not merely the stream.

        A pair that perturbs the sampled stream but is flattened in
        transport is INERT for any run that goes through the event source,
        which is every run this package performs.
        """
        return self.effect == APPLIED and self.transport == APPLIED

    @property
    def lost_in_transport(self) -> bool:
        return self.effect == APPLIED and self.transport == IGNORED


@dataclass
class ApplicabilityMatrix:
    """The measured answer to 'does this fault do anything to this sensor?'"""

    pairs: dict = field(default_factory=dict)   # (kind, target) -> PairResult

    def live_pairs(self) -> tuple:
        return tuple(sorted(k for k, v in self.pairs.items() if v.live))

    def inert_pairs(self) -> tuple:
        return tuple(sorted(k for k, v in self.pairs.items() if not v.live))

    def is_live(self, kind: str, target: str) -> bool:
        r = self.pairs.get((kind, target))
        return bool(r and r.live)

    def require_live(self, kind: str, target: str, where: str = "") -> None:
        """Refuse an inert pair, loudly, with the alternatives spelled out."""
        if self.is_live(kind, target):
            return
        known = sorted(k for (k, t) in self.live_pairs() if t == target)
        ctx = f" in {where}" if where else ""
        raise VacuousFault(
            f"fault {kind!r} on {target!r}{ctx} is INERT: the frozen core "
            f"accepts it and no sensor acts on it, so it would stress "
            f"nothing while still producing a result. "
            f"{target!r} responds to: {known or 'nothing'}.")

    def lost_in_transport(self) -> tuple:
        """Pairs that perturb the sampled stream and reach the layer as
        nothing. These are NOT quietly excluded -- they are reported, because
        a fault the simulator cannot deliver is a limitation of the test
        rig that anyone reading a stress result needs to know about."""
        return tuple(sorted(k for k, v in self.pairs.items()
                            if v.lost_in_transport))

    def summary(self) -> dict:
        return {
            "total_combinations": len(self.pairs),
            "live": len(self.live_pairs()),
            "inert": len(self.inert_pairs()),
            "live_pairs": [list(p) for p in self.live_pairs()],
            "inert_pairs": [list(p) for p in self.inert_pairs()],
            "lost_in_transport": [list(p) for p in self.lost_in_transport()],
            "what_lost_in_transport_means": (
                "the fault DOES perturb the sampled sensor stream, and the "
                "event source flattens it before the online layer sees it, "
                "so a run cannot exercise it. dropout on the vibration node "
                "is the known case: SimulatedFlightSource emits the 10 Hz "
                "RMS envelope with a hardcoded valid=True, discarding the "
                "invalidity. This is a property of the SIMULATION SOURCE "
                "(csia/runtime/plugins.py, which is not frozen), not of the "
                "frozen core, and it is recorded rather than worked around."),
            "what_this_means": (
                "Of the (kind, target) combinations the frozen core will "
                "accept, only the live ones perturb any sensor channel. The "
                "inert ones are accepted and silently ignored, which is why "
                "profiles are validated against this matrix rather than "
                "against KNOWN_KINDS."),
            "how_it_was_obtained": (
                "By injection against an unfaulted baseline with identical "
                "fixed seeds, not by reading the sensor source. A pair is "
                "APPLIED only if some channel of the target stream moved."),
        }


def _delta(a: dict, b: dict) -> dict:
    """Per-channel change between two samples of one sensor stream."""
    out = {}
    for key in a:
        x, y = np.asarray(a[key]), np.asarray(b[key])
        if x.shape != y.shape:
            out[key] = float("inf")
        elif x.dtype == bool or y.dtype == bool:
            out[key] = float(np.mean(x != y))
        else:
            out[key] = float(np.max(np.abs(x - y)))
    return out


def derive_matrix(truth=None, start: float = 20.0,
                  duration: float = 20.0) -> ApplicabilityMatrix:
    """Measure every (kind, target) pair by injecting it.

    The sensors carry fixed seeds, so the unfaulted baseline is exactly
    reproducible and ANY difference is attributable to the injected fault
    rather than to noise.
    """
    if truth is None:
        truth = generate_flight(duration=60.0, dt=0.01)
    baseline = sample_streams(truth, ())
    targets = sorted(make_sensors())

    pairs = {}
    for kind, target in itertools.product(sorted(KNOWN_KINDS), targets):
        try:
            fault = Fault(kind, target, start, duration,
                          dict(PROBE_PARAMS[kind]))
            faulted = sample_streams(truth, (fault,))
        except Exception:                       # noqa: BLE001 - recorded
            pairs[(kind, target)] = PairResult(kind, target, ERROR)
            continue

        moved = {k: v for k, v in _delta(baseline[target],
                                         faulted[target]).items() if v > 0}
        # A fault must perturb ITS OWN target and nothing else. Cross-talk
        # would mean a profile's channels are not independently attributable.
        cross = tuple(sorted(
            other for other in targets if other != target
            and any(v > 0 for v in
                    _delta(baseline[other], faulted[other]).values())))
        transport = None
        if moved:
            # SECOND STAGE. Perturbing the sampled stream is not enough: the
            # runs go through the event source, which can drop information.
            # `dropout` on the vibration node is exactly that case -- the
            # source emits the RMS envelope with a hardcoded valid=True, so
            # the invalidity never reaches the layer. Measured, not assumed.
            transport = (APPLIED if _survives_transport(truth, fault, target)
                         else IGNORED)

        pairs[(kind, target)] = PairResult(
            kind=kind, target=target,
            effect=APPLIED if moved else IGNORED,
            channels=tuple(sorted(moved)),
            max_delta=max(moved.values()) if moved else 0.0,
            cross_talk=cross,
            transport=transport)

    return ApplicabilityMatrix(pairs=pairs)


def _event_fingerprint(faults, truth, target: str) -> tuple:
    """The events the online layer would actually receive for one sensor."""
    from .source import StressFlightSource
    source = StressFlightSource(faults=faults, truth=truth)
    out = []
    for name, t, channels in source.samples():
        if name != target:
            continue
        out.append((round(float(t), 4), tuple(
            (k, float(np.sum(np.asarray(v))))
            for k, v in sorted(channels.items()))))
    return tuple(out)


def _survives_transport(truth, fault: Fault, target: str) -> bool:
    return (_event_fingerprint((fault,), truth, target)
            != _event_fingerprint((), truth, target))


_CACHED: ApplicabilityMatrix | None = None


def matrix() -> ApplicabilityMatrix:
    """The process-wide measured matrix (derived once; ~1 s)."""
    global _CACHED
    if _CACHED is None:
        _CACHED = derive_matrix()
    return _CACHED
