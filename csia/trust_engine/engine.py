"""Trust Coefficient engine.

CSIA role: the recursive Bayesian update at the heart of the architecture.
Each sensor node i carries a Beta-distributed belief over its reliability,
T_i ~ Beta(alpha_i, beta_i); the Trust Coefficient is the posterior mean
T_i = alpha_i / (alpha_i + beta_i) in [0, 1].

Per tick k, evidence E_i[k] in [0, 1] fuses four sub-scores:

  C_nbr  — physical consistency with graph neighbors: trust-weighted mean of
           edge consistencies c_ij, weighted by the edge gate AND the
           neighbor's own current trust T_j. A distrusted neighbor cannot
           drag a healthy sensor down (trust propagation), and a gated-out
           edge contributes nothing rather than false-alarming.
  C_phys — internal physics self-consistency (gated the same way).
  C_temp — temporal stability: agreement with the historical (Holt) predictor.
  C_stat — statistical confidence: innovation-whiteness (variance-ratio) test.

Update with adaptive forgetting factor rho_i[k]:

  alpha_i <- rho_i * alpha_i + E_i        beta_i <- rho_i * beta_i + (1 - E_i)

rho adapts to predictor disagreement D_i (spread of the sub-scores):
agreement -> long memory (stable trust); conflict -> short memory (fast
response). Evidence keeps flowing after a transient ends, so trust recovers
naturally — degradation is graceful and reversible, never a latched flag.

``TrustCore`` is the single per-tick implementation shared by the batch
replay path (``TrustEngine.run``) and the real-time runtime
(``csia.runtime.online.OnlineTrustLayer``) — one implementation, no drift.

Latency is measured with time.perf_counter; this is desktop-Python timing,
NOT a claim about embedded (STM32H7/Pi 5) timing.
"""

import logging
import time
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineConfig:
    """All trust-engine tunables in one place.

    w_*: evidence fusion weights, renormalized over the sub-scores actually
    available at each tick. rho_max/min: adaptive forgetting bounds —
    effective evidence memory is ~1/(1-rho) ticks (500 ticks / 20 s calm,
    20 ticks / 0.8 s under predictor disagreement). alpha0/beta0: Beta
    prior; T(0) = alpha0/(alpha0+beta0) = 0.8, mildly optimistic.
    """
    w_nbr: float = 0.35
    w_phys: float = 0.30
    w_temp: float = 0.20
    w_stat: float = 0.15
    rho_max: float = 0.998
    rho_min: float = 0.95
    alpha0: float = 8.0
    beta0: float = 2.0

    def __post_init__(self):
        if not (0.0 < self.rho_min <= self.rho_max < 1.0):
            raise ValueError("require 0 < rho_min <= rho_max < 1")
        if min(self.w_nbr, self.w_phys, self.w_temp, self.w_stat) < 0:
            raise ValueError("fusion weights must be non-negative")
        if self.alpha0 <= 0 or self.beta0 <= 0:
            raise ValueError("Beta prior parameters must be positive")


def consistency(lam):
    """Map a normalized squared innovation (per df) to a score in (0, 1].
    A healthy residual averages lambda ~ 1 (chi-square mean), so only the
    EXCESS over 1 counts against the sensor: c = exp(-max(0, lam - 1) / 2).
    Vectorized; accepts scalars or arrays."""
    return np.exp(-0.5 * np.maximum(0.0, lam - 1.0))


