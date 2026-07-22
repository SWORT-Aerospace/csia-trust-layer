"""Validation campaigns: single-configuration truth measurement.

Review finding C1: detection numbers were measured with field_mode OFF while
false-alarm numbers were measured with field_mode ON — two different systems.
This module measures BOTH metrics from ONE frozen configuration and never
reports numbers the run didn't produce.

  bench():      every catalog fault scenario through the ONLINE layer,
                field_mode off vs on, side by side — exposes exactly what
                the real-world tolerance package costs in detection power.
  monte_carlo(): N randomized runs (noise seeds x fault class x amplitude
                 x onset; ~half clean) -> TPR per class with Wilson 95% CIs,
                 false alarms/hr with Poisson CI, latency percentiles.
                 Results serialize to JSON for the evidence trail.
"""

import json
import math
import time

import numpy as np

from .runtime import (FailsafePolicy, OnlineTrustLayer, SimulatedFlightSource,
                      TrustLayerRuntime)
from .sensors import Fault, generate_flight

# Fault templates: class -> (target, param builder given amplitude scale k)
FAULTS = {
    "gps_spoof": ("gps", lambda k, t0: Fault(
        "gps_spoof", "gps", t0, 15.0, {"drift": (3.0 * k, 1.0 * k, 0.0)})),
    "imu_bias": ("imu0", lambda k, t0: Fault(
        "bias_drift", "imu0", t0, 20.0,
        {"axis": 2, "rate": 0.05 * k, "channel": "accel"})),
    "mag_emi": ("mag", lambda k, t0: Fault(
        "emi_spike", "mag", t0, 8.0, {"amplitude": 10.0 * k, "rate_hz": 12.0})),
    "power_sag": ("battery", lambda k, t0: Fault(
        "power_sag", "battery", t0, 6.0, {"depth_v": 1.2 * k})),
    "vibration": ("vibration", lambda k, t0: Fault(
        "vibration_anomaly", "vibration", t0, 12.0, {"gain": 1.0 + 2.0 * k})),
}


def _run_one(truth, faults, field_mode):
    src = SimulatedFlightSource("clean", truth=truth)
    src.streams = __import__("csia.scenarios", fromlist=["sample_streams"]) \
        .sample_streams(truth, faults)
    layer = OnlineTrustLayer(field_mode=field_mode)
    rt = TrustLayerRuntime(src, layer=layer, policy=FailsafePolicy(),
                           keep_states=True)
    return rt.run()


def _detection(summary, target, onset):
    """(detected_by_trust<0.85, latency_s, min_trust, alarmed)"""
    lat = None
    tmin = 1.0
    for st in summary.states:
        v = st.trust[target]
        if st.t > 10.0:
            tmin = min(tmin, v)
        if lat is None and st.t > onset and v < 0.85:
            lat = st.t - onset
    alarmed = any(tr.level.name != "NORMAL" for tr in summary.transitions)
    return lat is not None, lat, tmin, alarmed


def bench(out_path=None):
    """C1 truth table: detection under both configurations."""
    truth = generate_flight()
    rows = []
    print(f"{'fault':10s} {'config':6s} {'det':>4s} {'lat[s]':>7s} "
          f"{'minT':>5s} {'alarm':>5s}")
    for name, (target, mk) in FAULTS.items():
        for fm in (False, True):
            s = _run_one(truth, [mk(1.0, 20.0)], fm)
            det, lat, tmin, alarmed = _detection(s, target, 20.0)
            rows.append({"fault": name, "field_mode": fm, "detected": det,
                         "latency_s": lat, "min_trust": round(tmin, 3),
                         "alarmed": alarmed})
            print(f"{name:10s} {'field' if fm else 'sim':6s} "
                  f"{'YES' if det else 'NO':>4s} "
                  f"{lat if lat is not None else float('nan'):7.1f} "
                  f"{tmin:5.2f} {'YES' if alarmed else 'no':>5s}")
    # clean-run false alarms under both configs
    for fm in (False, True):
        s = _run_one(truth, [], fm)
        alarms = sum(1 for tr in s.transitions if tr.level.name != "NORMAL")
        rows.append({"fault": "clean", "field_mode": fm, "alarms": alarms})
        print(f"{'clean':10s} {'field' if fm else 'sim':6s} "
              f"false alarms: {alarms}")
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(rows, fh, indent=1)
        print(f"-> {out_path}")
    return rows


