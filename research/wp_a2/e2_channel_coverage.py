"""WP-A2 E2 — structural diagnostic coverage at the corpus's real channel counts.

The submission states the real-log campaign ran on "5 of 8 monitored
channels". 5 is the maximum, not the typical case: across the 26 logs the
mean is 3.88, and 6 logs carried only 2 channels.

Channel count is not a performance detail — it is structural. A diagnostic
feature exists only if the channels it spans are present, and
``bayes.py:99-100`` SKIPS an absent feature rather than down-weighting it.
Two hypotheses whose LOW signatures coincide over the surviving features are
therefore pinned at their prior ratio forever: indistinguishable, not merely
weakly evidenced.

This computes, for every channel configuration actually observed in
``data/real_logs_report.json``:

  * which diagnostic features survive
  * the induced partition of the 8 hypotheses into observable classes
  * the coarsening index  kappa = (H - P) / (H - 1)
        0.0 = fully distinguishable, 1.0 = everything collapses to one class
  * whether `nominal` is absorbed — i.e. some fault becomes structurally
    indistinguishable from healthy flight
  * which hypotheses merge

No telemetry is needed. The channel inventory is already committed, and the
signature matrix is the WP1 artifact. This is a deterministic structural
result, not a measurement of detection performance.

Run:  PYTHONPATH=. python research/wp_a2/e2_channel_coverage.py
Out:  reports/wp_a2/e2_channel_coverage.json
"""

import json
import os
import sys
from collections import Counter

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.trust_graph.graph import EDGES                        # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
MATRIX = os.path.join(ROOT, "research", "formalization",
                      "diagnostic_signature_matrix.yaml")
CORPUS = os.path.join(ROOT, "data", "real_logs_report.json")
OUT = os.path.join(ROOT, "reports", "wp_a2", "e2_channel_coverage.json")


def feature_requirements():
    """feature name -> set of trust-graph nodes it needs in order to exist.

    Edge features need both endpoints. `phys_X` and `temp_X` need X. The edge
    relation `velocity_gps_doppler` is carried by two distinct edges; the
    signature matrix does not reference it, but it is included for
    completeness of the survival count.
    """
    req = {}
    for edge in EDGES:
        a, b, relation = edge[0], edge[1], edge[2]
        req.setdefault(relation, set()).update({a, b})
    for node in ("gps", "mag", "battery", "motor_esc", "vibration", "baro"):
        req[f"phys_{node}"] = {node}
    for node in ("mag", "battery", "vibration", "gps"):
        req[f"temp_{node}"] = {node}
    return req


def partition(low_sets, available):
    """Restrict each hypothesis's LOW signature to available features.

    Hypotheses sharing a restricted signature are one observable class.
    """
    restricted = {h: tuple(sorted(set(low) & available))
                  for h, low in low_sets.items()}
    classes = {}
    for hyp, sig in restricted.items():
        classes.setdefault(sig, []).append(hyp)
    return restricted, {sig: sorted(members)
                        for sig, members in classes.items()}


def analyse(low_sets, req, channels):
    channels = set(channels)
    available = {f for f, need in req.items() if need <= channels}
    restricted, classes = partition(low_sets, available)

    n_hyp = len(low_sets)
    n_cls = len(classes)
    kappa = (n_hyp - n_cls) / (n_hyp - 1) if n_hyp > 1 else 0.0

    # `nominal` has an empty LOW set; any fault restricted to empty joins it.
    nominal_class = next(members for sig, members in classes.items()
                         if "nominal" in members)
    absorbed = sorted(h for h in nominal_class if h != "nominal")

    merged = {", ".join(members): list(sig)
              for sig, members in classes.items() if len(members) > 1}

    return {
        "channels": sorted(channels),
        "n_channels": len(channels),
        "features_available": sorted(available),
        "features_lost": sorted(set(req) - available),
        "n_observable_classes": n_cls,
        "kappa": round(kappa, 4),
        "nominal_absorbs": absorbed,
        "nominal_absorbed": bool(absorbed),
        "merged_classes": merged,
        "restricted_signatures": {h: list(s) for h, s in restricted.items()},
    }


def main() -> int:
    with open(MATRIX) as fh:
        matrix = yaml.safe_load(fh)
    low_sets = matrix["hypotheses"]
    req = feature_requirements()

    with open(CORPUS) as fh:
        flights = json.load(fh)["flights"]

    configs = Counter(tuple(sorted(f["sensors"])) for f in flights)

    per_config = []
    corpus_absorbed = 0
    for channels, n_logs in sorted(configs.items(), key=lambda kv: -kv[1]):
        row = analyse(low_sets, req, channels)
        row["n_logs"] = n_logs
        row["fraction_of_corpus"] = round(n_logs / len(flights), 4)
        per_config.append(row)
        if row["nominal_absorbed"]:
            corpus_absorbed += n_logs

    by_count = {}
    for row in per_config:
        entry = by_count.setdefault(row["n_channels"],
                                    {"n_logs": 0, "kappa": [],
                                     "any_nominal_absorbed": False})
        entry["n_logs"] += row["n_logs"]
        entry["kappa"].append(row["kappa"])
        entry["any_nominal_absorbed"] |= row["nominal_absorbed"]
    for entry in by_count.values():
        entry["kappa_min"] = min(entry["kappa"])
        entry["kappa_max"] = max(entry["kappa"])
        del entry["kappa"]

    report = {
        "purpose": "structural diagnostic coverage at the channel counts the "
                   "corpus actually carries",
        "method": "restrict each hypothesis LOW signature to the features "
                  "whose channels are present; hypotheses sharing a "
                  "restricted signature are indistinguishable "
                  "(bayes.py:99-100 skips absent features)",
        "signature_matrix": "research/formalization/"
                            "diagnostic_signature_matrix.yaml",
        "corpus": "data/real_logs_report.json",
        "n_logs": len(flights),
        "n_hypotheses": len(low_sets),
        "kappa_definition": "(H - P) / (H - 1); 0 = fully distinguishable, "
                            "1 = total collapse",
        "channel_count_histogram": dict(sorted(
            Counter(len(f["sensors"]) for f in flights).items())),
        "mean_channels": round(
            sum(len(f["sensors"]) for f in flights) / len(flights), 4),
        "logs_in_nominal_absorbing_config": corpus_absorbed,
        "fraction_of_corpus_nominal_absorbed": round(
            corpus_absorbed / len(flights), 4),
        "by_channel_count": {str(k): v for k, v in sorted(by_count.items())},
        "configurations": per_config,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    print(f"logs={report['n_logs']}  mean_channels={report['mean_channels']}")
    print(f"channel histogram: {report['channel_count_histogram']}")
    print(f"corpus fraction where nominal is absorbed: "
          f"{report['fraction_of_corpus_nominal_absorbed']:.2%} "
          f"({corpus_absorbed}/{len(flights)} logs)\n")
    print(f"{'channels':>8s} {'logs':>5s} {'classes':>8s} {'kappa':>7s}  "
          f"absorbed_into_nominal")
    for row in per_config:
        print(f"{row['n_channels']:>8d} {row['n_logs']:>5d} "
              f"{row['n_observable_classes']:>8d} {row['kappa']:>7.3f}  "
              f"{row['nominal_absorbs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
