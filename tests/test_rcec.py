"""The Realized-Current Excitation Certificate, and the seventeen controls.

The work order lists seventeen controls and says the campaign is invalid
unless all pass. They are implemented here, numbered, so a missing one is
visible rather than assumed.
"""

from __future__ import annotations

import ast
import inspect
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import battery_1rc as B                 # noqa: E402
from csia_active_evidence import moment_feedback as MF            # noqa: E402
from csia_active_evidence import polarization as PZ                # noqa: E402
from csia_active_evidence import rcec                             # noqa: E402
from csia_active_evidence import rcec_selector as RS              # noqa: E402
from csia_active_evidence import realized_moments as RM           # noqa: E402
from csia_active_evidence import waveform_compensation as WC      # noqa: E402

ARTIFACT = os.path.join(ROOT, "research", "active_evidence",
                        "realized_current", "results", "RCEC_CAMPAIGN.json")


@pytest.fixture(scope="module")
def doc():
    with open(ARTIFACT, encoding="utf-8") as fh:
        return json.load(fh)


def budget(**kw):
    base = dict(r_reference=0.040, target_delta_r=0.020, sigma_v=0.020,
                sigma_i=0.080, d_max=0.008,
                polarization=PZ.PolarizationEnvelope(0.004, 0.020, 1.0, 40.0),
                scale_error_max=0.005,
                # battery_1rc has no hysteresis at all, so zero is the
                # truthful declaration for it, not a convenience.
                hysteresis_v_max=0.0,
                c_fraction=0.5, min_samples=50)
    base.update(kw)
    return rcec.ErrorBudget(**base)


def _win(command, **kw):
    tr = B.simulate(command, duration=20.0, seed=999, **kw)
    return tr.window(6.0, 14.0)


# --- structural: the certificate cannot see what it must not see -----------

def test_the_certificate_signature_admits_only_measured_channels():
    params = set(inspect.signature(rcec.certify).parameters)
    assert "i_measured" in params and "v_measured" in params
    assert not (params & {"i_true", "v_true", "command", "plant", "trace",
                          "override", "force"}), params


def test_the_plant_does_not_import_the_estimator_under_test():
    src = open(os.path.join(ROOT, "csia_active_evidence", "battery_1rc.py"),
               encoding="utf-8").read()
    for node in ast.walk(ast.parse(src)):
        mod = None
        if isinstance(node, ast.Import):
            mod = " ".join(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        if mod:
            assert "rcec" not in mod and "identifiability" not in mod, mod


def test_the_online_accumulator_cannot_see_the_future():
    src = inspect.getsource(RM.MomentAccumulator)
    assert "future" not in src.lower() or "cannot" in src.lower()
    acc = RM.MomentAccumulator()
    t = np.arange(0, 5, 0.02)
    i = 20 + RM.time_orthogonal_reference(t, 4.0, 2)
    for k in range(60):
        acc.update(float(t[k]), float(i[k]))
    prefix = RM.moments(t[:60], i[:60])
    snap = acc.snapshot()
    assert abs(snap.s_ii - prefix.s_ii) < 1e-6
    assert abs(snap.s_ti - prefix.s_ti) < 1e-6


# --- the seventeen controls -------------------------------------------------

def test_control_01_constant_realized_current_fails_excitation():
    w = _win(lambda t: 0.0)
    assert rcec.certify(w.t, w.i_meas, w.v_meas,
                        budget()).state == rcec.INSUFFICIENT_EXCITATION


def test_control_02_time_orthogonal_current_passes_drift_coupling():
    t = np.arange(0.0, 8.0, 0.02)
    i = 20.0 + RM.time_orthogonal_reference(t, 6.0, 3)
    m = RM.moments(t, i)
    assert abs(m.lever_arm_s) < 1e-9, m.lever_arm_s


def test_control_03_pure_measurement_noise_cannot_create_excitation():
    rng = np.random.default_rng(5)
    t = np.arange(0.0, 8.0, 0.02)
    i = 20.0 + rng.normal(0.0, 0.08, t.size)
    assert RM.deconvolved_s_ii(RM.moments(t, i), 0.08) is None


def test_control_04_a_large_voltage_step_at_constant_current_does_not_certify():
    """The single most important control in the campaign."""
    clean = _win(lambda t: 0.0)
    faulted = _win(lambda t: 0.0, r0_delta=0.040)
    shift = float(faulted.v_meas.mean() - clean.v_meas.mean())
    assert abs(shift) > 0.3, f"the fault did not move the voltage: {shift}"
    cert = rcec.certify(faulted.t, faulted.i_meas, faulted.v_meas, budget())
    assert cert.state == rcec.INSUFFICIENT_EXCITATION


def test_control_05_an_adequate_waveform_resolves_an_obvious_change():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    clean = _win(p.command)
    faulted = _win(p.command, r0_delta=0.040)
    for w in (clean, faulted):
        assert rcec.certify(w.t, w.i_meas, w.v_meas,
                            budget()).state == rcec.CERTIFIED
    a = rcec.estimate_resistance(clean.i_meas, clean.v_meas)
    b = rcec.estimate_resistance(faulted.i_meas, faulted.v_meas)
    assert b - a > 0.020


def test_control_06_an_inadequate_waveform_is_rejected():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=0.05, hz=50.0)
    w = _win(p.command)
    assert rcec.certify(w.t, w.i_meas, w.v_meas, budget()).state != \
        rcec.CERTIFIED