class TrustCore:
    """Single-tick trust update — the shared real-time core.

    Inputs per tick are plain scalars:
      edges:  {edge_key: (node_a, node_b, lam, gate)}
      phys:   {node: (lam, gate)}
      hist:   {node: lam}
      var_ratio: {node: vr}
      fresh:  {node: bool}
    Returns {node: {"trust", "evidence", "rho", "nbr", "phys", "temp", "stat"}}.
    """

    def __init__(self, names, cfg: EngineConfig | None = None):
        self.names = list(names)
        self.cfg = cfg or EngineConfig()
        self.alpha = {n: self.cfg.alpha0 for n in self.names}
        self.beta = {n: self.cfg.beta0 for n in self.names}
        self.trust = {n: self.cfg.alpha0 / (self.cfg.alpha0 + self.cfg.beta0)
                      for n in self.names}

    def step(self, edges: dict, phys: dict, hist: dict,
             var_ratio: dict, fresh: dict) -> dict:
        cfg = self.cfg
        # incident map rebuilt cheaply from the edge dict (12 edges)
        out = {}
        new_trust = {}
        for n in self.names:
            num = den = 0.0
            for key, (a, b, lam_e, gate_e) in edges.items():
                if a != n and b != n:
                    continue
                other = b if a == n else a
                w = float(gate_e) * self.trust[other]
                if w <= 1e-6:
                    continue
                num += w * float(np.exp(-0.5 * max(0.0, lam_e - 1.0)))
                den += w
            c_nbr = num / den if den > 1e-6 else None

            c_phys = None
            if n in phys:
                lam_p, gate_p = phys[n]
                if float(gate_p) > 1e-6:
                    c_phys = float(np.exp(-0.5 * max(0.0, lam_p - 1.0)))

            c_temp = None if hist.get(n) is None else \
                float(np.exp(-0.5 * max(0.0, hist[n] - 1.0)))
            c_stat = None if var_ratio.get(n) is None else \
                float(np.exp(-0.5 * max(0.0, var_ratio[n] - 1.0)))

            parts = [(cfg.w_nbr, c_nbr), (cfg.w_phys, c_phys),
                     (cfg.w_temp, c_temp), (cfg.w_stat, c_stat)]
            avail = [(w, c) for w, c in parts if c is not None]
            wsum = sum(w for w, _ in avail)
            evidence = sum(w * c for w, c in avail) / wsum

            scores = [c for _, c in avail]
            d = max(scores) - min(scores) if len(scores) > 1 else 0.0
            rho = cfg.rho_max - (cfg.rho_max - cfg.rho_min) * d

            if fresh.get(n, True):
                self.alpha[n] = rho * self.alpha[n] + evidence
                self.beta[n] = rho * self.beta[n] + (1.0 - evidence)
            new_trust[n] = self.alpha[n] / (self.alpha[n] + self.beta[n])
            out[n] = {"trust": new_trust[n], "evidence": evidence, "rho": rho,
                      "nbr": c_nbr, "phys": c_phys, "temp": c_temp,
                      "stat": c_stat}
        # synchronous update: all nodes saw tick k-1 trust during this step
        self.trust = new_trust
        return out


class TrustHistory:
    def __init__(self, t, names):
        k, n = len(t), len(names)
        self.t = t
        self.names = list(names)
        self.trust = np.zeros((k, n))
        self.components = {c: np.full((k, n), np.nan)
                           for c in ("nbr", "phys", "temp", "stat")}
        self.evidence = np.zeros((k, n))
        self.rho = np.zeros((k, n))
        self.latency_us = np.zeros(k)

    def col(self, name):
        return self.names.index(name)


class TrustEngine:
    """Batch replay driver: runs TrustCore over precomputed TickData."""

    def __init__(self, graph, config: EngineConfig | None = None):
        self.graph = graph
        self.names = list(graph.nodes)
        self.cfg = config or EngineConfig()

    def run(self, td) -> TrustHistory:
        names = self.names
        k_total = len(td.t)
        hist = TrustHistory(td.t, names)
        core = TrustCore(names, self.cfg)

        edge_meta = {key: (a, b) for key, (a, b, _, _) in td.edges.items()}
        for k in range(k_total):
            t0 = time.perf_counter()
            edges_now = {key: (edge_meta[key][0], edge_meta[key][1],
                               float(td.edges[key][2][k]),
                               float(np.asarray(td.edges[key][3]).flat[
                                   min(k, np.asarray(td.edges[key][3]).size - 1)]))
                         for key in td.edges}
            phys_now = {n: (float(lam[k]), float(np.asarray(gate).flat[
                min(k, np.asarray(gate).size - 1)]))
                for n, (lam, gate) in td.physics.items()}
            hist_now = {n: float(td.hist[n][k]) for n in names}
            vr_now = {n: float(td.var_ratio[n][k]) for n in names}
            fresh_now = {n: bool(td.fresh[n][k]) for n in names}

            res = core.step(edges_now, phys_now, hist_now, vr_now, fresh_now)
            for i, n in enumerate(names):
                r = res[n]
                hist.trust[k, i] = r["trust"]
                hist.evidence[k, i] = r["evidence"]
                hist.rho[k, i] = r["rho"]
                for comp in ("nbr", "phys", "temp", "stat"):
                    hist.components[comp][k, i] = (
                        np.nan if r[comp] is None else r[comp])
            hist.latency_us[k] = (time.perf_counter() - t0) * 1e6

        return hist
