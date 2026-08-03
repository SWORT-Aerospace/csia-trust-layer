"""Native core (C) vs Python reference: same algorithm, pinned by test."""

import numpy as np
import pytest

from csia import native
from csia.diagnosis.bayes import (CAUSES, EPS, EVIDENCE_MULT, PRIOR_NOMINAL,
                                  SMOOTH_ALPHA, DiagnosisCore)
from csia.trust_engine.engine import EngineConfig, TrustCore

pytestmark = pytest.mark.skipif(not native.available,
                                reason="native core not built")

NODES = ["imu0", "imu1", "baro", "gps"]
EDGES = [("e0", "imu0", "imu1"), ("e1", "imu0", "gps"), ("e2", "baro", "gps")]


def test_native_trust_matches_python():
    cfg = EngineConfig()
    py = TrustCore(NODES, cfg)
    idx = {n: i for i, n in enumerate(NODES)}
    nat = native.NativeTrustState(
        len(NODES), len(EDGES),
        [idx[a] for _, a, _ in EDGES], [idx[b] for _, _, b in EDGES], cfg)
    rng = np.random.default_rng(0)
    for step in range(500):
        elam = rng.exponential(1.0, len(EDGES)) * (1 + 20 * (step % 100 > 80))
        egate = rng.random(len(EDGES))
        plam = rng.exponential(1.0, len(NODES))
        pgate = (rng.random(len(NODES)) > 0.3).astype(float)
        hist = rng.exponential(1.0, len(NODES))
        vr = rng.exponential(1.0, len(NODES))
        hist_has = rng.random(len(NODES)) > 0.2
        fresh = rng.random(len(NODES)) > 0.1

        edges = {k: (a, b, float(elam[e]), float(egate[e]))
                 for e, (k, a, b) in enumerate(EDGES)}
        phys = {n: (float(plam[i]), float(pgate[i]))
                for i, n in enumerate(NODES)}
        h = {n: (float(hist[i]) if hist_has[i] else None)
             for i, n in enumerate(NODES)}
        v = {n: (float(vr[i]) if hist_has[i] else None)
             for i, n in enumerate(NODES)}
        f = {n: bool(fresh[i]) for i, n in enumerate(NODES)}
        res = py.step(edges, phys, h, v, f)

        nat.elam[:], nat.egate[:] = elam, egate
        nat.plam[:], nat.pgate[:] = plam, pgate
        nat.phas[:] = 1
        nat.hist[:], nat.vr[:] = hist, vr
        nat.hist_has[:] = hist_has
        nat.vr_has[:] = hist_has
        nat.fresh[:] = fresh
        nat.step()

        for i, n in enumerate(NODES):
            assert abs(res[n]["trust"] - nat.out_trust[i]) < 1e-12, \
                f"step {step} node {n}"
            assert abs(res[n]["evidence"] - nat.out_ev[i]) < 1e-12


def test_native_trust_no_evidence_parity():
    """Both implementations must agree on the no-evidence branch: hold the
    belief, report the 0.5 placeholder (regression: Python divided by zero
    while C updated the belief with fabricated 0.5 evidence)."""
    cfg = EngineConfig()
    py = TrustCore(["a", "b"], cfg)
    nat = native.NativeTrustState(2, 1, [0], [1], cfg)
    steps = [
        (1.4, 1.0),   # normal evidence tick
        (5.0, 0.0),   # everything gated out -> no evidence anywhere
        (0.8, 1.0),   # evidence returns
    ]
    for lam, gate in steps:
        res = py.step({"e": ("a", "b", lam, gate)},
                      {"a": (lam, gate), "b": (lam, gate)},
                      {"a": None, "b": None}, {"a": None, "b": None},
                      {"a": True, "b": True})
        nat.elam[:], nat.egate[:] = [lam], [gate]
        nat.plam[:], nat.pgate[:] = [lam, lam], [gate, gate]
        nat.phas[:] = 1
        nat.hist_has[:] = 0
        nat.vr_has[:] = 0
        nat.fresh[:] = 1
        nat.step()
        for i, n in enumerate(("a", "b")):
            assert abs(res[n]["trust"] - nat.out_trust[i]) < 1e-12
            assert abs(res[n]["evidence"] - nat.out_ev[i]) < 1e-12


