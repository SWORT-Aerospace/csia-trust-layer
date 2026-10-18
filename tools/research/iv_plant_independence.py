"""Plant-independence audit for the independent-validation phase.

Answers three questions with measurements rather than assertions:

1. Are the Q plants numerically independent of the prior simulator, or do they
   just re-run the same integrator under a new name?
2. Is every declared dynamic effect actually wired into the observed voltage?
   A richer plant that changes nothing is falsifier 7 in the preregistration.
3. Does the independent outcome metric see plant differences that the
   certificate margin provably cannot?

Development partition only. Nothing here is a result; it is the evidence that
the instrument is connected.
"""
from __future__ import annotations

import json
import math
import pathlib
import statistics
import sys
from dataclasses import replace
from typing import Dict, List

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from csia_active_evidence import rcec                      # noqa: E402
from csia_active_evidence import polarization as pz        # noqa: E402
from csia_independent_validation import evaluator as ev    # noqa: E402
from csia_independent_validation import partitions as pt   # noqa: E402
from csia_independent_validation import plants             # noqa: E402
from csia_independent_validation.plants import (QParams, Sensing,  # noqa: E402
                                                SYNTHETIC_Q,
                                                SYNTHETIC_SENSING, simulate)
from csia_independent_validation.truth import TruthPair    # noqa: E402

OUT_JSON = ROOT / ("research/active_evidence/independent_validation/results/"
                   "PLANT_INDEPENDENCE.json")

#: The frozen magnitude grid from the preregistration.
MAGNITUDES = (0.002, 0.004, 0.006, 0.010, 0.020, 0.040)

#: A palindromic current burst, in amps of excess demand. Deliberately plain:
#: this audit is about the plants, not about probe design.
BURST_AMPLITUDE_A = 10.0
BURST_CYCLES = 3
DURATION_S = 8.0


def burst(t: float) -> float:
    if t < 0.0 or t > DURATION_S:
        return 0.0
    return BURST_AMPLITUDE_A * math.cos(
        2.0 * math.pi * BURST_CYCLES * t / DURATION_S)


def _budget(target_delta: float) -> rcec.ErrorBudget:
    """A declared envelope. Every number is an engineering declaration."""
    return rcec.ErrorBudget(
        r_reference=SYNTHETIC_Q["r0"], target_delta_r=target_delta,
        sigma_v=SYNTHETIC_SENSING["sigma_v"],
        sigma_i=SYNTHETIC_SENSING["sigma_i"],
        d_max=0.002,
        polarization=pz.PolarizationEnvelope(
            r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0,
            n_r1=5, n_tau=7),
        scale_error_max=0.02, hysteresis_v_max=0.040,
        delay_max_s=0.0, quantum_i=0.0)


def integration_path_difference() -> Dict:
    """How far the exact step is from the forward-Euler step actually used."""
    rows = []
    for tau, dt in ((0.25, 0.02), (1.20, 0.02), (13.5, 0.02), (40.0, 0.02)):
        euler = dt / tau
        exact = 1.0 - math.exp(-dt / tau)
        rows.append({"tau_s": tau, "dt_s": dt, "euler_coefficient": euler,
                     "exact_zoh_coefficient": exact,
                     "relative_difference": (euler - exact) / exact})
    return {"per_step_coefficients": rows,
            "note": ("the prior simulator uses x += dt/tau*(target-x); these "
                     "plants use the exact zero-order-hold step. The two are "
                     "different numerical methods, not two spellings of one.")}


