"""A library of diagnostic excitations, with their statistics COMPUTED.

WHAT A PROBE IS HERE
--------------------
A bounded, time-limited perturbation of a setpoint that a vehicle is
ALREADY tracking. It is not a manoeuvre, not a mode change and not a command
to an actuator: `csia_components.simulate.Platform` takes a `setpoint`
callable and the probe is a function of time added to it. Nothing in this
module transmits anything, and nothing in this module decides that a probe
may run -- `authority.py` does that, separately, and it can refuse.

THE DESIGN RULE THIS MODULE IS BUILT AROUND
--------------------------------------------
`identifiability.py` shows that a probe whose current correlates with time
aliases open-circuit-voltage drift straight into the resistance estimate,
with lever arm cov(t, I) / var(I). A ramp is the worst case. A sine is much
better but NOT zero: 20 s of 0.5 Hz leaves a lever arm of -0.0795 s, which
survives as the dominant error term for a strong probe.

    A COMMANDED PROFILE SYMMETRIC ABOUT THE WINDOW MIDPOINT HAS ZERO LEVER
    ARM, EXACTLY, AT EVERY AMPLITUDE AND EVERY WINDOW.

If I(t) = I(T - t) then pairing the sample at t with the sample at T - t
makes every contribution to cov(t, I) cancel against its mirror. Every probe
in `LIBRARY` is therefore a palindrome in time, and `tests/test_probes.py`
asserts it sample by sample rather than trusting the construction.

AND THAT GUARANTEE IS ABOUT THE COMMAND, NOT THE CURRENT. MEASURED.
--------------------------------------------------------------------
An earlier revision of this docstring said the symmetric design "removes the
one error term whose magnitude depends on a quantity that is never known
precisely". `tools/research/active_evidence_campaign.py` measured that claim
against the plant and it is FALSE as stated. The vehicle is a closed loop
with integral action; its current response LAGS the command; and a lag turns
a palindrome into something that is not one:

    probe            realised lever arm     realised drift bias
    triangle_soft         -1.138 s               -0.0052 ohm
    doublet               -0.943 s               -0.0043 ohm
    triangle              -0.860 s               -0.0040 ohm
    step_hold             -0.584 s               -0.0027 ohm
    burst_2hz             +0.019 s               +0.00009 ohm
    burst_wide            +0.004 s               +0.00002 ohm

The commanded lever arm is ~1e-16 for all six. The realised bias for
`triangle_soft` is LARGER THAN THE SMALLEST CHANGE THE CAMPAIGN TRIED TO
RESOLVE. What survives of the design rule is narrower and still useful:

    A MULTI-CYCLE SYMMETRIC BURST KEEPS THE PROPERTY THROUGH THE LOOP,
    BECAUSE THE LAG AVERAGES ACROSS CYCLES. A SINGLE EXCURSION DOES NOT.

Two consequences, both load-bearing:

  * `burst_2hz` and `burst_wide` are the only probes whose drift behaviour
    may be predicted from their definition. For every other shape the lever
    arm must be MEASURED from the realised current with
    `identifiability.ExcitationStats.from_measured`, never taken from
    `Probe.stats`, which knows only what was commanded.
  * a differential comparison -- the same probe on two packs -- cancels the
    bias and is unaffected. An absolute comparison against a hypothesis
    interval, which is what `updater.py` does, is not. The campaign scores
    the first, so the campaign could not have caught this on its cell
    verdicts alone, and did not: it was caught by measuring the realisation
    separately and comparing it to the prediction.

WHAT IS COMPUTED AND WHAT IS DECLARED
--------------------------------------
Each `Probe` DECLARES only what a human decided: its name, its amplitude in
amps, its duration, and its `cost` fields. Everything that decides whether
it works -- variance, sample count, lever arm, and therefore whether it
meets a requirement -- is COMPUTED from the realised profile by
`identifiability.ExcitationStats.from_profile`. A probe cannot claim a
correlation it does not have, which is the failure `csia_stress/fault_params.py`
had to be written to stop on the fault-injection side.

THE AMPLITUDES ARE NOT INVENTED HERE
-------------------------------------
`CURRENT_PER_AMP_OF_VZ` converts a vertical-velocity setpoint perturbation
into a pack-current excursion, and it is MEASURED from the component
simulator by `tools/research/active_evidence_campaign.py` rather than
asserted. The value recorded here is the default used for planning when no
measurement has been made, and it is labelled as such.

WHAT THIS IS NOT
----------------
No probe here has been run on any vehicle. The costs are declared
quantities in declared units, not measurements. The energy figures are
arithmetic on a nominal hover current, not a battery test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Callable, Tuple

import numpy as np

from .identifiability import ExcitationStats, NoiseModel, ProbeRequirement

#: Amps of pack current per m/s of commanded vertical velocity, at hover on
#: the 1.5 kg reference platform.
#:
#: THIS NUMBER IS MEASURED, AND IT REPLACED A GUESS. The first revision of
#: this file carried a planning default of 9.0 A per m/s, invented to have
#: something to compute with. The campaign measured 2.52 on the reference
#: platform: the guess was optimistic by a factor of 3.6, and every
#: excitation statistic derived from it overstated the probe's power, which
#: is the dangerous direction. A caller on another vehicle MUST re-measure;
#: this is one platform's number, not a constant of nature.
CURRENT_PER_AMP_OF_VZ = 2.52
CURRENT_PER_AMP_OF_VZ_BASIS = (
    "measured by tools/research/active_evidence_campaign.py on the held-out "
    "reference seed, as cov(vz_setpoint, pack_current)/var(vz_setpoint) over "
    "the probe window; tests/test_active_evidence.py couples this constant "
    "to that measurement so it cannot drift back into a guess")

LOOP_HZ = 50.0


@dataclass(frozen=True)
class Probe:
    """One named excitation. Shape is a function of NORMALISED time in [0,1].

    `shape` returns a dimensionless waveform which is scaled by `vz_amplitude`
    to give a vertical-velocity perturbation in m/s. Keeping the shape
    dimensionless is what lets the same waveform be scored at several
    amplitudes without a second definition of it.
    """

    name: str
    shape: Callable[[np.ndarray], np.ndarray]
    vz_amplitude: float          # m/s, peak of the setpoint perturbation
    duration_s: float
    rationale: str
    disturbs: str                # what a human or payload would notice

    def times(self, hz: float = LOOP_HZ) -> np.ndarray:
        n = max(int(round(self.duration_s * hz)), 3)
        return np.arange(n, dtype=float) / hz

    def setpoint(self, hz: float = LOOP_HZ) -> np.ndarray:
        """The commanded perturbation, m/s, over the probe window."""
        t = self.times(hz)
        span = max(float(t[-1] - t[0]), 1e-12)
        return self.vz_amplitude * np.asarray(
            self.shape((t - t[0]) / span), dtype=float)

    def as_setpoint_fn(self, start_s: float, hz: float = LOOP_HZ) -> Callable:
        """A `Platform(setpoint=...)` callable: zero outside the window.

        Returning zero outside the window is what makes the probe BOUNDED in
        time. There is no mode to leave and no state to reset: after
        `start_s + duration_s` the vehicle is being asked for exactly what it
        was asked for before.
        """
        sp = self.setpoint(hz)
        n = sp.size

        def fn(t: float) -> float:
            if t < start_s:
                return 0.0
            k = int(round((t - start_s) * hz))
            return float(sp[k]) if 0 <= k < n else 0.0

        return fn

    def is_time_symmetric(self, hz: float = LOOP_HZ) -> bool:
        sp = self.setpoint(hz)
        return bool(np.allclose(sp, sp[::-1], atol=1e-12))

    def predicted_current(self, hz: float = LOOP_HZ,
                          amps_per_vz: float = CURRENT_PER_AMP_OF_VZ,
                          hover_a: float = 20.0) -> np.ndarray:
        """PREDICTED, and named so. The campaign measures the real thing."""
        return hover_a + amps_per_vz * self.setpoint(hz)

    def stats(self, hz: float = LOOP_HZ,
              amps_per_vz: float = CURRENT_PER_AMP_OF_VZ) -> ExcitationStats:
        """Computed from the realised waveform. Never declared."""
        return ExcitationStats.from_profile(
            self.times(hz), self.predicted_current(hz, amps_per_vz))

    def energy_cost_as(self, hover_a: float = 20.0,
                       amps_per_vz: float = CURRENT_PER_AMP_OF_VZ,
                       hz: float = LOOP_HZ) -> float:
        """Amp-seconds of EXTRA charge drawn, relative to holding station.

        The integral of |excess current|, which is what a probe actually
        costs a pack. Arithmetic on a nominal hover current, not a battery
        measurement.
        """
        return float(np.sum(np.abs(amps_per_vz * self.setpoint(hz))) / hz)

    def to_dict(self, hz: float = LOOP_HZ) -> dict:
        st = self.stats(hz)
        return {"name": self.name, "vz_amplitude_m_s": self.vz_amplitude,
                "duration_s": self.duration_s, "rationale": self.rationale,
                "disturbs": self.disturbs,
                "time_symmetric": self.is_time_symmetric(hz),
                "energy_cost_as": self.energy_cost_as(hz=hz),
                "stats": st.to_dict()}


# --- shapes, all palindromic in normalised time ----------------------------

def _cosine_burst(cycles: int):
    """Whole cycles of a cosine, phased so the window is symmetric.

    Cosine rather than sine: cos is even about the window midpoint once it
    is centred, so the lever arm is zero by construction. A sine is odd and
    leaves the residual correlation the module docstring quotes.
    """
    def shape(u):
        return np.cos(2.0 * np.pi * cycles * (u - 0.5))
    return shape


def _symmetric_doublet(u):
    """Up, down, up: a single smooth excursion and back, symmetric."""
    return np.cos(2.0 * np.pi * (u - 0.5)) * (1.0 - 2.0 * np.abs(u - 0.5))


def _symmetric_triangle(u):
    """Linear out and linear back. The cheapest symmetric shape there is."""
    return 1.0 - 4.0 * np.abs(u - 0.5)


def _symmetric_step(u):
    """A held excursion with matched entry and exit."""
    return np.where(np.abs(u - 0.5) < 0.25, 1.0, -1.0)


LIBRARY: Tuple[Probe, ...] = (
    Probe(name="hold", shape=lambda u: np.zeros_like(u), vz_amplitude=0.0,
          duration_s=4.0,
          rationale=("the null probe. It exists so a selector can SCORE "
                     "doing nothing against every alternative instead of "
                     "special-casing it, and so a campaign has a negative "
                     "control that costs nothing and must resolve nothing"),
          disturbs="nothing"),
    Probe(name="triangle_soft", shape=_symmetric_triangle, vz_amplitude=0.15,
          duration_s=4.0,
          rationale="smallest excursion in the library; a first attempt",
          disturbs="a gentle rise and fall of about 0.3 m over 4 s"),
    Probe(name="triangle", shape=_symmetric_triangle, vz_amplitude=0.40,
          duration_s=6.0,
          rationale="linear out and back; no spectral content to argue about",
          disturbs="about 1.2 m of altitude excursion over 6 s"),
    Probe(name="doublet", shape=_symmetric_doublet, vz_amplitude=0.50,
          duration_s=6.0,
          rationale=("a single smooth excursion; the gentlest shape that "
                     "still reaches a large current swing"),
          disturbs="about 1 m of altitude excursion over 6 s"),
    Probe(name="burst_2hz", shape=_cosine_burst(4), vz_amplitude=0.35,
          duration_s=8.0,
          rationale=("four whole cycles: high variance for a bounded "
                     "altitude excursion, because the vehicle returns "
                     "through the setpoint four times"),
          disturbs="a 0.35 m/s oscillation for 8 s"),
    Probe(name="burst_wide", shape=_cosine_burst(6), vz_amplitude=0.60,
          duration_s=12.0,
          rationale=("the largest probe in the library; reserved for a "
                     "small delta_r that nothing cheaper can resolve"),
          disturbs="a 0.6 m/s oscillation for 12 s"),
    Probe(name="step_hold", shape=_symmetric_step, vz_amplitude=0.30,
          duration_s=6.0,
          rationale=("a held excursion with matched entry and exit; the "
                     "highest variance per metre of altitude used"),
          disturbs="a 0.3 m/s climb then descent, 6 s"),
)

BY_NAME = {p.name: p for p in LIBRARY}


def probe(name: str) -> Probe:
    if name not in BY_NAME:
        raise KeyError(f"no probe named {name!r}; have "
                       f"{sorted(BY_NAME)}")
    return BY_NAME[name]


def catalogue(hz: float = LOOP_HZ,
              amps_per_vz: float = CURRENT_PER_AMP_OF_VZ) -> list:
    """Every probe with its computed statistics. For an artifact."""
    return [p.to_dict(hz) for p in LIBRARY]


def meeting(requirement: ProbeRequirement, hz: float = LOOP_HZ,
            amps_per_vz: float = CURRENT_PER_AMP_OF_VZ) -> list:
    """Which probes are PREDICTED to meet a requirement, and why not.

    Returns every probe with its verdict, including the failures. A function
    that returned only the successes would make an empty result
    indistinguishable from an empty library.
    """
    out = []
    for p in LIBRARY:
        verdict = requirement.met_by(p.stats(hz, amps_per_vz))
        out.append({"probe": p.name, "met": verdict["met"],
                    "failed": verdict["failed"],
                    "energy_cost_as": p.energy_cost_as(
                        amps_per_vz=amps_per_vz, hz=hz),
                    "duration_s": p.duration_s,
                    "vz_amplitude_m_s": p.vz_amplitude,
                    "margins": verdict["margins"]})
    return out
