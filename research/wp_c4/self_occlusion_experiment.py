"""WP-C4 Part 2.3 — turn SOI(gps_fault) = 1.0 into an observed behaviour.

SOI = 1.0 is a property of a matrix: every feature that would reveal a GPS
fault is a feature a GPS fault silences. This runs the DEPLOYED pipeline on
GPS faults and measures what it actually reports.

Three arms, same truth and seed, differing only in whether the fault destroys
the GPS fix:

  A  spoof_only    position walks off, fix stays VALID -> gvalid open
                   (the control: evidence survives)
  B  denial_only   fix invalid -> gvalid closed
                   (the self-occlusion case)
  C  spoof_then_denial   spoof detected, then denial
                   (the realistic attack: measure how long the correct
                    diagnosis survives before the evidence is destroyed)

The failsafe is the shipping `FailsafePolicy`, driven exactly as
`csia/dashboard/export.py` drives it — no new logic.

Run:  PYTHONPATH=. python research/wp_c4/self_occlusion_experiment.py
Out:  research/wp_c4/results/self_occlusion.json
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Reuse the SHIPPING adapter rather than reimplementing it — it supplies
# top_causes(), which the policy calls and a naive dataclass omits.
from csia.dashboard.export import _BatchState                   # noqa: E402
from csia.runtime.failsafe import FailsafePolicy                # noqa: E402
from csia.scenarios import run_pipeline                         # noqa: E402
from csia.sensors.faults import Fault                           # noqa: E402
from csia.sensors.truth import generate_flight                  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
ONSET = 20.0
ACTIONABLE_TRUST = 0.85


ARMS = {
    "A_spoof_only": [
        Fault("gps_spoof", "gps", ONSET, 25.0, {"drift": (3.0, 1.0, 0.0)})],
    "B_denial_only": [
        Fault("dropout", "gps", ONSET, 25.0)],
    "C_spoof_then_denial": [
        Fault("gps_spoof", "gps", ONSET, 25.0, {"drift": (3.0, 1.0, 0.0)}),
        Fault("dropout", "gps", ONSET + 5.0, 20.0)],
}


def run_arm(faults):
    truth = generate_flight(profile="hover_circle")
    td, hist, diag = run_pipeline(truth=truth, faults=faults)
    t = np.asarray(td.t)
    causes = diag.causes
    lead = [causes[int(i)] for i in np.argmax(diag.posterior, axis=1)]

    # gvalid trajectory, read off a gvalid-gated edge's gate array.
    gate = np.asarray(td.edges["altitude_baro"][3], dtype=float)

    policy = FailsafePolicy()
    levels, events = [], []
    for k in range(len(t)):
        st = _BatchState(
            float(t[k]),
            {n: float(hist.trust[k, hist.col(n)]) for n in hist.names},
            {n: bool(td.fresh[n][k]) for n in hist.names},
            {causes[i]: float(diag.posterior[k][i])
             for i in range(len(causes))})
        acts = policy.update(st)
        levels.append(int(policy.level))
        for a in acts:
            events.append({"t": round(float(t[k]), 2), "action": a.name,
                           "params": a.params})

    after = t >= ONSET
    n_after = int(after.sum())
    gps_trust = hist.trust[:, hist.col("gps")]
    occupancy = {}
    for c in set(lead):
        occupancy[c] = round(sum(1 for i, s in enumerate(after)
                                 if s and lead[i] == c) / n_after, 4)

    first_correct = next((float(t[i]) - ONSET for i in range(len(t))
                          if after[i] and lead[i] == "gps_fault"), None)
    nominal_ticks = [i for i in range(len(t)) if after[i]
                     and lead[i] == "nominal"]
    # confident-wrong: nominal on top AND gps trust still above actionable
    confident_wrong = [i for i in nominal_ticks
                       if gps_trust[i] >= ACTIONABLE_TRUST]
    dt = float(t[1] - t[0])

    return {
        "n_ticks_after_onset": n_after,
        "gvalid_min_after_onset": round(float(gate[after].min()), 4),
        "gvalid_frac_closed_after_onset": round(
            float((gate[after] <= 1e-9).mean()), 4),
        "top_cause_occupancy_after_onset": dict(
            sorted(occupancy.items(), key=lambda kv: -kv[1])),
        "time_to_first_gps_fault_lead_s": (
            None if first_correct is None else round(first_correct, 2)),
        "seconds_nominal_on_top_while_faulted": round(
            len(nominal_ticks) * dt, 2),
        "seconds_confident_wrong_nominal_above_actionable_trust": round(
            len(confident_wrong) * dt, 2),
        "gps_trust_min_after_onset": round(float(gps_trust[after].min()), 4),
        "max_failsafe_level": max(levels),
        "failsafe_actions": events[:12],
        "n_failsafe_actions": len(events),
    }


def main() -> int:
    out = {arm: run_arm(f) for arm, f in ARMS.items()}
    report = {
        "purpose": "convert SOI(gps_fault)=1.0 from a matrix property into an "
                   "observed behaviour of the deployed pipeline",
        "onset_s": ONSET,
        "actionable_trust_threshold": ACTIONABLE_TRUST,
        "failsafe": "shipping FailsafePolicy, driven as dashboard/export.py "
                    "drives it",
        "arms": {
            "A_spoof_only": "fix stays VALID — control, evidence survives",
            "B_denial_only": "fix INVALID — the self-occlusion case",
            "C_spoof_then_denial": "spoof for 5 s, then denial",
        },
        "results": out,
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "self_occlusion.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    for arm, r in out.items():
        print(f"--- {arm} ---")
        print(f"  gvalid closed for {r['gvalid_frac_closed_after_onset']:.0%} "
              f"of post-onset ticks (min {r['gvalid_min_after_onset']})")
        print(f"  top-cause occupancy: {r['top_cause_occupancy_after_onset']}")
        print(f"  time to first gps_fault lead: "
              f"{r['time_to_first_gps_fault_lead_s']}")
        print(f"  nominal on top while faulted: "
              f"{r['seconds_nominal_on_top_while_faulted']} s "
              f"(confident-wrong: "
              f"{r['seconds_confident_wrong_nominal_above_actionable_trust']} s)")
        print(f"  gps trust min: {r['gps_trust_min_after_onset']}   "
              f"max failsafe level: {r['max_failsafe_level']}   "
              f"actions: {r['n_failsafe_actions']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