def _wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def monte_carlo(runs=150, field_mode=True, seed=0, out_path=None):
    """Randomized campaign. Reports ONLY what the runs produced."""
    rng = np.random.default_rng(seed)
    classes = list(FAULTS)
    per_class = {c: {"n": 0, "det": 0, "lats": []} for c in classes}
    clean = {"n": 0, "alarms": 0, "hours": 0.0}
    t0 = time.time()
    for i in range(runs):
        truth = generate_flight(seed=int(rng.integers(1, 2**31)))
        if rng.random() < 0.4:   # clean run for false-alarm statistics
            s = _run_one(truth, [], field_mode)
            clean["n"] += 1
            clean["hours"] += 60.0 / 3600.0
            clean["alarms"] += sum(1 for tr in s.transitions
                                   if tr.level.name != "NORMAL")
            continue
        cls = classes[int(rng.integers(len(classes)))]
        target, mk = FAULTS[cls]
        k = float(rng.uniform(0.5, 2.0))       # amplitude scale
        onset = float(rng.uniform(15.0, 35.0))
        s = _run_one(truth, [mk(k, onset)], field_mode)
        det, lat, _, _ = _detection(s, target, onset)
        st = per_class[cls]
        st["n"] += 1
        st["det"] += int(det)
        if lat is not None:
            st["lats"].append(lat)
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{runs} runs, {time.time() - t0:.0f}s elapsed")

    report = {"runs": runs, "field_mode": field_mode, "seed": seed,
              "classes": {}, "clean": {}}
    print(f"\n=== MONTE CARLO ({runs} runs, field_mode={field_mode}) ===")
    print(f"{'class':10s} {'n':>4s} {'TPR':>6s} {'95% CI':>14s} "
          f"{'lat p50':>8s} {'lat p95':>8s}")
    for c, st in per_class.items():
        if st["n"] == 0:
            continue
        lo, hi = _wilson(st["det"], st["n"])
        lats = sorted(st["lats"])
        p50 = lats[len(lats) // 2] if lats else float("nan")
        p95 = lats[int(0.95 * (len(lats) - 1))] if lats else float("nan")
        report["classes"][c] = {
            "n": st["n"], "detected": st["det"],
            "tpr": round(st["det"] / st["n"], 3),
            "ci95": [round(lo, 3), round(hi, 3)],
            "latency_p50_s": round(p50, 2) if lats else None,
            "latency_p95_s": round(p95, 2) if lats else None}
        print(f"{c:10s} {st['n']:4d} {st['det'] / st['n']:6.2f} "
              f"[{lo:.2f}, {hi:.2f}]  {p50:8.1f} {p95:8.1f}")
    if clean["n"]:
        rate = clean["alarms"] / max(clean["hours"], 1e-9)
        # Poisson exact-ish CI via chi2 bounds
        from scipy.stats import chi2
        k = clean["alarms"]
        lo = chi2.ppf(0.025, 2 * k) / 2 / clean["hours"] if k else 0.0
        hi = chi2.ppf(0.975, 2 * k + 2) / 2 / clean["hours"]
        report["clean"] = {"flights": clean["n"],
                           "hours": round(clean["hours"], 2),
                           "alarms": clean["alarms"],
                           "rate_per_hr": round(rate, 2),
                           "ci95_per_hr": [round(lo, 2), round(hi, 2)]}
        print(f"clean: {clean['n']} flights / {clean['hours']:.1f} h, "
              f"{clean['alarms']} alarms -> {rate:.1f}/hr "
              f"[{lo:.1f}, {hi:.1f}] 95% CI")
    if out_path:
        with open(out_path, "w") as fh:
            json.dump(report, fh, indent=1)
        print(f"-> {out_path}")
    return report