def effect_connectivity() -> Dict:
    """Remove each declared effect and measure what the voltage does."""
    params = QParams(**SYNTHETIC_Q)
    quiet = Sensing(**{**SYNTHETIC_SENSING, "sigma_v": 0.0, "sigma_i": 0.0})
    loop = plants.Loop(**{**plants.SYNTHETIC_LOOP, "controller_sigma": 0.0,
                          "process_sigma": 0.0})

    def peak_shift(plant: str, mutated: QParams) -> float:
        base, _ = simulate(burst, plant=plant, duration=DURATION_S, seed=1,
                           params=params, sensing=quiet, loop=loop)
        other, _ = simulate(burst, plant=plant, duration=DURATION_S, seed=1,
                            params=mutated, sensing=quiet, loop=loop)
        return float(np.max(np.abs(base.v_meas - other.v_meas)))

    def estimate_shift(plant: str, mutated: QParams) -> float:
        """How far removing the effect moves the resistance ESTIMATE.

        The voltage comparison above is per-sample and the sensor noise floor
        is per-sample too, so a systematic offset well under one sigma can
        still dominate a least-squares fit over hundreds of samples. This is
        the comparison that matters to an estimator, so it is reported as
        well and neither is allowed to stand alone.
        """
        base, _ = simulate(burst, plant=plant, duration=DURATION_S, seed=1,
                           params=params, sensing=quiet, loop=loop)
        other, _ = simulate(burst, plant=plant, duration=DURATION_S, seed=1,
                            params=mutated, sensing=quiet, loop=loop)
        return abs(rcec.estimate_resistance(base.i_meas, base.v_meas)
                   - rcec.estimate_resistance(other.i_meas, other.v_meas))

    return {
        "r1_removed_on_Q1_ohm_of_estimate":
            estimate_shift("Q1", replace(params, r1=0.0)),
        "r2_removed_on_Q2_ohm_of_estimate":
            estimate_shift("Q2", replace(params, r2=0.0)),
        "hysteresis_removed_on_Q2_ohm_of_estimate":
            estimate_shift("Q2", replace(params, hysteresis_v=0.0)),
        "ocv_curvature_removed_on_Q1_ohm_of_estimate":
            estimate_shift("Q1", replace(params, ocv_curvature=0.0)),
        "smallest_magnitude_on_the_grid_ohm": MAGNITUDES[0],
        "r1_removed_on_Q1_volts": peak_shift("Q1", replace(params, r1=0.0)),
        "r1_removed_on_Q2_volts": peak_shift("Q2", replace(params, r1=0.0)),
        "r2_removed_on_Q2_volts": peak_shift("Q2", replace(params, r2=0.0)),
        "hysteresis_removed_on_Q2_volts":
            peak_shift("Q2", replace(params, hysteresis_v=0.0)),
        "ocv_curvature_removed_on_Q1_volts":
            peak_shift("Q1", replace(params, ocv_curvature=0.0)),
        "sensor_noise_floor_volts": SYNTHETIC_SENSING["sigma_v"],
        "criterion": (
            "Two comparisons, both reported. Per-sample: does removing the "
            "effect move the terminal voltage by more than one sigma of "
            "sensor noise. At the estimator: does removing it move the "
            "least-squares resistance by more than the smallest magnitude on "
            "the grid. The second is the one that decides whether the effect "
            "can change a verdict; the first is included because a reader "
            "will look for it and because an effect that fails BOTH is not "
            "present in any useful sense."),
    }


def _run_pair(plant: str, seed: int, delta: float) -> Dict:
    """One matched nominal/fault pair under common random numbers."""
    nominal_obs, nominal_truth = simulate(
        burst, plant=plant, duration=DURATION_S, seed=seed)
    fault_obs, fault_truth = simulate(
        burst, plant=plant, duration=DURATION_S, seed=seed, r0_delta=delta)

    r_hat_nominal = rcec.estimate_resistance(nominal_obs.i_meas,
                                             nominal_obs.v_meas)
    r_hat_fault = rcec.estimate_resistance(fault_obs.i_meas,
                                           fault_obs.v_meas)
    pair = TruthPair(nominal=nominal_truth, fault=fault_truth)
    outcome = ev.evaluate_change(r_hat_nominal, r_hat_fault, pair)
    point = ev.evaluate_point(r_hat_fault, fault_truth)

    certificate = rcec.certify(fault_obs.t, fault_obs.i_meas,
                               fault_obs.v_meas, _budget(delta))
    return {
        "plant": plant, "seed": seed, "delta": delta,
        "m_r_out": outcome.m_r_out, "e_delta_r": outcome.e_delta_r,
        "resolved": outcome.resolved,
        "ae_r": point.ae_r, "e_r": point.e_r, "re_r": point.re_r,
        "r_hat_nominal": r_hat_nominal, "r_hat_fault": r_hat_fault,
        "state": certificate.state,
        "m_r_cert": certificate.resolution.get("margin"),
    }