def test_native_bounds_rejected():
    """Caller-supplied counts beyond the stack-sized scratch buffers must
    be rejected (-1 -> ValueError), not corrupt the stack."""
    cfg = EngineConfig()
    with pytest.raises(ValueError, match="CSIA_MAX_NODES"):
        native.NativeTrustState(65, 0, [], [], cfg).step()
    with pytest.raises(ValueError, match="CSIA_MAX_CAUSES"):
        native.NativeDiagState(1, 33, np.zeros((33, 1), np.uint8),
                               np.zeros(33), 0.06, 1.5, 0.02).step()


def test_native_diag_matches_python():
    py = DiagnosisCore()
    feats = sorted({f for lows in CAUSES.values() for f in lows}
                   | {"x1", "x2", "x3"})
    nf, nc = len(feats), len(py.names)
    low = np.zeros((nc, nf), dtype=np.uint8)
    for k, cause in enumerate(py.names):
        for f in CAUSES[cause]:
            low[k, feats.index(f)] = 1
    nat = native.NativeDiagState(nf, nc, low, py._log_prior,
                                 SMOOTH_ALPHA, EVIDENCE_MULT, EPS)
    rng = np.random.default_rng(1)
    for step in range(300):
        c = rng.random(nf)
        gate = (rng.random(nf) > 0.2).astype(float)
        post_py = py.step({feats[i]: (float(c[i]), float(gate[i]))
                           for i in range(nf)})
        nat.c[:], nat.gate[:] = c, gate
        post_c = nat.step()
        for k, cause in enumerate(py.names):
            assert abs(post_py[cause] - post_c[k]) < 1e-12, f"step {step}"


# --- production-topology parity (audit F-03) ---------------------------------
# The fixture above pins C<->Python on a 4-node / 3-edge graph. Production is
# 8 nodes / 11 edges, so equivalence was previously unverified at the topology
# that actually ships.

def test_native_parity_on_production_topology():
    """C and Python must agree on the REAL trust graph, not just a toy one."""
    from csia.trust_graph import build_trust_graph

    graph = build_trust_graph()
    nodes = list(graph.nodes)
    edges = [(f"e{i}", a, b) for i, (a, b) in enumerate(graph.edges)]
    assert (len(nodes), len(edges)) == (8, 11), "production topology changed"

    cfg = EngineConfig()
    py = TrustCore(nodes, cfg)
    idx = {n: i for i, n in enumerate(nodes)}
    nat = native.NativeTrustState(
        len(nodes), len(edges),
        [idx[a] for _, a, _ in edges], [idx[b] for _, _, b in edges], cfg)

    rng = np.random.default_rng(7)
    for step in range(300):
        elam = rng.exponential(1.0, len(edges)) * (1 + 15 * (step % 80 > 60))
        egate = (rng.random(len(edges)) > 0.25).astype(float)
        plam = rng.exponential(1.0, len(nodes))
        pgate = (rng.random(len(nodes)) > 0.3).astype(float)
        hist = rng.exponential(1.0, len(nodes))
        vr = rng.exponential(1.0, len(nodes))
        has = rng.random(len(nodes)) > 0.2
        fresh = rng.random(len(nodes)) > 0.1

        res = py.step(
            {k: (a, b, float(elam[e]), float(egate[e]))
             for e, (k, a, b) in enumerate(edges)},
            {n: (float(plam[i]), float(pgate[i])) for i, n in enumerate(nodes)},
            {n: (float(hist[i]) if has[i] else None)
             for i, n in enumerate(nodes)},
            {n: (float(vr[i]) if has[i] else None) for i, n in enumerate(nodes)},
            {n: bool(fresh[i]) for i, n in enumerate(nodes)})

        nat.elam[:], nat.egate[:] = elam, egate
        nat.plam[:], nat.pgate[:] = plam, pgate
        nat.phas[:] = 1
        nat.hist[:], nat.vr[:] = hist, vr
        nat.hist_has[:] = has
        nat.vr_has[:] = has
        nat.fresh[:] = fresh
        nat.step()

        for i, n in enumerate(nodes):
            assert abs(res[n]["trust"] - nat.out_trust[i]) < 1e-12, \
                f"step {step} node {n}"
            assert abs(res[n]["evidence"] - nat.out_ev[i]) < 1e-12
