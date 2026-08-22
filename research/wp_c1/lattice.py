"""WP-C1 Part 1 — the joint (gate x channel) availability lattice.

A configuration is a pair (G, X): G the set of CLOSED gates, X the set of
PRESENT channels. Feature f is observable iff every channel it spans is in X
AND no gate in G controls it.

Reachability is NOT the product of the two lattices. A gate whose every
feature is already destroyed by channel absence is vacuous: closing it changes
nothing, so (G u {g}, X) and (G, X) are the same configuration. C_reach is the
set of canonical pairs (G subset of actuatable(X), X).

METHOD NOTE — not novel. See NOVELTY_ATTACK.md. Worst-case diagnosability
under sensor loss and isolability across operating modes are both established
(Carvalho et al. 2013; Hashemniya & Krysander). This module applies that
machinery to CSIA; it does not introduce it.

Run:  PYTHONPATH=. python research/wp_c1/lattice.py
Out:  research/wp_c1/results/joint_lattice.json
"""

import itertools
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.trust_graph.graph import EDGES, NODES              # noqa: E402
from research.wp_e1.gate_map import GATE_FEATURES            # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MATRIX = os.path.join(ROOT, "research", "formalization",
                      "diagnostic_signature_matrix.yaml")
CORPUS = os.path.join(ROOT, "data", "real_logs_report.json")
RESULTS = os.path.join(os.path.dirname(__file__), "results")

GATES = tuple(sorted(GATE_FEATURES))
CHANNELS = tuple(sorted(n[0] if isinstance(n, (list, tuple)) else n
                        for n in NODES))


def feature_channels():
    """feature -> set of channels it spans. Read from the trust graph and the
    physics/temporal predictor definitions."""
    req = {}
    for a, b, relation, *_ in EDGES:
        req.setdefault(relation, set()).update({a, b})
    # comparator re-splits the shared relation name at online.py:206-208
    req["velocity_gps_doppler_0"] = {"imu0", "gps"}
    req["velocity_gps_doppler_1"] = {"imu1", "gps"}
    req.pop("velocity_gps_doppler", None)
    for n in ("gps", "mag", "battery", "motor_esc", "vibration", "baro"):
        req[f"phys_{n}"] = {n}
    for n in ("mag", "battery", "vibration", "gps"):
        req[f"temp_{n}"] = {n}
    return req


REQ = feature_channels()


def load_signatures():
    if not os.path.exists(MATRIX):
        raise SystemExit(f"WP1_FORMALIZATION_MISSING: {MATRIX}")
    with open(MATRIX) as fh:
        low = yaml.safe_load(fh).get("hypotheses")
    if not low:
        raise SystemExit("SIGNATURE_MATRIX_MISSING")
    return low


def actuatable(channels):
    """Gates that still remove at least one channel-available feature.

    A gate controlling only features whose channels are absent is vacuous —
    the configuration is identical to leaving it open. This is what makes
    C_reach strictly smaller than the naive product.
    """
    out = []
    for g, feats in GATE_FEATURES.items():
        if any(REQ[f] <= channels for f in feats):
            out.append(g)
    return tuple(sorted(out))


def observable(closed_gates, channels):
    """Diagnostic features observable under this configuration."""
    gated = {f for g in closed_gates for f in GATE_FEATURES[g]}
    return {f for f, need in REQ.items()
            if need <= channels and f not in gated}


def partition(low, closed_gates, channels):
    avail = observable(closed_gates, channels)
    restricted = {h: tuple(sorted(set(s) & avail)) for h, s in low.items()}
    classes = {}
    for hyp, sig in restricted.items():
        classes.setdefault(sig, []).append(hyp)
    return {sig: tuple(sorted(m)) for sig, m in classes.items()}


def kappa(low, classes):
    h = len(low)
    return (h - len(classes)) / (h - 1) if h > 1 else 0.0


def merged_pairs(classes):
    """Unordered hypothesis pairs that SHARE an observable class, i.e. that
    are indistinguishable in this configuration."""
    same = set()
    for members in classes.values():
        for a, b in itertools.combinations(sorted(members), 2):
            same.add((a, b))
    return same


