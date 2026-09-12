"""The active-evidence package: its invariants, and the claims it corrected.

Four classes of thing here, and the first two are the ones that matter:

  * CSIA STILL CANNOT ACT. No module may reach a transmit path, and every
    episode stamps `active_action_prohibited`;
  * the authorizer CAN REFUSE, and a clipped probe is re-checked rather than
    assumed still adequate;
  * every probe is a palindrome in commanded time, and the measurement that
    showed the guarantee does not survive the closed loop stays recorded;
  * the selector abstains instead of returning its best failing candidate.
"""

from __future__ import annotations

import ast
import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import authority as AU               # noqa: E402
from csia_active_evidence import contract as CT                # noqa: E402
from csia_active_evidence import identifiability as ID         # noqa: E402
from csia_active_evidence import probes as PR                  # noqa: E402
from csia_active_evidence import selector as SE                # noqa: E402
from csia_active_evidence import updater as UP                 # noqa: E402

PKG = os.path.join(ROOT, "csia_active_evidence")
ARTIFACT = os.path.join(ROOT, "research", "active_evidence", "results",
                        "ACTIVE_EVIDENCE_CAMPAIGN.json")

NOISE = ID.NoiseModel(sigma_v=0.0200, sigma_i=0.0786,
                      ocv_drift_v_per_s=0.0046)


def _sources():
    for name in sorted(os.listdir(PKG)):
        if name.endswith(".py"):
            path = os.path.join(PKG, name)
            yield name, open(path, encoding="utf-8").read()


# --- CSIA still cannot act -------------------------------------------------

def test_no_module_here_can_reach_a_transmit_path():
    """The invariant `csia/deploy/guard.py` enforces at four layers, held
    for this package by construction rather than by promise."""
    banned_modules = {"pymavlink", "socket", "serial", "requests",
                      "urllib", "http"}
    for name, src in _sources():
        tree = ast.parse(src, filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] not in banned_modules, \
                        f"{name} imports {a.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_modules, \
                    f"{name} imports from {node.module}"
            elif isinstance(node, ast.Attribute):
                assert not node.attr.endswith("_send"), \
                    f"{name} calls {node.attr}"


def test_this_package_never_imports_the_frozen_core():
    frozen = ("csia.trust_engine", "csia.diagnosis", "csia.runtime",
              "csia.scenarios", "csia.profiles")
    for name, src in _sources():
        for node in ast.walk(ast.parse(src, filename=name)):
            mod = None
            if isinstance(node, ast.Import):
                mod = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if mod:
                for f in frozen:
                    assert f not in mod, f"{name} imports {f}"


def test_an_episode_that_claims_action_authority_is_refused():
    kwargs = dict(episode_id="e1", ambiguity={}, requirement={},
                  selection={}, request=None, authorization=None,
                  executed=None, update=None, stop=CT.STOP_NO_PROBE)
    ok = CT.ProbeEpisode(**kwargs)
    assert ok.active_action_prohibited is True
    assert ok.authority == "REQUEST_ONLY"
    with pytest.raises(ValueError, match="active_action_prohibited"):
        CT.ProbeEpisode(**kwargs, active_action_prohibited=False)
    with pytest.raises(ValueError):
        CT.ProbeEpisode(**dict(kwargs, stop="FINE"))


