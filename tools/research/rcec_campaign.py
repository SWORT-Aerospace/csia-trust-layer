"""Does a closed-loop-aware probe realize enough excitation to resolve a fault?

WHAT IS BEING TESTED
--------------------
Eight arms, P0 to P7, through an independent one-RC Thevenin pack that does
NOT satisfy the estimator's model. Every arm is judged by the same
Realized-Current Excitation Certificate, computed from measured current and
voltage only. The commanded waveform never enters the verdict.

THE COMPARISON THAT DECIDES THE ANSWER
----------------------------------------
`P6_mission` is a manoeuvre the vehicle flies anyway, charged ZERO
incremental energy. If it matches the best purpose-built probe, the honest
conclusion is that CSIA should wait rather than ask, and the preregistration
names that as a falsifier.

SEPARATION IS SET-VALUED AND CERTIFICATE-CONSISTENT
-----------------------------------------------------
Two hypotheses are separated when their estimate intervals, each widened by
the SAME error bound the certificate declared for that run, are disjoint.
Using the certificate's own bound is what makes the campaign a test OF the
certificate rather than a second opinion beside it: if the bound is too
tight the campaign produces false separations and the confusion matrix shows
them.

    A FALSE CERTIFICATION IS A `CERTIFIED_IN_MODEL` RUN WHOSE INTERVALS DO
    NOT ACTUALLY SEPARATE THE TARGET CHANGE. IT IS THE ONLY OUTCOME THAT
    FALSIFIES THE CERTIFICATE.

SEED PARTITIONS ARE IMMUTABLE
------------------------------
Development seeds fit the lag and search P3. Locked seeds are opened once,
after every choice is frozen. `tests/test_rcec.py` asserts they are
disjoint, and nothing in this file reads a locked seed before the final
evaluation.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import battery_1rc as B                # noqa: E402
from csia_active_evidence import battery_multirc as MR          # noqa: E402
from csia_active_evidence import polarization as PZ              # noqa: E402
from csia_active_evidence import rcec                            # noqa: E402
from csia_active_evidence import rcec_selector as RS             # noqa: E402
from csia_active_evidence import realized_moments as RM          # noqa: E402
from csia_active_evidence import waveform_compensation as WC     # noqa: E402

INSTRUMENT = "tools.research.rcec_campaign"
SCHEMA = "csia.active_evidence.rcec_campaign/1"

DEV_SEEDS = (0, 100, 200, 300, 400)
CAL_SEED = 999
LOCKED_SEEDS = (7000, 7100, 7200, 7300, 7400, 7500, 7600, 7700, 7800, 7900)

HZ = 50.0
ACTION_START = 6.0
ACTION_DURATION = 8.0
DURATION = 20.0
AMPLITUDE = 8.0
AUTHORITY_A = 14.0

R_REFERENCE = 0.040
TARGET_DELTA_R = 0.020
C_FRACTION = 0.5
K_SIGMA = 3.0
D_MAX = 0.008
#: The declared polarization envelope, replacing the R1_MAX/TAU1_MIN pair
#: whose closed-form bound was measured to understate the truth fivefold.
POLARIZATION_ENVELOPE = PZ.PolarizationEnvelope(
    r1_min=0.004, r1_max=0.020, tau_min_s=1.0, tau_max_s=40.0)
SCALE_ERROR_MAX = 0.005
HYSTERESIS_V_MAX = 0.05

R0_DELTAS = (0.0, 0.005, 0.010, 0.020, 0.040)

#: Energy enters P3's objective only as a tie-break among waveforms that
#: already certify. Declared, normalized by a scale, never swept.
ENERGY_SCALE_AS = 50.0
ENERGY_SCALE_WEIGHT = 0.05


def budget(**kw) -> rcec.ErrorBudget:
    base = dict(r_reference=R_REFERENCE, target_delta_r=TARGET_DELTA_R,
                sigma_v=B.SYNTHETIC_SENSING["sigma_v"],
                sigma_i=B.SYNTHETIC_SENSING["sigma_i"],
                d_max=D_MAX, polarization=POLARIZATION_ENVELOPE,
                scale_error_max=SCALE_ERROR_MAX,
                hysteresis_v_max=HYSTERESIS_V_MAX,
                c_fraction=C_FRACTION, k_sigma=K_SIGMA, min_samples=50)
    base.update(kw)
    return rcec.ErrorBudget(**base)


def _plant(**kw):
    def sim(command, duration, seed):
        return B.simulate(command, duration=duration, seed=seed, **kw)
    return sim


#: The three plants. `multi_rc` adds a second polarization branch and
#: voltage hysteresis, neither of which the estimator has a term for.
PLANTS = {"simple": (B, {"r1_scale": 0.0}),
          "one_rc": (B, {"r1_scale": 1.0}),
          "multi_rc": (MR, {})}


def _run(arm_proposal, seed, *, r0_delta=0.0, plant_kw=None, feedback=None,
         plant=B):
    """Fly one proposal once and return the evaluation window."""
    plant_kw = dict(plant_kw or {})
    plant_kw["r0_delta"] = r0_delta
    if feedback is None:
        tr = plant.simulate(arm_proposal.command, duration=DURATION,
                            seed=seed, **plant_kw)
    else:
        tr = _run_with_feedback(feedback, seed, plant_kw, plant=plant)
    return tr.window(ACTION_START, ACTION_START + ACTION_DURATION)


def _run_with_feedback(probe, seed, plant_kw, plant=B):
    """P4 with the loop genuinely closed around the plant, one sample late.

    THE WIRING THIS REPLACES DID NOTHING. The first version kept a `state`
    dict that nothing ever wrote, so `probe.observe` was never called, the
    accumulator saw zero samples, and the feedback arm ran as a byte-identical
    copy of the open-loop arm for a whole pilot campaign -- reported under its
    own name, with its own row in the table. It was caught by noticing that
    P4's realized current matched P1's to the last bit.

    `battery_1rc.simulate` now takes a per-sample `observer`, called after
    sample k is measured and before sample k+1 is commanded. The probe
    therefore reacts to realized current it has actually seen, one tick late,
    and cannot reach a future sample.
    """
    return plant.simulate(probe.demand, duration=DURATION, seed=seed,
                          observer=lambda t, i, v: probe.observe(t, i),
                          **plant_kw)


def evaluate_arm(name, proposal, seeds, *, plant_kw=None,
                 feedback_factory=None, plant=B) -> dict:
    """Fly one arm over a seed set at every R0 delta and certify each run."""
    rows = []
    for seed in seeds:
        per_delta = {}
        for delta in R0_DELTAS:
            fb = feedback_factory() if feedback_factory else None
            w = _run(proposal, seed, r0_delta=delta, plant_kw=plant_kw,
                     feedback=fb, plant=plant)
            if w.n < 5:
                per_delta[delta] = {"state": rcec.ABORTED_INCOMPLETE}
                continue
            cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
            r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
            bound = cert.resolution.get("achieved_error")
            per_delta[delta] = {
                "state": cert.state,
                "r_hat": r_hat,
                "bound": bound,
                "s_ii": cert.moments.get("s_ii"),
                "s_ii_deconvolved": cert.coverage.get("s_ii_deconvolved"),
                "lever_arm_s": cert.coverage.get("lever_arm_s"),
                "reasons": list(cert.reasons),
                "saturated": bool(np.any(w.saturated)),
            }
        rows.append({"seed": int(seed), "by_delta": per_delta})
    return {"arm": name, "rows": rows,
            "nominal_energy_as": proposal.nominal_energy_as,
            "executable": proposal.executable,
            "detail": proposal.detail}


def separation(rows, delta) -> dict:
    """Do the nominal and faulted intervals separate, using the CERTIFICATE's
    own error bound? Counted only over runs the certificate certified."""
    sep, certified, total = 0, 0, 0
    for r in rows:
        a = r["by_delta"].get(0.0)
        b = r["by_delta"].get(delta)
        if not a or not b:
            continue
        total += 1
        if a["state"] != rcec.CERTIFIED or b["state"] != rcec.CERTIFIED:
            continue
        certified += 1
        lo_a, hi_a = a["r_hat"] - a["bound"], a["r_hat"] + a["bound"]
        lo_b, hi_b = b["r_hat"] - b["bound"], b["r_hat"] + b["bound"]
        if hi_a < lo_b or hi_b < lo_a:
            sep += 1
    return {"runs": total, "certified_both": certified, "separated": sep,
            "separated_of_certified": (sep / certified) if certified else None}


def false_certifications(rows) -> int:
    """CERTIFIED runs where the target change does NOT in fact separate.

    The only outcome that falsifies the certificate. Counted at the target
    delta the budget was written for.
    """
    bad = 0
    for r in rows:
        a = r["by_delta"].get(0.0)
        b = r["by_delta"].get(TARGET_DELTA_R)
        if not a or not b:
            continue
        if a["state"] != rcec.CERTIFIED or b["state"] != rcec.CERTIFIED:
            continue
        lo_a, hi_a = a["r_hat"] - a["bound"], a["r_hat"] + a["bound"]
        lo_b, hi_b = b["r_hat"] - b["bound"], b["r_hat"] + b["bound"]
        if not (hi_a < lo_b or hi_b < lo_a):
            bad += 1
    return bad


# --- P3's search, on development seeds only --------------------------------

def p3_candidates():
    out = []
    for shape in ("palindromic", "triangle", "chirp"):
        for amp in (2.0, 4.0, 8.0, 12.0):
            for dur in (2.0, 4.0, 8.0):
                # THE GRID THAT DID NOT CONTAIN THE OPTIMUM. The first
                # version offered 2, 3 and 5 cycles. The error decomposition
                # predicts the best probe sits where the polarization bias
                # equals the noise term, which on this pack is 6 to 12
                # cycles in an 8 s window, and the sweep confirmed it. A
                # search cannot find what its grid excludes.
                for cycles in ((2, 3, 5, 6, 9, 12, 18, 24)
                               if shape == "palindromic" else (0,)):
                    out.append({"shape": shape, "amplitude": amp,
                                "duration": dur, "cycles": cycles})
    return out


def p3_objective(cand, plant_kw=None) -> float:
    """J(u) on DEVELOPMENT seeds, scored by THE CERTIFICATE ITSELF.

    THE FIRST VERSION OF THIS FUNCTION SCORED PROXIES AND CHOSE BADLY. It
    penalised a shortfall against `S_II_min` and the drift lever arm, and
    divided energy by 100. `S_II_min` is only 36.9 A^2-sample here, so almost
    any waveform cleared it, the deficit term went to zero, and the objective
    reduced to "use as little energy as possible". It selected a 2 A chirp
    over 2 s, which the certificate then refused as `MEASUREMENT_LIMITED`
    with a lever arm of 0.591 s. The arm scored zero certificates in the
    pilot.

    The binding constraint was never `S_II_min`; it is the TOTAL ERROR
    BUDGET. A search that optimises a proxy for the thing it is judged on
    will find the corner where the proxy and the judgement disagree, and
    this one did.

    So the objective now calls `rcec.certify` on the realized current and
    minimises the certificate's own shortfall, with energy entering only as
    a tie-break among waveforms that already certify. Weights are normalized
    by the constraint scales they represent -- the allowed error and a
    declared energy scale -- so neither is a free parameter.

    Development seeds only. The chosen candidate is then flown unchanged on
    locked seeds.
    """
    t = RS.window_times(ACTION_START, cand["duration"], HZ)
    if cand["shape"] == "palindromic":
        w = RS.palindromic(t, ACTION_START, cand["duration"],
                           cand["amplitude"], cand["cycles"])
    else:
        w = RS.SHAPES[cand["shape"]](t, ACTION_START, cand["duration"],
                                     cand["amplitude"])
    cmd = WC.as_callable(w, t)
    energy = float(np.sum(np.abs(w)) / HZ)
    b = budget()

    shortfalls, refusals, sat_total = [], 0, 0.0
    for seed in DEV_SEEDS:
        tr = B.simulate(cmd, duration=DURATION, seed=seed, **(plant_kw or {}))
        win = tr.window(ACTION_START, ACTION_START + cand["duration"])
        if win.n < b.min_samples:
            refusals += 1
            continue
        cert = rcec.certify(win.t, win.i_meas, win.v_meas, b)
        sat_total += float(np.mean(win.saturated))
        if cert.state != rcec.CERTIFIED:
            allowed = cert.resolution.get("allowed_error")
            achieved = cert.resolution.get("achieved_error")
            if allowed and achieved:
                shortfalls.append((achieved - allowed) / allowed)
            else:
                refusals += 1
        else:
            shortfalls.append(0.0)

    n = len(DEV_SEEDS)
    shortfall = (sum(s ** 2 for s in shortfalls) / n) if shortfalls else 0.0
    return (shortfall + 4.0 * (refusals / n)
            + ENERGY_SCALE_WEIGHT * (energy / ENERGY_SCALE_AS)
            + 10.0 * (sat_total / n))


def hysteresis_hunt(n_draws: int, seeds) -> dict:
    """Hunt for a false certification on the multi-RC pack WITH hysteresis.

    Two halves, and the second is the point.

      * INSIDE the declared envelope, M drawn at or below
        `HYSTERESIS_V_MAX`. A false certification here would falsify the
        bound.
      * OUTSIDE it, M drawn above the declaration. False certifications here
        are EXPECTED and are recorded, because they are what an
        under-declared bound costs. The certificate never measures M; it is
        told M.
    """
    rng = np.random.default_rng(776644)
    t = RS.window_times(ACTION_START, ACTION_DURATION, HZ)
    out = {}
    for label, lo, hi in (("inside_declared_envelope", 0.0,
                           HYSTERESIS_V_MAX),
                          ("outside_declared_envelope", HYSTERESIS_V_MAX,
                           5.0 * HYSTERESIS_V_MAX)):
        rows = {"draws": 0, "certified": 0, "false_certifications": 0,
                "worst_ratio": 0.0, "states": {}}
        for k in range(n_draws):
            seed = int(seeds[k % len(seeds)])
            amp = float(rng.uniform(8.0, 18.0))
            cyc = int(rng.choice([3, 6, 9, 12]))
            base = float(rng.uniform(2.0, 8.0))
            m_v = float(rng.uniform(lo, hi))
            gamma = float(rng.uniform(500.0, 25000.0))
            pack = MR.MultiRCPack(**{**MR.SYNTHETIC_MULTIRC,
                                     "hysteresis_v": m_v,
                                     "hysteresis_gamma": gamma})
            loop = B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": base})
            cmd = WC.as_callable(
                RS.palindromic(t, ACTION_START, ACTION_DURATION, amp, cyc), t)
            r0_delta = float(rng.choice(R0_DELTAS))
            tr = MR.simulate(cmd, duration=DURATION, seed=seed, pack=pack,
                             loop=loop, r0_delta=r0_delta)
            w = tr.window(ACTION_START, ACTION_START + ACTION_DURATION)
            rows["draws"] += 1
            if w.n < 5:
                continue
            cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
            rows["states"][cert.state] = rows["states"].get(cert.state, 0) + 1
            if cert.state != rcec.CERTIFIED:
                continue
            rows["certified"] += 1
            r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
            truth = pack.r0_at(float(np.mean(w.temp_c))) + r0_delta
            bound = cert.resolution["achieved_error"]
            ratio = abs(r_hat - truth) / bound
            rows["worst_ratio"] = max(rows["worst_ratio"], ratio)
            if ratio > 1.0:
                rows["false_certifications"] += 1
        rows["false_certification_rate"] = (
            rows["false_certifications"] / rows["certified"]
            if rows["certified"] else None)
        out[label] = rows
    out["declared_bound_v"] = HYSTERESIS_V_MAX
    out["reading"] = (
        "Inside the declared envelope the bound must hold. Outside it, wrong "
        "certificates are the measured cost of an under-declared bound, and "
        "no test inside this framework detects them: the certificate is told "
        "M and cannot measure it.")
    return out


def cross_probe_check(seeds) -> dict:
    """Can two probes with different sign-reversal content catch it? NO.

    Measured, and reported as a null result rather than left out. A probe
    that never reverses the current has a zero hysteresis lever; one that
    reverses heavily has a large one. If the declared bound were too small
    their estimates should disagree by more than their combined bounds.

    They do not, at any over-declaration factor where the certificate still
    certifies, because the same M that creates the disagreement also inflates
    the declared bound on the reversing probe. The two scale together.
    """
    t = RS.window_times(ACTION_START, ACTION_DURATION, HZ)
    quiet = (B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 20.0}),
             WC.as_callable(RS.palindromic(t, ACTION_START, ACTION_DURATION,
                                           8.0, 6), t))
    reversing = (B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 5.0}),
                 WC.as_callable(RS.palindromic(t, ACTION_START,
                                               ACTION_DURATION, 15.0, 6), t))
    rows = {}
    for m_v in (0.0, 0.05, 0.08, 0.12):
        est = []
        for loop, cmd in (quiet, reversing):
            pack = MR.MultiRCPack(**{**MR.SYNTHETIC_MULTIRC,
                                     "hysteresis_v": m_v,
                                     "hysteresis_gamma": 20000.0})
            tr = MR.simulate(cmd, duration=DURATION, seed=int(seeds[0]),
                             pack=pack, loop=loop)
            w = tr.window(ACTION_START, ACTION_START + ACTION_DURATION)
            cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
            est.append((rcec.estimate_resistance(w.i_meas, w.v_meas),
                        cert.resolution.get("achieved_error"), cert.state))
        (ra, ba, sa), (rb, bb, sb) = est
        if ba is None or bb is None:
            rows[str(m_v)] = {"states": [sa, sb], "detected": None}
            continue
        rows[str(m_v)] = {
            "disagreement": abs(ra - rb), "combined_bound": ba + bb,
            "ratio": abs(ra - rb) / (ba + bb),
            "detected": bool(abs(ra - rb) > ba + bb),
            "states": [sa, sb]}
    detected = [k for k, v in rows.items() if v.get("detected")]
    return {"rows": rows, "detected_at": detected,
            "verdict": ("CROSS_PROBE_CHECK_DOES_NOT_DETECT_AN_UNDER_DECLARED_"
                        "HYSTERESIS_BOUND" if not detected
                        else "DETECTED"),
            "why": ("the same M that creates the disagreement also inflates "
                    "the declared bound on the reversing probe, so the two "
                    "scale together and the ratio stays below one")}


def true_resistance(trace, r0_delta: float) -> float:
    """The DC resistance the estimator SHOULD recover, from plant truth.

    Available to the campaign and never to the certificate. It is what makes
    a false certification detectable: a CERTIFIED run whose estimate misses
    the truth by more than its own declared bound has falsified the bound.
    """
    pack = B.PackParams(**B.SYNTHETIC_PACK)
    return pack.r0_at(float(np.mean(trace.temp_c))) + r0_delta


def adversarial(n_draws: int, seeds) -> dict:
    """Hunt for a confident wrong certificate across the declared envelope.

    Deterministic draws over every nuisance the work order names: RC values,
    loop lag, sensor bias, scale error, delay, quantisation, dropout and
    open-circuit drift. Concentrated near the thresholds, because a bound
    that fails does so at its edge.
    """
    rng = np.random.default_rng(20260912)
    p = RS.p1_palindromic(start=ACTION_START, duration=ACTION_DURATION,
                          amplitude=AMPLITUDE, hz=HZ)
    rows = {"draws": 0, "certified": 0, "false_certifications": 0,
            "worst_error_ohm": 0.0, "worst_case": None, "states": {}}
    for k in range(n_draws):
        seed = int(seeds[k % len(seeds)])
        pack = B.PackParams(**{**B.SYNTHETIC_PACK,
                               "r1": float(rng.uniform(0.004, 0.020)),
                               "c1": float(rng.uniform(300.0, 2000.0)),
                               "r0_temp_coeff": float(rng.uniform(-6e-4, 0.0))})
        sensing = B.Sensing(**{**B.SYNTHETIC_SENSING,
                               "bias_i": float(rng.uniform(-0.5, 0.5)),
                               "scale_i": float(rng.uniform(-SCALE_ERROR_MAX,
                                                            SCALE_ERROR_MAX)),
                               "delay_s": float(rng.choice([0.0, 0.02, 0.04])),
                               "quantum_i": float(rng.choice([0.0, 0.05])),
                               "quantum_v": float(rng.choice([0.0, 0.005])),
                               "dropout": float(rng.choice([0.0, 0.02, 0.10]))})
        loop = B.Loop(**{**B.SYNTHETIC_LOOP,
                         "lag_s": float(rng.uniform(0.05, 0.8))})
        r0_delta = float(rng.choice(R0_DELTAS))
        drift = float(rng.uniform(0.0, D_MAX))
        tr = B.simulate(p.command, duration=DURATION, seed=seed, pack=pack,
                        sensing=sensing, loop=loop, r0_delta=r0_delta,
                        ocv_drift_v_per_s=drift)
        w = tr.window(ACTION_START, ACTION_START + ACTION_DURATION)
        rows["draws"] += 1
        if w.n < 5:
            rows["states"]["NO_WINDOW"] = rows["states"].get("NO_WINDOW", 0) + 1
            continue
        cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
        rows["states"][cert.state] = rows["states"].get(cert.state, 0) + 1
        if cert.state != rcec.CERTIFIED:
            continue
        rows["certified"] += 1
        r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
        truth = true_resistance(w, r0_delta)
        err = abs(r_hat - truth)
        bound = cert.resolution["achieved_error"]
        if err > bound:
            rows["false_certifications"] += 1
            if err - bound > rows["worst_error_ohm"]:
                rows["worst_error_ohm"] = err - bound
                rows["worst_case"] = {
                    "seed": seed, "r0_delta": r0_delta, "r_hat": r_hat,
                    "truth": truth, "error": err, "bound": bound,
                    "r1": pack.r1, "c1": pack.c1, "lag_s": loop.lag_s,
                    "scale_i": sensing.scale_i, "bias_i": sensing.bias_i,
                    "delay_s": sensing.delay_s, "dropout": sensing.dropout,
                    "ocv_drift": drift}
    rows["false_certification_rate"] = (
        rows["false_certifications"] / rows["certified"]
        if rows["certified"] else None)
    return rows


def frequency_sweep(seeds) -> dict:
    """The term trade, measured. THE MAIN RESULT OF THIS CAMPAIGN.

    `B_dynamic` falls with probe frequency because a polarization branch
    cannot follow a fast probe. The noise term `k*SE` RISES with frequency,
    because the loop lag and the current-channel delay attenuate the realized
    excitation. The total therefore has a minimum, and the certificate's own
    decomposition predicts where.

    Swept at constant amplitude and constant energy, so the only thing that
    changes is where the energy sits in frequency.
    """
    rows = {}
    for cycles in (1, 2, 3, 6, 9, 12, 18, 24):
        t = RS.window_times(ACTION_START, ACTION_DURATION, HZ)
        w = RS.palindromic(t, ACTION_START, ACTION_DURATION, AMPLITUDE,
                           cycles)
        cmd = WC.as_callable(w, t)
        per_delta = {}
        cert = None
        for delta in (0.005, 0.008, 0.010, 0.020):
            sep = n = 0
            for seed in seeds:
                a = B.simulate(cmd, duration=DURATION, seed=int(seed),
                               r1_scale=1.0).window(
                                   ACTION_START,
                                   ACTION_START + ACTION_DURATION)
                b = B.simulate(cmd, duration=DURATION, seed=int(seed),
                               r1_scale=1.0, r0_delta=delta).window(
                                   ACTION_START,
                                   ACTION_START + ACTION_DURATION)
                ca = rcec.certify(a.t, a.i_meas, a.v_meas, budget())
                cb = rcec.certify(b.t, b.i_meas, b.v_meas, budget())
                if ca.state != rcec.CERTIFIED or cb.state != rcec.CERTIFIED:
                    continue
                n += 1
                cert = ca
                ra = rcec.estimate_resistance(a.i_meas, a.v_meas)
                rb = rcec.estimate_resistance(b.i_meas, b.v_meas)
                if abs(rb - ra) > (ca.resolution["achieved_error"]
                                   + cb.resolution["achieved_error"]):
                    sep += 1
            per_delta[str(delta)] = {"runs": n,
                                     "separated": sep,
                                     "fraction": (sep / n) if n else None}
        rows[str(cycles)] = {
            "effective_frequency_hz": cert.terms["effective_frequency_hz"]
            if cert else None,
            "B_dynamic": cert.terms["B_dynamic"] if cert else None,
            "k_sigma_SE": cert.resolution["k_sigma_SE"] if cert else None,
            "achieved_error": cert.resolution["achieved_error"]
            if cert else None,
            "energy_as": float(np.sum(np.abs(w)) / HZ),
            "separation": per_delta,
        }
    resolvable = {c: min((float(d) for d, v in r["separation"].items()
                          if v["fraction"] == 1.0), default=None)
                  for c, r in rows.items()}
    best = min((c for c, v in resolvable.items() if v is not None),
               key=lambda c: (resolvable[c], int(c)), default=None)
    return {
        "rows": rows,
        "smallest_resolvable_delta_by_cycles": resolvable,
        "best_cycles": best,
        "finding": (
            "At constant amplitude and constant energy, the smallest "
            "resolvable resistance change depends on WHERE the probe puts "
            "its energy in frequency. Too slow and the polarization bound "
            "dominates; too fast and the loop lag attenuates the realized "
            "excitation so the noise term dominates. The optimum is where "
            "the two are equal, which the certificate's own decomposition "
            "predicts without running the sweep."),
    }


def open_set(seeds) -> dict:
    """H5. A dynamic fault the estimator has no term for, at three sizes."""
    p = RS.p1_palindromic(start=ACTION_START, duration=ACTION_DURATION,
                          amplitude=AMPLITUDE, hz=HZ)
    out = {}
    for ring in (0.0, 0.05, 0.10, 0.20, 0.40):
        states = {}
        for seed in seeds:
            tr = B.simulate(p.command, duration=DURATION, seed=int(seed),
                            unmodelled_ringing=ring)
            w = tr.window(ACTION_START, ACTION_START + ACTION_DURATION)
            cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
            states[cert.state] = states.get(cert.state, 0) + 1
        out[str(ring)] = states
    return out


def execution_ablation(seeds) -> dict:
    """Clipping and abort must invalidate a certificate, not be inherited."""
    p = RS.p1_palindromic(start=ACTION_START, duration=ACTION_DURATION,
                          amplitude=AMPLITUDE, hz=HZ)
    w = _run(p, int(seeds[0]))
    proposal = rcec.digest(p.samples)
    clipped = rcec.digest(p.samples * 0.4)
    return {
        "full": rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                             execution=rcec.Execution(proposal, proposal,
                                                      True)).state,
        "clipped": rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                                execution=rcec.Execution(proposal, clipped,
                                                         True)).state,
        "aborted": rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                                execution=rcec.Execution(proposal, proposal,
                                                         False,
                                                         aborted_at_s=3.0)
                                ).state,
    }


# --- instrument controls ---------------------------------------------------

def _constant_current_is_not_certified(**_):
    """POSITIVE control: a hover, with a LARGE voltage change, must not certify.

    Known without this campaign: the certificate's excitation condition is
    on the deconvolved S_II of the current, and a hover's current variance is
    sensor noise. The voltage moving a long way is irrelevant, and that is
    exactly control 4 of the work order.
    """
    tr = B.simulate(lambda t: 0.0, duration=DURATION, seed=CAL_SEED,
                    r0_delta=0.040)
    w = tr.window(ACTION_START, ACTION_START + ACTION_DURATION)
    clean = B.simulate(lambda t: 0.0, duration=DURATION,
                       seed=CAL_SEED).window(ACTION_START,
                                             ACTION_START + ACTION_DURATION)
    shift = float(w.v_meas.mean() - clean.v_meas.mean())
    cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget())
    return {"state": cert.state, "voltage_shift_v": shift}


def _an_adequate_waveform_is_certified(**_):
    """NEGATIVE control: the instrument must not be stuck on refusing.

    A whole-cycle cosine at 8 A through this plant delivers a realized S_II
    orders of magnitude above the requirement and a lever arm near zero. If
    this does not certify, the certificate refuses everything and every
    refusal elsewhere is meaningless.
    """
    p = RS.p1_palindromic(start=ACTION_START, duration=ACTION_DURATION,
                          amplitude=AMPLITUDE, hz=HZ, cycles=6)
    w = _run(p, CAL_SEED)
    return rcec.certify(w.t, w.i_meas, w.v_meas, budget()).state


def _controls():
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)
    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a large voltage step at constant current does not certify",
            kind=POSITIVE, run=_constant_current_is_not_certified,
            expect=lambda r: (r["state"] == rcec.INSUFFICIENT_EXCITATION
                              and abs(r["voltage_shift_v"]) > 0.3),
            basis=("the certificate's excitation condition is on the "
                   "deconvolved second moment of CURRENT; a hover's current "
                   "variance is sensor noise whatever the voltage does. The "
                   "expected answer follows from the condition's definition "
                   "and from Ohm's law on a 0.040 ohm rise at roughly 20 A, "
                   "not from this campaign"),
        ),
        negative=Control(
            name="an adequate realized waveform is certified",
            kind=NEGATIVE, run=_an_adequate_waveform_is_certified,
            expect=lambda s: s == rcec.CERTIFIED,
            basis=("an 8 A SIX-cycle cosine puts its energy above the "
                   "polarization envelope's fastest declared time constant "
                   "while delivering a realized second moment orders of "
                   "magnitude above the requirement; a certificate that "
                   "refused it would refuse everything. SIX rather than "
                   "three because the corrected polarization bound measures "
                   "a three-cycle probe as no longer adequate, which is "
                   "itself a finding and is recorded in the counterexample "
                   "log"),
        ),
    ))


def run(quick: bool = False) -> dict:
    started = time.time()
    seeds = LOCKED_SEEDS[:3] if quick else LOCKED_SEEDS
    lag = WC.estimate_lag(B.simulate, seeds=DEV_SEEDS)

    cands = p3_candidates()
    if quick:
        cands = cands[::6]
    p3 = RS.p3_shaped(start=ACTION_START, duration=ACTION_DURATION, hz=HZ,
                      plant=None, budget_eval=p3_objective, candidates=cands)

    common = dict(start=ACTION_START, duration=ACTION_DURATION,
                  amplitude=AMPLITUDE, hz=HZ, lag=lag,
                  authority_a=AUTHORITY_A, seed=4242)
    p4_proposal, _ = RS.p4_feedback(**common)

    proposals = {
        "P0_passive": RS.p0_passive(),
        "P1_palindromic": RS.p1_palindromic(**common),
        "P2_compensated": RS.p2_compensated(**common),
        "P3_shaped": p3,
        "P4_feedback": p4_proposal,
        "P5_random_safe": RS.p5_random_safe(**common),
        "P6_mission": RS.p6_mission(**common),
        "P7_oracle": RS.p7_oracle(**common),
    }

    def fb_factory():
        _, probe = RS.p4_feedback(**common)
        return probe

    results = {}
    for model, (plant, plant_kw) in PLANTS.items():
        for name, prop in proposals.items():
            key = f"{model}/{name}"
            results[key] = evaluate_arm(
                name, prop, seeds, plant_kw=plant_kw, plant=plant,
                feedback_factory=fb_factory if name == "P4_feedback" else None)
            rows = results[key]["rows"]
            results[key]["separation"] = {
                str(d): separation(rows, d) for d in R0_DELTAS if d > 0}
            results[key]["false_certifications"] = false_certifications(rows)
            states = {}
            for r in rows:
                for d, v in r["by_delta"].items():
                    states[v["state"]] = states.get(v["state"], 0) + 1
            results[key]["state_counts"] = states
            results[key]["model"] = model

    freq = frequency_sweep(seeds)
    hyst = hysteresis_hunt(40 if quick else 400, seeds)
    cross = cross_probe_check(seeds)
    adv = adversarial(120 if quick else 2000, seeds)
    opens = open_set(seeds)
    execs = execution_ablation(seeds)
    return _summarise(results, lag, proposals, seeds, started, quick,
                      adv, opens, execs, freq, hyst, cross)


def _summarise(results, lag, proposals, seeds, started, quick,
               adv, opens, execs, freq, hyst, cross) -> dict:
    def metric(model, arm, field):
        return results[f"{model}/{arm}"].get(field)

    def swept(model, arm) -> float:
        """Mean separation over the WHOLE preregistered delta sweep.

        THE AGGREGATION CHANGED AFTER THE PILOT AND THAT IS RECORDED. The
        first version scored a single delta, 0.020, where every arm reached
        1.00 and the comparison carried no information -- a ceiling effect,
        not a result. The preregistration fixes five R0 changes "spanning
        non-detectable to obvious"; averaging over all of them is the
        faithful reading of that and the single point was not. The target
        delta the BUDGET is written for is unchanged at 0.020; only the
        summary statistic is swept.
        """
        sep = metric(model, arm, "separation")
        vals = [sep[str(d)]["separated_of_certified"] or 0.0
                for d in R0_DELTAS if d > 0]
        return sum(vals) / len(vals)

    falsifiers = {}
    for model in PLANTS:
        best_active = max(swept(model, a) for a in
                          ("P2_compensated", "P3_shaped", "P4_feedback"))
        falsifiers[f"{model}:mission_matches_best_closed_loop_aware_arm"] = (
            swept(model, "P6_mission") >= best_active)
        falsifiers[f"{model}:no_arm_beats_naive_palindrome"] = (
            best_active <= swept(model, "P1_palindromic"))
        falsifiers[f"{model}:no_arm_beats_random_safe"] = (
            best_active <= swept(model, "P5_random_safe"))
    falsifiers["any_false_certification"] = any(
        r["false_certifications"] > 0 for r in results.values())
    falsifiers["adversarial_found_a_false_certification"] = (
        adv["false_certifications"] > 0)
    falsifiers["hysteresis_inside_declared_envelope_false_certified"] = (
        hyst["inside_declared_envelope"]["false_certifications"] > 0)
    falsifiers["an_unmodelled_fault_was_certified_at_the_largest_size"] = (
        opens[str(0.40)].get(rcec.CERTIFIED, 0) > 0)
    falsifiers["a_clipped_action_kept_its_certificate"] = (
        execs["clipped"] == rcec.CERTIFIED)
    falsifiers["an_aborted_action_kept_its_certificate"] = (
        execs["aborted"] == rcec.CERTIFIED)

    fired = sorted(k for k, v in falsifiers.items() if v)
    if falsifiers["any_false_certification"]:
        verdict = "CERTIFICATE_FALSIFIED"
    elif len(fired) >= 3:
        verdict = "ACTIVE_PROBING_NOT_SUPPORTED"
    elif fired:
        verdict = "SUPPORTED_WITH_NARROW_SCOPE"
    else:
        verdict = "SUPPORTED_IN_THIS_MODEL"

    return {
        "schema": SCHEMA,
        "preregistration":
            "research/active_evidence/realized_current/PREREGISTRATION.md",
        "owner_authorization":
            "research/active_evidence/realized_current/OWNER_AUTHORIZATION.md",
        "quarantine": "POST_FREEZE_RESEARCH_ONLY_AWAITING_REVIEW",
        "evidence_tier": "E0",
        "quick_mode": quick,
        "locked_seeds_used": list(seeds),
        "development_seeds": list(DEV_SEEDS),
        "calibration_seed": CAL_SEED,
        "seed_partitions_disjoint": not (set(seeds) & set(DEV_SEEDS)),
        "lag_model": lag.to_dict(),
        "budget": budget().to_dict(),
        "r0_deltas": list(R0_DELTAS),
        "arms": list(RS.ARMS),
        "not_executable": list(RS.NOT_EXECUTABLE),
        "results": results,
        "frequency_sweep": freq,
        "hysteresis_hunt": hyst,
        "cross_probe_check": cross,
        "adversarial": adv,
        "open_set": opens,
        "execution_ablation": execs,
        "separation_swept": {k: {str(d): v["separation"][str(d)]
                                 for d in R0_DELTAS if d > 0}
                             for k, v in results.items()},
        "falsifiers": falsifiers,
        "falsifiers_fired": fired,
        "verdict": verdict,
        "what_falsifies_the_certificate": (
            "a CERTIFIED_IN_MODEL run whose estimate intervals, widened by "
            "the certificate's own declared error bound, fail to separate "
            "the target change"),
        "battery_parameters_are_synthetic": (
            "Every pack and sensing parameter is synthetic and normalized. "
            "There is no real cell data in this repository and none is "
            "obtainable from this host. NOTHING here characterises lithium "
            "polymer, NMC, LFP or any other real chemistry."),
        "what_this_is_not": (
            "E0, simulation only. One synthetic pack, one loop family, one "
            "platform. Monte Carlo satisfaction of a constraint is empirical "
            "evidence and not a proof. No novelty is claimed: scholarly "
            "access was denied by organization policy and rechecked this "
            "session."),
        "elapsed_s": time.time() - started,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)

    doc = stamp(run(quick=args.quick), report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    print(f"\nverdict: {doc['verdict']}   elapsed {doc['elapsed_s']:.1f}s")
    print(f"{'model/arm':28s}{'sep@0.020':>11s}{'certd':>7s}"
          f"{'falseC':>8s}{'energy':>9s}{'lever':>9s}")
    for key in sorted(doc["results"]):
        r = doc["results"][key]
        s = r["separation"][str(TARGET_DELTA_R)]
        lev = [v.get("lever_arm_s") for row in r["rows"]
               for v in row["by_delta"].values() if v.get("lever_arm_s")
               is not None]
        med = float(np.median(lev)) if lev else float("nan")
        frac = s["separated_of_certified"]
        print(f"{key:28s}{(f'{frac:.2f}' if frac is not None else '  -'):>11s}"
              f"{s['certified_both']:7d}{r['false_certifications']:8d}"
              f"{r['nominal_energy_as']:9.2f}{med:9.3f}")
    f = doc["frequency_sweep"]
    print(f"\nfrequency sweep (constant amplitude and energy):")
    print(f"  {'cycles':>7s}{'f_eff':>8s}{'B_dyn':>10s}{'k*SE':>9s}"
          f"{'total':>9s}{'sep@0.005':>11s}")
    for c in sorted(f["rows"], key=int):
        r = f["rows"][c]
        fr = r["separation"]["0.005"]["fraction"]
        print(f"  {c:>7s}{r['effective_frequency_hz']:8.2f}"
              f"{r['B_dynamic']:10.5f}{r['k_sigma_SE']:9.5f}"
              f"{r['achieved_error']:9.5f}"
              f"{(f'{fr:.2f}' if fr is not None else '   -'):>11s}")
    print(f"  best cycle count: {f['best_cycles']}")
    h = doc["hysteresis_hunt"]
    print("\nhysteresis hunt (multi-RC pack with voltage hysteresis):")
    for k in ("inside_declared_envelope", "outside_declared_envelope"):
        r = h[k]
        print(f"  {k:30s} {r['draws']:4d} draws, {r['certified']:4d} "
              f"certified, {r['false_certifications']:3d} false, worst "
              f"ratio {r['worst_ratio']:.2f}")
    print(f"cross-probe: {doc['cross_probe_check']['verdict']}")
    a = doc["adversarial"]
    print(f"\nadversarial: {a['draws']} draws, {a['certified']} certified, "
          f"{a['false_certifications']} false certifications")
    print(f"open set  : {json.dumps(doc['open_set'][str(0.4)])}")
    print(f"execution : {json.dumps(doc['execution_ablation'])}")
    if doc["falsifiers_fired"]:
        print("\nFALSIFIERS FIRED:")
        for f in doc["falsifiers_fired"]:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