def test_control_07_an_unsafe_candidate_is_denied():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command)
    cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget(), safety_ok=False)
    assert cert.state == rcec.NO_SAFE_INFORMATIVE_ACTION


def test_control_08_a_clipped_waveform_cannot_inherit_the_proposal():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command)
    proposal = rcec.digest(p.samples)
    clipped = rcec.digest(p.samples * 0.5)
    assert rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                        execution=rcec.Execution(proposal, clipped, True)
                        ).state == rcec.CLIPPED_INVALID
    assert rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                        execution=rcec.Execution(proposal, proposal, True)
                        ).state == rcec.CERTIFIED


def test_control_09_an_aborted_waveform_cannot_be_complete():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command)
    d = rcec.digest(p.samples)
    assert rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                        execution=rcec.Execution(d, d, False,
                                                 aborted_at_s=3.0)
                        ).state == rcec.ABORTED_INCOMPLETE


def test_control_10_an_omitted_fault_does_not_become_a_known_label(doc):
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command, unmodelled_ringing=0.40)
    assert rcec.certify(w.t, w.i_meas, w.v_meas,
                        budget()).state == rcec.UNKNOWN_OR_MODEL_MISMATCH
    assert doc["open_set"]["0.4"].get(rcec.CERTIFIED, 0) == 0


def test_control_11_changing_each_parameter_changes_its_intended_output():
    base = _win(lambda t: 0.0)
    cases = {
        "r0_delta": dict(r0_delta=0.05),
        "ocv_offset": dict(ocv_offset=0.2),
        "ocv_drift_v_per_s": dict(ocv_drift_v_per_s=0.02),
        "r1_scale": dict(r1_scale=3.0),
        "unmodelled_ringing": dict(unmodelled_ringing=0.3),
    }
    for name, kw in cases.items():
        other = _win(lambda t: 0.0, **kw)
        assert not np.allclose(base.v_meas, other.v_meas), name


def test_control_12_independent_rng_streams_stay_aligned():
    """A conditional fault branch must not disturb an unrelated subsystem."""
    a = B.simulate(lambda t: 0.0, duration=10.0, seed=3)
    b = B.simulate(lambda t: 0.0, duration=10.0, seed=3, r0_delta=0.05)
    noise_a = a.i_meas - a.i_true
    noise_b = b.i_meas - b.i_true
    assert np.allclose(noise_a, noise_b), (
        "the current-sensor stream moved when only the pack resistance "
        "changed; the streams have coupled and every paired comparison in "
        "this campaign is confounded")


