"""Shadow-mode driver: run the hypothesis layer over a scenario.

Reuses the EXISTING comparator output — no new sensor path, no change to the
trust core, the legacy diagnoser, or the failsafe. This is the only supported
way to produce hypothesis reports, so tests, ablations and sweeps all share
one code path.
"""

from dataclasses import dataclass

import numpy as np

from ..prediction import PredictionComparator
from ..sensors import generate_flight
from ..trust_engine.engine import consistency
from .bayes import TEMP_FEATURES
from .hypothesis import HypothesisEngine, classify_isolation

# csia.scenarios imports csia.diagnosis, so it is imported lazily inside
# run_shadow() to keep the package import graph acyclic.


def features_over_time(td) -> dict:
    """{feature: (c[K], gate[K])} — identical inputs to the legacy diagnoser."""
    feats = {}
    for key, (_, _, lam, gate) in td.edges.items():
        g = np.asarray(gate, dtype=float) * np.ones(len(lam))
        feats[key] = (consistency(lam), g)
    for name, (lam, gate) in td.physics.items():
        g = np.asarray(gate, dtype=float) * np.ones(len(lam))
        feats[f"phys_{name}"] = (consistency(lam), g)
    for name in TEMP_FEATURES:
        feats[f"temp_{name}"] = (consistency(td.hist[name]),
                                 np.ones(len(td.hist[name])))
    return feats


@dataclass
class ShadowRun:
    t: np.ndarray
    reports: list
    peak_confidence: dict
    first_root: tuple | None          # (t, hypothesis_id, affected_sources)
    tick_cost_us: float

    def at(self, t: float):
        k = int(np.argmin(np.abs(self.t - t)))
        return self.reports[k]

    def isolation(self, truth_sources, shared_resource=None) -> str:
        if self.first_root is None:
            return classify_isolation(self.reports[-1], truth_sources,
                                      shared_resource=shared_resource)
        k = int(np.argmin(np.abs(self.t - self.first_root[0])))
        return classify_isolation(self.reports[k], truth_sources,
                                  shared_resource=shared_resource)

    def latency(self, onset: float) -> float | None:
        return None if self.first_root is None else self.first_root[0] - onset


def run_shadow(faults=(), truth=None, duration: float | None = None,
               **engine_kw) -> ShadowRun:
    import time

    from ..scenarios import DURATION, TICK_HZ, sample_streams
    duration = DURATION if duration is None else duration
    truth = truth if truth is not None else generate_flight()
    streams = sample_streams(truth, faults)
    td = PredictionComparator(tick_hz=TICK_HZ).build(streams, duration)
    feats = features_over_time(td)

    eng = HypothesisEngine(**engine_kw)
    reports, peak, first = [], {}, None
    t0 = time.perf_counter()
    for k in range(len(td.t)):
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in feats.items()}
        r = eng.step(float(td.t[k]), tick)
        reports.append(r)
        for h in r.hypotheses:
            peak[h.hypothesis_id] = max(peak.get(h.hypothesis_id, 0.0),
                                        h.confidence)
        if first is None and r.most_probable_root_cause:
            first = (float(td.t[k]), r.most_probable_root_cause,
                     tuple(r.affected_sources))
    cost = (time.perf_counter() - t0) / max(len(td.t), 1) * 1e6
    return ShadowRun(t=td.t, reports=reports, peak_confidence=peak,
                     first_root=first, tick_cost_us=cost)
