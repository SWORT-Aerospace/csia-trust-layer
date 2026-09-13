"""The repair: partitions, the corrected polarization bound, and the ladder.

The load-bearing tests here are the ones that keep a correction corrected.
The polarization term has now been wrong twice, in opposite directions, and
each time the error was invisible until something evaluated the branch
instead of approximating it.
"""

from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import difficulty as DF                  # noqa: E402
from csia_active_evidence import partitions as PT                  # noqa: E402
from csia_active_evidence import polarization as PZ                # noqa: E402
from csia_active_evidence import rcec                              # noqa: E402
from csia_active_evidence import rcec_selector as RS               # noqa: E402
from csia_active_evidence import waveform_compensation as WC       # noqa: E402

DIAG = os.path.join(ROOT, "research", "active_evidence", "realized_current",
                    "results", "RCEC_DIAGNOSTICS.json")


@pytest.fixture(scope="module")
def diag():
    with open(DIAG, encoding="utf-8") as fh:
        return json.load(fh)


# --- seed partitions --------------------------------------------------------

def test_the_partition_manifest_hash_is_pinned():
    assert PT.manifest_hash() == (
        "e872d36fb3a9337704c18290e1b8ec0452d295c416eef0ba58a8b97c5b6f65c2"), (
        "the seed partitions moved. That is only legitimate with a new dated "
        "amendment; update the amendment and this hash together or not at all")


def test_every_seed_belongs_to_exactly_one_partition():
    PT.assert_disjoint()
    seen = set()
    for seeds in PT.PARTITIONS.values():
        assert not (seen & set(seeds))
        seen |= set(seeds)


def test_a_sealed_partition_cannot_be_read_through_the_accessor():
    with pytest.raises(PermissionError, match="sealed"):
        PT.seeds("amended_locked")
    assert PT.seeds("diagnostic")


def test_the_diagnostics_touched_no_locked_seed(diag):
    used = set(diag["seeds_used"]["diagnostic"]) | \
        set(diag["seeds_used"]["amended_calibration"])
    assert not (used & set(PT.AMENDED_LOCKED))
    assert not (used & set(PT.ORIGINAL_LOCKED))
    assert diag["partition_manifest_sha256"] == PT.manifest_hash()


# --- the corrected polarization bound ---------------------------------------

def _wave(cycles, amp=8.0, n=400, dt=0.02):
    t = np.arange(n) * dt
    mid = 0.5 * (t[0] + t[-1])
    span = max(float(t[-1] - t[0]), 1e-9)
    return t, 20.0 + amp * np.cos(2.0 * math.pi * cycles * (t - mid) / span)


ENV = PZ.PolarizationEnvelope(0.004, 0.020, 1.0, 40.0)


def test_the_bound_is_sound_over_the_declared_envelope():
    """Zero violations. A violation is a defect in the bound, never a
    tolerance to widen."""
    for cycles, amp in ((3, 8.0), (6, 8.0), (12, 4.0), (1, 2.0)):
        t, i = _wave(cycles, amp)
        rep = PZ.validate(i, 0.02, ENV, draws=250, seed=cycles)
        assert rep["violations"] == 0, (cycles, amp, rep)
        assert rep["sound_on_this_grid"] is True


def test_the_bound_is_not_vacuously_loose():
    """A bound never approached is safe and useless. Tightness is measured."""
    t, i = _wave(6, 8.0)
    rep = PZ.validate(i, 0.02, ENV, draws=400, seed=1)
    assert 0.3 < rep["tightness"] <= 1.0, rep["tightness"]


def test_the_bound_discriminates_between_waveforms():
    """If every waveform earned the same bound, design would be pointless."""
    _, fast = _wave(12, 8.0)
    t = np.arange(400) * 0.02
    slow = 20.0 + 0.2 * t
    assert PZ.bound(slow, 0.02, ENV) > 50.0 * PZ.bound(fast, 0.02, ENV)


