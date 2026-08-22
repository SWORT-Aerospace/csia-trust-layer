"""WP-C2 Part 2 — the free repair, executed as a measured experiment.

Adding `attitude_gravity_mag` to `imu0_bias_drift`'s LOW signature separates
the IMU pair under every configuration. It is ungated, spans imu0 and mag, and
is physically justified: an imu0 bias corrupts the mag-heading-versus-imu0-yaw
comparison while an imu1 bias does not.

RESEARCH FLAG, DEFAULT OFF. Production behaviour is unchanged unless
CSIA_WP_C2_IMU_REPAIR=1 is set. The repair is applied by post-hoc mutation of
a CausalDiagnosis instance's cause table — no production file is edited, and
`tests/test_wp_c2_repair_flag.py` asserts the default path is untouched.

Measures, before and after:
  * all five scripted scenarios: detection latency, min trust, correct-cause
    posterior, and false positives on the clean scenario
  * the FULL certificate diff over all 1232 reachable configurations, not just
    the target pair
  * the effect on CWE(gate closure) and on IRE

Run:  PYTHONPATH=. python research/wp_c2/repair_experiment.py
Out:  research/wp_c2/results/repair_experiment.json
"""

import copy
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis import CausalDiagnosis                      # noqa: E402
from csia.scenarios import run_scenario                         # noqa: E402
from research.wp_c1.certificate import d_critical               # noqa: E402
from research.wp_c1.lattice import (                            # noqa: E402
    CHANNELS, enumerate_reach, load_signatures)
from research.wp_c2.criticality import (                        # noqa: E402
    cwe, exposed_over, gate_only_configs)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
FULL = frozenset(CHANNELS)

FLAG = "CSIA_WP_C2_IMU_REPAIR"
REPAIR_FEATURE = "attitude_gravity_mag"
REPAIR_TARGET = "imu0_bias_drift"

CASES = {
    "gps_spoof": ("gps", "gps_fault", 20.0),
    "imu0_bias_drift": ("imu0", "imu0_bias_drift", 20.0),
    "mag_emi": ("mag", "mag_interference", 25.0),
    "power_sag": ("battery", "power_fault", 30.0),
    "vibration_anomaly": ("vibration", "vibration_anomaly", 28.0),
}
DETECT_LINE = 0.85


def repair_enabled() -> bool:
    """Default OFF. Only an explicit opt-in turns the experiment on."""
    return os.environ.get(FLAG, "0") == "1"


def repaired_causes(base_causes):
    """CAUSES with REPAIR_FEATURE added to REPAIR_TARGET's LOW set."""
    out = copy.deepcopy(base_causes)
    low = list(out[REPAIR_TARGET])
    if REPAIR_FEATURE not in low:
        low.append(REPAIR_FEATURE)
    out[REPAIR_TARGET] = sorted(low)
    return out


def make_diagnosis(repair: bool):
    """A CausalDiagnosis with or without the repair. No production edit."""
    base = CausalDiagnosis()
    if repair:
        return CausalDiagnosis(causes=repaired_causes(base.causes))
    return base


def scenario_metrics(repair: bool):
    rows = {}
    for name, (node, cause, onset) in CASES.items():
        _, _, td, hist, _ = run_scenario(name)
        diag = make_diagnosis(repair).run(td)
        t = np.asarray(td.t)
        trust = hist.trust[:, hist.col(node)]
        crossed = np.where((t > onset) & (trust < DETECT_LINE))[0]
        post = diag.posterior[:, diag.causes.index(cause)] \
            if cause in diag.causes else None
        k_peak = int(np.argmax(post)) if post is not None else None
        top = diag.top(k_peak)[0][0] if k_peak is not None else None
        rows[name] = {
            "detect_latency_s": (round(float(t[crossed[0]] - onset), 3)
                                 if crossed.size else None),
            "min_trust": round(float(trust.min()), 4),
            "peak_posterior_correct_cause": (round(float(post.max()), 4)
                                             if post is not None else None),
            "top_cause_at_peak": top,
            "top_cause_correct": top == cause,
        }

    # clean-scenario false positives: any non-nominal cause taking the lead
    _, _, td_c, _, _ = run_scenario("clean")
    dc = make_diagnosis(repair).run(td_c)
    lead = [dc.causes[int(i)] for i in np.argmax(dc.posterior, axis=1)]
    settled = np.asarray(td_c.t) > 20.0
    fp = sorted({c for c, s in zip(lead, settled) if s and c != "nominal"})
    rows["_clean_false_positives"] = {
        "non_nominal_leading_causes_after_20s": fp,
        "n_ticks_non_nominal": int(sum(
            1 for c, s in zip(lead, settled) if s and c != "nominal")),
        "n_settled_ticks": int(settled.sum()),
    }
    return rows


