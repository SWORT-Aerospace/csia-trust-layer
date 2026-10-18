"""The synthetic scenario harness — §27's machinery, with no platform in it.

    Synthetic data only for initial v2. No UAV hardware required.

WHY THIS FILE HAS NO SIGNAL VALUES IN IT
----------------------------------------
It used to. `AIRCRAFT_NOMINAL` sat here alongside the runner, and the core
hygiene test (`tests/test_v2_framework.py`) failed on it — correctly. A core
that ships one platform's battery voltages has an opinion about what it is
attached to, and §37's genericity question would have been decided in this
file rather than tested.

So the harness keeps only what is true of every machine: a scenario is a
declared perturbation of a nominal signal set over a run, timestamps are
derived from per-channel offsets, and nothing anywhere consults a clock or an
RNG. The nominal tables and the injections live with their profiles, in
`csia/v2/profiles/`, where platform knowledge belongs.

WHAT THESE SCENARIOS ARE AND ARE NOT
------------------------------------
They are **wiring tests for the assurance logic**, not evidence about any real
machine. Every value a profile injects is a value chosen to exercise a
declared threshold; none is a measurement, and none supports a claim about how
a real regulator sags or how a real ESC behaves when a motor seizes. Domain
thresholds are declared in the profile FIRST and are not adjusted afterwards
to make a scenario come out a particular way.

The only non-synthetic input anywhere is the v1.1 payload: the SENSOR domain's
evidence comes from real payloads produced by the frozen v1.1 runtime, because
a synthetic v1.1 payload would make §36's baseline test meaningless.

DETERMINISM
-----------
No RNG. Every signal is an exact function of the tick index, so a scenario
replays bit-for-bit and a ledger over it is reproducible. Where a fault ramps,
it ramps linearly between declared endpoints.

THE INJECTION DISCIPLINE, WHICH IS THE PART THAT MATTERS
--------------------------------------------------------
A scenario perturbs the smallest set of signals that represents its fault, and
it perturbs them at the SOURCE of the fault, never at the conclusion. A CPU
overload raises `cpu_load` and lets the deadline miss follow from the
process's own runtime; it does not also set `deadline_misses` by hand. A
scenario that injected its own expected answer would test nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Snapshot


@dataclass(frozen=True)
class Scenario:
    """One synthetic fault, and what it is supposed to demonstrate.

    `expectation` is written down BEFORE the run and is checked against the
    result. It is prose, not an assertion — the assertions live in the tests —
    but writing it here means a scenario whose behaviour drifts becomes
    visible rather than quietly re-interpreted.
    """

    name: str
    system: str                       # a profile's name, opaque to the core
    section: str                      # which part of the brief asked for it
    description: str
    expectation: str
    #: `{domain: {component: {signal: value}}}` before any perturbation.
    nominal: dict = None
    #: `(signals, frac, t) -> None`, mutating the copy it is handed.
    inject: object = None
    #: Which real v1.1 payload stream to pair with, where a profile has one.
    v1_1_variant: str = "clean"
    tags: tuple = ()


def ramp(frac: float, onset: float, lo: float, hi: float) -> float:
    """Linear from `lo` to `hi` over the post-onset part of the run."""
    if frac < onset:
        return lo
    span = max(1e-9, 1.0 - onset)
    return lo + (hi - lo) * min(1.0, (frac - onset) / span)


def _deep(d: dict) -> dict:
    return {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in d.items()}


@dataclass
class SnapshotSource:
    """Turns a scenario into a deterministic sequence of snapshots."""

    scenario: Scenario
    ticks: int = 200
    dt: float = 0.05
    #: `(index, t) -> payload | None`. A profile with a SENSOR domain supplies
    #: real v1.1 payloads; one without simply leaves this `None`.
    payload_for: object = None
    t0: float = 0.0

    def __iter__(self):
        base = self.scenario.nominal or {}
        for k in range(self.ticks):
            t = self.t0 + k * self.dt
            frac = k / max(1, self.ticks - 1)
            sig = _deep(base)
            if self.scenario.inject is not None:
                self.scenario.inject(sig, frac, t)
            stamp(sig, t)
            payload = (self.payload_for(k, t) if self.payload_for is not None
                       else None)
            yield Snapshot(t=t, signals=sig, v1_1_payload=payload)


def stamp(signals: dict, t: float) -> None:
    """Turn per-channel offsets into the four absolute timestamps.

    The offsets are what a scenario perturbs; the stamps are what the TIMING
    domain reads. Keeping them separate means a scenario cannot accidentally
    produce an inconsistent stamp set except where it means to — and one
    scenario does mean to, which is the point of having the check.
    """
    for _name, ch in signals.get("TIMING", {}).items():
        validity = t - float(ch.get("interval_s", 0.0))
        arrival = validity + float(ch.pop("transport_s", 0.0))
        processed = arrival + float(ch.pop("processing_s", 0.0))
        decision = processed + float(ch.pop("decision_s", 0.0))
        ch["t_validity"] = validity
        ch["t_arrival"] = arrival
        ch["t_processed"] = processed
        ch["t_decision"] = decision


def run(engine, scenario, ticks=200, dt=0.05, payload_for=None) -> list:
    """Evaluate a whole scenario. Returns one `SystemAssurance` per tick."""
    return [engine.evaluate(s) for s in
            SnapshotSource(scenario, ticks=ticks, dt=dt,
                           payload_for=payload_for)]


def summarize(results) -> dict:
    """What actually happened, in the terms §16 asks for."""
    if not results:
        return {"ticks": 0}
    systems, verdicts, limiting, codes = {}, {}, {}, {}
    fn_states: dict = {}
    for r in results:
        systems[r.system] = systems.get(r.system, 0) + 1
        verdicts[r.attribution.verdict] = \
            verdicts.get(r.attribution.verdict, 0) + 1
        for d in r.limiting_domains:
            limiting[d] = limiting.get(d, 0) + 1
        for name, v in r.functions.items():
            fn_states.setdefault(name, {})
            fn_states[name][v.state] = fn_states[name].get(v.state, 0) + 1
            for c in v.reason_codes:
                if c != "ALL_REQUIREMENTS_MET":
                    codes[c] = codes.get(c, 0) + 1
    last = results[-1]
    return {
        "ticks": len(results),
        "system_states": dict(sorted(systems.items())),
        "attribution_verdicts": dict(sorted(verdicts.items())),
        "limiting_domains": dict(sorted(limiting.items())),
        "function_states": {k: dict(sorted(v.items()))
                            for k, v in sorted(fn_states.items())},
        "reason_codes": dict(sorted(codes.items())),
        "final": {
            "system": last.system,
            "domains": dict(sorted(last.domains.items())),
            "functions": {k: v.state
                          for k, v in sorted(last.functions.items())},
            "limiting_domains": list(last.limiting_domains),
            "attribution": last.attribution.verdict,
            "candidates": [c.id for c in last.attribution.candidates],
            "common_cause": last.attribution.common_cause,
            "unsupported": list(last.attribution.unsupported),
        },
    }