def test_the_steady_state_term_alone_is_far_too_small():
    """THE REASON THE SHIPPED CLOSED FORM WAS UNSOUND. Over a window shorter
    than the time constant the transient dominates and no steady-state
    expression sees it."""
    t = np.arange(400) * 0.02
    ramp = 20.0 + 1.2 * t
    ss = PZ.spectral_steady_state(ramp, 0.02, 0.015, 13.5)
    direct = abs(PZ.apparent_resistance(ramp, 0.02, 0.015, 13.5, 0.0))
    assert direct > 20.0 * ss, (direct, ss)
    assert direct > 0.015, (
        "the true apparent resistance should exceed R1 itself here, which is "
        "what no steady-state formula can produce")


def test_an_undeclared_envelope_is_unbounded_not_zero():
    t, i = _wave(6)
    assert PZ.bound(i, 0.02, None) == PZ.UNBOUNDED


def test_the_bound_cannot_be_told_the_answer():
    """No fault label, hypothesis or outcome may reach it."""
    import inspect
    params = set(inspect.signature(PZ.bound).parameters)
    assert params == {"i_measured", "dt", "envelope"}, params


def test_a_three_cycle_probe_no_longer_certifies():
    """THE CONSEQUENCE FOR THE PUBLISHED ARMS. P1, P2, P4, P5 and P7 all used
    it in MX-039, so that comparison was computed on an unsound bound."""
    from csia_active_evidence import battery_1rc as B
    from tools.research import rcec_campaign as V
    t = RS.window_times(V.ACTION_START, V.ACTION_DURATION, V.HZ)
    for cycles, expected_certified in ((3, False), (6, True)):
        cmd = WC.as_callable(
            RS.palindromic(t, V.ACTION_START, V.ACTION_DURATION,
                           V.AMPLITUDE, cycles), t)
        w = B.simulate(cmd, duration=V.DURATION,
                       seed=int(PT.seeds("diagnostic")[0])).window(
                           V.ACTION_START, V.ACTION_START + V.ACTION_DURATION)
        cert = rcec.certify(w.t, w.i_meas, w.v_meas, V.budget())
        assert (cert.state == rcec.CERTIFIED) is expected_certified, (
            cycles, cert.state)


# --- P3's failure, classified -----------------------------------------------

def test_the_feasible_set_is_not_empty_and_a_witness_is_named(diag):
    f = diag["feasibility_and_binding"]
    assert f["feasible_set_is_empty"] is False
    assert f["feasible_count"] > 0
    assert f["cheapest_feasible_witness"] is not None


def test_the_binding_constraint_is_the_error_budget_not_excitation(diag):
    """RC-3 asserted this from one observation. Here is the count."""
    counts = diag["feasibility_and_binding"]["binding_counts"]
    assert counts.get("MODEL_MISMATCH", 0) > counts.get("EXCITATION", 0)
    assert sum(counts.values()) == \
        diag["feasibility_and_binding"]["candidates"]


def test_the_repaired_search_finds_a_feasible_candidate(diag):
    o = diag["optimizer"]
    assert o["verdict"] == "OPTIMIZER_OK"
    assert o["repaired_choice_certifies"] is True


def test_the_reconstructed_pilot_choice_still_fails(diag):
    """If it started certifying, the reconstruction stopped reproducing the
    failure it exists to preserve."""
    o = diag["optimizer"]
    assert o["reconstructed_pilot_choice_certifies"] is False
    assert o["pilot_label"] == "RECONSTRUCTED_NOT_RECOVERED"


# --- the lag claim, withdrawn ----------------------------------------------

def test_the_lag_error_is_not_monotone_and_the_lever_sign_flips(diag):
    """Both halves of why `conservative` was withdrawn."""
    lg = diag["lag_sweep"]
    assert lg["error_is_monotone_in_lag_ratio"] is False
    assert lg["lever_sign_flips_relative_to_exact"], (
        "no sign flip was found, so the withdrawal rests on monotonicity "
        "alone and the counterexample log must be re-read")


def test_the_word_conservative_is_not_used_bare_for_the_lag():
    src = open(os.path.join(ROOT, "csia_active_evidence",
                            "waveform_compensation.py"),
               encoding="utf-8").read()
    assert "WAS WITHDRAWN HERE" in src
    assert "NOT monotone" in src


