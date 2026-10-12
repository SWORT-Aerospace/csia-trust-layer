"""PRODUCTION SIDE of the independent-checker experiment (brief B3).

Exports, per scenario and per tick, exactly two things:

    which diagnostic features are ACTIVE (gate > GATE_EPS)
    the consistency value c of each feature

and nothing else. No leader, no posterior, no support label, no
identifiability verdict. The independent checker consumes this file and must
reach its own conclusions from the signature structure alone; if this exporter
handed it any part of the production analysis, agreement between the two would
be circular.

COMPRESSION IS LOSSLESS FOR THE STRUCTURAL QUESTION. Whether a hypothesis pair
is structurally distinguishable depends only on the ACTIVE SET, so ticks are
grouped by their distinct active set. Nine scenarios x 1500 ticks collapse to
a few dozen groups. The per-tick consistencies are not stored; instead each
group records whether any feature was numerically degenerate
(|log(1-c+eps) - log(c+eps)| <= TAU), which is the only way a structurally
distinguishing term can fail to distinguish numerically.

    python research/systems-paper/export_active_sets.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.diagnosis.bayes import EPS, CausalDiagnosis       # noqa: E402
from csia.scenarios import run_scenario                     # noqa: E402

#: Taken from the frozen core's own analysis convention, not introduced here.
GATE_EPS = 1e-9
TAU_NUM = 1e-12

#: The same scenario mapping Phase 2 used. A row the catalogue cannot express
#: is recorded there, not silently omitted; this file inherits that mapping so
#: the two analyses see the same flights.
SCENARIOS = {
    "CLEAN": "clean",
    "GNSS_FIX_LOSS": "gps_dropout",
    "GNSS_BIAS_RAMP": "gps_spoof",
    "IMU_BIAS": "imu0_bias_drift",
    "MAG_DEGRADED": "mag_emi",
    "POWER": "power_sag",
    "VIBRATION": "vibration_anomaly",
    "DUAL_IMU_AMBIGUITY": "dual_imu_failure",
    "HIGH_SPEED_ENVELOPE": "high_speed_dash",
}

OUT = os.path.join(_HERE, "results", "active_sets.json")


def _git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def export_one(scenario_key: str) -> dict:
    _title, _faults, td, _hist, _diag = run_scenario(scenario_key)
    feats = CausalDiagnosis()._features(td)
    names = sorted(feats)
    K = len(td.t)

    gate = np.zeros((K, len(names)))
    degenerate = np.zeros((K, len(names)), dtype=bool)
    for j, fn in enumerate(names):
        c, g = feats[fn]
        c = np.asarray(c, dtype=float) * np.ones(K)
        g = np.asarray(g, dtype=float) * np.ones(K)
        gate[:, j] = g
        # lo == hi exactly when 1 - c + EPS == c + EPS, i.e. c == 0.5. That is
        # the ONLY way an active, structurally distinguishing term contributes
        # zero difference between two hypotheses.
        lo = np.log(1.0 - c + EPS)
        hi = np.log(c + EPS)
        degenerate[:, j] = np.abs(g * (lo - hi)) <= TAU_NUM

    active = gate > GATE_EPS
    groups: dict = {}
    for k in range(K):
        key = tuple(np.nonzero(active[k])[0])
        slot = groups.setdefault(key, {"ticks": 0, "first_tick": k,
                                       "degenerate_active": set()})
        slot["ticks"] += 1
        for j in np.nonzero(active[k] & degenerate[k])[0]:
            slot["degenerate_active"].add(names[j])

    out_groups = []
    for key in sorted(groups, key=lambda kk: groups[kk]["first_tick"]):
        slot = groups[key]
        out_groups.append({
            "active": [names[j] for j in key],
            "ticks": slot["ticks"],
            "first_tick": slot["first_tick"],
            "degenerate_active": sorted(slot["degenerate_active"]),
        })

    return {"features": names, "ticks": K,
            "distinct_active_sets": len(out_groups), "groups": out_groups}


def main() -> int:
    doc = {
        "artifact": "ACTIVE_SETS",
        "purpose": "input to research/systems-paper/independent_checker.py; "
                   "carries NO production support analysis by construction",
        "generation_command":
            "python research/systems-paper/export_active_sets.py",
        "commit": _git("rev-parse", "HEAD"),
        "gate_eps": GATE_EPS, "tau_num": TAU_NUM, "eps_likelihood": EPS,
        "signature_source_for_checker":
            "research/formalization/diagnostic_signature_matrix.yaml",
        "scenarios": {},
    }
    for label, key in sorted(SCENARIOS.items()):
        doc["scenarios"][label] = {"scenario": key, **export_one(key)}
        g = doc["scenarios"][label]
        print(f"  {label:<22} {g['ticks']:>5} ticks  "
              f"{g['distinct_active_sets']:>3} distinct active sets")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\n{OUT}\n  sha256 {_sha(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
