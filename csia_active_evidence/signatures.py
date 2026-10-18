"""The observation signature, and the lineage that stops double counting.

WHAT A SIGNATURE IS
-------------------
A fixed-order vector of the twelve implemented component residuals over one
evaluation window, each paired with its GATE. The gate is the whole reason
this is not simply a feature vector: an ineligible relation contributes
NOTHING, not a small amount, because a check that cannot run must not be
allowed to supply agreement.

LINEAGE, AND WHY IT IS RECORDED RATHER THAN ASSUMED AWAY
----------------------------------------------------------
`power_balance`, `source_impedance` and `charge_accounting` all read pack
current. `actuator_response` and `effort_drift` both read the duty command.
`loop_rate` and `clock_agreement` both read the loop clock. Treating those
as independent evidence and multiplying them would manufacture confidence
out of one measurement seen three times.

`CHANNELS` records, per residual, which raw channels it descends from, read
from the residual source rather than declared, and `independent_families`
collapses residuals sharing a raw channel into one family. Nothing in this
package multiplies per-residual scores; separation is decided per residual
and then counted BY FAMILY, so a pair separated only by three views of the
same current counts once.

WHAT A SEPARATION IS HERE
-------------------------
Set-valued, not statistical. For a hypothesis and a residual, the bounded
set is the [min, max] envelope of that residual over the seeds. Two
hypotheses are separated on a residual when their envelopes do not overlap
AND the gate was open in every seed of both. No distribution is assumed and
no p-value is computed: a pair either has a residual on which their observed
ranges are disjoint, or it does not.

THAT IS A WEAKER STATEMENT THAN IT LOOKS
-----------------------------------------
A min-max envelope over five seeds is not a confidence interval and does not
bound the population. It understates the spread, so this measure is
OPTIMISTIC about separation. It is reported as an observed disjointness over
a declared seed set and nothing more, and `RESULTS.md` says so where the
number appears.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, Tuple

import numpy as np

from csia_components import residuals as R
from csia_components import simulate as S

SCHEMA = "csia.active_evidence.signature/1"

#: Residual -> the raw telemetry channels it descends from. Asserted against
#: the residual source by tests/test_active_evidence_pairs.py.
CHANNELS: Dict[str, Tuple[str, ...]] = {
    "power_balance": ("pack_current", "branch_current"),
    "source_impedance": ("pack_current", "pack_voltage"),
    "charge_accounting": ("pack_current", "pack_voltage"),
    "actuator_response": ("duty", "vz"),
    "actuator_agreement": ("duty",),
    "effort_drift": ("duty",),
    "loop_rate": ("clock_a",),
    "bus_rate": ("frames_ok",),
    "clock_agreement": ("clock_a", "clock_b"),
    "thermal_rise": ("temperature", "branch_current"),
    "sequence_continuity": ("seq_gaps",),
    "error_rate": ("frames_err",),
}

ORDER = tuple(sorted(CHANNELS))

#: Physical scale per residual, in that residual's own units, with the basis
#: for each. A SEPARATION SMALLER THAN THIS IS NOT A SEPARATION.
#:
#: WHY THIS EXISTS, AND IT IS NOT A TUNING KNOB. The first run of
#: `tools/research/aea_pair_campaign.py` reported that a PASSIVE hover
#: separated 27 of 28 hypothesis pairs, which would have made active
#: evidence acquisition pointless and was entirely an artifact. Six of the
#: twelve residuals have ZERO-WIDTH envelopes in this simulator -- the
#: control loop reads true vertical velocity rather than a noisy one, and
#: the frame and sequence counters are integers -- so "the envelopes are
#: disjoint" degenerated into "these two floats are not equal". Pairs
#: separated on differences of 1e-17.
#:
#: Each scale below is either a DECLARED SENSOR NOISE from
#: `csia_components.simulate.SIGMA` or ONE COUNT of a counter, because a
#: counter cannot meaningfully differ by less than one count. None is
#: derived from the campaign it gates, and none was chosen after seeing a
#: result.
_WINDOW_S = 12.0
_FRAMES = _WINDOW_S * S.LOOP_HZ

SCALES: Dict[str, Tuple[float, str]] = {
    "power_balance": (
        S.SIGMA["pack_current"],
        "one sigma of the pack current channel; the residual is in amps"),
    "source_impedance": (
        S.SIGMA["pack_voltage"] / S.SIGMA["pack_current"] * 0.1,
        "voltage noise over current noise, the ohm-scale floor of a "
        "two-point impedance read; the residual is in ohms"),
    "charge_accounting": (
        S.SIGMA["pack_current"] * _WINDOW_S / 3600.0,
        "current noise integrated over the window; the residual is in "
        "amp-hours"),
    "actuator_response": (
        S.SIGMA["vz"] * S.LOOP_HZ,
        "vertical-velocity noise differentiated at the loop rate; the "
        "residual is an acceleration in m/s^2"),
    "actuator_agreement": (
        S.SIGMA["branch_current"],
        "one sigma of a branch current channel; the residual is the "
        "amp spread across motors"),
    "effort_drift": (
        0.01,
        "one percent of commanded duty, the smallest effort change an "
        "engineer would call a drift; declared, not measured, because this "
        "simulator's loop is noise-free and would otherwise report a zero "
        "scale"),
    "loop_rate": (
        S.SIGMA["loop_period"],
        "one sigma of the loop-period channel; the residual is in seconds"),
    "bus_rate": (
        1.0 / _WINDOW_S,
        "one frame per window expressed as a rate; a frame counter cannot "
        "differ by less than one frame"),
    "clock_agreement": (
        1.5e-6,
        "the specified relative drift between the two clocks, which is the "
        "quantity the relation is declared against"),
    "thermal_rise": (
        S.SIGMA["temperature"],
        "one sigma of the temperature channel; the residual is in kelvin"),
    "sequence_continuity": (
        1.0,
        "one sequence gap; a gap counter cannot differ by less than one"),
    "error_rate": (
        1.0 / _FRAMES,
        "one errored frame out of the window's frames; a counter again"),
}

#: How many scales apart two envelopes must be. Declared in the
#: preregistration and never swept.
SEPARATION_K = 1.0


def _args(name: str, reference_effort: float, baseline_rate):
    """Every residual's configuration, in one place, passed IN.

    `residuals.py` deliberately does not import the plant's constants where
    it can avoid it, so the caller supplies them. On a real vehicle these
    come from a datasheet or a commissioning run.
    """
    return {
        "power_balance": {"quiescent_a": S.QUIESCENT_A},
        "source_impedance": {"r_nominal": S.PACK_R_NOMINAL},
        "charge_accounting": {"capacity_ah": S.PACK_CAPACITY_AH},
        "actuator_response": {"k_thrust": S.K_THRUST, "mass_kg": S.MASS_KG,
                              "n_motors": S.N_MOTORS},
        "actuator_agreement": {},
        "effort_drift": {"reference_effort": reference_effort},
        "loop_rate": {"nominal_period": 1.0 / S.LOOP_HZ},
        "bus_rate": {"nominal_hz": S.LOOP_HZ},
        "clock_agreement": {"specified_drift_rate": 1.5e-6},
        "thermal_rise": {"thermal_k": S.THERMAL_K, "esc_r": S.ESC_R,
                         "motor": 0, "settle_s": S.THERMAL_TAU,
                         "fault_free_change_at": None},
        "sequence_continuity": {},
        "error_rate": {"baseline_rate": baseline_rate},
    }[name]


@dataclass(frozen=True)
class Signature:
    """One window's worth of evidence. Values and gates, never collapsed."""

    values: Dict[str, float]
    gates: Dict[str, float]

    def open_residuals(self) -> Tuple[str, ...]:
        return tuple(k for k in ORDER if self.gates.get(k, 0.0) == 1.0)

    def to_dict(self) -> dict:
        return asdict(self)