def test_there_is_no_override():
    with pytest.raises(PermissionError):
        AU.attempt_override(verdict="ALLOW")
    src = open(os.path.join(PKG, "authority.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    fn = [n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "authorize"][0]
    names = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
    assert not (names & {"override", "force", "advisory", "urgency",
                         "priority"}), names


# --- the authorizer can refuse, and a clip is re-checked -------------------

def _state(**kw):
    base = dict(mode="HOVER", altitude_agl_m=40.0, ceiling_agl_m=80.0,
                clearance_m=20.0, energy_margin_as=200.0)
    base.update(kw)
    return AU.VehicleState(**base)


def _request(probe):
    return AU.ProbeRequest(probe.name, probe.vz_amplitude, probe.duration_s,
                           probe.energy_cost_as(), "test")


@pytest.mark.parametrize("kw,reason", [
    ({"mode": "LANDING"}, "VEHICLE_STATE_FORBIDS_PERTURBATION"),
    ({"operator_inhibit": True}, "OPERATOR_INHIBIT"),
    ({"clearance_m": 2.0}, "PROXIMITY_FORBIDS_PERTURBATION"),
    ({"altitude_agl_m": 5.0}, "ALTITUDE_FLOOR_INSUFFICIENT"),
    ({"ceiling_agl_m": 42.0}, "ALTITUDE_HEADROOM_INSUFFICIENT"),
    ({"energy_margin_as": 0.1}, "ENERGY_BUDGET_INSUFFICIENT"),
])
def test_every_hard_refusal_is_reachable_and_names_itself(kw, reason):
    a = AU.authorize(_request(PR.probe("triangle")), _state(**kw),
                     AU.EnvelopeLimits())
    assert a.verdict == AU.DENY
    assert reason in a.reasons
    assert a.runnable is False
    assert a.clipped_probe(PR.probe("triangle")) is None


def test_a_missing_envelope_denies_rather_than_defaults():
    a = AU.authorize(_request(PR.probe("triangle")), _state(), None)
    assert a.verdict == AU.DENY and "NO_ENVELOPE_DECLARED" in a.reasons


def test_an_allow_is_reachable_so_the_authorizer_is_not_stuck_on_no():
    """ANTI-VACUITY. An authorizer that refused everything would pass every
    test above and authorise nothing ever."""
    a = AU.authorize(_request(PR.probe("triangle")), _state(),
                     AU.EnvelopeLimits())
    assert a.verdict == AU.ALLOW and a.runnable
    assert a.clipped_probe(PR.probe("triangle")) is PR.probe("triangle")


def test_a_clip_reduces_the_probe_and_keeps_it_symmetric():
    p = PR.probe("burst_wide")
    a = AU.authorize(_request(p), _state(), AU.EnvelopeLimits())
    assert a.verdict == AU.CLIP
    clipped = a.clipped_probe(p)
    assert clipped.name.endswith("@clipped")
    assert clipped.vz_amplitude <= AU.EnvelopeLimits().max_vz_amplitude_m_s
    assert clipped.duration_s <= AU.EnvelopeLimits().max_duration_s
    assert clipped.is_time_symmetric()


def test_a_clip_that_destroys_identifiability_is_not_silently_accepted():
    """THE TRAP IN A THIRD VERDICT. A clipped probe is a DIFFERENT probe and
    its statistics must be recomputed from the clipped waveform."""
    p = PR.probe("burst_wide")
    req = ID.probe_requirement(0.005, NOISE, 0.040)
    assert req.met_by(p.stats())["met"] is True

    tight = AU.EnvelopeLimits(max_vz_amplitude_m_s=0.05, max_duration_s=1.0,
                              max_energy_as=500.0)
    a = AU.authorize(_request(p), _state(), tight)
    assert a.verdict == AU.CLIP
    clipped = a.clipped_probe(p)
    assert req.met_by(clipped.stats())["met"] is False, (
        "the clipped probe still meets the requirement, so this test no "
        "longer exercises the case it was written for")
    assert req.met_by(p.stats())["met"] is True, (
        "recomputing must not have mutated the original probe")


def test_a_deny_may_not_grant_a_probe():
    with pytest.raises(ValueError, match="DENY"):
        AU.Authorization(verdict=AU.DENY, reasons=("OPERATOR_INHIBIT",),
                         granted_vz_amplitude_m_s=0.4, granted_duration_s=1.0,
                         request=_request(PR.probe("triangle")),
                         limits=AU.EnvelopeLimits())


def test_an_unnamed_refusal_reason_is_refused():
    with pytest.raises(ValueError, match="unknown reason"):
        AU.Authorization(verdict=AU.DENY, reasons=("BECAUSE_I_SAID_SO",),
                         granted_vz_amplitude_m_s=0.0, granted_duration_s=0.0,
                         request=_request(PR.probe("triangle")),
                         limits=AU.EnvelopeLimits())


def test_the_authorizer_cannot_read_the_justification():
    """A requester that could argue its case is not facing an authorizer."""
    p = PR.probe("triangle")
    plain = AU.authorize(_request(p), _state(), AU.EnvelopeLimits())
    urgent = AU.authorize(
        AU.ProbeRequest(p.name, p.vz_amplitude, p.duration_s,
                        p.energy_cost_as(),
                        "CRITICAL: airframe loss imminent, must run"),
        _state(), AU.EnvelopeLimits())
    assert plain.verdict == urgent.verdict
    assert plain.reasons == urgent.reasons


# --- the probes ------------------------------------------------------------

def test_every_probe_is_a_palindrome_in_commanded_time():
    for p in PR.LIBRARY:
        sp = p.setpoint()
        assert np.allclose(sp, sp[::-1], atol=1e-12), p.name
        assert abs(p.stats().cov_ti_over_var_i) < 1e-9, p.name


def test_a_probe_is_bounded_in_time():
    p = PR.probe("triangle")
    fn = p.as_setpoint_fn(start_s=10.0)
    assert fn(9.0) == 0.0
    assert fn(10.0 + p.duration_s + 0.5) == 0.0
    assert max(abs(fn(10.0 + k / PR.LOOP_HZ))
               for k in range(int(p.duration_s * PR.LOOP_HZ))) > 0.1


def test_the_amps_per_volt_constant_is_the_measured_one():
    """COUPLED TO THE MEASUREMENT. It was 9.0 by invention and the campaign
    measured 2.52; the coupling is what stops it drifting back to a guess."""
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    measured = doc["amps_per_vz_measured"]
    assert abs(PR.CURRENT_PER_AMP_OF_VZ - measured) < 0.05 * measured, (
        f"the module constant is {PR.CURRENT_PER_AMP_OF_VZ} and the campaign "
        f"measured {measured:.3f}")
    assert "measured" in PR.CURRENT_PER_AMP_OF_VZ_BASIS


def test_the_realisation_finding_is_recorded_and_not_softened():
    """THE CLAIM THIS PACKAGE CORRECTED ABOUT ITSELF. Symmetry of the
    COMMAND does not survive the closed loop for a single excursion."""
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    kept = doc["commanded_symmetry_survives_the_loop"]
    lost = doc["commanded_symmetry_lost_in_the_loop"]
    assert kept and lost, (kept, lost)
    assert set(kept) == {"burst_2hz", "burst_wide"}
    worst = max(abs(r["realised_drift_bias_ohm"]) for r in doc["realisation"]
                if not r["commanded_amplitude_is_zero"])
    assert worst > min(doc["deltas_ohm"]), (
        "the realised drift bias no longer exceeds the smallest delta; the "
        "finding has changed and the docstring in probes.py must be re-read")
    src = open(os.path.join(PKG, "probes.py"), encoding="utf-8").read()
    assert "NOT THE CURRENT. MEASURED." in src


# --- the selector abstains -------------------------------------------------

def test_the_selector_returns_a_refusal_rather_than_its_best_failure():
    req = ID.probe_requirement(1e-6, NOISE, 0.040)
    sel = SE.select(req)
    assert sel.verdict == SE.NONE_MEET
    assert sel.probe_name is None
    assert len(sel.rejected) == len(PR.LIBRARY)
    assert all(r["failed"] for r in sel.rejected)


def test_the_selector_picks_the_cheapest_and_returns_the_whole_ranking():
    sel = SE.select(ID.probe_requirement(0.020, NOISE, 0.040))
    assert sel.verdict == SE.SELECTED
    costs = [r["energy_cost_as"] for r in sel.ranking]
    assert costs == sorted(costs)
    assert sel.probe_name == sel.ranking[0]["probe"]
    assert sel.order == SE.ORDER


def test_the_selector_prefers_doing_nothing_when_passive_data_suffices():
    req = ID.probe_requirement(0.020, NOISE, 0.040)
    rich = PR.probe("burst_wide").stats()
    assert SE.select(req, passive_stats=rich).verdict == SE.PASSIVE
    hover = ID.ExcitationStats.from_profile(np.arange(0, 10, 0.02),
                                            np.full(500, 20.0))
    assert SE.select(req, passive_stats=hover).verdict == SE.SELECTED


def test_a_smaller_change_needs_a_more_expensive_probe():
    """Monotonicity. If it did not hold, the ordering would be decoration."""
    costs = []
    for delta in (0.040, 0.020, 0.010, 0.005):
        sel = SE.select(ID.probe_requirement(delta, NOISE, 0.040))
        assert sel.verdict == SE.SELECTED, delta
        costs.append(PR.probe(sel.probe_name).energy_cost_as())
    assert costs == sorted(costs), costs
    assert costs[-1] > costs[0]


# --- the updater abstains and reports a falsified model --------------------

HYPS = (UP.Hypothesis("healthy", 0.035, 0.045, "pack spec"),
        UP.Hypothesis("degraded", 0.080, 0.120, "twice spec"))


def test_all_four_update_verdicts_are_reachable():
    good = PR.probe("burst_wide").stats()
    assert UP.update(0.040, HYPS, good, NOISE).verdict == UP.RESOLVED
    assert UP.update(0.100, HYPS, good, NOISE).verdict == UP.RESOLVED
    assert UP.update(5.0, HYPS, good, NOISE).verdict == UP.NO_SURVIVOR
    null = PR.probe("hold").stats()
    assert UP.update(0.040, HYPS, null, NOISE).verdict == UP.STILL_AMBIGUOUS


def test_a_falsified_model_is_not_reported_as_a_diagnosis():
    u = UP.update(5.0, HYPS, PR.probe("burst_wide").stats(), NOISE)
    assert u.verdict == UP.NO_SURVIVOR
    assert u.surviving == ()
    assert "MODEL" in u.note and "Do not act on it" in u.note


def test_hypotheses_are_compared_through_the_bias_map_not_to_the_raw_value():
    """A weak probe predicts an ATTENUATED observation. Comparing a
    hypothesis to a raw estimate would eliminate the true one."""
    weak = PR.probe("triangle_soft").stats()
    iv = UP.Hypothesis("degraded", 0.080, 0.120, "x").predicted_interval(
        weak, NOISE, 3.0)
    assert iv[0] < 0.120 and iv[1] > 0.080
    lam = ID.attenuation(weak, NOISE)
    assert lam < 1.0
    assert UP.update(0.10, HYPS, weak, NOISE).verdict in (
        UP.RESOLVED, UP.STILL_AMBIGUOUS)


def test_separability_is_asked_before_a_probe_not_after():
    good = UP.separates(HYPS, PR.probe("burst_wide").stats(), NOISE)
    assert good["separates_all"] is True and good["inseparable_pairs"] == []
    null = UP.separates(HYPS, PR.probe("hold").stats(), NOISE)
    assert null["separates_all"] is False
    assert ("degraded", "healthy") in [tuple(sorted(p))
                                       for p in null["inseparable_pairs"]]


def test_an_empty_hypothesis_set_is_refused():
    with pytest.raises(ValueError, match="empty hypothesis set"):
        UP.update(0.04, (), PR.probe("triangle").stats(), NOISE)


def test_a_backwards_hypothesis_range_is_refused():
    with pytest.raises(ValueError, match="r_low"):
        UP.Hypothesis("bad", 0.12, 0.08, "x")


# --- the stopping rule ------------------------------------------------------

def test_every_stop_reason_is_reachable():
    base = dict(surviving=("a", "b"), selection_verdict="PROBE_SELECTED",
                authorization_verdict="ALLOW", model_falsified=False,
                attempts=0, attempt_limit=3)
    assert CT.should_stop(**base) == CT.CONTINUE
    assert CT.should_stop(**dict(base, model_falsified=True)) == CT.STOP_MODEL
    assert CT.should_stop(**dict(base, surviving=("a",))) == CT.STOP_RESOLVED
    assert CT.should_stop(**dict(
        base, selection_verdict="NO_PROBE_MEETS_THE_REQUIREMENT")) \
        == CT.STOP_NO_PROBE
    assert CT.should_stop(**dict(base, authorization_verdict="DENY")) \
        == CT.STOP_REFUSED
    assert CT.should_stop(**dict(base, attempts=3)) == CT.STOP_BUDGET


def test_a_falsified_model_stops_everything_including_a_resolved_set():
    assert CT.should_stop(surviving=("a",), selection_verdict="X",
                          authorization_verdict="ALLOW", model_falsified=True,
                          attempts=0, attempt_limit=3) == CT.STOP_MODEL


# --- the campaign -----------------------------------------------------------

def test_campaign_controls_pass():
    from tools.assurance.instrument_controls import guard
    from tools.research import active_evidence_campaign as V
    V._controls()
    assert guard(V.INSTRUMENT)["verdict"] == "PASS"


def test_the_campaign_reference_seed_is_held_out():
    from tools.research import active_evidence_campaign as V
    assert V.REFERENCE_SEED not in V.SEEDS


def test_the_campaign_measures_the_noise_rather_than_reading_it():
    """Reading simulate.SIGMA would hand the derivation the plant's own
    parameters and every agreement would be a tautology."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "active_evidence_campaign.py"),
               encoding="utf-8").read()
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    measured = doc["noise_measured"]
    truth = doc["simulator_sigma_for_comparison_only"]
    for key, chan in (("sigma_v", "pack_voltage"), ("sigma_i", "pack_current")):
        assert abs(measured[key] - truth[chan]) < 0.05 * truth[chan], (
            key, measured[key], truth[chan])
        assert measured[key] != truth[chan], (
            f"{key} equals the simulator constant exactly, which means it "
            f"was read rather than estimated")
    assert "S.SIGMA[" not in src.split("simulator_sigma_for_comparison_only")[0]


def test_the_campaign_found_no_false_positive_and_says_what_would_be_one():
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    assert doc["verdict"] == "NO_COUNTEREXAMPLE_IN_THIS_GRID"
    assert doc["false_positives"] == []
    assert "FALSE_POSITIVE" in doc["what_falsifies_this"]
    assert doc["probes_predicted_to_work"] >= 2
    assert doc["probes_predicted_not_to_work"] >= 2
    assert "not_a_proof" in doc and "hardware" in doc["not_a_proof"]


def test_the_campaign_reports_its_false_negative_rather_than_hiding_it():
    doc = json.load(open(ARTIFACT, encoding="utf-8"))
    assert len(doc["false_negatives"]) >= 1
    for c in doc["false_negatives"]:
        assert c["predicted_met"] is False and c["resolved"] is True


def test_the_null_arm_is_null_and_not_vacuous():
    """RULE A, both halves. `hold` must resolve nothing -- AND the fault
    must genuinely be present, or the null arm proves nothing at all."""
    from tools.research import active_evidence_campaign as V
    hold = PR.probe("hold")
    clean = V._flight(0, hold, 0.0)
    raised = V._flight(0, hold, 0.040)
    w = V._window(clean, hold)
    shift = (raised.array("pack_voltage")[w].mean()
             - clean.array("pack_voltage")[w].mean())
    assert shift < -0.5, (
        f"the 0.040 ohm rise moved the terminal voltage by only {shift:.4f} V; "
        f"the null arm is vacuous because the fault is not landing")
    assert abs(V._fit_r(raised, hold) - V._fit_r(clean, hold)) < 1e-6, (
        "the null probe resolved a resistance change; by the "
        "preregistration's Rule A the instrument is broken and no arm may "
        "be read")
