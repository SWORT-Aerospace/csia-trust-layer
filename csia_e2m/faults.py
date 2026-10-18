"""Derived fault streams, written beside a raw log and never over it.

E2M-5. Each function takes observations replayed from an immutable raw log and
returns a NEW sequence. The raw log is opened read-only by
:mod:`csia_e2m.replay` and is never written by anything here; a test asserts
its digest is unchanged after every derivation runs.

WHY DERIVED FAULTS ARE WORTH HAVING AT ALL
------------------------------------------
A physical bench can produce a dropout and a brownout. It cannot cheaply
produce a 40-minute slow drift, and it cannot produce the *same* drift twice.
Derived streams are reproducible and cost nothing, and they are strictly weaker
evidence: they show how a consumer behaves on a stream with a known defect, not
how the hardware behaves.

Every derived stream is tagged with ``derived_from`` and the transform that
made it, so a reader cannot mistake one for a measurement.

THE CORRELATED CASES ARE THE POINT
----------------------------------
``correlated_bias`` and ``correlated_drift`` move every sensor together,
because that is what a shared rail or a shared driver defect does
(:mod:`csia_e2m.ancestry`). A consumer that treats agreement among
mux channels as corroboration will read a correlated fault as confirmation,
and these two streams are how that is demonstrated rather than argued.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .replay import Observation

TRANSFORMS = ("constant_bias", "gradual_drift", "freeze", "dropout", "delay",
              "jitter", "correlated_bias", "correlated_drift")


def _measured(observations: Iterable[Observation]) -> List[Observation]:
    return list(observations)


def constant_bias(observations: Iterable[Observation], *, milli: int,
                  sensors: Optional[Sequence[str]] = None
                  ) -> List[Observation]:
    out = []
    for o in _measured(observations):
        if o.observed and (sensors is None or o.sensor in sensors):
            out.append(replace(o, value_milli=o.value_milli + milli))
        else:
            out.append(o)
    return out


def gradual_drift(observations: Iterable[Observation], *,
                  milli_per_sweep: int,
                  sensors: Optional[Sequence[str]] = None
                  ) -> List[Observation]:
    out = []
    for o in _measured(observations):
        if o.observed and (sensors is None or o.sensor in sensors):
            out.append(replace(o,
                               value_milli=o.value_milli
                               + milli_per_sweep * o.sweep))
        else:
            out.append(o)
    return out


def freeze(observations: Iterable[Observation], *, sensor: str,
           from_sweep: int) -> List[Observation]:
    """Hold the last value. The classic failure that looks like a healthy
    sensor in a calm environment."""
    out: List[Observation] = []
    held: Optional[int] = None
    for o in _measured(observations):
        if o.sensor != sensor or not o.observed:
            out.append(o)
            continue
        if o.sweep < from_sweep:
            held = o.value_milli
            out.append(o)
        else:
            out.append(replace(o, value_milli=held))
    return out


def dropout(observations: Iterable[Observation], *, sensor: str,
            from_sweep: int, to_sweep: Optional[int] = None
            ) -> List[Observation]:
    """Remove the measurement. `value_milli` becomes None, never 0."""
    out = []
    for o in _measured(observations):
        inside = o.sweep >= from_sweep and (to_sweep is None
                                            or o.sweep <= to_sweep)
        if o.sensor == sensor and inside:
            out.append(replace(o, value_milli=None, unit=None,
                               status="ERR_SENSOR_NACK"))
        else:
            out.append(o)
    return out


def delay(observations: Iterable[Observation], *, ns: int,
          sensors: Optional[Sequence[str]] = None) -> List[Observation]:
    out = []
    for o in _measured(observations):
        if sensors is None or o.sensor in sensors:
            out.append(replace(o, host_monotonic_ns=o.host_monotonic_ns + ns))
        else:
            out.append(o)
    return out


def jitter(observations: Iterable[Observation], *, amplitude_ns: int,
           seed: int) -> List[Observation]:
    """Deterministic given `seed`. No wall clock, no unseeded RNG."""
    import random
    rng = random.Random(seed)
    return [replace(o, host_monotonic_ns=o.host_monotonic_ns
                    + rng.randint(-amplitude_ns, amplitude_ns))
            for o in _measured(observations)]


def correlated_bias(observations: Iterable[Observation], *, milli: int
                    ) -> List[Observation]:
    """Every sensor moves together, as a shared rail sag would move them."""
    return constant_bias(observations, milli=milli, sensors=None)


def correlated_drift(observations: Iterable[Observation], *,
                     milli_per_sweep: int) -> List[Observation]:
    """Every sensor drifts together, as a shared reference would drift them."""
    return gradual_drift(observations, milli_per_sweep=milli_per_sweep,
                         sensors=None)


def provenance(name: str, raw_log_sha256: str, params: Dict) -> Dict:
    """The tag every derived stream carries, so it cannot pass for a run."""
    if name not in TRANSFORMS:
        raise ValueError(f"unknown transform {name!r}; have {TRANSFORMS}")
    return {
        "schema": "csia.e2m.derived_stream/1",
        "transform": name,
        "parameters": dict(params),
        "derived_from_raw_log_sha256": raw_log_sha256,
        "is_physical_measurement": False,
        "what_this_is_not": (
            "not a measurement and not a hardware observation. A software "
            "transform of a recorded stream, reproducible from the same raw "
            "log and the same parameters."),
    }


REGISTRY: Dict[str, Callable] = {
    "constant_bias": constant_bias, "gradual_drift": gradual_drift,
    "freeze": freeze, "dropout": dropout, "delay": delay, "jitter": jitter,
    "correlated_bias": correlated_bias, "correlated_drift": correlated_drift,
}
