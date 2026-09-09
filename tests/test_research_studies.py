"""The two research studies must not be able to report a gain they did not see.

Both tools answer "would this help, and by how much", and both are the kind
of instrument this repository has been burned by three times: one that
produces a clean, plausible, entirely fictional number. So the tests here are
mostly about the guards rather than the results.

WHAT EACH GUARD IS FOR
----------------------
`config_sweep`
    Its whole claim rests on a configuration reaching the frozen math. If
    `EngineConfig` were ignored the surface would be flat and the tool would
    report "no headroom" for the wrong reason.
    And its seed offsets must reproduce the frozen simulator at offset 0, or
    every number describes a different simulator from the rest of the repo.

`predictor_study`
    Three separate ways to report a fake result, all of which HAPPENED during
    development and are now pinned:
      * scoring a channel the fault does not perturb at all (NO_STIMULUS),
      * sweeping a magnitude parameter the sensor does not read, so every
        point is the same fault (PARAMETER_INERT),
      * comparing a fault window against whole-flight clean statistics, so
        flight phase reads as a fault.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.research import config_sweep as cs                      # noqa: E402
from tools.research import predictor_study as ps                   # noqa: E402


# --- config sweep ----------------------------------------------------------

def test_sweep_seed_offset_zero_is_the_frozen_simulator():
    from csia.scenarios import make_sensors
    frozen, mine = make_sensors(), cs._sensors(0)
    assert sorted(frozen) == sorted(mine)
    for name in frozen:
        assert (frozen[name].rng.bit_generator.state
                == mine[name].rng.bit_generator.state), name


def test_sweep_seed_offsets_are_actually_different():
    a, b = cs._sensors(0), cs._sensors(100)
    assert any(a[n].rng.bit_generator.state != b[n].rng.bit_generator.state
               for n in a), (
        "every offset produced the same generator state, so the 'independent "
        "realisations' are one realisation and the noise estimate is zero")


def test_sweep_controls_pass():
    from tools.assurance.instrument_controls import guard
    cs._controls()
    assert guard(cs.INSTRUMENT)["verdict"] == "PASS"


def test_sweep_configurations_are_all_distinct():
    seen = set()
    for label, cfg in cs._configs():
        key = (cfg.rho_max, cfg.rho_min, round(cfg.w_nbr, 6),
               round(cfg.w_phys, 6), round(cfg.w_temp, 6),
               round(cfg.w_stat, 6))
        assert key not in seen, f"{label} duplicates an earlier configuration"
        seen.add(key)


def test_sweep_weight_variants_still_sum_to_one():
    for label, cfg in cs._configs():
        total = cfg.w_nbr + cfg.w_phys + cfg.w_temp + cfg.w_stat
        assert abs(total - 1.0) < 1e-9, f"{label} sums to {total}"


def test_sweep_reports_headroom_alongside_separation():
    """A configuration that raises separation by dragging clean flight down
    buys nothing. One combined score would hide it."""
    src = open(os.path.join(ROOT, "tools", "research", "config_sweep.py"),
               encoding="utf-8").read()
    assert "headroom_min" in src and "separation_mean" in src
    assert "NEVER COLLAPSED" in src.upper()


# --- predictor study -------------------------------------------------------

def test_the_holt_copy_matches_the_frozen_one_exactly():
    """The baseline must be the real baseline, sample for sample."""
    from csia.runtime.online import _Holt
    rng = np.random.default_rng(11)
    x = rng.normal(0, 1, 1500).cumsum() * 0.01 + rng.normal(0, 0.05, 1500)
    mine, frozen = ps.Holt(), _Holt()
    assert max(abs(mine.innovation(v) - frozen.innovation(v))
               for v in x) == 0.0


def test_every_magnitude_parameter_is_read_by_its_sensor():
    """THE BUG THIS PINS. Three grids named a parameter the sensor ignores.

    A sensor applies its default for an unknown key, so the grid swept
    nothing while looking perfectly healthy, and the study reported "no
    detection floor" for a fault that never varied.
    """
    for (sensor, kind), (param, values) in ps.MAGNITUDES.items():
        base = ps._streams((), "hover_circle", 0)
        lo = ps.Fault(kind, sensor, ps.FAULT_START, ps.FAULT_LEN,
                      {param: values[0]})
        hi = ps.Fault(kind, sensor, ps.FAULT_START, ps.FAULT_LEN,
                      {param: values[-1]})
        a = ps._streams((lo,), "hover_circle", 0)[sensor]
        b = ps._streams((hi,), "hover_circle", 0)[sensor]
        moved = any(
            not np.array_equal(np.asarray(a[k]), np.asarray(b[k]))
            for k in a if k not in ("t", "valid") and k in b)
        assert moved, (
            f"{sensor}/{kind}: the smallest and largest {param!r} produce "
            f"identical streams, so the sensor is not reading that parameter")
        del base


def test_series_refuses_a_mismatched_timeline():
    """`vibration` carries the raw signal at 59990 samples under `t` and the
    windowed rms at 599 under `t_rms`. Pairing the wrong one puts the fault
    window on the wrong samples."""
    streams = ps._streams((), "hover_circle", 0)
    t, x = ps._series(streams, "vibration", "rms", None)
    assert t.shape == x.shape
    assert t.shape[0] < 1000, "rms should be on its own low-rate timeline"


def test_parameter_inert_is_detected_and_raises():
    """The guard must fire, not warn. A sweep that measured nothing must not
    reach a report at all."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "predictor_study.py"), encoding="utf-8").read()
    assert "PARAMETER_INERT" in src
    assert "raise ValueError" in src.split("def run_floors")[1][:2000], (
        "an inert sweep must raise; returning a status a caller may ignore "
        "is how a null becomes a published finding")