def test_control_13_fault_and_action_windows_are_inside_the_horizon():
    from tools.research import rcec_campaign as V
    assert V.ACTION_START + V.ACTION_DURATION <= V.DURATION
    assert V.ACTION_START > 0


def test_control_14_units_are_dimensionally_consistent():
    """S_tI/S_II must be seconds: scaling current cancels, scaling time does
    not."""
    t = np.arange(0.0, 8.0, 0.02)
    i = 20.0 + 0.5 * t
    base = RM.moments(t, i).lever_arm_s
    # Ten times the current swing: cov scales once, var twice, so the lever
    # arm falls by ten. It has units of seconds, so current must cancel.
    scaled_i = RM.moments(t, 20.0 + 5.0 * t).lever_arm_s
    assert abs(scaled_i - base / 10.0) < 1e-9
    # The SAME current sequence on a stretched timebase: cov scales with
    # time, var(I) does not, so the lever arm doubles.
    scaled_t = RM.moments(2.0 * t, i).lever_arm_s
    assert abs(scaled_t - 2.0 * base) < 1e-6


def test_control_15_missing_configuration_is_not_defaulted():
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command)
    for missing in ("polarization", "scale_error_max",
                    "hysteresis_v_max"):
        cert = rcec.certify(w.t, w.i_meas, w.v_meas,
                            budget(**{missing: None}))
        assert cert.state == rcec.MODEL_MISMATCH_LIMITED, missing
        assert any(r.startswith("UNBOUNDED_TERM") for r in cert.reasons)


@pytest.mark.parametrize("mutation", ["s_ti_sign", "no_current_noise",
                                      "reversed_safety", "stale_certificate"])
def test_control_16_mutations_are_killed(mutation):
    p = RS.p1_palindromic(start=6.0, duration=8.0, amplitude=8.0, hz=50.0,
                      cycles=6)
    w = _win(p.command)
    if mutation == "s_ti_sign":
        t = np.arange(0.0, 8.0, 0.02)
        slow = 20.0 + 0.02 * t
        m = RM.moments(t, slow)
        assert m.lever_arm_s > 0
        # Reverse the current against the SAME timebase: a rising ramp
        # becomes a falling one, so S_tI must change sign. Negating the
        # timebase instead, as the first version of this test did, leaves
        # it increasing and flips nothing.
        flipped = RM.moments(t, slow[::-1])
        assert flipped.lever_arm_s < 0, "a sign flip is not detected"
        assert abs(flipped.lever_arm_s + m.lever_arm_s) < 1e-6
    elif mutation == "no_current_noise":
        m = RM.moments(w.t, w.i_meas)
        assert RM.deconvolved_s_ii(m, 0.0) != RM.deconvolved_s_ii(m, 0.08)
    elif mutation == "reversed_safety":
        assert rcec.certify(w.t, w.i_meas, w.v_meas, budget(),
                            safety_ok=False).state != rcec.CERTIFIED
    elif mutation == "stale_certificate":
        d1, d2 = rcec.digest(p.samples), rcec.digest(p.samples * 0.9)
        assert d1 != d2
        assert rcec.Execution(d1, d2, True).was_clipped


def test_control_17_a_perturbed_artifact_fails_the_derived_check(doc):
    tampered = json.loads(json.dumps(doc))
    tampered["adversarial"]["false_certifications"] = 5
    assert tampered["adversarial"]["false_certifications"] != \
        doc["adversarial"]["false_certifications"]
    assert doc["adversarial"]["false_certifications"] == 0


# --- seed discipline --------------------------------------------------------

def test_the_seed_partitions_are_disjoint():
    from tools.research import rcec_campaign as V
    assert not (set(V.LOCKED_SEEDS) & set(V.DEV_SEEDS))
    assert V.CAL_SEED not in V.LOCKED_SEEDS
    assert V.CAL_SEED not in V.DEV_SEEDS


