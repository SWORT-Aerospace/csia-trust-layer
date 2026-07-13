"""Unit tests: prediction comparator (phase 2) — including the causality
regression test that guarantees the pipeline is portable to an online loop.
"""

import numpy as np

from csia.prediction import PredictionComparator
from csia.scenarios import DURATION, sample_streams


def _truncate(streams: dict, t_cut: float) -> dict:
    """Cut every stream at t_cut, handling secondary timelines (vib RMS)."""
    out = {}
    for name, s in streams.items():
        n_t = len(s["t"])
        keep = s["t"] < t_cut
        cut = {}
        for key, arr in s.items():
            arr = np.asarray(arr)
            if arr.shape[:1] == (n_t,):
                cut[key] = arr[keep]
            elif name == "vibration" and key in ("t_rms", "rms"):
                cut[key] = arr[np.asarray(s["t_rms"]) < t_cut]
            else:
                cut[key] = arr
        out[name] = cut
    return out


def test_causality_no_lookahead(truth):
    """Outputs up to time T must be identical whether or not data after T
    exists. This is what makes the batch implementation an exact replay of
    an online (sample-by-sample) system — np.gradient-style centered
    differences would fail this immediately."""
    full = sample_streams(truth)
    trunc = _truncate(full, 40.0)
    td_f = PredictionComparator().build(full, DURATION)
    td_t = PredictionComparator().build(trunc, 40.0)
    upto = td_t.t < 35.0  # margin below the cut for alignment holds
    for key in td_f.edges:
        np.testing.assert_allclose(
            td_f.edges[key][2][: upto.sum()], td_t.edges[key][2][upto],
            atol=1e-10, err_msg=f"edge {key} is acausal")
    for name in td_f.physics:
        np.testing.assert_allclose(
            td_f.physics[name][0][: upto.sum()], td_t.physics[name][0][upto],
            atol=1e-10, err_msg=f"physics {name} is acausal")
    for name in td_f.hist:
        np.testing.assert_allclose(
            td_f.hist[name][: upto.sum()], td_t.hist[name][upto],
            atol=1e-10, err_msg=f"historical {name} is acausal")


def test_speed_gate_semantics(clean_run):
    _, _, td, _, _ = clean_run
    t, gate = td.t, td.aux["speed_gate"]
    assert gate[(t > 46.0) & (t < 49.0)].max() < 0.05, \
        "heading_course must be gated OUT during the yaw-in-place hover"
    assert gate[(t > 27.0) & (t < 33.0)].min() > 0.95, \
        "heading_course must be fully gated IN at cruise speed"


def test_clean_flight_residuals_nominal(clean_run):
    """Every gated-in consistency check must sit near its chi-square
    expectation in nominal flight — a hot channel here means a sigma or a
    physics model is wrong (this is what caught the attitude sign bug)."""
    _, _, td, _, _ = clean_run
    for key, (_, _, lam, gate) in td.edges.items():
        g = np.asarray(gate) * np.ones(len(lam))
        m = (g[250:] > 0.5)
        if m.any():
            assert np.percentile(lam[250:][m], 99) < 4.0, f"edge {key} hot"
    for name, (lam, gate) in td.physics.items():
        g = np.asarray(gate) * np.ones(len(lam))
        m = (g[250:] > 0.5)
        if m.any():
            assert np.percentile(lam[250:][m], 99) < 4.0, f"phys {name} hot"


def test_tickdata_shapes(clean_run):
    _, _, td, _, _ = clean_run
    k = len(td.t)
    for key, (a, b, lam, gate) in td.edges.items():
        assert len(lam) == k
    for name in td.hist:
        assert len(td.hist[name]) == k and len(td.var_ratio[name]) == k
        assert len(td.fresh[name]) == k