def signature(tel, lo: float, hi: float, *, reference_effort: float,
              baseline_rate=None) -> Signature:
    """Every implemented residual over one window.

    A residual that RAISES is recorded as gated shut with a NaN value, never
    as a zero. MX-021 was a swallowed exception that read as "not detected"
    and produced a finding about the frozen core out of a typo.
    """
    values, gates = {}, {}
    for name in ORDER:
        fn = getattr(R, name)
        try:
            value, gate = fn(tel, lo, hi, **_args(name, reference_effort,
                                                  baseline_rate))
        except Exception as exc:            # noqa: BLE001 - recorded, not hidden
            values[name] = float("nan")
            gates[name] = 0.0
            values[name + "__error"] = repr(exc)[:120]
            continue
        values[name] = float(value)
        gates[name] = float(gate)
    return Signature(values=values, gates=gates)


def independent_families(names) -> Tuple[Tuple[str, ...], ...]:
    """Collapse residuals sharing a raw channel into one family.

    Union-find over the channel graph. Two residuals reading the same raw
    channel are in the same family whatever they are called, so a pair
    separated by three views of pack current counts once.
    """
    names = [n for n in names if n in CHANNELS]
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if set(CHANNELS[a]) & set(CHANNELS[b]):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb

    groups: Dict[str, list] = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    return tuple(tuple(sorted(g)) for g in
                 sorted(groups.values(), key=lambda g: sorted(g)))