# --- the difficulty ladder --------------------------------------------------

def test_the_margin_is_signed_and_does_not_saturate():
    assert DF.classify_margin(DF.resolution_margin(0.020, 0.004, 0.001)) == \
        DF.RESOLVABLE
    assert DF.classify_margin(DF.resolution_margin(0.005, 0.008, 0.001)) == \
        DF.INSUFFICIENT
    big = DF.resolution_margin(1.0, 0.004, 0.001)
    assert big > 0.9, "the margin capped, which is the defect it replaces"


def test_the_ladder_covers_every_named_factor():
    spec = DF.specification()
    assert len(spec["factors"]) == 16
    for f in DF.LADDER:
        assert f.unit, f.name
        assert f.easy != f.hard, f.name


def test_effort_drift_is_a_factor_and_was_not_deleted():
    assert "absent" in DF.EFFORT_DRIFT_STATES
    assert len(DF.EFFORT_DRIFT_STATES) >= 3
    cells = DF.factorial_cells()
    assert len(cells) == len(DF.STRATEGIES) * len(DF.EFFORT_DRIFT_STATES) \
        * len(DF.PLANT_MODELS)
    assert any(c["effort_drift"] == "absent" for c in cells)
    assert any(c["effort_drift"] != "absent" for c in cells)


def test_a_sign_change_in_the_active_advantage_is_reported():
    """The measured interaction: passive 5 with drift, 9 without, active 6
    in both. The advantage changes sign and must not be averaged away."""
    out = DF.interaction(active_with=6, passive_with=5,
                         active_without=6, passive_without=9)
    assert out["active_advantage_changes_sign"] is True
    assert out["delta_interaction"] == 4


def test_the_oracle_is_marked_not_deployable():
    assert "P7_oracle" in DF.NOT_DEPLOYABLE
    assert "P7_oracle" in DF.specification()["not_deployable"]


# --- the locked campaign runner, before it is run ---------------------------

def test_the_sealed_partition_is_opened_in_exactly_one_place():
    """The whole of the exposure must be one greppable import."""
    import subprocess
    out = subprocess.run(
        ["git", "grep", "-l", "AMENDED_LOCKED", "--", "*.py"],
        cwd=ROOT, capture_output=True, text=True)
    files = {f for f in out.stdout.split() if f.endswith(".py")}
    assert files <= {"csia_active_evidence/partitions.py",
                     "tools/research/rcec_locked_campaign.py",
                     "tests/test_rcec_repair.py"}, files


def test_the_locked_runner_does_not_search_or_tune_at_run_time():
    """P3's waveform is frozen before the partition opens; the runner must
    not re-search it against locked outcomes."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "rcec_locked_campaign.py"), encoding="utf-8").read()
    assert "_P3_CACHE" in src
    assert "rozen before the locked partition was opened" in src
    for banned in ("locked_rows", "tune", "refit"):
        assert f"def {banned}" not in src


def test_the_oracle_is_excluded_from_deployable_comparisons():
    src = open(os.path.join(ROOT, "tools", "research",
                            "rcec_locked_campaign.py"), encoding="utf-8").read()
    assert "a for a in DF.STRATEGIES\n                      if a not in DF.NOT_DEPLOYABLE" in src


def test_the_runner_records_the_required_per_row_quantities():
    from tools.research import rcec_locked_campaign as L
    src = open(os.path.join(ROOT, "tools", "research",
                            "rcec_locked_campaign.py"), encoding="utf-8").read()
    for field in ("proposed_command_digest", "authorized_command_digest",
                  "predicted_s_ii", "realized_s_ii", "predicted_drift_lever",
                  "realized_drift_lever", "B_total", "U_R", "M_R", "state",
                  "energy_as", "mission_deviation_as",
                  "min_safety_margin_a", "runtime_s", "config_hash",
                  "rng_streams"):
        assert f'"{field}"' in src, field
    assert L.source_sha()
