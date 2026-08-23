"""WP-C8 Part 3 — why detection at every magnitude escalates at none.

CHARACTERISATION ONLY. No fix is implemented and no production file changes.
The correction belongs in a separate authorised change with before-and-after
evidence, as the IMU repair did.

--------------------------------------------------------------------------
1. THE ALGEBRA
--------------------------------------------------------------------------

Trust is a Beta belief updated once per tick (engine.py:146-149):

    alpha_{k+1} = rho * alpha_k + e_k
    beta_{k+1}  = rho * beta_k  + (1 - e_k)
    T_k         = alpha_k / (alpha_k + beta_k)

LEMMA (mass dynamics). Let S_k = alpha_k + beta_k. Adding the two updates,
S_{k+1} = rho * S_k + 1 regardless of e_k, with fixed point 1/(1-rho). The
denominator does not depend on the evidence. It DOES depend on rho, and rho is
adaptive (engine.py:143-144): calm flight has spread d = 0 and runs at
rho_max = 0.998, so the belief settles at

    S_0 = 1/(1 - rho_max) = 500

which is this system's implicit concentration cap.

THEOREM (step response with an adaptive forgetting factor). Suppose the belief
has settled at trust T_0 with mass S_0, and then evidence is held at a constant
e_f for N ticks while rho sits at a NEW constant value. Writing M = 1/(1-rho)
for the new fixed-point mass and x = rho^N,

    alpha_N = x * T_0 * S_0 + e_f * (1 - x) * M
    S_N     = x * S_0       +       (1 - x) * M

    T_N = [ x S_0 T_0 + (1 - x) M e_f ] / [ x S_0 + (1 - x) M ]          (1)

which is a mass-weighted average of the old trust and the new evidence, NOT a
simple first-order lag. THE ASYMPTOTE IS STILL e_f. What the old mass buys is
delay: the fault must first erode 500 units of accumulated agreement down to
the 20 units that rho = 0.95 sustains.

A NOTE ON HOW THIS WAS FOUND. The first version of this file asserted mass
invariance across the transition and gave T_N = T_0 rho^N + e_f (1 - rho^N).
Verified against the shipping TrustCore it missed by 0.198 and predicted
escalation at tick 35 where the code took 100. The invariance holds only for
CONSTANT rho; the settle phase runs at 0.998 and the fault phase at 0.95, so
S_0 = 500 while M = 20. The corrected equation (1) is exact.

COROLLARY (the escalation floor). At the gps node the fusion weights are
w_nbr 0.35, w_phys 0.30, w_temp 0.20, w_stat 0.15, summing to 1. A fault that
destroys ONLY the physics residual, leaving neighbour, temporal and statistical
evidence intact, holds

    e_f = (0.35*1 + 0.30*0 + 0.20*1 + 0.15*1) / 1.00 = 0.70

against a nav_caution threshold of 0.75. The margin is 0.05. Escalation is
possible but only just, and only with enough consecutive ticks.

COROLLARY (ticks required). Setting T_N = T* in (1) and solving for x,

    x = M (T* - e_f) / [ S_0 (T_0 - T*) + M (T* - e_f) ]
    N* = ln(x) / ln(rho)                                                 (2)

With phys at 0 and the others at 1 the spread d = 1, so rho sits at its floor
rho_min = 0.95 (engine.py:144) and M = 20. With T_0 = 1.00, e_f = 0.70,
T* = 0.75 and S_0 = 500 this gives N* about 94 ticks, or 3.8 s at 25 Hz.

Note what dominates. The numerator M(T* - e_f) = 20 * 0.05 = 1.0 is small
against S_0(T_0 - T*) = 500 * 0.25 = 125. THE DELAY IS SET BY THE ACCUMULATED
MASS, not by the evidence margin. Doubling the margin barely moves N*; halving
the concentration cap nearly halves it.

--------------------------------------------------------------------------
2. WHY A STEP CANNOT SUPPLY THOSE TICKS, AND WHY MAGNITUDE DOES NOT HELP
--------------------------------------------------------------------------

The step detector (online.py:366-372, 570-571) keeps a decaying peak:

    peak_{k+1} = 0.85 * peak_k          (no new step to refresh it)
    lam_step_k = (peak_k / 20)^2
    phys_k     = exp(-0.5 * max(0, lam_step_k - 1))

phys_k < f requires lam_step_k > 1 - 2 ln f, i.e.

    peak_k > 20 * sqrt(1 - 2 ln f) =: P_f

so the number of ticks the physics residual stays below f is

    N_floor(peak_0) = ln(peak_0 / P_f) / ln(1/0.85)                      (3)

which is LOGARITHMIC in the injected amplitude. Raising the position error by
a factor of 1000 buys ln(1000)/ln(1/0.85) = 42 extra ticks at most, and every
tick of that budget is spent on a residual that is already saturated at zero,
so it contributes nothing further to the evidence. THE DETECTOR SATURATES AND
THE CLOCK RUNS: that is the defect, in one line.

--------------------------------------------------------------------------
3. THE PREDICTION THIS MAKES, WHICH PART 3.2 TESTS
--------------------------------------------------------------------------

A SUSTAINED fault that holds the residual at the floor for at least N* ticks
must escalate, at any magnitude above the detector's saturation point. A ramp
does exactly that: it refreshes the step peak every GPS sample, so the floor
persists for the whole ramp rather than decaying.

    minimum escalating duration = N* / tick_hz = about 1.35 s

independent of magnitude, provided the magnitude is enough to saturate.

Run:  PYTHONPATH=. python research/wp_c8/escalation_algebra.py
Out:  research/wp_c8/results/escalation_algebra.json
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.trust_engine.engine import EngineConfig, TrustCore     # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
TICK_HZ = 25.0
NAV_CAUTION = 0.75
DECAY = 0.85
STEP_SIGMA = 20.0


def closed_form(t0, e_f, rho, n, s0):
    """Equation (1): mass-weighted average of old trust and new evidence."""
    m = 1.0 / (1.0 - rho)
    x = rho ** n
    return (x * s0 * t0 + (1.0 - x) * m * e_f) / (x * s0 + (1.0 - x) * m)


def ticks_required(t0, e_f, rho, s0, t_star=NAV_CAUTION):
    """Equation (2). None when the asymptote never reaches the threshold."""
    if e_f >= t_star:
        return None
    if t0 <= t_star:
        return 0
    m = 1.0 / (1.0 - rho)
    x = m * (t_star - e_f) / (s0 * (t0 - t_star) + m * (t_star - e_f))
    return math.log(x) / math.log(rho)


def floor_ticks(peak0, f=0.10):
    """Equation (3): how long a decaying step keeps the residual below f."""
    p_f = STEP_SIGMA * math.sqrt(max(1e-12, 1.0 - 2.0 * math.log(f)))
    if peak0 <= p_f:
        return 0.0
    return math.log(peak0 / p_f) / math.log(1.0 / DECAY)


def e_floor(cfg, dead=("phys",), alive_value=1.0):
    """Evidence asymptote when the named components are destroyed."""
    w = {"nbr": cfg.w_nbr, "phys": cfg.w_phys, "temp": cfg.w_temp,
         "stat": cfg.w_stat}
    num = sum(wi * (0.0 if k in dead else alive_value) for k, wi in w.items())
    return num / sum(w.values())


def verify_against_trustcore(cfg, e_f, n_hold=200):
    """Drive the SHIPPING TrustCore with a synthetic evidence sequence.

    The algebra above is only worth anything if the deployed recursion obeys
    it. This settles the belief at a healthy level, then holds the physics
    component at zero and compares tick by tick against equation (1).
    """
    # A neighbour edge MUST be present or c_nbr is None and the weights
    # renormalise over three components instead of four, moving e_f from 0.70
    # to 0.35/0.65 = 0.538. The first version of this check omitted the edge
    # and the closed form missed by 0.17; the discrepancy was the missing
    # edge, not the algebra.
    core = TrustCore(["gps", "baro"], cfg)
    edges = {"altitude_baro": ("baro", "gps", 0.0, 1.0)}
    healthy = ({"gps": (0.0, 1.0), "baro": (0.0, 1.0)},
               {"gps": 0.0, "baro": 0.0}, {"gps": 0.0, "baro": 0.0},
               {"gps": True, "baro": True})
    for _ in range(1500):
        core.step(edges, *healthy)
    t0 = core.trust["gps"]
    s0 = core.alpha["gps"] + core.beta["gps"]

    # hold: physics residual saturated, the other three healthy. lam huge ->
    # consistency exp(-0.5*(lam-1)) underflows to 0, which is the floor.
    trace, worst, crossed = [], 0.0, None
    for k in range(1, n_hold + 1):
        res = core.step(edges, {"gps": (1e6, 1.0), "baro": (0.0, 1.0)},
                        {"gps": 0.0, "baro": 0.0},
                        {"gps": 0.0, "baro": 0.0},
                        {"gps": True, "baro": True})
        actual = res["gps"]["trust"]
        if crossed is None and actual <= NAV_CAUTION:
            crossed = k
        rho = res["gps"]["rho"]
        pred = closed_form(t0, e_f, rho, k, s0)
        worst = max(worst, abs(actual - pred))
        if k <= 60 or k % 20 == 0:
            trace.append({"k": k, "actual": round(actual, 6),
                          "predicted": round(pred, 6),
                          "rho": round(rho, 6),
                          "evidence": round(res["gps"]["evidence"], 6)})
    return {
        "settled_trust_T0": round(t0, 6),
        "settled_mass_S0": round(s0, 4),
        "concentration_cap_1_over_1_minus_rho_max": round(
            1.0 / (1.0 - cfg.rho_max), 1),
        "fault_phase_mass_M": round(1.0 / (1.0 - cfg.rho_min), 1),
        "rho_observed": round(trace[0]["rho"], 6),
        "evidence_observed": round(trace[0]["evidence"], 6),
        "evidence_predicted": round(e_f, 6),
        "max_abs_error_vs_equation_1": round(worst, 8),
        "closed_form_matches_shipping_code": worst < 1e-9,
        "first_tick_at_or_below_threshold": crossed,
        "note_on_crossing": ("scanned over every tick, not over the sampled "
                             "trace below. An earlier version scanned the "
                             "sample and reported 100 because 94 was not in "
                             "it."),
        "trace": trace,
    }


def _retro(n_star):
    """Does N* separate every run WP-C7 already flew?

    WP-C7 measured floor ticks and alarm outcome for six steps and three
    ramps, before this derivation existed. If N* is the real boundary it must
    classify all nine correctly with no free parameters.
    """
    runs = [
        ("step 5.6 m", 26, False), ("step 22.3 m", 32, False),
        ("step 55.7 m", 33, False), ("step 222.6 m", 33, False),
        ("step 1113.2 m", 33, False), ("step 5566.0 m", 40, False),
        ("ramp 5 s", 104, True), ("ramp 20 s", 168, True),
        ("ramp 60 s", 139, True),
    ]
    rows, wrong = [], 0
    for label, ticks, alarmed in runs:
        pred = ticks >= n_star
        ok = pred == alarmed
        wrong += not ok
        rows.append({"run": label, "measured_floor_ticks": ticks,
                     "predicted_escalates": pred,
                     "measured_escalated": alarmed, "correct": ok})
    return {
        "boundary_N_star_ticks": round(n_star, 2),
        "runs": rows,
        "n_misclassified": wrong,
        "separates_every_wp_c7_run": wrong == 0,
        "why_this_is_strong": (
            "the nine runs were flown before the derivation existed and the "
            "boundary has no free parameters: N* comes from the fusion "
            "weights, the forgetting bounds and the threshold, all read from "
            "source. Steps range 26 to 40 floor ticks and none escalated; "
            "ramps range 104 to 168 and all did; N* = 93 lies in the gap."),
    }


def main() -> int:
    cfg = EngineConfig()
    e_f = e_floor(cfg)
    rho_fast = cfg.rho_min          # spread d = 1 drives rho to its floor

    ver = verify_against_trustcore(cfg, e_f)
    t0 = ver["settled_trust_T0"]
    s0 = ver["settled_mass_S0"]
    rho_obs = ver["rho_observed"]
    n_star = ticks_required(t0, e_f, rho_obs, s0)

    # Equation (3) against the magnitudes WP-C7 actually flew. peak is the
    # unexplained speed |fd_vel - vel| at the jump: error / GPS interval.
    gps_dt = 1.0 / 5.0
    sweep = []
    for err_m in (5.6, 22.3, 55.7, 222.6, 1113.2, 5566.0):
        peak = err_m / gps_dt
        n_f = floor_ticks(peak)
        sweep.append({
            "position_error_m": err_m,
            "implied_peak_m_s": round(peak, 1),
            "predicted_floor_ticks": round(n_f, 1),
            "predicted_min_trust": round(
                closed_form(t0, e_f, rho_obs, n_f, s0), 4),
            "predicted_escalates": bool(n_f >= n_star) if n_star else False,
        })

    # WP-C7 measured these, on the same magnitudes.
    measured = {5.6: (26, 0.9237), 22.3: (32, 0.9089), 55.7: (33, 0.9063),
                222.6: (33, 0.9061), 1113.2: (33, 0.9061),
                5566.0: (40, 0.8881)}
    for row in sweep:
        obs = measured.get(row["position_error_m"])
        if obs:
            row["measured_floor_ticks"] = obs[0]
            row["measured_min_trust"] = obs[1]
            row["floor_tick_error"] = round(
                row["predicted_floor_ticks"] - obs[0], 1)
            row["trust_error"] = round(
                row["predicted_min_trust"] - obs[1], 4)

    # The magnitude-independence result, stated as a number.
    decades = math.log(1000.0) / math.log(1.0 / DECAY)

    report = {
        "characterisation_only": True,
        "no_fix_implemented": True,
        "constants_from_source": {
            "w_nbr": cfg.w_nbr, "w_phys": cfg.w_phys, "w_temp": cfg.w_temp,
            "w_stat": cfg.w_stat, "rho_min": cfg.rho_min,
            "rho_max": cfg.rho_max, "step_decay_per_tick": DECAY,
            "step_sigma_m_s": STEP_SIGMA, "tick_hz": TICK_HZ,
            "nav_caution": NAV_CAUTION,
        },
        "lemma_mass_invariance": (
            "S_{k+1} = rho*S_k + 1 regardless of evidence, fixed point "
            "1/(1-rho). The Beta denominator is constant once settled."),
        "equation_1": "T_N = (x S_0 T_0 + (1-x) M e_f) / (x S_0 + (1-x) M), "
                      "x = rho^N, M = 1/(1-rho)",
        "equation_2": "N* = ln(M(T*-e_f) / (S_0(T_0-T*) + M(T*-e_f))) / "
                      "ln(rho)",
        "what_dominates_N_star": {
            "mass_term_S0_times_T0_minus_Tstar": round(
                s0 * (t0 - NAV_CAUTION), 2),
            "margin_term_M_times_Tstar_minus_ef": round(
                (1.0 / (1.0 - rho_obs)) * (NAV_CAUTION - e_f), 2),
            "statement": (
                "the accumulated mass term is two orders of magnitude larger "
                "than the evidence-margin term, so the escalation delay is "
                "set by how much agreement the calm period banked, not by how "
                "bad the fault is. Halving the concentration cap nearly "
                "halves the delay; doubling the threshold margin barely "
                "moves it."),
        },
        "equation_3": "N_floor(peak) = ln(peak / (20*sqrt(1 - 2 ln f))) / "
                      "ln(1/0.85)",
        "evidence_asymptote_e_f": round(e_f, 6),
        "why_e_f_is_0_70": (
            "a fault that destroys only the physics residual removes weight "
            "w_phys = 0.30 of a unit weight sum, so evidence cannot fall "
            "below 0.70 however bad the residual is. The nav_caution "
            "threshold is 0.75, leaving a margin of 0.05."),
        "rho_under_full_disagreement": rho_fast,
        "ticks_required_N_star": round(n_star, 2) if n_star else None,
        "seconds_required": round(n_star / TICK_HZ, 3) if n_star else None,
        "verification_against_shipping_trustcore": ver,
        "magnitude_sweep_prediction_vs_wp_c7_measurement": sweep,
        "magnitude_buys_only_logarithmic_time": {
            "extra_ticks_per_1000x_amplitude": round(decades, 1),
            "statement": (
                "N_floor grows as ln(amplitude), and every tick of it is "
                "spent on a residual already saturated at zero, so it adds "
                "no further evidence. A detector that saturates while its "
                "decay runs cannot escalate on magnitude alone."),
        },
        "retro_validation_against_wp_c7": _retro(n_star),
        "prediction_for_part_3_2": {
            "claim": ("a SUSTAINED fault holding the physics residual at the "
                      "floor escalates after N* ticks at ANY magnitude above "
                      "saturation, and never before"),
            "minimum_escalating_duration_s":
                round(n_star / TICK_HZ, 3) if n_star else None,
            "independent_of_magnitude": True,
            "how_it_is_tested": (
                "ramps refresh the step peak every GPS sample, so the floor "
                "persists for the whole ramp instead of decaying. Sweeping "
                "ramp duration across N*/25 Hz should show a sharp boundary."),
        },
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "escalation_algebra.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print("=== derivation ===")
    print(f"  e_f (evidence asymptote, phys destroyed) = {e_f:.4f}")
    print(f"  nav_caution                              = {NAV_CAUTION}")
    print(f"  T_0 (settled)                            = {t0:.4f}")
    print(f"  rho under full disagreement              = {rho_obs:.4f}")
    print(f"  S_0 settled mass (concentration cap)     = {s0:.1f}")
    print(f"  M  fault-phase mass 1/(1-rho)            = "
          f"{1.0 / (1.0 - rho_obs):.1f}")
    print(f"  N* ticks required to cross threshold     = "
          f"{n_star:.2f}  ({n_star / TICK_HZ:.3f} s)")
    print("\n=== verification against the shipping TrustCore ===")
    print(f"  max |actual - equation(1)|  = "
          f"{ver['max_abs_error_vs_equation_1']:.2e}")
    print(f"  closed form matches code    = "
          f"{ver['closed_form_matches_shipping_code']}")
    print(f"  first tick <= threshold     = "
          f"{ver['first_tick_at_or_below_threshold']}")
    print("\n=== equation (3) against WP-C7 measurements ===")
    print(f"{'error m':>10s} {'pred ticks':>11s} {'meas ticks':>11s} "
          f"{'pred trust':>11s} {'meas trust':>11s}")
    for r in sweep:
        print(f"{r['position_error_m']:>10.1f} "
              f"{r['predicted_floor_ticks']:>11.1f} "
              f"{r.get('measured_floor_ticks', '-'):>11} "
              f"{r['predicted_min_trust']:>11.4f} "
              f"{r.get('measured_min_trust', '-'):>11}")
    print(f"\nmagnitude buys {decades:.1f} extra ticks per 1000x, all of them "
          "on a saturated residual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
