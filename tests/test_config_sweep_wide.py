"""The wide sweep's separations must be paired, and its faults must be real.

The narrow sweep it supersedes subtracted a hover_circle fault floor from a
clean floor taken as the minimum over BOTH profiles. The two sides came from
different flights, so the separation was understated whenever fast_cruise had
the lower clean floor. These tests pin the pairing and the two other ways
this instrument could report a number it did not measure.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.research import config_sweep_wide as w                  # noqa: E402


def test_every_single_fault_comes_from_the_applicability_matrix():
    """A pair the simulator cannot produce must never be swept as though it
    could. The matrix is the authority; this file lists nothing."""
    from csia_stress.applicability import matrix
    live = set(matrix().live_pairs())
    for _label, (target, faults) in w.SINGLE.items():
        for f in faults:
            assert (f.kind, f.target) in live, f"{f.kind}/{f.target}"
            assert f.target == target


def test_every_fault_magnitude_reaches_its_sensor():
    from csia_stress.fault_params import assert_any_effective
    for _label, (_target, faults) in w.SINGLE.items():
        for f in faults:
            assert_any_effective(f.target, f.kind, list(f.params))


def test_magnitudes_are_not_invented_in_this_file():
    """They come from WORST_PARAMS, so no new number enters here."""
    from csia_stress.falsify import WORST_PARAMS
    for _label, (_target, faults) in w.SINGLE.items():
        for f in faults:
            assert dict(f.params) == dict(WORST_PARAMS[f.kind])


def test_the_fault_set_is_materially_wider_than_the_narrow_sweep():
    from tools.research import config_sweep as narrow
    assert len(w.SINGLE) > 4 * len(narrow.FAULTS)
    assert len(w.MULTI) >= 8
    assert len(w.SEED_OFFSETS) > len(narrow.SEED_OFFSETS)


def test_seed_offsets_are_distinct_realisations():
    states = []
    for offset in w.SEED_OFFSETS:
        s = w._sensors(offset)
        states.append(tuple(str(s[n].rng.bit_generator.state)
                            for n in sorted(s)))
    assert len(set(states)) == len(states), (
        "two seed offsets produced identical generator states, so the "
        "'independent realisations' overlap and the spread understates noise")


def test_seed_offset_zero_is_the_frozen_simulator():
    from csia.scenarios import make_sensors
    frozen, mine = make_sensors(), w._sensors(0)
    for name in frozen:
        assert (frozen[name].rng.bit_generator.state
                == mine[name].rng.bit_generator.state), name


def test_separations_are_paired_within_one_seed_and_one_profile():
    """THE CORRECTNESS FIX THIS TOOL EXISTS FOR.

    Every row carries the seed and profile it was measured on, and the
    clean floor subtracted must be the one from that same seed and profile.
    """
    src = open(os.path.join(ROOT, "tools", "research",
                            "config_sweep_wide.py"), encoding="utf-8").read()
    body = src[src.index("def evaluate"):src.index("def _summarise")]
    assert "clean_by_profile[profile]" in body
    assert "for profile in PROFILES" in body
    # and the row records both, so a reader can check the pairing
    assert '"seed_offset": offset' in body and '"profile": profile' in body


def test_a_row_never_mixes_two_profiles(monkeypatch):
    """Behavioural version of the above: the clean floor a row subtracts
    must equal the clean floor measured on that row's own profile."""
    seen = {}
    real = w._post_arm_min

    def spy(faults, profile, offset, cfg, duration=w.DURATION):
        out = real(faults, profile, offset, cfg, duration)
        if not faults:
            seen[(profile, offset)] = dict(out)
        return out

    monkeypatch.setattr(w, "_post_arm_min", spy)
    monkeypatch.setattr(w, "SEED_OFFSETS", (0,))
    monkeypatch.setattr(w, "SINGLE", {
        "baro__bias_drift": w.SINGLE["baro__bias_drift"]})
    monkeypatch.setattr(w, "MULTI", {})
    from csia.trust_engine.engine import EngineConfig
    got = w.evaluate(EngineConfig())
    assert got["rows"], "no rows produced"
    for row in got["rows"]:
        expected = seen[(row["profile"], row["seed_offset"])][row["sensor"]]
        assert row["clean_floor"] == expected, (
            f"row on {row['profile']} subtracted a clean floor from a "
            f"different flight")


def test_saturated_faults_are_excluded_not_averaged():
    """A fault whose floor is identical under every configuration
    discriminates nothing. Averaging it in would dilute every statistic
    toward 'no difference' and look like a null result."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "config_sweep_wide.py"), encoding="utf-8").read()
    assert "saturated_and_excluded" in src
    assert "SATURATION_EPS" in src
    body = src[src.index("def run()"):src.index("def _verdict")]
    assert "saturated.append(key)" in body and "continue" in body


def test_the_verdict_requires_both_halves_and_reports_the_losses():
    """A configuration that raises separation while losing headroom has not
    won, and one that wins on some cases and loses on others must show
    both."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "config_sweep_wide.py"), encoding="utf-8").read()
    body = src[src.index("def _verdict"):]
    assert "d_head >= 0" in body
    assert "worse_on_at_least_one" in body
    assert "gain_exceeds_seed_and_profile_spread" in body


def test_the_opposite_direction_is_measured_as_a_control():
    """Raising w_phys is only a finding alongside the measurement that
    lowering it hurts. A one-sided move can be luck on the fault set."""
    labels = [c for c, _ in w._configs()]
    assert "w_phys=0.40" in labels and "w_phys=0.20" in labels
    assert "w_nbr=0.25" in labels and "w_nbr=0.45" in labels


def test_every_configuration_still_sums_to_one():
    for label, cfg in w._configs():
        total = cfg.w_nbr + cfg.w_phys + cfg.w_temp + cfg.w_stat
        assert abs(total - 1.0) < 1e-9, f"{label} sums to {total}"


def test_controls_pass():
    from tools.assurance.instrument_controls import guard
    w._controls()
    assert guard(w.INSTRUMENT)["verdict"] == "PASS"


def test_it_declares_what_it_supersedes():
    src = open(os.path.join(ROOT, "tools", "research",
                            "config_sweep_wide.py"), encoding="utf-8").read()
    assert "supersedes" in src
    assert "CONFIG_SWEEP.json" in src
