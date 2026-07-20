"""interceptor_seeker fault-scenario harness (SYNTHETIC profile).

Mirrors tests/scenarios/test_fault_scenarios.py: per fault, assert detection
of the faulted channel, correct diagnosis attribution, exoneration of
unfaulted channels, and no alarm on the clean engagement. Fixed seeds;
deterministic. Thresholds are set below measured performance (see
deliverables/montecarlo_results.md), not tuned to pass.
"""

import numpy as np
import pytest

from csia.seeker import run_seeker
from csia.seeker.runtime import DETECT_TRUST, SeekerConfig
from csia.seeker.scenarios import scenario_faults

WARMUP = SeekerConfig().arm_time
ONSET = 8.0


def _run(name, seed=0):
    return run_seeker(scenario_faults(name), tick_hz=100.0, seed=seed)


def _peak_cause(r):
    t = r.t
    mask = t > ONSET
    best_c, best_p = None, -1.0
    for c in r.causes:
        if c == "nominal":
            continue
        seg = r.diag[c][mask]
        if len(seg) and seg.max() > best_p:
            best_p, best_c = float(seg.max()), c
    return best_c, best_p


def test_clean_no_false_alarm():
    eng, r = _run("clean_engagement")
    post = r.t > WARMUP
    assert all(r.trust[n][post].min() > 0.80 for n in r.trust), \
        "clean engagement trust sagged below 0.80 post-warmup"
    assert not [x for x in r.transitions if x["to"] != "NORMAL"], \
        f"clean engagement raised alarms: {r.transitions}"


def test_ir_decoy_detected_attributed_isolated():
    eng, r = _run("ir_decoy")
    t = r.t
    ir = r.trust["ir_seeker"]
    below = np.where((t > ONSET) & (ir < DETECT_TRUST))[0]
    assert len(below), "IR decoy not detected on the IR channel"
    assert t[below[0]] - ONSET < 3.0, "IR decoy detection too slow"
    cause, p = _peak_cause(r)
    assert cause == "ir_decoy" and p > 0.7, f"misattributed: {cause} p={p:.2f}"
    # INS exonerated (untouched by an IR bearing decoy)
    assert r.trust["ins"][t > ONSET].min() > 0.80, "INS falsely implicated"


def test_rf_jam_detected_attributed():
    eng, r = _run("rf_jam")
    t = r.t
    rf = r.trust["rf_seeker"]
    below = np.where((t > ONSET) & (rf < DETECT_TRUST))[0]
    assert len(below), "RF jam not detected on the RF channel"
    assert t[below[0]] - ONSET < 3.0, "RF jam detection too slow"
    cause, p = _peak_cause(r)
    assert cause == "rf_jam" and p > 0.7, f"misattributed: {cause} p={p:.2f}"


def test_determinism():
    _, a = _run("ir_decoy", seed=7)
    _, b = _run("ir_decoy", seed=7)
    for n in a.trust:
        np.testing.assert_array_equal(a.trust[n], b.trust[n])


def test_uses_unmodified_cores():
    """The seeker must drive the same TrustCore/DiagnosisCore as the quad."""
    from csia.seeker.runtime import SeekerRuntime
    from csia.trust_engine.engine import TrustCore
    from csia.diagnosis.bayes import DiagnosisCore
    rt = SeekerRuntime()
    assert isinstance(rt.core, TrustCore)
    assert isinstance(rt.diag, DiagnosisCore)


@pytest.mark.parametrize("offset,should_detect", [(0.1, False), (4.0, True)])
def test_detection_floor_bracket(offset, should_detect):
    """Bracket the bearing-noise detection floor: a decoy well below combined
    bearing noise (~0.36 deg) must NOT be detected; a large one must be."""
    faults = [{"kind": "ir_decoy", "start": ONSET, "offset_deg": offset,
               "ramp_s": 1.5}]
    eng, r = run_seeker(faults, tick_hz=100.0, seed=3)
    t = r.t
    below = np.where((t > ONSET) & (r.trust["ir_seeker"] < DETECT_TRUST))[0]
    assert bool(len(below)) == should_detect
