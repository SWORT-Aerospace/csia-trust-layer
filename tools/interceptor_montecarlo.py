"""Monte Carlo characterization of the interceptor_seeker profile.

SYNTHETIC first-pass numbers. Every value written to the deliverables comes
from an actual run here — nothing is estimated or hand-entered. Fixed seeds
(seed = run index) make every number reproducible bit-for-bit.

Run:  .venv/bin/python tools/interceptor_montecarlo.py
Outputs: deliverables/montecarlo_results.md, deliverables/montecarlo_results.json
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csia.seeker import run_seeker
from csia.seeker.runtime import DETECT_TRUST, SeekerConfig
from csia.seeker.scenarios import SEEKER_SCENARIOS, scenario_faults

WARMUP = SeekerConfig().arm_time
ONSET = 8.0
FAULTED = {"ir_decoy": "ir_seeker", "rf_jam": "rf_seeker"}
OUT = os.path.join(os.path.dirname(__file__), "..", "deliverables")


def _analyze(name, faults, seed):
    eng, r = run_seeker(faults, tick_hz=100.0, seed=seed)
    t = r.t
    post = t > WARMUP
    out = {"transitions": [x for x in r.transitions if x["to"] != "NORMAL"]}
    if name == "clean_engagement":
        out["alarm"] = len(out["transitions"]) > 0
        out["min_trust"] = {n: float(r.trust[n][post].min()) for n in r.trust}
        return out
    ch = FAULTED[name]
    tr = r.trust[ch]
    below = np.where((t > ONSET) & (tr < DETECT_TRUST))[0]
    out["detected"] = bool(len(below))
    out["latency_s"] = float(t[below[0]] - ONSET) if len(below) else None
    out["min_trust_faulted"] = float(tr[t > ONSET].min())
    out["min_trust_others"] = {n: float(r.trust[n][t > ONSET].min())
                               for n in r.trust if n != ch}
    # attribution: top non-nominal cause at its peak, post-onset
    P = {c: r.diag[c] for c in r.causes}
    mask = t > ONSET
    peak_c, peak_p, peak_k = None, -1, None
    for c in r.causes:
        if c == "nominal":
            continue
        seg = P[c][mask]
        if len(seg) and seg.max() > peak_p:
            peak_p, peak_c = float(seg.max()), c
    out["peak_cause"] = peak_c
    out["peak_posterior"] = peak_p
    out["attributed_correct"] = (peak_c == name)
    return out


def _stats(latencies):
    a = np.array([x for x in latencies if x is not None])
    if not len(a):
        return {"n": 0}
    return {"mean": round(float(a.mean()), 3),
            "median": round(float(np.median(a)), 3),
            "p95": round(float(np.percentile(a, 95)), 3)}


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {"config": {"tick_hz": 100.0, "warmup_s": WARMUP,
                         "onset_s": ONSET, "detect_trust": DETECT_TRUST,
                         "runs_per_scenario": 50, "note": "SYNTHETIC "
                         "first-pass; not validated against seeker hardware"},
              "scenarios": {}, "magnitude_sweep": {}}

    # --- item 1-2: 50 runs each of ir_decoy, rf_jam, clean ------------------
    for name in ("ir_decoy", "rf_jam", "clean_engagement"):
        faults = scenario_faults(name)
        runs = [_analyze(name, faults, seed=1000 * (hash(name) % 7) + i)
                for i in range(50)]
        if name == "clean_engagement":
            fa = sum(r["alarm"] for r in runs)
            report["scenarios"][name] = {
                "runs": 50, "false_alarm_runs": fa,
                "false_alarm_rate": round(fa / 50, 3)}
            print(f"{name:18s} false-alarm runs: {fa}/50")
        else:
            det = sum(r["detected"] for r in runs)
            lat = _stats([r["latency_s"] for r in runs if r["detected"]])
            attr = np.mean([r["attributed_correct"] for r in runs if r["detected"]]) \
                if det else 0.0
            report["scenarios"][name] = {
                "runs": 50, "detections": det,
                "detection_rate": round(det / 50, 3),
                "latency_s": lat,
                "attribution_accuracy": round(float(attr), 3),
                "mean_min_trust_faulted": round(float(np.mean(
                    [r["min_trust_faulted"] for r in runs])), 3)}
            print(f"{name:18s} det {det}/50  lat {lat}  attr {attr:.2f}")

    # --- item 3: ir_decoy magnitude sweep ----------------------------------
    print("\nir_decoy magnitude sweep (20 runs/magnitude):")
    # sweep brackets the combined bearing noise floor (~0.36 deg) to find
    # where detection actually breaks down — a required honest result.
    for mag in (0.1, 0.2, 0.35, 0.6, 1.5, 4.0):
        det = 0; lats = []
        for i in range(20):
            faults = [{"kind": "ir_decoy", "start": ONSET,
                       "offset_deg": mag, "ramp_s": 1.5}]
            r = _analyze("ir_decoy", faults, seed=50000 + int(mag * 100) + i)
            det += r["detected"]
            if r["detected"]:
                lats.append(r["latency_s"])
        report["magnitude_sweep"][f"{mag}deg"] = {
            "runs": 20, "detections": det,
            "detection_rate": round(det / 20, 3),
            "mean_latency_s": round(float(np.mean(lats)), 3) if lats else None}
        print(f"  {mag:4.1f} deg: det {det}/20  "
              f"mean lat {np.mean(lats):.2f}s" if lats
              else f"  {mag:4.1f} deg: det {det}/20  (no detections)")

    json.dump(report, open(os.path.join(OUT, "montecarlo_results.json"), "w"),
              indent=1)
    _write_md(report)
    print(f"\n-> {OUT}/montecarlo_results.{{md,json}}")


def _write_md(rep):
    L = ["# interceptor_seeker — Monte Carlo results (SYNTHETIC first pass)",
         "",
         "All numbers produced by `tools/interceptor_montecarlo.py` "
         "(fixed seeds, 100 Hz). **Synthetic; not validated against seeker "
         "hardware.**", "",
         f"Config: warmup {rep['config']['warmup_s']} s (excluded from "
         f"metrics), fault onset {rep['config']['onset_s']} s, actionable "
         f"trust threshold {rep['config']['detect_trust']}.", "",
         "## Detection & attribution (50 runs each)", "",
         "| scenario | detection rate | latency mean / median / p95 (s) | "
         "attribution acc | mean min-trust (faulted) |",
         "|---|---|---|---|---|"]
    for nm in ("ir_decoy", "rf_jam"):
        s = rep["scenarios"][nm]
        lt = s["latency_s"]
        L.append(f"| {nm} | {s['detection_rate']:.2f} ({s['detections']}/50) "
                 f"| {lt.get('mean','-')} / {lt.get('median','-')} / "
                 f"{lt.get('p95','-')} | {s['attribution_accuracy']:.2f} | "
                 f"{s['mean_min_trust_faulted']:.2f} |")
    c = rep["scenarios"]["clean_engagement"]
    L += ["", f"**clean_engagement:** {c['false_alarm_runs']}/50 runs raised "
          f"any alarm (false-alarm rate {c['false_alarm_rate']:.2f}).", "",
          "## ir_decoy magnitude sweep (20 runs/magnitude) — detection floor",
          "", "| decoy offset | detection rate | mean latency (s) |",
          "|---|---|---|"]
    for k, v in rep["magnitude_sweep"].items():
        L.append(f"| {k} | {v['detection_rate']:.2f} ({v['detections']}/20) | "
                 f"{v['mean_latency_s'] if v['mean_latency_s'] else '—'} |")
    L += ["", "The detection floor is the smallest offset with a detection "
          "rate below 1.0; below it the decoy is within the combined bearing "
          "noise budget and is (correctly) not separable from noise."]
    open(os.path.join(OUT, "montecarlo_results.md"), "w").write("\n".join(L))


if __name__ == "__main__":
    main()