def test_no_stimulus_channels_are_excluded_not_scored():
    """A GPS spoof perturbs no channel the temporal predictor watches.
    Reporting a floor for those would be reporting an instrument artifact."""
    clean = ps._streams((), "fast_cruise", 100)
    fault = ps.Fault("gps_spoof", "gps", ps.FAULT_START, ps.FAULT_LEN,
                     {"drift": (30.0, 0.0, 0.0)})
    faulted = ps._streams((fault,), "fast_cruise", 100)
    from csia.prediction.predictors import HIST_CHANNELS
    for key, col, _ in HIST_CHANNELS["gps"]:
        _, a = ps._series(clean, "gps", key, col)
        _, b = ps._series(faulted, "gps", key, col)
        assert np.array_equal(a, b), (
            f"gps.{key}[{col}] now moves under a horizontal spoof; the "
            f"no-stimulus finding has changed and the study must be re-read")


def test_predictor_controls_pass_and_are_informative():
    from tools.assurance.instrument_controls import guard
    ps._controls()
    report = guard(ps.INSTRUMENT)
    assert report["verdict"] == "PASS"
    text = " ".join(str(r.get("observed", "")) for r in report["controls"])
    assert "diff_ar" in text and "ar_sigma" in text


def test_the_fault_tracking_effect_is_real_and_large():
    """The finding the whole study rests on, as arithmetic.

    A model fitted on first differences predicts a linear ramp almost
    exactly, so its innovation collapses -- which is a predictor HIDING a
    bias drift, not detecting one.
    """
    ramp = np.arange(800, dtype=float) * 0.01
    pers = ps._innovations(lambda: ps.Persistence(), ramp)[64:]
    dar = ps._innovations(lambda: ps.DiffAR(8), ramp, coef_source=ramp)[64:]
    assert float(np.mean(np.abs(dar))) < float(np.mean(np.abs(pers))) / 1e5


def test_a_fitted_model_gains_nothing_on_white_noise():
    """Anti-vacuity for every fitted result: on structureless data the AR
    must land at the sqrt(2) ratio persistence gives by construction, and no
    better. Anything more is fitted noise."""
    rng = np.random.default_rng(5)
    train, test = rng.normal(0, 1, 4000), rng.normal(0, 1, 4000)
    pers = ps._innovations(lambda: ps.Persistence(), test)[64:]
    ar = ps._innovations(lambda: ps.AR(8), test, coef_source=train)[64:]
    ratio = float(np.std(pers)) / float(np.std(ar))
    assert 1.30 < ratio < 1.55, ratio


def test_d_prime_threshold_is_the_same_for_every_predictor():
    """Comparing floors requires one threshold. A per-predictor threshold
    would be comparing thresholds instead."""
    src = open(os.path.join(ROOT, "tools", "research",
                            "predictor_study.py"), encoding="utf-8").read()
    assert "D_PRIME_DETECTED = 1.0" in src
    assert src.count("D_PRIME_DETECTED =") == 1


def test_the_study_states_what_it_cannot_tell_you():
    assert "injector" in ps.__doc__
    assert "not a reason to ship" in ps.__doc__


@pytest.mark.parametrize("sensor,key,col", [("baro", "altitude", None)])
def test_a_known_channel_still_shows_stimulus(sensor, key, col):
    """Anti-vacuity for the no-stimulus guard: it must not reject everything."""
    param, values = ps.MAGNITUDES[(sensor, ps._kind_for(sensor))]
    clean = ps._streams((), "fast_cruise", 100)
    fault = ps.Fault(ps._kind_for(sensor), sensor, ps.FAULT_START,
                     ps.FAULT_LEN, {param: values[-1]})
    faulted = ps._streams((fault,), "fast_cruise", 100)
    _, a = ps._series(clean, sensor, key, col)
    _, b = ps._series(faulted, sensor, key, col)
    assert float(np.max(np.abs(a - b))) > 0.0
