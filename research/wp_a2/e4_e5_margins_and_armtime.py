"""WP-A2 E4/E5 — how much degradation passes silently, and who owns the
arm-time exposure loss.

E4 — regression-bound headroom.
    ``tests/scenarios/test_fault_scenarios.py`` sets its assertion bounds
    below values measured from the same seeds. That is correct regression-test
    design and it means the tests cannot fail for insufficient detection
    capability, only for regression. The question a reviewer will ask is how
    much degradation would pass. This measures the margin per scenario.

E5 — arm-time exposure.
    The corrected alert-rate denominator excludes the 20 s arm window, losing
    21.8% of quoted exposure. If that loss is concentrated in a few flights,
    a handful of logs dominate the corrected rate. This reports the per-flight
    distribution.

Run:  PYTHONPATH=. python research/wp_a2/e4_e5_margins_and_armtime.py
Out:  reports/wp_a2/e4_regression_headroom.json
      reports/wp_a2/e5_armtime_exposure.json
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from csia.diagnosis import CausalDiagnosis                      # noqa: E402
from csia.scenarios import run_scenario                         # noqa: E402
from csia.trust_engine import TrustEngine                       # noqa: E402
from csia.trust_graph import build_trust_graph                  # noqa: E402
from tests.scenarios.test_fault_scenarios import CASES          # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CORPUS = os.path.join(ROOT, "data", "real_logs_report.json")
OUT4 = os.path.join(ROOT, "reports", "wp_a2", "e4_regression_headroom.json")
OUT5 = os.path.join(ROOT, "reports", "wp_a2", "e5_armtime_exposure.json")

DETECT_LINE = 0.85   # test_fault_scenarios.py:60 — fixed, not drop_below
ARM_TIME_S = 20.0          # offline posture; csia/metrics/exposure.py
ONSET = {"gps_spoof": 20.0, "imu0_bias_drift": 20.0, "mag_emi": 25.0,
         "power_sag": 30.0, "vibration_anomaly": 28.0}


def _margin(measured, bound, direction):
    """Signed headroom. `direction` says which way the assertion points."""
    if measured is None:
        return None
    return round(bound - measured if direction == "below"
                 else measured - bound, 6)


def e4():
    rows = {}
    for name, exp in CASES.items():
        _, _, td, hist, diag = run_scenario(name)
        t = np.asarray(td.t)
        onset = ONSET[name]
        target = exp["target"]

        # Mirror the assertions in tests/scenarios/test_fault_scenarios.py
        # exactly: min over the WHOLE run, crossing against the fixed 0.85
        # detection line (not drop_below), exonerated floor from tick 250.
        trust = hist.trust[:, hist.col(target)]
        min_trust = float(trust.min())

        crossed = np.where((t > onset) & (trust < DETECT_LINE))[0]
        latency = float(t[crossed[0]] - onset) if crossed.size else None

        cause = exp["cause"]
        post = diag.posterior[:, diag.causes.index(cause)]
        peak = float(post.max())

        others = [n for n in hist.names if n not in exp["exempt"]]
        others_min = float(min(hist.trust[250:, hist.col(n)].min()
                               for n in others))

        rows[name] = {
            "target": target,
            "cause": cause,
            "min_trust": {
                "measured": round(min_trust, 4),
                "asserted_below": exp["drop_below"],
                "headroom": _margin(min_trust, exp["drop_below"], "below"),
                "reading": "min trust may rise this far before the test fails",
            },
            "detect_latency_s": {
                "measured": None if latency is None else round(latency, 3),
                "asserted_within": exp["detect_within"],
                "headroom": _margin(latency, exp["detect_within"], "below"),
                "reading": "detection may slow this much before the test fails",
            },
            "peak_posterior": {
                "measured": round(peak, 4),
                "asserted_at_least": exp["p_cause"],
                "headroom": round(peak - exp["p_cause"], 4),
                "reading": "confidence may fall this far before the test fails",
            },
            "exonerated_floor": {
                "measured_min": round(others_min, 4),
                "asserted_at_least": exp["others_floor"],
                "headroom": round(others_min - exp["others_floor"], 4),
            },
        }

    report = {
        "purpose": "how much detection degradation passes the scripted fault "
                   "harness silently",
        "method": "run each scenario unchanged; compare the measured value "
                  "against the bound the test asserts",
        "caveat": "assertion bounds were set below values measured from these "
                  "same seeds (test_fault_scenarios.py:22-27), so passing "
                  "indicates no regression, not detection capability",
        "scenarios": rows,
    }
    os.makedirs(os.path.dirname(OUT4), exist_ok=True)
    with open(OUT4, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    return report


def e5():
    with open(CORPUS) as fh:
        flights = json.load(fh)["flights"]

    per = []
    for f in flights:
        dur = f["duration_s"]
        unmon = min(ARM_TIME_S, dur)
        per.append({
            "log": f["log"],
            "duration_s": dur,
            "unmonitored_s": round(unmon, 3),
            "monitored_s": round(dur - unmon, 3),
            "fraction_unmonitored": round(unmon / dur, 4),
            "n_transitions": len(f["transitions"]),
        })
    per.sort(key=lambda r: -r["fraction_unmonitored"])

    raw = sum(r["duration_s"] for r in per)
    mon = sum(r["monitored_s"] for r in per)
    fracs = np.array([r["fraction_unmonitored"] for r in per])

    # concentration: how much of the total lost time the worst flights own
    lost = np.array(sorted((r["unmonitored_s"] for r in per), reverse=True))
    share = lost.cumsum() / lost.sum()

    # 2 alert episodes = 2 CAUTION escalations; the third transition is a
    # NORMAL recovery edge (audit F-01).
    episodes = 2
    report = {
        "purpose": "distribution of the arm-time exposure exclusion across "
                   "the corpus",
        "arm_time_s": ARM_TIME_S,
        "n_logs": len(per),
        "raw_hours": round(raw / 3600, 4),
        "monitored_hours": round(mon / 3600, 4),
        "unmonitored_hours": round((raw - mon) / 3600, 4),
        "fraction_of_raw_unmonitored": round((raw - mon) / raw, 4),
        "per_flight_fraction_unmonitored": {
            "min": round(float(fracs.min()), 4),
            "median": round(float(np.median(fracs)), 4),
            "mean": round(float(fracs.mean()), 4),
            "max": round(float(fracs.max()), 4),
        },
        "concentration": {
            "top_5_flights_share_of_lost_time": round(float(share[4]), 4),
            "top_10_flights_share_of_lost_time": round(float(share[9]), 4),
            "reading": "every flight longer than the arm window loses exactly "
                       "20 s, so the loss is spread by construction and is "
                       "proportionally largest on the shortest flights",
        },
        "alert_episodes": episodes,
        "rate_raw_per_hour": round(episodes / (raw / 3600), 4),
        "rate_monitored_per_hour": round(episodes / (mon / 3600), 4),
        "flights": per,
    }
    with open(OUT5, "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    return report


def main() -> int:
    r4 = e4()
    print("=== E4 regression-bound headroom ===")
    print(f"{'scenario':20s} {'min_trust':>22s} {'latency(s)':>22s} "
          f"{'posterior':>22s}")
    for name, row in r4["scenarios"].items():
        mt, lt, pp = (row["min_trust"], row["detect_latency_s"],
                      row["peak_posterior"])
        print(f"{name:20s} "
              f"{mt['measured']:>8.4f} vs {mt['asserted_below']:<5} "
              f"(+{mt['headroom']:.3f}) "
              f"{str(lt['measured']):>6s} vs {lt['asserted_within']:<5} "
              f"(+{lt['headroom']:.2f}) "
              f"{pp['measured']:>7.4f} vs {pp['asserted_at_least']:<5} "
              f"(+{pp['headroom']:.3f})")

    r5 = e5()
    print("\n=== E5 arm-time exposure ===")
    print(f"raw {r5['raw_hours']} h -> monitored {r5['monitored_hours']} h "
          f"({r5['fraction_of_raw_unmonitored']:.1%} excluded)")
    pf = r5["per_flight_fraction_unmonitored"]
    print(f"per-flight unmonitored fraction: min {pf['min']:.1%}, "
          f"median {pf['median']:.1%}, max {pf['max']:.1%}")
    print(f"top-5 flights own {r5['concentration']['top_5_flights_share_of_lost_time']:.1%} "
          f"of the lost time")
    print(f"rate: {r5['rate_raw_per_hour']} /raw h -> "
          f"{r5['rate_monitored_per_hour']} /monitored h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
