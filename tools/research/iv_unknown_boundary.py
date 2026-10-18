"""Detectability boundary for unknown faults, and the sensing sensitivity audit.

Two questions from the task, answered on the development partition.

Section 10: the prior campaign routed 0.40 V ringing to unknown and absorbed
0.10 V. Rather than lowering a threshold until the 0.10 V case is caught, this
measures how far each unknown trajectory lies from the modelled observation
set, sweeps amplitude, frequency, damping, phase and onset, and reports where
the boundary between "observationally contained" and "reliably outside" falls.

Section 11: sensing defects barely moved the prior margin. That is either
genuine insensitivity or another disconnected instrument. This computes
d(M_R_out)/dq and d(M_R_cert)/dq for every sensing and telemetry parameter, by
finite difference, and runs a mutation control for each.
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

from csia_active_evidence import polarization as pz                # noqa: E402
from csia_active_evidence import rcec                              # noqa: E402
from csia_independent_validation import evaluator as ev            # noqa: E402
from csia_independent_validation import partitions as pt           # noqa: E402
from csia_independent_validation.openset import (ModelledSet,      # noqa: E402
                                                 boundary_from)
from csia_independent_validation.plants import (SYNTHETIC_Q,       # noqa: E402
                                                SYNTHETIC_SENSING,
                                                Sensing, simulate)
from csia_independent_validation.truth import TruthPair            # noqa: E402

OUT = ROOT / ("research/active_evidence/independent_validation/results/"
              "UNKNOWN_AND_SENSITIVITY.json")

DURATION_S = 8.0
#: Chosen so the certificate is not saturated. At 0.010 ohm this command's
#: union bound is 0.005161 against an allowed 0.005000 -- dominated by the
#: polarization term -- so the no-fault case already routes to
#: MODEL_MISMATCH_LIMITED and every unknown-fault question would be asked of an
#: instrument that says "cannot resolve" whatever it is shown. At 0.020 ohm the
#: no-fault case certifies, which is the operating point the prior phase's
#: ablation used and the only one where routing carries information. Fixed
#: before the boundary was read.
TARGET_DELTA = 0.020

#: The sweep. Amplitude is the axis the prior phase reported; the other four
#: are the ones it never varied.
AMPLITUDES_V = (0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60)
FREQUENCIES_HZ = (2.0, 6.0, 15.0)
DAMPINGS = (0.1, 0.4, 1.5)
PHASES_RAD = (0.0, math.pi / 2.0)
ONSETS_S = (0.0, 3.0)

#: Sensing and telemetry parameters, with the step used for the derivative.
SENSING_STEPS = {
    "bias_i": 0.50, "scale_i": 0.010, "sigma_i": 0.050, "quantum_i": 0.050,
    "delay_i_s": 0.020, "bias_v": 0.020, "sigma_v": 0.010,
    "quantum_v": 0.010, "delay_v_s": 0.020, "timestamp_jitter_s": 0.002,
    "sample_phase": 0.500, "dropout": 0.100, "antialias_tau_s": 0.020,
}


def burst(t: float) -> float:
    if t < 0.0 or t > DURATION_S:
        return 0.0
    return 10.0 * math.cos(2.0 * math.pi * 3.0 * t / DURATION_S)


def budget() -> rcec.ErrorBudget:
    return rcec.ErrorBudget(
        r_reference=SYNTHETIC_Q["r0"], target_delta_r=TARGET_DELTA,
        sigma_v=SYNTHETIC_SENSING["sigma_v"],
        sigma_i=SYNTHETIC_SENSING["sigma_i"], d_max=0.002,
        polarization=pz.PolarizationEnvelope(
            r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0,
            n_r1=5, n_tau=7),
        scale_error_max=0.02, hysteresis_v_max=0.040)


def _routed_to_unknown(state: str) -> bool:
    """Only the open-set route counts.

    The first version of this also counted MODEL_MISMATCH_LIMITED, which is
    the in-model "my budget cannot resolve this" answer and is what a no-fault
    run returns at a tight target. Lumping the two made the routing rate 1.000
    at every amplitude including zero, and the boundary estimate that came out
    of it was an artifact of the predicate rather than a property of the
    plant.
    """
    return state == "UNKNOWN_OR_MODEL_MISMATCH"


def unknown_sweep(seeds) -> Dict:
    rows: List[Dict] = []
    for seed in seeds:
        modelled = ModelledSet(burst, plant="Q1", duration=DURATION_S,
                               seed=seed)
        for amplitude in AMPLITUDES_V:
            for frequency in FREQUENCIES_HZ:
                for damping in DAMPINGS:
                    for phase in PHASES_RAD:
                        for onset in ONSETS_S:
                            observation, truth = simulate(
                                burst, plant="Q1", duration=DURATION_S,
                                seed=seed, ringing_amplitude_v=amplitude,
                                ringing_hz=frequency, ringing_damping=damping,
                                ringing_phase_rad=phase,
                                ringing_onset_s=onset)
                            separation = modelled.distance(observation)
                            kept_t, kept_i, kept_v = observation.kept()
                            certificate = rcec.certify(
                                kept_t, kept_i, kept_v, budget())
                            rows.append({
                                "seed": seed, "amplitude_v": amplitude,
                                "frequency_hz": frequency,
                                "damping": damping, "phase_rad": phase,
                                "onset_s": onset,
                                "delta_unknown": separation.delta_unknown,
                                "nearest_magnitude":
                                    separation.nearest_magnitude,
                                "state": certificate.state,
                                "routed_to_unknown":
                                    _routed_to_unknown(certificate.state),
                            })
    faults = [r for r in rows if r["amplitude_v"] > 0]
    return {
        "rows": rows,
        "modelled_set_size": 126,
        "boundary": boundary_from(
            [r["delta_unknown"] for r in faults],
            [r["routed_to_unknown"] for r in faults]),
        "baseline_delta_no_fault": statistics.median(
            r["delta_unknown"] for r in rows if r["amplitude_v"] == 0),
        "by_amplitude": {
            f"{amplitude}": {
                "median_delta": statistics.median(
                    r["delta_unknown"] for r in rows
                    if r["amplitude_v"] == amplitude),
                "routed_fraction": statistics.mean(
                    float(r["routed_to_unknown"]) for r in rows
                    if r["amplitude_v"] == amplitude),
                "n": sum(1 for r in rows if r["amplitude_v"] == amplitude),
            } for amplitude in AMPLITUDES_V},
    }


def _run_pair(sensing: Sensing, seed: int) -> Dict:
    """One matched pair, using only the samples telemetry actually delivered.

    The first version passed the full arrays to the estimator, so a 20%
    dropout changed nothing: the invalid samples were still being fitted. Its
    sensitivity came out at exactly zero, which looked like a finding and was
    a disconnected instrument.
    """
    nominal, nominal_truth = simulate(burst, plant="Q1", duration=DURATION_S,
                                      seed=seed, sensing=sensing)
    fault, fault_truth = simulate(burst, plant="Q1", duration=DURATION_S,
                                  seed=seed, sensing=sensing,
                                  r0_delta=TARGET_DELTA)
    _, nominal_i, nominal_v = nominal.kept()
    fault_t, fault_i, fault_v = fault.kept()
    outcome = ev.evaluate_change(
        rcec.estimate_resistance(nominal_i, nominal_v),
        rcec.estimate_resistance(fault_i, fault_v),
        TruthPair(nominal=nominal_truth, fault=fault_truth))
    certificate = rcec.certify(fault_t, fault_i, fault_v, budget())
    return {"m_r_out": outcome.m_r_out,
            "m_r_cert": certificate.resolution.get("margin"),
            "state": certificate.state}


def sensitivity(seeds) -> Dict:
    base_sensing = Sensing(**SYNTHETIC_SENSING)
    rows: Dict[str, Dict] = {}
    for parameter, step in SENSING_STEPS.items():
        out_slopes, cert_slopes, mutation = [], [], []
        for seed in seeds:
            base = _run_pair(base_sensing, seed)
            perturbed = _run_pair(
                replace(base_sensing,
                        **{parameter: getattr(base_sensing, parameter) + step}),
                seed)
            out_slopes.append((perturbed["m_r_out"] - base["m_r_out"]) / step)
            if base["m_r_cert"] is not None \
                    and perturbed["m_r_cert"] is not None:
                cert_slopes.append(
                    (perturbed["m_r_cert"] - base["m_r_cert"]) / step)
            mutation.append(abs(perturbed["m_r_out"] - base["m_r_out"]))
        rows[parameter] = {
            "step": step,
            "J_q_out": statistics.median(out_slopes),
            "J_q_cert": (statistics.median(cert_slopes)
                         if cert_slopes else None),
            "median_abs_move_in_m_r_out": statistics.median(mutation),
            "mutation_detected": statistics.median(mutation) > 0.0,
        }
    return rows


def main() -> int:
    seeds = pt.seeds("development")[:4]
    doc = {
        "schema": "csia.independent_validation.unknown_and_sensitivity/1",
        "partition": "development",
        "seeds": list(seeds),
        "partition_manifest_sha256": pt.manifest_hash(),
        "target_delta_r_ohm": TARGET_DELTA,
        "unknown": unknown_sweep(seeds),
        "sensitivity": sensitivity(pt.seeds("development")[:8]),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print("baseline delta with no fault: "
          f"{doc['unknown']['baseline_delta_no_fault']:.3f} sigmas")
    print("boundary:", json.dumps(doc["unknown"]["boundary"]))
    for amplitude, stats in doc["unknown"]["by_amplitude"].items():
        print(f"  {amplitude:>5} V  delta {stats['median_delta']:7.3f}  "
              f"routed {stats['routed_fraction']:.3f}  n={stats['n']}")
    print("sensitivity (median over seeds):")
    for parameter, stats in doc["sensitivity"].items():
        cert = ("None" if stats["J_q_cert"] is None
                else f"{stats['J_q_cert']:+.4e}")
        print(f"  {parameter:20s} J_out {stats['J_q_out']:+.4e}  "
              f"J_cert {cert}  moved {stats['mutation_detected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
