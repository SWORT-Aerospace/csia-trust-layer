"""Unit tests: trust engine (phase 2)."""

import numpy as np
import pytest

from csia.trust_engine import EngineConfig, consistency


def test_consistency_mapping():
    assert consistency(0.0) == 1.0
    assert consistency(1.0) == 1.0  # chi-square nominal is NOT penalized
    assert 0.0 < consistency(10.0) < consistency(5.0) < 1.0


def test_engine_config_validation():
    with pytest.raises(ValueError):
        EngineConfig(rho_min=0.999, rho_max=0.99)
    with pytest.raises(ValueError):
        EngineConfig(alpha0=0.0)


def test_no_evidence_holds_trust():
    """A node can lose every evidence source at once (edges gated out or
    endpoints stale, physics gated, temporal evidence withdrawn in field
    mode). That must HOLD the belief — not crash (regression: this divided
    by zero) and not fabricate 0.5-consistency into the Beta update."""
    from csia.trust_engine.engine import TrustCore
    core = TrustCore(["gps"])
    t0 = core.trust["gps"]
    for fresh in (True, False):
        res = core.step(edges={}, phys={}, hist={"gps": None},
                        var_ratio={"gps": None}, fresh={"gps": fresh})
        assert res["gps"]["trust"] == t0, "trust must hold with no evidence"
        assert core.alpha["gps"] == core.cfg.alpha0, "belief must not update"
        assert res["gps"]["evidence"] == 0.5  # neutral placeholder only


def test_trust_bounded_and_clean_floor(clean_run):
    _, _, _, hist, _ = clean_run
    assert (hist.trust >= 0.0).all() and (hist.trust <= 1.0).all()
    assert (hist.evidence >= 0.0).all() and (hist.evidence <= 1.0).all()
    # after prior convergence (~10 s) no sensor may false-alarm in clean air
    assert hist.trust[250:].min() > 0.88, "clean-flight false alarm"


def test_prior_and_convergence(clean_run):
    _, _, _, hist, _ = clean_run
    cfg = EngineConfig()
    t0 = cfg.alpha0 / (cfg.alpha0 + cfg.beta0)
    assert abs(hist.trust[0].mean() - t0) < 0.05
    assert hist.trust[-1].min() > 0.95  # converged high by flight end


def test_latency_budget(clean_run):
    _, _, _, hist, _ = clean_run
    mean_us = float(hist.latency_us[10:].mean())
    print(f"\ntrust-core latency: mean {mean_us:.1f} us/tick "
          f"(desktop Python, informational)")
    assert mean_us < 2000.0, "trust core exceeds 2 ms/tick on desktop"
