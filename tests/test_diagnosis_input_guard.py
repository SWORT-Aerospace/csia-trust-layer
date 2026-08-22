"""`DiagnosisCore` must reject out-of-domain consistency, not return NaN.

WP-C4 boundary testing found the asymmetry: `TrustCore` has bounds rejection
(29 negative cases under ASan/UBSan), `DiagnosisCore` had none. A NaN or an
out-of-range consistency made `np.log` return NaN at `bayes.py:107-108`, which
propagated through the softmax and produced a posterior that is not a
distribution -- with only a `RuntimeWarning`.

Not reachable from production upstreams today, since `consistency()` maps
lambda into (0, 1]. The guard exists because that is one refactor away from
being reachable, and a silent non-distribution is indistinguishable from a
diagnosis.

These tests also pin that the guard changes nothing for valid input.
"""

import math

import numpy as np
import pytest

from csia.diagnosis.bayes import DiagnosisCore


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"),
                                 5.0, -3.0, 1.0000001, -1e-9])
def test_out_of_domain_consistency_raises(bad):
    with pytest.raises(ValueError, match="consistency"):
        DiagnosisCore().step({"phys_gps": (bad, 1.0)})


def test_the_error_names_the_offending_feature():
    """A raise that does not say which feature is barely better than a NaN."""
    with pytest.raises(ValueError, match="redundant_imu"):
        DiagnosisCore().step({"redundant_imu": (float("nan"), 1.0)})


@pytest.mark.parametrize("good", [0.0, 1e-12, 0.5, 0.98, 1.0])
def test_domain_boundaries_are_accepted(good):
    """0 and 1 inclusive are legal: consistency() can return exactly 1.0."""
    post = DiagnosisCore().step({"phys_gps": (good, 1.0)})
    assert abs(sum(post.values()) - 1.0) < 1e-9
    assert all(math.isfinite(v) for v in post.values())


def test_gated_feature_is_skipped_before_the_guard():
    """A closed gate must still short-circuit. A gated feature contributes
    nothing, so its value is irrelevant and must not be validated -- otherwise
    the guard would change behaviour on data the system currently ignores."""
    post = DiagnosisCore().step({"phys_gps": (float("nan"), 0.0)})
    assert abs(sum(post.values()) - 1.0) < 1e-9
    assert post["nominal"] == max(post.values())


def test_guard_does_not_change_valid_output():
    """Bit-identical posteriors for a realistic sequence."""
    feats = {"phys_gps": (0.02, 1.0), "redundant_imu": (0.97, 1.0),
             "attitude_gravity_mag": (0.88, 1.0), "temp_mag": (0.91, 1.0)}
    a = DiagnosisCore()
    b = DiagnosisCore()
    for _ in range(200):
        pa, pb = a.step(feats), b.step(feats)
        assert pa == pb
    assert abs(sum(pa.values()) - 1.0) < 1e-12
    assert np.isfinite(list(pa.values())).all()
