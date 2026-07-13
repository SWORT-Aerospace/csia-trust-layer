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

from ..trust_engine.engine import consistency


def _r(x, nd=4):
    return np.round(np.asarray(x, dtype=float), nd).tolist()


def export_replay(name: str, title: str, td, hist, diag, graph,
                  faults, out_dir: str) -> str:
    layout = nx.spring_layout(graph, seed=7, k=1.6)
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