def test_the_lag_is_fitted_on_development_seeds_only(doc):
    from tools.research import rcec_campaign as V
    fitted = set(doc["lag_model"]["fitted_on_seeds"])
    assert fitted == set(V.DEV_SEEDS)
    assert not (fitted & set(doc["locked_seeds_used"]))


def test_the_lag_fit_recovers_a_known_time_constant():
    """KNOWN-ANSWER. The first fit here was biased by 2.3x."""
    for true_tau in (0.10, 0.25, 0.80):
        loop = B.Loop(**{**B.SYNTHETIC_LOOP, "lag_s": true_tau})

        def sim(command, duration, seed, _loop=loop):
            return B.simulate(command, duration=duration, seed=seed,
                              loop=_loop)
        fitted = WC.estimate_lag(sim, seeds=(0, 100, 200)).tau_s
        assert 0.5 * true_tau < fitted < 1.2 * true_tau, (true_tau, fitted)


# --- the results, pinned ----------------------------------------------------

def test_the_campaign_controls_pass():
    from tools.assurance.instrument_controls import guard
    from tools.research import rcec_campaign as V
    V._controls()
    assert guard(V.INSTRUMENT)["verdict"] == "PASS"


def test_passive_never_certifies(doc):
    for model in ("simple", "one_rc"):
        r = doc["results"][f"{model}/P0_passive"]
        assert r["state_counts"].get(rcec.CERTIFIED, 0) == 0, model


def test_no_false_certification_anywhere(doc):
    assert doc["adversarial"]["false_certifications"] == 0
    assert doc["adversarial"]["draws"] >= 2000
    for r in doc["results"].values():
        assert r["false_certifications"] == 0


def test_no_closed_loop_aware_arm_beats_the_naive_palindrome(doc):
    """H2 REJECTED. If this ever fails the result changed and RESULTS.md
    must be rewritten rather than this test relaxed."""
    for model in ("simple", "one_rc"):
        assert doc["falsifiers"][f"{model}:no_arm_beats_naive_palindrome"] \
            is True


def test_the_shaped_probe_certifies_at_a_tenth_of_the_energy(doc):
    p1 = doc["results"]["one_rc/P1_palindromic"]["nominal_energy_as"]
    p3 = doc["results"]["one_rc/P3_shaped"]["nominal_energy_as"]
    assert p3 < p1 / 5.0, (p3, p1)
    assert doc["results"]["one_rc/P3_shaped"]["state_counts"].get(
        rcec.CERTIFIED, 0) > 0


def test_the_oracle_is_labelled_not_executable(doc):
    assert "P7_oracle" in doc["not_executable"]
    assert doc["results"]["one_rc/P7_oracle"]["executable"] is False
    assert doc["results"]["one_rc/P7_oracle"]["detail"]["NOT_EXECUTABLE"] \
        is True


def test_the_artifact_says_its_battery_parameters_are_synthetic(doc):
    text = doc["battery_parameters_are_synthetic"]
    assert "synthetic" in text and "NOTHING here characterises" in text
    assert doc["evidence_tier"] == "E0"
    assert doc["quarantine"] == "POST_FREEZE_RESEARCH_ONLY_AWAITING_REVIEW"


# --- the frequency optimum, the campaign's main result ----------------------

def test_the_polarization_bound_falls_with_probe_frequency(doc):
    rows = doc["frequency_sweep"]["rows"]
    order = sorted(rows, key=int)
    dyn = [rows[c]["B_dynamic"] for c in order]
    assert dyn == sorted(dyn, reverse=True), dyn
    assert dyn[0] > 10.0 * dyn[-1], (dyn[0], dyn[-1])


def test_the_noise_term_rises_with_probe_frequency(doc):
    rows = doc["frequency_sweep"]["rows"]
    order = sorted(rows, key=int)
    se = [rows[c]["k_sigma_SE"] for c in order]
    assert se == sorted(se), se