def outcome_sees_the_plant(seeds) -> Dict:
    """The central check: does M_R_out vary across plants where M_R_cert does not?"""
    rows: List[Dict] = []
    for plant in plants.PLANTS:
        for delta in MAGNITUDES:
            for seed in seeds:
                rows.append(_run_pair(plant, seed, delta))

    by_plant: Dict[str, Dict] = {}
    for plant in plants.PLANTS:
        subset = [r for r in rows if r["plant"] == plant]
        by_plant[plant] = {
            "n": len(subset),
            "median_abs_e_delta_r": statistics.median(
                abs(r["e_delta_r"]) for r in subset),
            "resolved_fraction": sum(r["resolved"] for r in subset)
                / len(subset),
            "median_m_r_out": statistics.median(r["m_r_out"] for r in subset),
            "median_ae_r": statistics.median(r["ae_r"] for r in subset),
            "worst_ae_r": max(r["ae_r"] for r in subset),
        }

    # Cells matched on (delta, seed): is the certificate margin identical
    # across plants, and is the outcome error not?
    identical_cert = 0
    identical_out = 0
    comparable = 0
    for delta in MAGNITUDES:
        for seed in seeds:
            cell = [r for r in rows
                    if r["delta"] == delta and r["seed"] == seed]
            certs = [r["m_r_cert"] for r in cell]
            outs = [r["e_delta_r"] for r in cell]
            if len(cell) != len(plants.PLANTS) or any(c is None for c in certs):
                continue
            comparable += 1
            identical_cert += len(set(certs)) == 1
            identical_out += len(set(outs)) == 1

    return {
        "by_plant": by_plant,
        "matched_cells": comparable,
        "cells_where_cert_margin_is_identical_across_plants": identical_cert,
        "cells_where_outcome_error_is_identical_across_plants": identical_out,
        "rows": rows,
    }


def main() -> int:
    seeds = pt.seeds("development")[:8]
    doc = {
        "schema": "csia.independent_validation.plant_independence/1",
        "partition": "development",
        "seeds": list(seeds),
        "partition_manifest_sha256": pt.manifest_hash(),
        "command": {"amplitude_a": BURST_AMPLITUDE_A, "cycles": BURST_CYCLES,
                    "duration_s": DURATION_S, "shape": "cosine burst"},
        "integration_path": integration_path_difference(),
        "effect_connectivity": effect_connectivity(),
        "outcome_vs_certificate": outcome_sees_the_plant(seeds),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")

    connectivity = doc["effect_connectivity"]
    comparison = doc["outcome_vs_certificate"]
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print("effect connectivity (volts of peak shift when removed):")
    for key, value in connectivity.items():
        if key.endswith("_volts"):
            print(f"  {key:42s} {value:.6f}")
    print(f"matched cells: {comparison['matched_cells']}")
    print("  certificate margin identical across plants in "
          f"{comparison['cells_where_cert_margin_is_identical_across_plants']}")
    print("  outcome error identical across plants in "
          f"{comparison['cells_where_outcome_error_is_identical_across_plants']}")
    for plant, stats in comparison["by_plant"].items():
        print(f"  {plant}: median |e_dR| {stats['median_abs_e_delta_r']:.6f} "
              f"ohm, median AE_R {stats['median_ae_r']:.6f} ohm, "
              f"resolved {stats['resolved_fraction']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
