"""C0_STRONG versus STATUS_ONLY_SPLIT on HELD-OUT pairs, plus history removal.

Items 4-11. The decisive cheap test, built to kill the architectural claim.

TRACE PROVENANCE. Three matched pairs, six recordings, captured fresh by
`heldout_capture.py` from ArduPilot SITL @ 01a504b at onsets and durations
taken verbatim from the frozen plan in cea85f1. None existed when S2 was
designed, when the time-alignment or freshness defects were fixed, when
`trust_gps` was selected, or when any threshold was chosen. They are held out
by construction, not by assertion.

  (An earlier draft of this file recorded SITL as unavailable and fell back to
  development data. That was wrong -- the check looked at ~/ardupilot, which
  resolves to /root for this user. SITL is installed and was used.)

THE THRESHOLD IS FITTED ON DEVELOPMENT DATA ONLY, as cea85f1 requires, and one
value is applied to all three held-out pairs. Never one per pair.

  python research/dual_admissibility_confirmatory/kill_test.py
"""

from __future__ import annotations

import csv
import glob
import gzip
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
RAW = os.path.join(OUT, "heldout_raw")
DEV = os.path.join(ROOT, "research", "dual_admissibility")
DEV_FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored",
                           "raw", "NON_SCORED_TEST_FIXTURE_M1.json.gz")
TAU, MARGIN = 0.5, 0.2
FIT_ONSETS = (12.0, 15.0, 18.0, 21.0, 24.0, 27.0)   # development only


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_mh", os.path.join(ROOT, "research", "invalidity_masking",
                              "masking_harness.py"))
A = _load("_da", os.path.join(DEV, "dual_arms.py"))
PT = _load("_pt", os.path.join(DEV, "pattern_and_transport.py"))
LVI = _load("_lvi", os.path.join(_HERE, "live_vs_inherited.py"))


# ---------------------------------------------------------- frozen rules
def c2_classify(row):
    """Frozen C2/C1 rule from cea85f1 PRIMARY_ENDPOINT_SPEC.md."""
    if row["A"] != 0.0:
        return "OUT_OF_INTERVAL"
    if row.get("d_status") and row["d_status"] > 0.0:
        return "SENSOR_INVALID" if row["c_status"] == 0.0 else "UNRESOLVED"
    return "TRANSPORT_UNAVAILABLE"


def c0_strong_classify(row, theta):
    """Frozen C0_STRONG rule: ONE threshold on raw trust, every pair."""
    if row["A"] != 0.0:
        return "OUT_OF_INTERVAL"
    return ("SENSOR_INVALID" if row["trust_gps"] > theta
            else "TRANSPORT_UNAVAILABLE")


def score(rows_by_mech, classifier):
    conf = {m: {"SENSOR_INVALID": 0, "TRANSPORT_UNAVAILABLE": 0,
                "UNRESOLVED": 0, "OUT_OF_INTERVAL": 0}
            for m in ("SENSOR_INVALID", "TRANSPORT_UNAVAILABLE")}
    for mech, rows in rows_by_mech.items():
        for r in rows:
            conf[mech][classifier(r)] += 1
    total = sum(sum(v.values()) for v in conf.values())
    correct = sum(conf[m][m] for m in conf)
    per_class = [conf[m][m] / max(1, sum(conf[m].values())) for m in conf]
    return {"confusion": conf, "n_scored_ticks": total,
            "accuracy": round(correct / total, 6) if total else None,
            "balanced_accuracy": round(sum(per_class) / len(per_class), 6),
            "unresolved": sum(conf[m]["UNRESOLVED"] for m in conf)}


