"""P1 — B2 and B4 evaluated offline on the recorded per-tick streams.

B2 and B4 consume EXACTLY the information CSIA v1 consumes: the per-node
physics-consistency sequence the layer already computes. No new sensor input,
no new message, no added state beyond each detector's own. They are therefore
scored on the same flights as B1, paired tick for tick, which is stronger than
re-flying them.

B2 — simplest credible static threshold. Alarm when a node's physics
     consistency sits at or below the project's own saturation floor
     (PHYS_FLOOR = 0.10, csia/runtime/online.py's detection criterion) for k
     consecutive ticks. One integer parameter, searched on the development
     spec only, subject to R10 = 0.

B4 — classical sequential detector. A one-sided CUSUM on the standardised
     inconsistency z_t = ((1 - c_t) - mu0) / sigma0, with mu0 and sigma0
     estimated from the CLEAN NOMINAL ARM, not from any fault outcome:

         S_t = max(0, S_{t-1} + z_t - k),      alarm when S_t > h

     k = 0.5 and h = 5.0 are the textbook design pair for detecting a
     one-sigma shift at a long in-control ARL (Page 1954; standard in
     model-based FDI). They are SET BY DESIGN, not tuned to the outcome.
     docs/REQUIREMENTS.md R16 already names CUSUM as this repository's own
     tracked remedy for its known blind spot, so this is the project's method
     applied to a second phenomenon.

Both are research-only. No production file is touched.

Run:  PYTHONPATH=. python research/phase2/p1_offline_baselines.py
Out:  research/phase2/results/baseline_comparison.json
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")

PHYS_FLOOR = 0.10
NODES = ("gps", "mag", "battery", "vibration", "imu0", "imu1")
# Nodes for which the pre-transform residual is recorded. B4 uses these.
LAM_NODES = ("gps_eff", "mag", "battery", "vibration", "baro")
# "gps_eff" is max(lam_gps, (gps_step_peak/20)^2), the term online.py:572
# actually puts into P["gps"]. Recording plain lam_gps handed B4 a stream
# that was identically zero even under a GPS spoof.
LAM_TO_NODE = {"gps_eff": "gps"}

# FIRST PASS FED B2/B4 A SATURATED INPUT. `phys_*` is the consistency
# exp(-0.5*max(0, lam-1)), whose max(0, .) floor maps every sub-unity
# chi-square to exactly 1.0. Measured on the clean arm that gave
# sigma0 = 0 for gps, mag and battery and no samples at all for imu0, imu1
# and vibration, so B2 and B4 could only ever alarm on gps. Reporting them
# as failures on that input would have been choosing weak baselines, which
# the brief forbids. B4 now consumes `lam_*`, the pre-transform smoothed
# chi-square the layer already computes. B2 keeps the consistency floor,
# because "residual saturated for k ticks" is defined on the consistency and
# is the project's own detection criterion.
# node -> the fault family whose target it is
TARGET_NODE = {"gps_spoof": "gps", "gps_dropout": "gps",
               "imu0_bias_drift": "imu0", "mag_emi": "mag",
               "power_sag": "battery", "vibration_anomaly": "vibration",
               "dual_imu_failure": "imu0"}
NEGATIVE_CONTROL = {"gps_dropout"}     # scenario says trust must HOLD

B2_K_GRID = (5, 10, 25, 50, 100)       # searched on development only

# B4 drift stays at the textbook 0.5 (half the one-sigma shift to detect).
#
# The decision interval was FIRST fixed at the textbook h = 5.0, which pairs
# with k = 0.5 for an in-control ARL of roughly 465 samples. That is the wrong
# design point here and the mis-specification is mine: the layer ticks at
# ~25 Hz, so a 100 s flight is ~2500 samples and h = 5.0 predicts about five
# false alarms per flight. Measured: 3 on the clean nominal arm, failing R10.
#
# The corrected rule is the same one B2's k is chosen by, and it is a
# constraint-satisfaction rule evaluated ONLY on the clean nominal arm, never
# on a fault outcome: take the smallest h from a fixed grid for which the
# clean arm produces zero alarms. The h = 5.0 result is retained below as a
# committed negative result.
B4_K = 0.5
B4_H_TEXTBOOK = 5.0
B4_H_GRID = (5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0)


def b2_alarms(stream, k, inject_s):
    """First tick, per node, where consistency <= floor for k in a row."""
    out = {}
    t = stream["t"]
    for n in NODES:
        seq = stream.get(f"phys_{n}") or []
        run = 0
        for i, c in enumerate(seq):
            if c is not None and c <= PHYS_FLOOR:
                run += 1
                if run >= k:
                    out[n] = t[i] if i < len(t) else None
                    break
            else:
                run = 0
    return out


def clean_stats(nominal_stream):
    """mu0, sigma0 of the RAW residual per node, from the clean arm only."""
    st = {}
    for n in LAM_NODES:
        vals = [v for v in (nominal_stream.get(f"lam_{n}") or [])
                if v is not None]
        if len(vals) < 30:
            st[n] = {"usable": False, "n": len(vals),
                     "reason": "fewer than 30 clean samples"}
            continue
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
        st[n] = {"usable": sd > 1e-9, "mu0": round(mu, 8),
                 "sigma0": round(sd, 8), "n": len(vals),
                 "reason": None if sd > 1e-9 else
                 "clean-flight residual has zero variance; no scale exists "
                 "for a standardised detector"}
    return st


def b4_alarms(stream, stats, inject_s, h):
    """One-sided CUSUM on the standardised RAW residual."""
    out = {}
    t = stream["t"]
    for n in LAM_NODES:
        s = stats.get(n)
        if not s or not s.get("usable"):
            continue
        S = 0.0
        for i, v in enumerate(stream.get(f"lam_{n}") or []):
            if v is None:
                continue
            z = (v - s["mu0"]) / s["sigma0"]
            S = max(0.0, S + z - B4_K)
            if S > h:
                out[LAM_TO_NODE.get(n, n)] = t[i] if i < len(t) else None
                break
    return out


def evaluate(name, alarm_fn, trials, streams, inject_s=60.0):
    """Score a detector on both ledgers, plus R10."""
    per_trial, nominal_alarms = [], 0
    for r in trials:
        s = streams.get(r["label"])
        if not s:
            continue
        al = alarm_fn(s)
        # only alarms at or after injection count as a response
        post = {n: tt for n, tt in al.items()
                if tt is not None and tt >= inject_s}
        pre = {n: tt for n, tt in al.items()
               if tt is not None and tt < inject_s}
        if r["arm"] == "nominal":
            nominal_alarms += len(al)
            per_trial.append({"label": r["label"], "arm": "nominal",
                              "alarms": al, "counts_against_R10": len(al)})
            continue
        tn = TARGET_NODE.get(r["arm"])
        responded = bool(post)
        correct = bool(tn in post) if r["arm"] not in NEGATIVE_CONTROL \
            else not responded
        first = min(post.values()) if post else None
        per_trial.append({
            "label": r["label"], "arm": r["arm"],
            "target_node": tn,
            "alarming_nodes": sorted(post),
            "pre_injection_alarms": sorted(pre),
            "response": responded,
            "correct_diagnostic": correct,
            "wrong_isolation": bool(responded and tn not in post
                                    and r["arm"] not in NEGATIVE_CONTROL),
            "response_time_s": (round(first - inject_s, 3)
                                if first is not None else None),
            "autopilot_response": r["autopilot_response"],
        })
    return {"detector": name, "R10_nominal_alarms": nominal_alarms,
            "per_trial": per_trial}


def decompose(ev, ledger):
    cov = {"BOTH": 0, "AUTOPILOT_ONLY": 0, "CSIA_ONLY": 0, "JOINT_MISS": 0}
    for t in ev["per_trial"]:
        if t["arm"] == "nominal":
            continue
        A = t["autopilot_response"]
        C = t["response"] if ledger == "A" else (
            t["response"] and t["correct_diagnostic"])
        cov["BOTH" if (A and C) else "AUTOPILOT_ONLY" if A
            else "CSIA_ONLY" if C else "JOINT_MISS"] += 1
    return cov


def main() -> int:
    suite = sys.argv[1] if len(sys.argv) > 1 else "fault_suite_lambda_spec0"
    suite_p = os.path.join(RESULTS, f"{suite}.json")
    streams_p = os.path.join(RESULTS, f"p1_streams_{suite}.json")
    if not (os.path.isfile(suite_p) and os.path.isfile(streams_p)):
        print("fault_suite_coverage.json / p1_streams.json not present; "
              "run p1_fault_suite.py first")
        return 1
    sdata = json.load(open(suite_p))
    streams = json.load(open(streams_p))
    # B2/B4 read the residual sequence, which does not depend on rho_max, so
    # the B1 flights are the correct and only input.
    trials = [r for r in sdata["per_trial"]
              if r["candidate"] == "B1" and r.get("TRIAL_VALID")
              and "error" not in r]
    nominal = next((r for r in trials if r["arm"] == "nominal"), None)
    if nominal is None:
        print("no valid nominal arm")
        return 1

    stats = clean_stats(streams[nominal["label"]])

    # ---- B2: search k on the development spec, subject to R10 = 0 ----
    b2_search = []
    for k in B2_K_GRID:
        t0 = time.perf_counter()
        ev = evaluate(f"B2_k{k}", lambda s, k=k: b2_alarms(s, k, 60.0),
                      trials, streams)
        us = (time.perf_counter() - t0) * 1e6 / max(
            1, sum(len(streams[r["label"]]["t"]) for r in trials))
        b2_search.append({
            "k": k, "R10_nominal_alarms": ev["R10_nominal_alarms"],
            "satisfies_R10": ev["R10_nominal_alarms"] == 0,
            "ledger_A": decompose(ev, "A"), "ledger_B": decompose(ev, "B"),
            "cpu_us_per_tick": round(us, 3),
            "_ev": ev})
    feasible = [c for c in b2_search if c["satisfies_R10"]]
    # objective: maximise correct-diagnostic coverage (ledger B BOTH+CSIA_ONLY)
    b2_best = max(feasible or b2_search,
                  key=lambda c: (c["satisfies_R10"],
                                 c["ledger_B"]["BOTH"]
                                 + c["ledger_B"]["CSIA_ONLY"],
                                 -c["k"]))

    # ---- B4: k by design, h by the R10 constraint on the clean arm ----
    b4_search = []
    for h in B4_H_GRID:
        t0 = time.perf_counter()
        ev = evaluate(f"B4_h{h:g}", lambda s, h=h: b4_alarms(s, stats, 60.0, h),
                      trials, streams)
        us = (time.perf_counter() - t0) * 1e6 / max(
            1, sum(len(streams[r["label"]]["t"]) for r in trials))
        b4_search.append({
            "h": h, "R10_nominal_alarms": ev["R10_nominal_alarms"],
            "satisfies_R10": ev["R10_nominal_alarms"] == 0,
            "ledger_A": decompose(ev, "A"), "ledger_B": decompose(ev, "B"),
            "cpu_us_per_tick": round(us, 3), "_ev": ev})
    b4_feasible = [c for c in b4_search if c["satisfies_R10"]]
    b4_best = (min(b4_feasible, key=lambda c: c["h"])
               if b4_feasible else b4_search[-1])
    b4_ev = b4_best["_ev"]
    b4_us = b4_best["cpu_us_per_tick"]
    b4_textbook = next(c for c in b4_search if c["h"] == B4_H_TEXTBOOK)

    # ---- B0 / B1 / B3 from the flown campaign ----
    flown = {}
    for cand, s in sdata.get("summary", {}).items():
        flown[cand] = {"R10_nominal_transitions": s["R10_nominal_transitions"],
                       "ledger_A": s["ledger_A"], "ledger_B": s["ledger_B"],
                       "wrong_isolation": s["wrong_isolation"],
                       "valid_fault_trials": s["valid_fault_trials"]}
    b0_A = sum(1 for r in trials
               if r["arm"] != "nominal" and r["autopilot_response"])
    b0_total = sum(1 for r in trials if r["arm"] != "nominal")

    report = {
        "work_package": "P1 established-method challenge, B0-B4",
        "rig": "LEGACY_COMPAT_CONTROL",
        "development_spec": sdata.get("flight_spec"),
        "information_used_by_candidates": (
            "B2 and B4 read the per-node physics-consistency sequence CSIA "
            "already computes. No new sensor input, no new message."),
        "B0_native_autopilot": {
            "responds_on": b0_A, "of": b0_total,
            "criterion": "EKF variance above FS_EKF_THRESH on the family's "
                         "channel, OR a failsafe mode change, OR a STATUSTEXT "
                         "at severity <= 4",
            "note": "this is MORE sensitive than ArduCopter's own failsafe, "
                    "which requires two of three variances over threshold or "
                    "velocity variance at twice threshold "
                    "(ArduCopter/ekf_check.cpp:142-154). B0 is therefore "
                    "generous to the autopilot, not a strawman.",
        },
        "flown_candidates": flown,
        "B2": {"parameter": "k consecutive ticks at or below PHYS_FLOOR",
               "floor": PHYS_FLOOR,
               "searched_on": "development spec only",
               "grid": list(B2_K_GRID),
               "search": [{kk: vv for kk, vv in c.items() if kk != "_ev"}
                          for c in b2_search],
               "selected_k": b2_best["k"],
               "selected": {kk: vv for kk, vv in b2_best.items()
                            if kk != "_ev"},
               "per_trial": b2_best["_ev"]["per_trial"]},
        "B4": {"detector": "one-sided CUSUM on the standardised PRE-TRANSFORM "
                           "residual (OnlineTrustLayer._lam, read-only)",
               "drift_k": B4_K,
               "drift_set_by": "design: half the one-sigma shift to detect "
                               "(Page 1954; standard in model-based FDI)",
               "decision_h_selected": b4_best["h"],
               "decision_h_rule": "smallest h from a fixed grid for which the "
                                  "CLEAN NOMINAL ARM produces zero alarms. "
                                  "Evaluated on the clean arm only, never on "
                                  "a fault outcome — the same constraint rule "
                                  "B2's k is chosen by.",
               "grid": list(B4_H_GRID),
               "search": [{kk: vv for kk, vv in c.items() if kk != "_ev"}
                          for c in b4_search],
               "textbook_h_negative_result": {
                   "h": B4_H_TEXTBOOK,
                   "R10_nominal_alarms": b4_textbook["R10_nominal_alarms"],
                   "why_it_failed": (
                       "h=5.0 pairs with k=0.5 for an in-control ARL of about "
                       "465 samples. The layer ticks at ~25 Hz, so a 100 s "
                       "flight is ~2500 samples and this design point "
                       "predicts about five false alarms per flight. The "
                       "mis-specification was the analyst's, not the "
                       "method's. Retained as a committed negative result."),
                   "ledger_A": b4_textbook["ledger_A"]},
               "in_control_stats_from": "the clean nominal arm only",
               "clean_stats": stats,
               "R10_nominal_alarms": b4_ev["R10_nominal_alarms"],
               "satisfies_R10": b4_ev["R10_nominal_alarms"] == 0,
               "ledger_A": decompose(b4_ev, "A"),
               "ledger_B": decompose(b4_ev, "B"),
               "cpu_us_per_tick": round(b4_us, 3),
               "per_trial": b4_ev["per_trial"]},
    }
    out = os.path.join(RESULTS, "baseline_comparison.json" if suite == "fault_suite_lambda_spec0" else f"baseline_comparison_{suite}.json")
    json.dump(report, open(out, "w"), indent=1, sort_keys=True)

    print(f"B0 native: responds on {b0_A}/{b0_total} valid fault trials")
    for cand, s in sorted(flown.items()):
        print(f"{cand:12s} R10={s['R10_nominal_transitions']}  "
              f"A={s['ledger_A']}  B={s['ledger_B']}")
    print("\nB2 search (k, R10, ledgerB):")
    for c in b2_search:
        print(f"  k={c['k']:4d}  R10={c['R10_nominal_alarms']:2d}  "
              f"A={c['ledger_A']}  B={c['ledger_B']}")
    print(f"  selected k={b2_best['k']}")
    print("\nB4 CUSUM search (h, R10, ledgerA):")
    for c in b4_search:
        print(f"  h={c['h']:7.1f}  R10={c['R10_nominal_alarms']:2d}  "
              f"A={c['ledger_A']}  B={c['ledger_B']}")
    print(f"  selected h={b4_best['h']}  (textbook h=5.0 gave R10="
          f"{b4_textbook['R10_nominal_alarms']})")
    print(f"wrote {os.path.relpath(out, os.path.join(HERE, '..', '..'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
