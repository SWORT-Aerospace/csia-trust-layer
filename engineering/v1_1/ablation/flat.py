"""The FLAT baseline: CSIA with graph propagation removed and nothing else.

Phase 3A. `csia/trust_engine` is FROZEN, so FLAT is built by SUBCLASSING the
frozen `TrustCore` and neutralising exactly one coupling. **No method is
copied.** `FlatTrustCore.step` calls `TrustCore.step` verbatim, so every other
line of the trust update -- consistency function, gates, physics, temporal and
statistical components, the w_nbr/w_phys/w_temp/w_stat mixture, rho, the Beta
update, freshness handling -- is literally the same code.

WHAT THE GRAPH ACTUALLY IS
--------------------------
In `TrustCore.step` (engine.py:108-113) the neighbour-consistency component is
a trust-weighted average over incident edges:

    w = float(gate_e) * self.trust[other]
    num += w * consistency(lam_e)
    den += w
    c_nbr = num / den

`self.trust[other]` -- the NEIGHBOUR's current trust -- is the graph. It is
what makes trust propagate between nodes: an edge to a node that is itself
distrusted counts for less, so blame flows away from the distrusted end. That
single factor is the whole of the graph-specific responsibility propagation in
the trust update.

FLAT sets that factor to 1.0, leaving `w = gate_e`. Edge consistencies are
then averaged by gate alone. Every edge is still present, still gated, still
contributing; only the trust-weighting between nodes is gone.

WHY THIS IS NOT A STRAW MAN
---------------------------
Section 17 lists what must be identical: raw trace, canonical ingestion,
normalised channels, relation outputs, gates, evidence likelihood functions,
priors, smoothing, assurance thresholds. All of them are, by construction,
because FLAT executes the frozen code path. The only permitted removal is
graph-specific responsibility allocation, and that is the only removal made.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.trust_engine.engine import TrustCore, TrustEngine     # noqa: E402


class FlatTrustCore(TrustCore):
    """Frozen TrustCore with neighbour-trust weighting neutralised."""

    def step(self, edges, phys, hist, var_ratio, fresh):
        # self.trust is read in exactly one place inside the frozen step():
        # the neighbour weight. Presenting it as all-ones for the duration of
        # the call removes the graph coupling and nothing else. The frozen
        # method reassigns self.trust = new_trust before returning, so the
        # substitution has to be redone each tick -- which is what happens.
        self.trust = {n: 1.0 for n in self.names}
        return super().step(edges, phys, hist, var_ratio, fresh)


class FlatTrustEngine(TrustEngine):
    """Batch driver for FLAT. Identical to TrustEngine but for the core."""

    def run(self, td):
        import csia.trust_engine.engine as eng
        real = eng.TrustCore
        eng.TrustCore = FlatTrustCore          # harness-local, restored below
        try:
            return super().run(td)
        finally:
            eng.TrustCore = real


def arms():
    """{name: engine factory} for the ablation."""
    return {"GRAPH": TrustEngine, "FLAT": FlatTrustEngine}