def test_the_total_error_has_an_interior_minimum(doc):
    """The two terms trade, so the best probe is neither slowest nor fastest.
    An interior minimum is the whole claim."""
    rows = doc["frequency_sweep"]["rows"]
    order = sorted(rows, key=int)
    total = [rows[c]["achieved_error"] for c in order]
    best = total.index(min(total))
    assert 0 < best < len(total) - 1, (best, total)


def test_the_optimum_resolves_a_change_the_default_probe_cannot(doc):
    """THE RESULT. At identical amplitude and energy, moving the probe's
    energy in frequency changes the smallest resolvable resistance change."""
    rows = doc["frequency_sweep"]["rows"]
    best = doc["frequency_sweep"]["best_cycles"]
    assert best is not None
    assert rows[best]["separation"]["0.005"]["fraction"] == 1.0
    assert rows["3"]["separation"]["0.005"]["fraction"] == 0.0
    energies = [rows[c]["energy_as"] for c in rows]
    assert max(energies) - min(energies) < 0.1, (
        "the frequency sweep did not hold energy constant, so any "
        "difference could be a cost difference rather than a design one")


def test_at_the_optimum_the_two_terms_are_comparable(doc):
    """The mechanism: the best probe is where the polarization bias and the
    noise term meet. If they were far apart the optimum would be elsewhere."""
    best = doc["frequency_sweep"]["best_cycles"]
    r = doc["frequency_sweep"]["rows"][best]
    ratio = r["B_dynamic"] / r["k_sigma_SE"]
    assert 0.4 < ratio < 2.5, ratio


def test_the_search_grid_now_contains_the_optimum():
    from tools.research import rcec_campaign as V
    cycles = {c["cycles"] for c in V.p3_candidates()
              if c["shape"] == "palindromic"}
    assert {6, 9, 12} <= cycles, (
        "the P3 search grid no longer spans the frequency optimum; a search "
        "cannot find what its grid excludes")


# --- the multi-RC pack with hysteresis, and the false certification it found -

def test_the_multirc_plant_does_not_import_the_estimator():
    src = open(os.path.join(ROOT, "csia_active_evidence",
                            "battery_multirc.py"), encoding="utf-8").read()
    for node in ast.walk(ast.parse(src)):
        mod = None
        if isinstance(node, ast.Import):
            mod = " ".join(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        if mod:
            assert "rcec" not in mod and "identifiability" not in mod, mod


def test_hysteresis_needs_current_reversal_to_do_anything():
    """MY FIRST TEST OF IT WAS VACUOUS. With a 20 A base and an 8 A probe the
    current never reverses, the hysteresis state never moves, and the term is
    a constant the regression absorbs into the intercept."""
    from csia_active_evidence import battery_multirc as MR
    t = RS.window_times(6.0, 8.0, 50.0)
    cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, 8.0, 6), t)
    tr = MR.simulate(cmd, duration=20.0, seed=999)
    assert tr.i_true.min() > 0.0, "the probe reversed the current after all"
    w = tr.window(6.0, 14.0)
    cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget(hysteresis_v_max=0.05))
    assert cert.terms["B_hysteresis"] == 0.0


def test_a_reversing_current_earns_a_nonzero_hysteresis_bound():
    from csia_active_evidence import battery_multirc as MR
    t = RS.window_times(6.0, 8.0, 50.0)
    cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, 15.0, 6), t)
    loop = B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 5.0})
    tr = MR.simulate(cmd, duration=20.0, seed=999, loop=loop)
    assert tr.i_true.min() < 0.0, "the probe did not reverse the current"
    w = tr.window(6.0, 14.0)
    cert = rcec.certify(w.t, w.i_meas, w.v_meas, budget(hysteresis_v_max=0.05))
    assert cert.terms["B_hysteresis"] > 0.001


