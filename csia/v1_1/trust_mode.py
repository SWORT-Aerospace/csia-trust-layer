"""Versioned trust mode — Phase 4 §2.

Two modes, one selected by configuration, neither reachable by accident:

  LEGACY_NEIGHBOR_PROPAGATION   w = gate_e * trust[other]     (v1, historical)
  FLAT_V1_1                     w = gate_e                    (v1.1 DEFAULT)

`w` is the neighbour-edge weight inside `TrustCore.step`. It is the entire
graph-specific coupling in the trust update — one factor on one line,
`csia/trust_engine/engine.py:110` — and Phase 3B measured that removing it
costs nothing and gains 0.28 s on `dual_imu_failure`.

WHAT "LEGACY" MEANS HERE
------------------------
It means the frozen class, not a copy of it. `make_core(LEGACY, ...)` returns
`csia.trust_engine.engine.TrustCore` itself. There is therefore no way for
legacy behaviour to drift from v1: reproducing it is not a re-implementation
that has to be kept in sync, it is the same object.

FLAT is the frozen class with one factor neutralised, by subclassing:

    self.trust = {n: 1.0 for n in self.names}
    return super().step(...)

`self.trust` is read in exactly one place inside the frozen `step()` — the
neighbour weight. Presenting it as all-ones for the duration of the call
removes the coupling and nothing else; every other line of the trust update
(consistency, gates, physics, temporal, statistical, the w_* mixture, rho, the
Beta update, freshness) is literally the frozen code. The frozen method
reassigns `self.trust = new_trust` before returning, so the substitution is
redone each tick.

This is the same construction Phase 3A used for its FLAT arm, promoted from an
ablation harness to the default runtime. A regression test asserts the two
agree bit-for-bit, so the Phase 3A/3B results carry over unchanged rather than
being re-derived.

NO HISTORICAL CONFIGURATION IS SILENTLY CHANGED
-----------------------------------------------
The default is FLAT_V1_1 for v1.1 consumers, and `trust_mode_of()` resolves an
explicit request. Replay of a v1 or research configuration must pass
`LEGACY_NEIGHBOR_PROPAGATION` explicitly, and the mode is recorded in every
ledger event and every API payload so a trajectory can never be attributed to
the wrong mode after the fact.
"""

from __future__ import annotations

import contextlib
from enum import Enum

from ..trust_engine.engine import EngineConfig, TrustCore, TrustEngine


class TrustMode(str, Enum):
    """How the neighbour edge weight is formed. `str` so it serialises."""

    LEGACY_NEIGHBOR_PROPAGATION = "LEGACY_NEIGHBOR_PROPAGATION"
    FLAT_V1_1 = "FLAT_V1_1"

    @property
    def neighbour_weight_expression(self) -> str:
        """The exact expression this mode puts at engine.py:110."""
        return ("w = float(gate_e) * self.trust[other]"
                if self is TrustMode.LEGACY_NEIGHBOR_PROPAGATION
                else "w = float(gate_e)")

    @property
    def propagates_trust(self) -> bool:
        return self is TrustMode.LEGACY_NEIGHBOR_PROPAGATION


#: v1.1 default. Phase 3B decision E. Changing this is an architecture change
#: and must go through the freeze document, not a patch.
DEFAULT_TRUST_MODE = TrustMode.FLAT_V1_1


def trust_mode_of(value=None) -> TrustMode:
    """Resolve a configuration value to a mode. `None` -> the v1.1 default.

    Raises on an unknown string rather than falling back, because a typo in a
    trust mode that silently selected the default would change which
    architecture produced a flight record.
    """
    if value is None:
        return DEFAULT_TRUST_MODE
    if isinstance(value, TrustMode):
        return value
    try:
        return TrustMode(str(value))
    except ValueError as exc:
        raise ValueError(
            f"unknown trust_mode {value!r}; expected one of "
            f"{[m.value for m in TrustMode]}") from exc


class FlatTrustCore(TrustCore):
    """Frozen `TrustCore` with neighbour-trust weighting neutralised."""

    def step(self, edges, phys, hist, var_ratio, fresh):
        self.trust = {n: 1.0 for n in self.names}
        return super().step(edges, phys, hist, var_ratio, fresh)


def make_core(mode=None, names=None, cfg: EngineConfig | None = None):
    """The per-tick trust core for `mode`.

    LEGACY returns the frozen class itself; FLAT returns the subclass above.
    """
    mode = trust_mode_of(mode)
    cls = (TrustCore if mode is TrustMode.LEGACY_NEIGHBOR_PROPAGATION
           else FlatTrustCore)
    return cls(names, cfg)


@contextlib.contextmanager
def _core_class(cls):
    """Substitute the class `TrustEngine.run` instantiates, then restore.

    `TrustEngine.run` constructs its core inline, so selecting a different one
    for the batch path means either copying `run()` — which would duplicate
    frozen code and create exactly the drift this design exists to prevent —
    or substituting the name it looks up. The substitution is scoped to the
    call and restored in a `finally`, and a test asserts the restoration.

    The REAL-TIME path needs none of this: `OnlineTrustLayer.core` is a plain
    attribute, so `attach_to_online_layer` below simply assigns it.
    """
    import csia.trust_engine.engine as eng
    real = eng.TrustCore
    eng.TrustCore = cls
    try:
        yield
    finally:
        eng.TrustCore = real


class V1_1TrustEngine(TrustEngine):
    """Batch replay driver carrying an explicit trust mode."""

    def __init__(self, graph, config: EngineConfig | None = None, *,
                 trust_mode=None):
        super().__init__(graph, config)
        self.trust_mode = trust_mode_of(trust_mode)

    def run(self, td):
        if self.trust_mode is TrustMode.LEGACY_NEIGHBOR_PROPAGATION:
            return super().run(td)          # frozen path, no substitution
        with _core_class(FlatTrustCore):
            return super().run(td)


def make_engine(mode=None, graph=None, cfg: EngineConfig | None = None):
    """Batch engine for `mode`."""
    return V1_1TrustEngine(graph, cfg, trust_mode=mode)


def attach_to_online_layer(layer, mode=None):
    """Point a live `OnlineTrustLayer` at the core for `mode`.

    `layer.core` is a public attribute holding a freshly constructed
    `TrustCore` whose constructor only seeds alpha/beta/trust from the config,
    so replacing it immediately after construction is equivalent to having
    constructed the other class. Returns the resolved mode.
    """
    mode = trust_mode_of(mode)
    if mode is TrustMode.FLAT_V1_1:
        layer.core = FlatTrustCore(layer.core.names, layer.core.cfg)
    layer.trust_mode = mode
    return mode