@dataclass(frozen=True)
class Envelope:
    """The observed [min, max] of one residual over a seed set.

    NOT a confidence interval. See the module docstring: it understates the
    spread and is therefore optimistic about separation.
    """

    low: float
    high: float
    n: int
    gate_open_in_every_seed: bool


def envelopes(signatures) -> Dict[str, Envelope]:
    signatures = list(signatures)
    out = {}
    for name in ORDER:
        vals = [s.values.get(name, float("nan")) for s in signatures]
        gates = [s.gates.get(name, 0.0) for s in signatures]
        finite = [v for v in vals if not math.isnan(v)]
        if not finite:
            out[name] = Envelope(float("nan"), float("nan"), 0, False)
            continue
        out[name] = Envelope(min(finite), max(finite), len(finite),
                             all(g == 1.0 for g in gates))
    return out


def gap(a: Envelope, b: Envelope) -> float:
    """Signed gap between two envelopes. Positive means disjoint."""
    return max(b.low - a.high, a.low - b.high)


def separating_residuals(a: Dict[str, Envelope], b: Dict[str, Envelope],
                         k: float = SEPARATION_K) -> Tuple[str, ...]:
    """Residuals on which two hypotheses are separated BY A PHYSICAL MARGIN.

    Three conditions, all necessary:

      * the gate was open in every seed of BOTH hypotheses. An ineligible
        relation cannot contribute a separating score -- control 8 of the
        twelve, enforced here rather than checked afterwards;
      * the envelopes are disjoint;
      * the gap exceeds `k` times the residual's declared physical scale.
        Without this last condition a zero-width envelope makes any
        difference at all a separation, which is how a passive hover came
        to "separate" 27 of 28 pairs on differences of 1e-17.
    """
    out = []
    for name in ORDER:
        ea, eb = a.get(name), b.get(name)
        if ea is None or eb is None:
            continue
        if not (ea.gate_open_in_every_seed and eb.gate_open_in_every_seed):
            continue
        if math.isnan(ea.low) or math.isnan(eb.low):
            continue
        scale = SCALES[name][0]
        if gap(ea, eb) > k * scale:
            out.append(name)
    return tuple(out)


def separated(a, b, k: float = SEPARATION_K) -> dict:
    """Is this pair separated, and by how many INDEPENDENT families?"""
    res = separating_residuals(a, b, k)
    fams = independent_families(res)
    return {"separated": bool(res), "residuals": list(res),
            "independent_families": [list(f) for f in fams],
            "family_count": len(fams), "k": k}
