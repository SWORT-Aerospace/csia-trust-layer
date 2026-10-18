"""The MAER h_acc transform: saturation arithmetic and validity semantics.

Two things are pinned here because both were got wrong once.

SATURATION. A report stated that consistency falls below 0.01 at
`h_acc ~ 2.8x` nominal. It does not: 2.8x is close to the ratio at consistency
0.5 (2.9176), while the 0.01 threshold is at 9.16x. The claim was asserted
rather than derived, so the derivation is now executed on every test run.

VALIDITY. `h_acc = 0` was being fed through `max(0, log(h_acc/h0))`, which
yields 0 and hence consistency 1.0 -- a receiver reporting nothing scoring as
perfectly healthy. The committed captures contain TWO such populations: 870
pre-lock samples (fix 0 / sats 0 / eph 65535) and 30 acquisition samples
(fix 1 / sats 3 / eph 121) whose eph and satellite count are both valid, so
only the `h_acc <= 0` clause rejects them.
"""

from __future__ import annotations

import importlib.util
import math
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MOD = os.path.join(ROOT, "research", "maer", "maer_hacc_transform.py")


def _load():
    spec = importlib.util.spec_from_file_location("_maer_hacc", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def T():
    return _load()


# ---------------------------------------------------------- saturation
def test_lambda_at_one_percent_consistency(T):
    """lam = 1 + 2 ln 100, solved rather than quoted."""
    assert T.lam_at_consistency(0.01) == pytest.approx(
        1.0 + 2.0 * math.log(100.0), rel=1e-12)
    assert T.lam_at_consistency(0.01) == pytest.approx(10.21034037, abs=1e-8)


def test_hacc_ratio_at_one_percent_consistency_is_9_16_not_2_8(T):
    """The corrected figure. 2.8x is not the 0.01 threshold."""
    ratio = T.ratio_at_consistency(0.01)
    assert ratio == pytest.approx(9.1601, abs=1e-4)
    assert ratio == pytest.approx(
        2.0 ** math.sqrt(1.0 + 2.0 * math.log(100.0)), rel=1e-12)
    assert not (2.7 < ratio < 2.9), (
        "the stale 2.8x claim has come back; it is the ratio near "
        "consistency 0.5, not 0.01")


def test_the_stale_ratio_is_actually_the_half_consistency_point(T):
    """Documents where the wrong number most likely came from."""
    assert T.ratio_at_consistency(0.5) == pytest.approx(2.9176, abs=1e-4)


def test_round_trip_ratio_to_consistency(T):
    """Feeding the solved ratio back through the transform returns the target."""
    for c in (0.5, 0.1, 0.01):
        h_acc = T.H0_MM * T.ratio_at_consistency(c)
        lam = T.degradation_units(h_acc) ** 2       # steady state, EWMA settled
        assert T.consistency(lam) == pytest.approx(c, rel=1e-9)


def test_one_doubling_is_one_degradation_unit(T):
    """kappa_h is a declared log scale, not an estimated spread."""
    assert T.degradation_units(T.H0_MM) == pytest.approx(0.0)
    assert T.degradation_units(2 * T.H0_MM) == pytest.approx(1.0, rel=1e-12)
    assert T.degradation_units(4 * T.H0_MM) == pytest.approx(2.0, rel=1e-12)


def test_below_nominal_is_not_a_fault(T):
    """One-sided: better-than-nominal accuracy contributes nothing."""
    for h in (1.0, 100.0, 299.0, 300.0):
        assert T.degradation_units(h) == 0.0


# ---------------------------------------------------------- validity
def test_zero_hacc_is_rejected_not_read_as_perfect_health(T):
    """The trap: max(0, log(0/h0)) = 0 would score as consistency 1.0."""
    pre_lock = {"h_acc": 0, "eph": 65535, "satellites_visible": 0,
                "fix_type": 0}
    assert T.hacc_valid(pre_lock) is False


def test_unknown_sentinels_are_rejected(T):
    assert T.hacc_valid({"h_acc": 0xFFFFFFFF, "eph": 121,
                         "satellites_visible": 10}) is False
    assert T.hacc_valid({"h_acc": 300, "eph": 0xFFFF,
                         "satellites_visible": 10}) is False


def test_zero_satellites_is_rejected(T):
    """A receiver tracking nothing is not making an accuracy statement."""
    assert T.hacc_valid({"h_acc": 300, "eph": 121,
                         "satellites_visible": 0}) is False


def test_a_normal_degraded_sample_is_accepted(T):
    assert T.hacc_valid({"h_acc": 250000, "eph": 121,
                         "satellites_visible": 5}) is True
    assert T.hacc_valid({"h_acc": 300, "eph": 121,
                         "satellites_visible": 10}) is True


def test_invalid_samples_do_not_update_the_smoother(T):
    """An unusable reading must contribute nothing, not a value."""
    msgs = [
        {"h_acc": 0, "eph": 65535, "satellites_visible": 0},      # pre-lock
        {"h_acc": 300, "eph": 121, "satellites_visible": 10},     # nominal
        {"h_acc": 0, "eph": 65535, "satellites_visible": 0},      # pre-lock
    ]
    out = list(T.lam_stream(msgs))
    assert out[0][1] is None and out[0][3] is False
    assert out[1][1] == pytest.approx(0.0) and out[1][3] is True
    assert out[2][1] is None and out[2][3] is False


def _zero_hacc_rows():
    import glob
    import json
    rows = []
    for p in sorted(glob.glob(os.path.join(
            ROOT, "research", "maer", "MAER_ARDUPILOT_JAM_RAW", "*.json"))):
        with open(p, encoding="utf-8") as fh:
            for r in json.load(fh).get("rows") or []:
                if r.get("h_acc") == 0:
                    rows.append(r)
    return rows


def test_every_zero_hacc_sample_in_the_captures_is_rejected(T):
    """The property that matters: none of them reaches the transform.

    Checked behaviourally rather than by co-occurrence pattern. An earlier
    version of this test asserted that every h_acc==0 sample carried the
    pre-lock signature (fix 0 / sats 0 / eph 65535); that was too narrow and
    it failed, which is how the second population below was found.
    """
    rows = _zero_hacc_rows()
    assert rows, "no h_acc==0 samples found; the fixture data changed"
    leaked = [r for r in rows if T.hacc_valid(r)]
    assert not leaked, f"{len(leaked)} zero-h_acc samples passed validity"


def test_there_are_two_distinct_zero_hacc_populations(T):
    """Pre-lock AND early acquisition, and only one clause catches the second.

    pre-lock     fix_type 0, sats 0, eph 65535 -- caught by several clauses
    acquisition  fix_type 1, sats 3, eph 121   -- eph and sats are both VALID,
                 so ONLY the `h_acc <= 0` clause rejects it
    """
    rows = _zero_hacc_rows()
    sigs = {(r.get("fix_type"), r.get("satellites_visible"), r.get("eph"))
            for r in rows}
    assert (0, 0, 65535) in sigs
    assert (1, 3, 121) in sigs, (
        "the acquisition population is gone; if the fixtures changed, "
        "re-check that the h_acc<=0 clause is still load-bearing")
    # the load-bearing check: strip the zero clause and the second population
    # would sail through
    acquisition = {"h_acc": 0, "eph": 121, "satellites_visible": 3,
                   "fix_type": 1}
    assert T.hacc_valid(acquisition) is False
    assert T.hacc_valid({**acquisition, "h_acc": 300}) is True