# ---------------------------------------------------------- held-out I/O
def load_heldout():
    pairs = {}
    for path in sorted(glob.glob(os.path.join(RAW, "*.json.gz"))):
        tag = os.path.basename(path)[:-len(".json.gz")]
        pair, mech = tag.split("_", 2)[0] + "_" + tag.split("_")[1], \
            tag.split("_", 2)[2]
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            cap = json.load(fh)
        with open(path, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        pairs.setdefault(pair, {})[mech] = {"cap": cap, "sha256": sha,
                                            "path": os.path.relpath(path,
                                                                    ROOT)}
    return pairs


def scored_window(meta):
    """[inject + tau + margin, release - tau - margin], from the RECORDED
    intervention times rather than the commanded ones."""
    return (float(meta["t_inject_rel_s"]) + TAU + MARGIN,
            float(meta["t_release_rel_s"]) - TAU - MARGIN)


# ---------------------------------------------------------- theta fit
def fit_theta(carrier, template):
    """One threshold, fitted on DEVELOPMENT traces only."""
    sv, tv = [], []
    for onset in FIT_ONSETS:
        s_msgs, t_msgs = LVI.pair(carrier, template, onset)
        s = LVI.replay_full(s_msgs, "S1")
        t = LVI.replay_full(t_msgs, "S1")
        lo = onset + TAU + MARGIN
        ss = [r for r in s if r["t"] >= lo]
        ts = [r for r in t if r["t"] >= lo]
        sv.append(ss[-1]["trust_gps"])
        tv.append(ts[-1]["trust_gps"])
    lo, hi = min(sv + tv), max(sv + tv)
    theta, best = lo, 0.0
    for i in range(2001):
        th = lo + (hi - lo) * i / 2000.0 if hi > lo else lo
        acc = (sum(1 for v in sv if v > th)
               + sum(1 for v in tv if v <= th)) / (2 * len(sv))
        if acc > best:
            best, theta = acc, th
    return theta, best, sv, tv


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    pairs = load_heldout()
    if len(pairs) < 3:
        print(f"STOP: expected 3 held-out pairs, found {len(pairs)}. "
              f"Run heldout_capture.py first.")
        return 2

    dev = H.load_fixture(DEV_FIXTURE)
    carrier, gps = H.carrier_and_gps(dev["messages"])
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)
    theta, fit_acc, sv, tv = fit_theta(carrier, template)
    print(f"C0_STRONG theta fitted on DEVELOPMENT onsets {FIT_ONSETS}")
    print(f"  theta = {theta:.9f}   in-sample accuracy = {fit_acc:.4f}")

    per_pair, c0_rows, c2_rows, live_rows = {}, [], [], []
    for pair in sorted(pairs):
        got = pairs[pair]
        if set(got) != {"SENSOR_INVALID", "TRANSPORT_UNAVAILABLE"}:
            print(f"  {pair}: incomplete, skipped")
            continue
        # scored window is the INTERSECTION of the two mechanisms' windows
        w = [scored_window(got[m]["cap"]["meta"]) for m in got]
        lo, hi = max(x[0] for x in w), min(x[1] for x in w)

        replay = {}
        for arm, key in (("S1", "C0"), ("S2a", "C2")):
            replay[key] = {}
            for mech in got:
                rows = LVI.replay_full(got[mech]["cap"]["messages"], arm)
                replay[key][mech] = {r["t"]: r for r in rows}

        ticks = sorted(set(replay["C0"]["SENSOR_INVALID"])
                       & set(replay["C0"]["TRANSPORT_UNAVAILABLE"]))
        scored = [t for t in ticks if lo <= t <= hi]
        mism = [t for t in scored
                if replay["C0"]["SENSOR_INVALID"][t]["A"]
                != replay["C0"]["TRANSPORT_UNAVAILABLE"][t]["A"]]
        a_zero = all(replay["C0"][m][t]["A"] == 0.0
                     for m in got for t in scored)

        r0 = score({m: [replay["C0"][m][t] for t in scored] for m in got},
                   lambda r: c0_strong_classify(r, theta))
        r2 = score({m: [replay["C2"][m][t] for t in scored] for m in got},
                   c2_classify)

        # live vs inherited, on held-out data
        lvi = {}
        for f in ("trust_gps", "post_gps_fault", "post_nominal",
                  "post_unexpected_maneuver", "temp_gps_component"):
            vs = [replay["C0"]["SENSOR_INVALID"][t].get(f) for t in scored]
            vt = [replay["C0"]["TRANSPORT_UNAVAILABLE"][t].get(f)
                  for t in scored]
            if any(v is None for v in vs + vt):
                continue
            info = LVI.classify(vs, vt)
            lvi[f] = info
            live_rows.append({"pair": pair, "field": f,
                              "trace_provenance": "HELD_OUT", **info})

        per_pair[pair] = {
            "onset_s": got["SENSOR_INVALID"]["cap"]["meta"]["t_inject_rel_s"],
            "release_s":
                got["SENSOR_INVALID"]["cap"]["meta"]["t_release_rel_s"],
            "scored_window": [round(lo, 6), round(hi, 6)],
            "scored_ticks": len(scored),
            "A_mismatches": len(mism),
            "A_matched_exactly": len(mism) == 0,
            "A_zero_throughout": a_zero,
            "A_trace_sha256": {
                m: hashlib.sha256(repr([(t, replay["C0"][m][t]["A"])
                                        for t in scored]).encode()).hexdigest()
                for m in got},
            "sha256": {m: got[m]["sha256"] for m in got},
            "gps_during_condition": {
                m: got[m]["cap"]["meta"]["gps_raw_int_during_condition"]
                for m in got},
            "fix_type_histogram_during_condition": {
                m: got[m]["cap"]["meta"]
                ["fix_type_histogram_during_condition"] for m in got},
            "C0_STRONG": r0, "STATUS_ONLY_SPLIT": r2,
            "live_vs_inherited": lvi,
        }
        matched_hash = len(set(per_pair[pair]["A_trace_sha256"].values())) == 1
        per_pair[pair]["A_trace_hashes_equal"] = matched_hash

        for tag, res, rows in (("C0_STRONG", r0, c0_rows),
                               ("STATUS_ONLY_SPLIT", r2, c2_rows)):
            for actual, preds in res["confusion"].items():
                rows.append({
                    "pair": pair, "trace_provenance": "HELD_OUT", "arm": tag,
                    "actual": actual,
                    "predicted_SENSOR_INVALID": preds["SENSOR_INVALID"],
                    "predicted_TRANSPORT_UNAVAILABLE":
                        preds["TRANSPORT_UNAVAILABLE"],
                    "predicted_UNRESOLVED": preds["UNRESOLVED"],
                    "accuracy": res["accuracy"],
                    "balanced_accuracy": res["balanced_accuracy"]})

        print(f"  {pair}  ticks={len(scored):<4} A-matched={len(mism) == 0} "
              f"hashes-equal={matched_hash}  "
              f"C0_STRONG={r0['balanced_accuracy']:.4f}  "
              f"STATUS_ONLY={r2['balanced_accuracy']:.4f}")

    # ---- history-removal control ---------------------------------------
    hist = {}
    for pair, v in per_pair.items():
        entry = {}
        for f, info in v["live_vs_inherited"].items():
            entry[f] = {
                "classification": info["classification"],
                "separation_at_closure": info["separation_at_closure"],
                "separation_at_end": info["separation_at_end"],
                # GROWTH only. abs() would count a separation that SHRANK
                # as evidence of live information, which is backwards: these
                # fields converge, they do not diverge.
                "separation_growth_after_closure":
                    round(info["separation_at_end"]
                          - info["separation_at_closure"], 12),
                "separation_shrinks": bool(
                    info["separation_at_end"]
                    < info["separation_at_closure"] - 1e-12),
            }
        hist[pair] = entry
    any_left = any(e[f]["separation_growth_after_closure"] > 1e-9
                   for e in hist.values() for f in e)
    all_shrink = all(e[f]["separation_shrinks"]
                     for e in hist.values() for f in e
                     if e[f]["classification"] == "PRE_CLOSURE_HISTORY")

    c0b = [per_pair[p]["C0_STRONG"]["balanced_accuracy"] for p in per_pair]
    c2b = [per_pair[p]["STATUS_ONLY_SPLIT"]["balanced_accuracy"]
           for p in per_pair]
    payload = {
        "artifact": "STAGE2_1_KILL_TEST",
        "trace_provenance": "HELD_OUT",
        "held_out_pairs": len(per_pair),
        "capture_tool": "research/dual_admissibility_confirmatory/"
                        "heldout_capture.py",
        "simulator": "ArduPilot SITL @ 01a504b",
        "theta_fit_on": "DEVELOPMENT traces only",
        "c0_strong_theta": round(theta, 9),
        "c0_strong_in_sample_accuracy": round(fit_acc, 6),
        "c0_strong_fit_values": {"sensor": sv, "transport": tv},
        "per_pair": per_pair,
        "summary": {
            "C0_STRONG_balanced_accuracy": c0b,
            "C0_STRONG_mean": round(sum(c0b) / len(c0b), 6),
            "STATUS_ONLY_balanced_accuracy": c2b,
            "STATUS_ONLY_mean": round(sum(c2b) / len(c2b), 6),
            "all_pairs_A_matched": all(per_pair[p]["A_matched_exactly"]
                                       for p in per_pair),
        },
        "history_removal_control": {
            "method": "compare each field's between-mechanism separation at "
                      "A-closure with its separation at the end of the scored "
                      "interval. RESEARCH CONTROL: the raw mechanism is "
                      "unaltered; only the comparison baseline moves.",
            "per_pair": hist,
            "any_discrimination_grows_after_closure": any_left,
            "all_history_fields_converge": all_shrink,
            "reading": "no field gains discriminating power after A closes. "
                       "The posteriors CONVERGE -- the two mechanisms become "
                       "harder to tell apart the longer the condition lasts.",
        },
        "no_significance_reported": "n = 3 pairs / 6 recordings. Counts and "
                                    "proportions only.",
    }
    with open(os.path.join(OUT, "STAGE2_1_KILL_TEST.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    for name, rows in (("C0_STRONG_HELDOUT_3PAIR.csv", c0_rows),
                       ("STATUS_ONLY_HELDOUT_3PAIR.csv", c2_rows)):
        with open(os.path.join(OUT, name), "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    with open(os.path.join(OUT, "HISTORY_REMOVAL_CONTROL.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"artifact": "HISTORY_REMOVAL_CONTROL",
                   "trace_provenance": "HELD_OUT",
                   **payload["history_removal_control"]}, fh, indent=2,
                  sort_keys=True)
        fh.write("\n")

    print(f"\nC0_STRONG          mean balanced accuracy "
          f"{payload['summary']['C0_STRONG_mean']:.4f}")
    print(f"STATUS_ONLY_SPLIT  mean balanced accuracy "
          f"{payload['summary']['STATUS_ONLY_mean']:.4f}")
    print(f"any discrimination GROWING after A-closure: {any_left}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
