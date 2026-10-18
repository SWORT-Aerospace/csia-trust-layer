#!/usr/bin/env python3
"""Drive the shipped FailsafePolicy over the exact Mechanism-B bench arms.

Measures, per arm, (a) the first crossing of the raw gps trust series below
FailsafeConfig.nav_caution after onset -- the quantity mechanism_b.json records
as `trust_latency_s` -- and (b) the first FailsafePolicy escalation after onset.
If the dwell sits AFTER the crossing, (b) - (a) equals dwell_up.

It runs against a temporary `git archive` of HEAD, never the working tree, and
imports the committed generator module `research/systems-paper/mechanism_b.py`
unmodified for ARMS, ONSET_S, DURATION_S and `_first_crossing`. The policy is
stepped per tick exactly as `csia/dashboard/export.py` and
`research/wp_c4/self_occlusion_experiment.py` step it. Nothing is regenerated:
the output is a NEW, separately named verification record.

    python research/physical_validation/corrections/FL-053_SC09/verification/measure_policy_alerts.py [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
DEFAULT_OUT = os.path.join(HERE, "policy_alerts.json")


def measure(archive: str) -> dict:
    sys.path[:0] = [archive, os.path.join(archive, "research", "systems-paper")]
    cwd = os.getcwd()
    os.chdir(archive)
    try:
        import numpy as np
        import mechanism_b as MB
        from csia.dashboard.export import _BatchState
        from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy
        from csia.scenarios import Fault, run_pipeline
        from csia.sensors.truth import generate_flight
    finally:
        os.chdir(cwd)

    cfg = FailsafeConfig()
    out = {"nav_caution": cfg.nav_caution, "dwell_up_s": cfg.dwell_up,
           "arm_time_s": cfg.arm_time, "arms": {}}
    for name, drift in MB.ARMS.items():
        faults = ([] if drift is None else
                  [Fault("gps_spoof", "gps", MB.ONSET_S, MB.DURATION_S,
                         {"drift": (float(drift), 1.0, 0.0)})])
        td, hist, diag = run_pipeline(truth=generate_flight(profile="hover_circle"), faults=faults)
        t = np.asarray(td.t, dtype=float)
        trust = np.asarray(hist.trust[:, hist.col("gps")], dtype=float)
        t_cross, k_cross = MB._first_crossing(t, trust, cfg.nav_caution, above=False, after=MB.ONSET_S)
        pol, causes, first = FailsafePolicy(), diag.causes, None
        for k in range(len(t)):
            st = _BatchState(float(t[k]), {n: float(hist.trust[k, hist.col(n)]) for n in hist.names},
                             {n: bool(td.fresh[n][k]) for n in hist.names},
                             {causes[i]: float(diag.posterior[k][i]) for i in range(len(causes))})
            before = int(pol.level)
            pol.update(st)
            if first is None and t[k] >= MB.ONSET_S and int(pol.level) > before:
                tr = pol.transitions[-1]
                first = {"t_s": round(float(t[k]), 4), "tick": k, "level": tr.level.name,
                         "reasons": list(tr.reasons)}
        pre = [{"t_s": round(tr.t, 2), "level": tr.level.name} for tr in pol.transitions
               if cfg.arm_time <= tr.t < MB.ONSET_S]
        out["arms"][name] = {
            "drift_m_per_s": drift, "tick_s": round(float(t[1] - t[0]), 4),
            "trust_crossing_after_onset_s": None if t_cross is None else round(t_cross - MB.ONSET_S, 4),
            "trust_crossing_tick": k_cross,
            "first_policy_escalation_after_onset": first,
            "policy_alert_after_onset_s": None if first is None else round(first["t_s"] - MB.ONSET_S, 4),
            "alert_minus_crossing_s": (None if first is None or t_cross is None
                                       else round(first["t_s"] - t_cross, 4)),
            "escalations_between_arm_time_and_onset": pre}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="fl053_") as tmp:
        tar = subprocess.run(["git", "archive", "HEAD", "csia", "engineering/v1_1", "research/systems-paper",
                              "research/formalization"], cwd=ROOT, capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", tmp], input=tar, check=True)
        res = measure(tmp)
    res = {"schema": "csia.research.fl053_policy_alert_measurement/1",
           "status": "VERIFICATION FOR A PROPOSED CORRECTION -- not an adopted result",
           "measured_at_commit": head,
           "method": ("FailsafePolicy stepped per tick over run_pipeline output for mechanism_b.ARMS "
                      "(hover_circle truth, gps_spoof drift, onset 20 s, 15 s), in a git archive of HEAD"),
           **res}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for name, a in res["arms"].items():
        print(f"{name:10s} crossing {a['trust_crossing_after_onset_s']}  alert {a['policy_alert_after_onset_s']}"
              f"  alert-crossing {a['alert_minus_crossing_s']}")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
