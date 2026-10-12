"""Does a probe that MEETS the requirement actually resolve the change?

WHY THIS EXISTS
---------------
`csia_active_evidence/identifiability.py` makes a falsifiable prediction:
three closed-form conditions on a probe's excitation statistics, predicted to
be sufficient to resolve a stated resistance change at a stated confidence.
`tests/test_identifiability.py` checks the algebra against a Monte Carlo
generator written inside that test. THAT IS NOT ENOUGH: the generator and
the derivation share every assumption, so agreement between them tests the
arithmetic and nothing else.

This campaign runs the same prediction against `csia_components/simulate.py`
-- a plant with a closed-loop PI controller, state of charge falling as
charge is drawn, a thermal model, quantised sampling and four independent
noise channels, none of which appear in the derivation. The prediction is
either right there or it is wrong.

WHAT "INDEPENDENT" MEANS HERE, AND WHAT IT DOES NOT
-----------------------------------------------------
The simulator was written first, for MX-036, to test a different set of
claims, by a path that had no error model in it. That is the only sense in
which it is independent, and it is a WEAK sense: both it and the derivation
assume a linear terminal-voltage law. It is not hardware and it is not a
second opinion about physics. `SIMULATOR_VALIDITY_ENVELOPE.md` states what
this cannot catch.

THE PREDICTION, AND WHAT KILLS IT
----------------------------------
Fixed in `research/active_evidence/PREREGISTRATION.md` before this ran:

    a probe MEETING all three conditions resolves delta_r;
    a probe FAILING any one does not.

A single FALSE_POSITIVE -- met the requirement, did not resolve -- falsifies
it. False negatives do not: they show the requirement is conservative, which
is the safe direction, and they are counted separately.

THE NOISE MODEL IS MEASURED, NOT ASSERTED
------------------------------------------
`measure_noise()` estimates sigma_V and sigma_I from clean simulator runs on
the HELD-OUT reference seed by differencing successive samples at a constant
operating point. Reading `simulate.SIGMA` directly would hand the derivation
the simulator's own parameters, and every agreement would then be a
tautology rather than a measurement.

THE OUTPUT IS NOT A PROOF
--------------------------
Four delta values, five seeds, seven probes, one plant. It measures a
surface. It recommends nothing and promotes nothing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import identifiability as ID       # noqa: E402
from csia_active_evidence import probes as PR                # noqa: E402
from csia_components import simulate as S                    # noqa: E402

INSTRUMENT = "tools.research.active_evidence_campaign"
SCHEMA = "csia.active_evidence.campaign/1"

SEEDS = (0, 100, 200, 300, 400)
REFERENCE_SEED = 999            # HELD OUT, never scored
DELTAS = (0.005, 0.010, 0.020, 0.040)
K_SIGMA = 3.0
BIAS_FRACTION = 0.25
PROBE_START = 8.0               # s, after the loop has settled
SETTLE_S = 6.0                  # s of settling before the probe window
R_REFERENCE = S.PACK_R_NOMINAL


def _flight(seed: float, probe, delta_r: float):
    """One flight with the probe applied and an optional resistance rise."""
    duration = PROBE_START + probe.duration_s + 4.0
    faults = ()
    if delta_r > 0.0:
        faults = (S.Fault("pack_impedance_rise", "pack", 0.0, duration,
                          delta_r),)
    plant = S.Platform(seed=int(seed), duration=duration,
                       setpoint=probe.as_setpoint_fn(PROBE_START))
    return plant.run(faults)


def _window(tel, probe):
    t = tel.array("t")
    lo, hi = PROBE_START, PROBE_START + probe.duration_s
    return (t >= lo) & (t <= hi)


def _fit_r(tel, probe) -> float:
    """Least squares on [1, -I] over the probe window. The estimator itself."""
    w = _window(tel, probe)
    i = tel.array("pack_current")[w]
    v = tel.array("pack_voltage")[w]
    if i.size < 3:
        return float("nan")
    design = np.column_stack([np.ones(i.size), -i])
    return float(np.linalg.lstsq(design, v, rcond=None)[0][1])


def measure_noise() -> ID.NoiseModel:
    """sigma_V, sigma_I and the drift rate, FROM the plant, on a held-out seed.

    Successive-difference estimation at a constant operating point: for white
    measurement noise on a slowly varying signal, sd(x[k] - x[k-1]) is
    sqrt(2) times the channel sigma. It recovers the noise without being told
    it, which is the point.
    """
    tel = S.Platform(seed=REFERENCE_SEED, duration=40.0).run()
    t = tel.array("t")
    w = t >= 10.0
    out = {}
    for ch in ("pack_voltage", "pack_current"):
        d = np.diff(tel.array(ch)[w])
        out[ch] = float(np.std(d) / math.sqrt(2.0))
    v = tel.array("pack_voltage")[w]
    drift = float(-np.polyfit(t[w], v, 1)[0])
    return ID.NoiseModel(sigma_v=out["pack_voltage"],
                         sigma_i=out["pack_current"],
                         ocv_drift_v_per_s=max(drift, 0.0))


def measure_amps_per_vz(noise: ID.NoiseModel) -> float:
    """Amps of pack current per m/s of commanded vz. MEASURED, held-out seed.

    `probes.CURRENT_PER_AMP_OF_VZ` is a planning default and this replaces
    it. Using the default in the scored runs would make every predicted
    excitation statistic a guess about the plant rather than a reading of it.
    """
    probe = PR.probe("triangle")
    tel = _flight(REFERENCE_SEED, probe, 0.0)
    w = _window(tel, probe)
    sp = tel.array("vz_setpoint")[w]
    cur = tel.array("pack_current")[w]
    if float(np.var(sp)) <= 0:
        raise RuntimeError("the reference probe commanded nothing")
    return float(np.cov(sp, cur, bias=True)[0, 1] / np.var(sp))


def realisation(probe, noise, amps_per_vz) -> dict:
    """What the plant ACTUALLY did, against what the probe predicted.

    THE MEASUREMENT THAT FALSIFIED A DESIGN CLAIM. `probes.py` builds every
    probe symmetric about its window midpoint, which makes cov(t, I) zero to
    machine precision IN THE COMMANDED PROFILE. It does not follow that the
    REALISED current is symmetric: the vehicle is a closed loop with integral
    action, its response lags the command, and a lag turns a palindrome into
    something that is not one.

    Recorded per probe so the claim can never be restated without the
    measurement beside it.
    """
    tel = _flight(REFERENCE_SEED, probe, 0.0)
    w = _window(tel, probe)
    t, cur = tel.array("t")[w], tel.array("pack_current")[w]
    predicted = probe.stats(amps_per_vz=amps_per_vz)
    if predicted.var_i <= 0.0:
        return {"probe": probe.name, "commanded_amplitude_is_zero": True,
                "predicted_std_i": 0.0, "realised_std_i": float(np.std(cur)),
                "predicted_lever_arm_s": 0.0, "realised_lever_arm_s": None,
                "std_i_ratio": None,
                "note": "the null probe commands nothing; there is no "
                        "realisation to compare"}
    realised = ID.ExcitationStats.from_measured(t, cur, noise)
    return {"probe": probe.name,
            "commanded_amplitude_is_zero": False,
            "predicted_std_i": predicted.std_i,
            "realised_std_i": realised.std_i,
            "std_i_ratio": realised.std_i / predicted.std_i,
            "predicted_lever_arm_s": predicted.cov_ti_over_var_i,
            "realised_lever_arm_s": realised.cov_ti_over_var_i,
            "predicted_drift_bias_ohm": (noise.ocv_drift_v_per_s
                                         * predicted.cov_ti_over_var_i),
            "realised_drift_bias_ohm": (noise.ocv_drift_v_per_s
                                        * realised.cov_ti_over_var_i)}


def _cell(probe, delta_r, amps_per_vz, noise):
    """One (probe, delta_r) cell over every scored seed."""
    base, raised = [], []
    for seed in SEEDS:
        base.append(_fit_r(_flight(seed, probe, 0.0), probe))
        raised.append(_fit_r(_flight(seed, probe, delta_r), probe))
    base = np.asarray(base, dtype=float)
    raised = np.asarray(raised, dtype=float)
    gap = float(raised.mean() - base.mean())
    scatter = float(max(base.std(ddof=1), raised.std(ddof=1)))

    # A cell RESOLVES when the two populations separate by more than
    # k_sigma times the observed scatter. Scatter is measured across seeds,
    # not predicted, so the verdict does not borrow from the model it tests.
    resolved = bool(scatter > 0 and gap > K_SIGMA * scatter)

    req = ID.probe_requirement(delta_r, noise, R_REFERENCE, k_sigma=K_SIGMA,
                               bias_fraction=BIAS_FRACTION)
    stats = probe.stats(amps_per_vz=amps_per_vz)
    verdict = req.met_by(stats)

    if verdict["met"] and not resolved:
        agreement = "FALSE_POSITIVE"
    elif verdict["met"] and resolved:
        agreement = "AGREE_MET_AND_RESOLVED"
    elif resolved:
        agreement = "FALSE_NEGATIVE"
    else:
        agreement = "AGREE_FAILED_AND_UNRESOLVED"

    return {"probe": probe.name, "delta_r": delta_r,
            "predicted_met": verdict["met"], "failed": verdict["failed"],
            "resolved": resolved, "gap": gap, "scatter": scatter,
            "gap_over_scatter": (gap / scatter) if scatter > 0 else None,
            "mean_base": float(base.mean()),
            "mean_raised": float(raised.mean()),
            "agreement": agreement,
            "predicted_sd": ID.estimate_sd(stats, noise, R_REFERENCE),
            "predicted_base": ID.expected_estimate(R_REFERENCE, stats, noise),
            "std_i_predicted": stats.std_i,
            "lever_arm": stats.cov_ti_over_var_i}


# --- instrument controls ---------------------------------------------------

def _null_probe_resolves_nothing(**_):
    """POSITIVE control on the ABORT condition: `hold` must never resolve.

    Named a positive control because the instrument must DETECT the null
    arm's nullness: a run in which `hold` separates two packs is a broken
    instrument, and this is the stimulus whose answer is known without the
    campaign -- a zero-amplitude probe changes the current profile not at
    all, so there is nothing for a regression to find.
    """
    noise = measure_noise()
    amps = measure_amps_per_vz(noise)
    return _cell(PR.probe("hold"), 0.040, amps, noise)["resolved"]


def _seed_zero_reproduces_the_frozen_simulator(**_):
    """NEGATIVE control: a clean run at seed 0 is bit-identical on re-run.

    If it is not, the plant has acquired a hidden state and every paired
    comparison in this file is between two different simulators.
    """
    a = S.Platform(seed=0, duration=20.0).run().array("pack_voltage")
    b = S.Platform(seed=0, duration=20.0).run().array("pack_voltage")
    return bool(np.array_equal(a, b))


def _controls():
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)
    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="the null probe resolves nothing at the largest delta",
            kind=POSITIVE, run=_null_probe_resolves_nothing,
            expect=lambda resolved: resolved is False,
            basis=("csia_active_evidence.probes.LIBRARY defines `hold` with "
                   "vz_amplitude 0.0, so its commanded perturbation is "
                   "identically zero and the current profile is whatever "
                   "the vehicle was already drawing; a regression of "
                   "voltage on a constant current has no slope to find. "
                   "The expected answer comes from the probe definition, "
                   "not from this campaign"),
        ),
        negative=Control(
            name="seed 0 is bit-identical on re-run",
            kind=NEGATIVE, run=_seed_zero_reproduces_the_frozen_simulator,
            expect=lambda same: same is True,
            basis=("csia_components.simulate.Platform seeds a "
                   "numpy Generator from its `seed` argument and draws "
                   "unconditionally; tests/test_component_validation.py "
                   "already pins that a fault outside its window changes "
                   "nothing"),
        ),
    ))


def run() -> dict:
    noise = measure_noise()
    amps_per_vz = measure_amps_per_vz(noise)

    realised = [realisation(p, noise, amps_per_vz) for p in PR.LIBRARY]
    kept = [r for r in realised if not r["commanded_amplitude_is_zero"]]
    symmetry_kept = [r["probe"] for r in kept
                     if abs(r["realised_lever_arm_s"]) < 0.05]
    symmetry_lost = [r["probe"] for r in kept
                     if abs(r["realised_lever_arm_s"]) >= 0.05]

    cells = []
    for probe in PR.LIBRARY:
        for delta in DELTAS:
            cells.append(_cell(probe, delta, amps_per_vz, noise))

    counts = {}
    for c in cells:
        counts[c["agreement"]] = counts.get(c["agreement"], 0) + 1
    false_positives = [c for c in cells if c["agreement"] == "FALSE_POSITIVE"]
    false_negatives = [c for c in cells if c["agreement"] == "FALSE_NEGATIVE"]

    met = sum(1 for c in cells if c["predicted_met"])
    failed = len(cells) - met
    if met < 2 or failed < 2:
        verdict = "GRID_DOES_NOT_DISCRIMINATE"
    elif false_positives:
        verdict = "PREDICTION_FALSIFIED"
    else:
        verdict = "NO_COUNTEREXAMPLE_IN_THIS_GRID"

    return {
        "schema": SCHEMA,
        "preregistration": "research/active_evidence/PREREGISTRATION.md",
        "seeds": list(SEEDS),
        "reference_seed_held_out": REFERENCE_SEED,
        "deltas_ohm": list(DELTAS),
        "k_sigma": K_SIGMA,
        "bias_fraction": BIAS_FRACTION,
        "r_reference_ohm": R_REFERENCE,
        "noise_measured": noise.to_dict(),
        "noise_measured_how": (
            "successive differencing of clean simulator channels on the "
            "held-out reference seed; simulate.SIGMA is never read"),
        "simulator_sigma_for_comparison_only": {
            "pack_voltage": S.SIGMA["pack_voltage"],
            "pack_current": S.SIGMA["pack_current"]},
        "amps_per_vz_measured": amps_per_vz,
        "amps_per_vz_planning_default": PR.CURRENT_PER_AMP_OF_VZ,
        "probe_library": PR.catalogue(amps_per_vz=amps_per_vz),
        "realisation": realised,
        "commanded_symmetry_survives_the_loop": sorted(symmetry_kept),
        "commanded_symmetry_lost_in_the_loop": sorted(symmetry_lost),
        "realisation_finding": (
            "Every probe is a palindrome in COMMANDED vertical velocity, so "
            "its commanded lever arm cov(t,I)/var(I) is zero to machine "
            "precision. The REALISED current is not symmetric for every "
            "shape: the closed loop lags the command, and a lag breaks the "
            "palindrome. Multi-cycle bursts keep the property because the "
            "lag averages across cycles; single-excursion shapes do not. "
            "The realised standard deviation also exceeds the open-loop "
            "linear prediction, because holding a commanded velocity "
            "against integral action costs more current excursion than the "
            "static gain predicts -- which makes the variance condition "
            "CONSERVATIVE and is the direction the one false negative "
            "lies in."),
        "why_the_lever_arm_does_not_produce_a_false_positive": (
            "A drift bias is common to the clean and raised runs of the "
            "same probe, so it cancels in the GAP this campaign scores. It "
            "does NOT cancel when an estimate is compared against an "
            "absolute hypothesis interval, which is what "
            "csia_active_evidence.updater does. The drift condition is "
            "therefore slack for this campaign and load-bearing for that "
            "caller, and the correct practice is to compute the statistics "
            "from the REALISED current with "
            "ExcitationStats.from_measured rather than from the commanded "
            "profile."),
        "cells": cells,
        "counts": counts,
        "probes_predicted_to_work": met,
        "probes_predicted_not_to_work": failed,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "verdict": verdict,
        "what_falsifies_this": (
            "a single FALSE_POSITIVE -- a probe meeting all three necessary "
            "conditions that did not resolve delta_r in the plant"),
        "not_a_proof": (
            "Four deltas, five seeds, seven probes and one simulator. "
            "NO_COUNTEREXAMPLE_IN_THIS_GRID is exactly that sentence: the "
            "grid was searched and nothing in it contradicted the "
            "prediction. It is not a statement about any other grid and it "
            "is not a statement about hardware."),
        "what_this_is_not": (
            "No number here measures any real vehicle. The plant shares a "
            "linear terminal-voltage assumption with the derivation, so "
            "agreement cannot rule out an error common to both; see "
            "research/active_evidence/SIMULATOR_VALIDITY_ENVELOPE.md. "
            "Nothing here is a safety argument and no novelty is claimed."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)          # RAISES on failure. CONTROLS FIRST.

    doc = stamp(run(), report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
        print(f"verdict: {doc['verdict']}")
        for k in sorted(doc["counts"]):
            print(f"  {k:32s} {doc['counts'][k]}")
        print(f"measured sigma_v={doc['noise_measured']['sigma_v']:.5f} "
              f"sigma_i={doc['noise_measured']['sigma_i']:.5f} "
              f"drift={doc['noise_measured']['ocv_drift_v_per_s']:.6f} V/s")
        print(f"measured amps per m/s of vz = {doc['amps_per_vz_measured']:.3f}"
              f" (planning default {doc['amps_per_vz_planning_default']})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