def certificate_state(low):
    """Full exposure state over the reachable lattice."""
    reach = enumerate_reach(low)
    exposed = set()
    for row in reach.values():
        exposed |= row["merged_pairs"]
    kmax_by_k = {}
    for k in range(len(CHANNELS) + 1):
        sub = [r for r in reach.values() if r["n_channels"] >= k]
        if sub:
            kmax_by_k[k] = max(r["kappa"] for r in sub)
    return reach, exposed, kmax_by_k


def main() -> int:
    low_before = load_signatures()
    low_after = {k: list(v) for k, v in low_before.items()}
    low_after[REPAIR_TARGET] = sorted(
        set(low_after[REPAIR_TARGET]) | {REPAIR_FEATURE})

    hyps = sorted(low_before)
    all_pairs = set(itertools.combinations(hyps, 2))
    crit, _ = d_critical(hyps)

    reach_b, exp_b, kmax_b = certificate_state(low_before)
    reach_a, exp_a, kmax_a = certificate_state(low_after)

    fixed = sorted("+".join(p) for p in sorted(exp_b - exp_a))
    broken = sorted("+".join(p) for p in sorted(exp_a - exp_b))

    # Exposure unioned over the WHOLE lattice includes the degenerate
    # zero-channel configuration, where every pair merges regardless. That
    # makes the whole-lattice diff read as "no change" even when the repair
    # works. The diff must be reported per admissibility level.
    per_k = {}
    for k in range(len(CHANNELS) + 1):
        eb = set(); ea = set()
        for r in reach_b.values():
            if r["n_channels"] >= k:
                eb |= r["merged_pairs"]
        for r in reach_a.values():
            if r["n_channels"] >= k:
                ea |= r["merged_pairs"]
        per_k[k] = {
            "exposed_before": len(eb),
            "exposed_after": len(ea),
            "critical_exposed_before": len(crit & eb),
            "critical_exposed_after": len(crit & ea),
            "fixed": sorted("+".join(p) for p in sorted(eb - ea)),
            "newly_broken": sorted("+".join(p) for p in sorted(ea - eb)),
        }

    cwe_gate_b = cwe(low_before, crit, gate_only_configs(FULL))
    cwe_gate_a = cwe(low_after, crit, gate_only_configs(FULL))
    ire_b = sorted(crit & exposed_over(low_before, gate_only_configs(FULL)))
    ire_a = sorted(crit & exposed_over(low_after, gate_only_configs(FULL)))

    scen_b = scenario_metrics(repair=False)
    scen_a = scenario_metrics(repair=True)

    deltas = {}
    for name in CASES:
        b, a = scen_b[name], scen_a[name]
        deltas[name] = {
            "d_detect_latency_s": (None if b["detect_latency_s"] is None
                                   or a["detect_latency_s"] is None
                                   else round(a["detect_latency_s"]
                                              - b["detect_latency_s"], 4)),
            "d_min_trust": round(a["min_trust"] - b["min_trust"], 6),
            "d_peak_posterior": round(a["peak_posterior_correct_cause"]
                                      - b["peak_posterior_correct_cause"], 6),
            "top_cause_still_correct": a["top_cause_correct"],
            "top_cause_changed": a["top_cause_at_peak"]
            != b["top_cause_at_peak"],
        }

    report = {
        "purpose": "execute the free repair behind a research flag and measure "
                   "it, including the FULL certificate diff",
        "flag": FLAG,
        "default": "OFF — production behaviour unchanged; asserted by "
                   "tests/test_wp_c2_repair_flag.py",
        "repair": {
            "feature": REPAIR_FEATURE,
            "into_hypothesis": REPAIR_TARGET,
            "gated_by": [],
            "channels_spanned": ["imu0", "mag"],
            "new_hardware": False,
            "physical_justification":
                "attitude_gravity_mag compares mag heading against "
                "imu0-integrated yaw. An imu0 bias corrupts that comparison; "
                "an imu1 bias does not. The asymmetry is what breaks the tie.",
        },
        "certificate_diff": {
            "n_reachable_configurations": len(reach_b),
            "n_exposed_pairs_before": len(exp_b),
            "n_exposed_pairs_after": len(exp_a),
            "pairs_fixed": fixed,
            "pairs_newly_broken": broken,
            "no_new_collisions": not broken,
            "guaranteed_before": len(all_pairs - exp_b),
            "guaranteed_after": len(all_pairs - exp_a),
            "kappa_max_by_min_channels_before": kmax_b,
            "kappa_max_by_min_channels_after": kmax_a,
            "diff_by_min_channels": per_k,
            "whole_lattice_diff_is_degenerate":
                "the union over ALL configurations includes the zero-channel "
                "case, where every pair merges; use diff_by_min_channels",
        },
        "criticality_effect": {
            "cwe_gate_before": cwe_gate_b["cwe"],
            "cwe_gate_after": cwe_gate_a["cwe"],
            "ire_before": round(len(ire_b) / len(crit), 4),
            "ire_after": round(len(ire_a) / len(crit), 4),
            "irreducible_pairs_before": sorted("+".join(p) for p in ire_b),
            "irreducible_pairs_after": sorted("+".join(p) for p in ire_a),
        },
        "scenarios_before": scen_b,
        "scenarios_after": scen_a,
        "scenario_deltas": deltas,
    }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "repair_experiment.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)

    cd = report["certificate_diff"]
    print(f"certificate over {cd['n_reachable_configurations']} reachable "
          f"configurations")
    print(f"  exposed pairs : {cd['n_exposed_pairs_before']} -> "
          f"{cd['n_exposed_pairs_after']}")
    print(f"  fixed         : {cd['pairs_fixed']}")
    print(f"  newly broken  : {cd['pairs_newly_broken'] or 'NONE'}")
    print(f"  kappa_max@8   : {kmax_b[8]} -> {kmax_a[8]}")
    print(f"  (whole-lattice union is degenerate — per-admissibility diff:)")
    for k in (8, 7, 6, 5):
        d = per_k[k]
        print(f"    k>={k}: exposed {d['exposed_before']}->"
              f"{d['exposed_after']}, critical "
              f"{d['critical_exposed_before']}->"
              f"{d['critical_exposed_after']}, fixed {d['fixed']}, "
              f"broken {d['newly_broken'] or 'none'}")
    ce = report["criticality_effect"]
    print(f"  CWE(gate)     : {ce['cwe_gate_before']} -> "
          f"{ce['cwe_gate_after']}")
    print(f"  IRE           : {ce['ire_before']} -> {ce['ire_after']}  "
          f"{ce['irreducible_pairs_after']}")
    print(f"\n{'scenario':<20s} {'d_latency':>10s} {'d_min_trust':>12s} "
          f"{'d_posterior':>12s}  top cause OK")
    for name, d in deltas.items():
        print(f"{name:<20s} {str(d['d_detect_latency_s']):>10s} "
              f"{d['d_min_trust']:>12.6f} {d['d_peak_posterior']:>12.6f}  "
              f"{d['top_cause_still_correct']}")
    fpb = scen_b["_clean_false_positives"]
    fpa = scen_a["_clean_false_positives"]
    print(f"\nclean false positives: before "
          f"{fpb['n_ticks_non_nominal']}/{fpb['n_settled_ticks']} ticks "
          f"{fpb['non_nominal_leading_causes_after_20s']}; after "
          f"{fpa['n_ticks_non_nominal']}/{fpa['n_settled_ticks']} ticks "
          f"{fpa['non_nominal_leading_causes_after_20s']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