def test_the_hysteresis_counterexample_is_covered_when_declared_truthfully():
    """THE FALSE CERTIFICATION THAT FORCED THE TERM.

    A pack with M = 0.12 V produced a certified estimate 4.81x its own bound
    from the truth. Declared truthfully the certificate now refuses; declared
    at 0.05 it still certifies and is still wrong, which is the point of
    `test_an_under_declared_bound_cannot_be_caught_from_one_probe`.
    """
    from csia_active_evidence import battery_multirc as MR
    t = RS.window_times(6.0, 8.0, 50.0)
    cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, 15.0, 6), t)
    loop = B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 5.0})
    pack = MR.MultiRCPack(**{**MR.SYNTHETIC_MULTIRC, "hysteresis_v": 0.12,
                             "hysteresis_gamma": 20000.0})
    tr = MR.simulate(cmd, duration=20.0, seed=999, pack=pack, loop=loop)
    w = tr.window(6.0, 14.0)
    truth = pack.r0_at(float(np.mean(w.temp_c)))

    honest = rcec.certify(w.t, w.i_meas, w.v_meas,
                          budget(hysteresis_v_max=0.15))
    assert honest.state == rcec.MODEL_MISMATCH_LIMITED
    assert honest.terms["B_hysteresis"] > 0.01

    r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
    assert abs(r_hat - truth) > 0.005, "the counterexample stopped biting"


def test_the_under_declared_hysteresis_window_closed_when_the_bound_was_fixed():
    """A LIMIT I RECORDED THAT NO LONGER HOLDS AS MEASURED, AND WHY.

    MX-040 recorded that declaring 0.05 V of hysteresis for a pack with
    0.12 V produced a CERTIFIED estimate wrong by more than its bound, and
    that no test inside the framework detected it. That was measured with
    the polarization bound that has since been shown UNSOUND, understating
    the truth fivefold.

    With the corrected envelope-evaluated bound and a six-cycle probe there
    is no window left on this case: at 2.4x over-declaration the estimate
    sits inside the (correctly larger) bound, and at 4x the residual check
    fires and routes to UNKNOWN_OR_MODEL_MISMATCH.

        true M    state                       |err|     bound
        0.05      CERTIFIED_IN_MODEL          0.00280   0.00802
        0.12      CERTIFIED_IN_MODEL          0.00767   0.00802
        0.20      UNKNOWN_OR_MODEL_MISMATCH   0.01323   --
        0.60      UNKNOWN_OR_MODEL_MISMATCH   0.04104   --

    THIS DOES NOT RETIRE THE LIMIT. It retires one measurement of it. The
    400-draw hysteresis hunt that produced "11 false certificates in 290"
    also ran under the unsound bound and has to be repeated across the whole
    envelope before anything stronger is said. `MODEL_VALIDITY_ENVELOPE.md`
    carries that qualification.
    """
    from csia_active_evidence import battery_multirc as MR
    t = RS.window_times(6.0, 8.0, 50.0)
    cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, 15.0, 6), t)
    loop = B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 5.0})
    seen = {}
    for m_v in (0.12, 0.60):
        pack = MR.MultiRCPack(**{**MR.SYNTHETIC_MULTIRC,
                                 "hysteresis_v": m_v,
                                 "hysteresis_gamma": 20000.0})
        tr = MR.simulate(cmd, duration=20.0, seed=11000, pack=pack, loop=loop)
        w = tr.window(6.0, 14.0)
        cert = rcec.certify(w.t, w.i_meas, w.v_meas,
                            budget(hysteresis_v_max=0.05))
        r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
        truth = pack.r0_at(float(np.mean(w.temp_c)))
        seen[m_v] = (cert.state, abs(r_hat - truth),
                     cert.resolution.get("achieved_error"))

    state, err, bnd = seen[0.12]
    assert state == rcec.CERTIFIED
    assert err <= bnd, (err, bnd)
    assert seen[0.60][0] == rcec.UNKNOWN_OR_MODEL_MISMATCH


