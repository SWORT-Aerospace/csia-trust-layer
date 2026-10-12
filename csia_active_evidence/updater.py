"""What a probe's result does to the hypothesis set. SET-VALUED, AND IT ABSTAINS.

WHY NOT A POSTERIOR
-------------------
A posterior over fault hypotheses would require a prior over them and a
likelihood for each, and neither exists for a pack that has been degrading
for an unknown number of cycles. `csia/diagnosis/bayes.py` maintains a
softmax posterior inside the frozen core and the repository is explicit that
its outputs are model states and not calibrated probabilities. Rather than
add a second uncalibrated number, this module does the thing the evidence
actually supports:

    KEEP EVERY HYPOTHESIS WHOSE PREDICTED OBSERVATION INTERVAL OVERLAPS THE
    MEASURED INTERVAL. DISCARD THE REST. REPORT THE SET.

The prediction goes through the SAME bias model the probe was selected with.
A hypothesis of R = 0.09 ohm does not predict an observation of 0.09: it
predicts lambda * (0.09 + d * lever), which for a weak probe may be nowhere
near it. Comparing a hypothesis to a raw estimate without that map is the
mistake this whole package exists to make impossible.

FOUR OUTCOMES, AND THE FOURTH IS THE ONE USUALLY MISSING
---------------------------------------------------------
  RESOLVED            exactly one hypothesis survives
  STILL_AMBIGUOUS     more than one survives; the probe helped or did not
  NO_HYPOTHESIS_SURVIVES  the measurement is outside EVERY hypothesis's
                      predicted interval

The fourth is the honest one. It does not mean the fault is unknown, it
means THE MODEL IS WRONG -- the hypothesis set is incomplete, or the noise
model understates the channels, or the linear relation does not hold in this
regime. Silently returning "ambiguous" there, or quietly keeping the nearest
hypothesis, would convert a falsification of the model into a routine
diagnostic outcome. It is reported as its own verdict and the caller is told
not to act on it.

ABSTENTION IS PRESERVED
-----------------------
`update` never promotes anything. It returns a set and a verdict; it does
not change a trust value, does not write to any capability state, and has no
path to the frozen core. A caller holding STILL_AMBIGUOUS after an
authorized, executed probe is in a strictly better documented position than
before and in exactly the same authority position: none.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Tuple

from .identifiability import (ExcitationStats, NoiseModel, estimate_sd,
                              expected_estimate)

SCHEMA = "csia.active_evidence.update/1"

RESOLVED = "RESOLVED"
STILL_AMBIGUOUS = "STILL_AMBIGUOUS"
NO_SURVIVOR = "NO_HYPOTHESIS_SURVIVES"
NOT_EVALUABLE = "NOT_EVALUABLE"


@dataclass(frozen=True)
class Hypothesis:
    """A named causal hypothesis, as a BOUNDED RANGE of the parameter.

    A range rather than a point because "the pack has degraded" is not a
    claim about a specific resistance. The bounds are engineering
    declarations and are carried into the artifact so a reader can see what
    was assumed.
    """

    name: str
    r_low: float
    r_high: float
    basis: str

    def __post_init__(self):
        if not self.r_low <= self.r_high:
            raise ValueError(f"{self.name}: r_low must not exceed r_high")

    def predicted_interval(self, stats: ExcitationStats, noise: NoiseModel,
                           k_sigma: float) -> Tuple[float, float]:
        """What this hypothesis predicts the ESTIMATE will be.

        Through the attenuation and drift map, not the raw resistance. The
        scatter is evaluated at both ends of the range because it depends on
        the resistance itself.
        """
        lo = expected_estimate(self.r_low, stats, noise)
        hi = expected_estimate(self.r_high, stats, noise)
        lo, hi = min(lo, hi), max(lo, hi)
        pad_lo = k_sigma * estimate_sd(stats, noise, self.r_low)
        pad_hi = k_sigma * estimate_sd(stats, noise, self.r_high)
        return lo - max(pad_lo, pad_hi), hi + max(pad_lo, pad_hi)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Update:
    verdict: str
    surviving: Tuple[str, ...]
    eliminated: Tuple[str, ...]
    measured: float
    intervals: dict
    k_sigma: float
    excitation_source: str
    note: str
    schema: str = SCHEMA

    def to_dict(self) -> dict:
        out = asdict(self)
        out["surviving"] = list(self.surviving)
        out["eliminated"] = list(self.eliminated)
        return out


def update(measured_r: float, hypotheses, stats: ExcitationStats,
           noise: NoiseModel, k_sigma: float = 3.0) -> Update:
    """Eliminate the hypotheses the measurement is inconsistent with.

    `stats` must come from the probe AS EXECUTED, not as requested. A
    clipped probe has different statistics and predicts different intervals;
    passing the requested probe's statistics here would be the same
    train-on-test shape as MX-030, one level up.
    """
    hypotheses = tuple(hypotheses)
    if not hypotheses:
        raise ValueError("an empty hypothesis set cannot be updated; "
                         "eliminating nothing from nothing is not a result")

    intervals, surviving, eliminated = {}, [], []
    for h in hypotheses:
        lo, hi = h.predicted_interval(stats, noise, k_sigma)
        intervals[h.name] = {"low": lo, "high": hi,
                             "r_low": h.r_low, "r_high": h.r_high}
        (surviving if lo <= measured_r <= hi else eliminated).append(h.name)

    if not surviving:
        return Update(
            verdict=NO_SURVIVOR, surviving=(), eliminated=tuple(eliminated),
            measured=measured_r, intervals=intervals, k_sigma=k_sigma,
            excitation_source=stats.source,
            note=("the measurement lies outside every hypothesis's predicted "
                  "interval. This is a statement about the MODEL, not about "
                  "the vehicle: the hypothesis set is incomplete, the noise "
                  "model understates a channel, or the linear relation does "
                  "not hold here. Do not act on it as a diagnosis"))

    if len(surviving) == 1:
        return Update(
            verdict=RESOLVED, surviving=tuple(surviving),
            eliminated=tuple(eliminated), measured=measured_r,
            intervals=intervals, k_sigma=k_sigma,
            excitation_source=stats.source,
            note=("exactly one hypothesis is consistent with the "
                  "measurement at this confidence. It is not promoted, "
                  "scored or acted on here; it is reported"))

    return Update(
        verdict=STILL_AMBIGUOUS, surviving=tuple(surviving),
        eliminated=tuple(eliminated), measured=measured_r,
        intervals=intervals, k_sigma=k_sigma,
        excitation_source=stats.source,
        note=("more than one hypothesis remains consistent. The probe may "
              "have eliminated some and it did not eliminate enough; "
              "abstention is preserved and the remaining set is the result"))


def separates(hypotheses, stats: ExcitationStats, noise: NoiseModel,
              k_sigma: float = 3.0) -> dict:
    """Could this excitation separate these hypotheses AT ALL? Ask BEFORE.

    Pure prediction, no measurement. Two hypotheses whose predicted
    intervals overlap cannot be told apart by this probe whatever it
    returns, and running it to find that out wastes the vehicle's energy on
    a question that was already answered on paper.
    """
    hypotheses = tuple(hypotheses)
    iv = {h.name: h.predicted_interval(stats, noise, k_sigma)
          for h in hypotheses}
    overlapping = []
    names = sorted(iv)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if iv[a][0] <= iv[b][1] and iv[b][0] <= iv[a][1]:
                overlapping.append((a, b))
    return {"intervals": {k: {"low": v[0], "high": v[1]}
                          for k, v in iv.items()},
            "inseparable_pairs": overlapping,
            "separates_all": not overlapping,
            "k_sigma": k_sigma}