def enumerate_reach(low, channel_sets=None):
    """C_reach as {(frozenset(gates_closed), frozenset(channels)): info}."""
    if channel_sets is None:
        channel_sets = [frozenset(c)
                        for r in range(len(CHANNELS) + 1)
                        for c in itertools.combinations(CHANNELS, r)]
    reach = {}
    for X in channel_sets:
        act = actuatable(X)
        for r in range(len(act) + 1):
            for G in itertools.combinations(act, r):
                cls = partition(low, G, X)
                reach[(frozenset(G), X)] = {
                    "gates_closed": sorted(G),
                    "channels": sorted(X),
                    "n_channels": len(X),
                    "n_classes": len(cls),
                    "kappa": round(kappa(low, cls), 6),
                    "classes": cls,
                    "merged_pairs": merged_pairs(cls),
                }
    return reach


def corpus_channel_sets():
    with open(CORPUS) as fh:
        flights = json.load(fh)["flights"]
    counts = {}
    for f in flights:
        key = frozenset(f["sensors"])
        counts[key] = counts.get(key, 0) + 1
    return counts, len(flights)


def main() -> int:
    low = load_signatures()
    reach = enumerate_reach(low)

    naive = (2 ** len(GATES)) * (2 ** len(CHANNELS))
    kmax = max(reach.values(), key=lambda r: r["kappa"])

    # kappa_max restricted to "at least k channels present"
    by_k = {}
    for k in range(len(CHANNELS) + 1):
        subset = [r for r in reach.values() if r["n_channels"] >= k]
        if subset:
            worst = max(subset, key=lambda r: r["kappa"])
            by_k[k] = {"kappa_max": worst["kappa"],
                       "argmax_gates": worst["gates_closed"],
                       "argmax_channels": worst["channels"],
                       "n_configurations": len(subset)}

    counts, n_logs = corpus_channel_sets()
    corpus_reach = enumerate_reach(low, list(counts))
    corpus_worst = max(corpus_reach.values(), key=lambda r: r["kappa"])

    report = {
        "purpose": "joint gate x channel availability lattice for CSIA",
        "not_novel": "see research/wp_c1/NOVELTY_ATTACK.md — worst-case "
                     "diagnosability under sensor loss and isolability across "
                     "modes are established results; this applies them",
        "gates": list(GATES),
        "channels": list(CHANNELS),
        "naive_product_size": naive,
        "reachable_size": len(reach),
        "reduction_factor": round(naive / len(reach), 3),
        "reachability_rule": "a gate whose every feature has an absent channel "
                             "is vacuous; (G u {g}, X) collapses to (G, X)",
        "kappa_max_unrestricted": {
            "kappa": kmax["kappa"],
            "gates_closed": kmax["gates_closed"],
            "channels": kmax["channels"],
            "note": "the empty channel set trivially collapses everything; "
                    "an admissibility assumption is required for a "
                    "non-degenerate certificate",
        },
        "kappa_max_by_min_channels": by_k,
        "corpus": {
            "n_logs": n_logs,
            "distinct_channel_configurations": len(counts),
            "reachable_configurations": len(corpus_reach),
            "kappa_max": corpus_worst["kappa"],
            "argmax_gates": corpus_worst["gates_closed"],
            "argmax_channels": corpus_worst["channels"],
        },
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "joint_lattice.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"naive product   : {naive}")
    print(f"reachable       : {len(reach)}  "
          f"(x{report['reduction_factor']} smaller)")
    print(f"kappa_max (all) : {kmax['kappa']}  at gates={kmax['gates_closed']} "
          f"channels={kmax['channels']}")
    print(f"\n{'min channels':>13s} {'kappa_max':>10s} {'#configs':>9s}  argmax")
    for k, v in sorted(by_k.items()):
        print(f"{k:>13d} {v['kappa_max']:>10.4f} {v['n_configurations']:>9d}  "
              f"gates={v['argmax_gates']} ch={len(v['argmax_channels'])}")
    print(f"\ncorpus: {len(counts)} distinct channel configs over {n_logs} "
          f"logs -> {len(corpus_reach)} reachable configurations, "
          f"kappa_max = {corpus_worst['kappa']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