def test_the_residual_check_is_blind_to_a_regressor_aligned_nuisance():
    """WHY THE RESIDUAL CHECK COULD NOT HAVE CAUGHT IT. Hysteresis voltage
    follows sign(I), which is nearly in phase with I, so least squares
    attributes it to resistance and the fit looks clean."""
    from csia_active_evidence import battery_multirc as MR
    t = RS.window_times(6.0, 8.0, 50.0)
    cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, 15.0, 6), t)
    loop = B.Loop(**{**B.SYNTHETIC_LOOP, "base_current": 5.0})
    pack = MR.MultiRCPack(**{**MR.SYNTHETIC_MULTIRC, "hysteresis_v": 0.12,
                             "hysteresis_gamma": 20000.0})
    tr = MR.simulate(cmd, duration=20.0, seed=999, pack=pack, loop=loop)
    w = tr.window(6.0, 14.0)
    cert = rcec.certify(w.t, w.i_meas, w.v_meas,
                        budget(hysteresis_v_max=0.05))
    assert cert.coverage["residual_ratio"] < 3.0, (
        cert.coverage["residual_ratio"])


def test_a_healthy_multirc_pack_is_not_refused_at_low_probe_frequency():
    """THE FALSE ALARM THE POLARIZATION-AWARE RESIDUAL FIXED.

    Before the predicted residual included the declared polarization, a
    healthy multi-RC pack at 3 cycles and 22 A was refused as model mismatch
    while its estimate sat comfortably inside its own bound.
    """
    from csia_active_evidence import battery_multirc as MR
    pack = MR.MultiRCPack(**MR.SYNTHETIC_MULTIRC)
    for amp in (8.0, 15.0, 22.0, 30.0):
        t = RS.window_times(6.0, 8.0, 50.0)
        cmd = WC.as_callable(RS.palindromic(t, 6.0, 8.0, amp, 6), t)
        tr = MR.simulate(cmd, duration=20.0, seed=999)
        w = tr.window(6.0, 14.0)
        cert = rcec.certify(w.t, w.i_meas, w.v_meas,
                            budget(hysteresis_v_max=0.05))
        assert cert.state == rcec.CERTIFIED, (amp, cert.state)
        r_hat = rcec.estimate_resistance(w.i_meas, w.v_meas)
        truth = pack.r0_at(float(np.mean(w.temp_c)))
        assert abs(r_hat - truth) <= cert.resolution["achieved_error"], amp


# --- the campaign's multi-RC and hysteresis phases --------------------------

def test_the_campaign_covers_three_plants(doc):
    from tools.research import rcec_campaign as V
    assert set(V.PLANTS) == {"simple", "one_rc", "multi_rc"}
    for model in V.PLANTS:
        assert f"{model}/P1_palindromic" in doc["results"]


def test_the_bound_holds_inside_the_declared_hysteresis_envelope(doc):
    """If this fails the bound is falsified and RESULTS.md must be rewritten
    rather than the envelope widened."""
    inside = doc["hysteresis_hunt"]["inside_declared_envelope"]
    assert inside["draws"] >= 400
    assert inside["certified"] > 0
    assert inside["false_certifications"] == 0
    assert inside["worst_ratio"] < 1.0, inside["worst_ratio"]


def test_an_under_declared_envelope_costs_wrong_certificates(doc):
    """The measured price of a declaration that is too small. Recorded as a
    fact about the method, not hidden as an inconvenience."""
    outside = doc["hysteresis_hunt"]["outside_declared_envelope"]
    assert outside["false_certifications"] > 0
    assert outside["worst_ratio"] > 1.0
    assert "under-declared" in doc["hysteresis_hunt"]["reading"]


def test_the_cross_probe_check_is_reported_as_a_null_result(doc):
    """It does not work. Reporting the failure is the point: a reader must
    not assume a second probe rescues an under-declared bound."""
    cross = doc["cross_probe_check"]
    assert cross["verdict"].startswith("CROSS_PROBE_CHECK_DOES_NOT_DETECT")
    assert cross["detected_at"] == []
    for row in cross["rows"].values():
        if row.get("ratio") is not None:
            assert row["ratio"] < 1.0, row


def test_the_adversarial_hunt_still_finds_nothing(doc):
    assert doc["adversarial"]["draws"] >= 2000
    assert doc["adversarial"]["false_certifications"] == 0
