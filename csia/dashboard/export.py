"""Export a scenario run (comparator + trust engine + diagnosis output) as a
self-contained replay JSON for the web dashboard.

CSIA role: scenario replay. The JSON carries everything the live view needs:
per-tick trust, evidence sub-scores, gated edge consistencies, diagnosis
posterior, and the graph layout — so the browser does zero physics, it just
replays what the engine computed.
"""

import json
import os

import networkx as nx
import numpy as np

from ..runtime.failsafe import FailsafePolicy
from ..trust_engine.engine import consistency


def _r(x, nd=4):
    return np.round(np.asarray(x, dtype=float), nd).tolist()


class _BatchState:
    """Minimal TrustState adapter so the real FailsafePolicy can run over the
    batch replay history — same fields the online TrustState exposes to the
    policy (trust, fresh, posterior, top_causes, armed). armed=None makes the
    policy use its arm_time gate, matching the simulator's scripted arming."""

    __slots__ = ("t", "trust", "fresh", "posterior", "armed")

    def __init__(self, t, trust, fresh, posterior):
        self.t = t
        self.trust = trust
        self.fresh = fresh
        self.posterior = posterior
        self.armed = None

    def top_causes(self, n=3):
        return sorted(self.posterior.items(), key=lambda kv: -kv[1])[:n]


def _run_failsafe(td, hist, diag):
    """Replay the deterministic failsafe state machine over the batch trust
    history. Returns (per-tick level ints, issuance events, transitions) so
    the dashboard can render the SAME recovery response the live runtime
    computes — no new logic, the shipping FailsafePolicy verbatim."""
    names = hist.names
    causes = diag.causes
    policy = FailsafePolicy()
    levels = []          # per-tick FailsafeLevel value 0..3
    events = []          # discrete action issuances (the "what we did" log)
    for k in range(len(td.t)):
        t = float(td.t[k])
        trust = {n: float(hist.trust[k, hist.col(n)]) for n in names}
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        posterior = {causes[i]: float(diag.posterior[k][i])
                     for i in range(len(causes))}
        actions = policy.update(_BatchState(t, trust, fresh, posterior))
        levels.append(int(policy.level))
        if actions:
            events.append({"k": k, "t": round(t, 2), "level": int(policy.level),
                           "actions": [{"name": a.name, "reason": a.reason}
                                       for a in actions]})
    transitions = [{"t": round(tr.t, 2), "from": tr.previous.name,
                    "to": tr.level.name, "reasons": tr.reasons}
                   for tr in policy.transitions]
    return levels, events, transitions


def export_replay(name: str, title: str, td, hist, diag, graph,
                  faults, out_dir: str) -> str:
    layout = nx.spring_layout(graph, seed=7, k=1.6)
    fs_levels, fs_events, fs_transitions = _run_failsafe(td, hist, diag)
    doc = {
        "name": name,
        "title": title,
        "t": _r(td.t, 3),
        "sensors": hist.names,
        "trust": {n: _r(hist.trust[:, hist.col(n)]) for n in hist.names},
        "components": {
            comp: {n: _r(np.nan_to_num(arr[:, hist.col(n)], nan=-1.0))
                   for n in hist.names}
            for comp, arr in hist.components.items()
        },
        "edges": [
            {"key": key, "a": a, "b": b,
             "c": _r(consistency(lam_e)),
             "gate": _r(np.asarray(gate_e, dtype=float)
                        * np.ones(len(lam_e)))}
            for key, (a, b, lam_e, gate_e) in td.edges.items()
        ],
        "diagnosis": {"causes": diag.causes,
                      "posterior": _r(diag.posterior)},
        "aux": {"speed_gate": _r(td.aux["speed_gate"]),
                "vh": _r(td.aux["vh"], 2)},
        # Autonomous remediation: the failsafe state machine's response,
        # replayed per tick. levels: 0 NORMAL 1 CAUTION 2 CRITICAL 3 EMERGENCY.
        # events: the concrete recovery actions issued (SWITCH_NAV_INERTIAL,
        # STABILIZE, ...). This is what the vehicle DOES about each fault.
        "failsafe": {"level": fs_levels, "events": fs_events,
                     "transitions": fs_transitions},
        "faults": [{"kind": f.kind, "target": f.target, "start": f.start,
                    "duration": f.duration} for f in faults],
        "layout": {n: [round(float(xy[0]), 4), round(float(xy[1]), 4)]
                   for n, xy in layout.items()},
        "latency_us": {"mean": round(float(hist.latency_us[10:].mean()), 1),
                       "p95": round(float(np.percentile(
                           hist.latency_us[10:], 95)), 1)},
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.json")
    with open(path, "w") as fh:
        json.dump(doc, fh)
    return path
