"""Temporal patterns, transport control, and the four-state confusion matrix.

Items 20, 21 and 22. Three questions the M1 recording cannot answer on its own:

1. The M1 jam is INTERMITTENT -- 29% of observations invalid, at 50 Hz. That
   leaves the coupled arm's gate open on most ticks, so a coupled arm can still
   see receiver health during the valid gaps. Does the split matter more when
   invalidity is SUSTAINED? This is the experiment that decides whether the
   S1D result generalises or is a property of one duty cycle.

2. Can an arm tell "the receiver said it has no fix" apart from "no message
   arrived"? A status feature that fires on transport starvation would be
   worse than no status feature at all.

3. Four upstream conditions, one downstream vocabulary. Which alias?

All fixtures here use the real ArduPilot non-GPS carrier from
NON_SCORED_TEST_FIXTURE_M1 with a PROGRAMMED GNSS stream. Payload values are
held constant except where a condition is defined by a payload field (h_acc),
in which case the value used is one observed in the real jam recording.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
OUT = os.path.join(_HERE, "results")
ONSET = 12.0
HZ = 5.0
# a degraded-but-valid accuracy actually observed in the jam recording
DEGRADED_H_ACC_MM = 288825


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", os.path.join(
    ROOT, "research", "invalidity_masking", "masking_harness.py"))
R = _load("_dual_replay", os.path.join(_HERE, "dual_replay.py"))
A = _load("_dual_arms", os.path.join(_HERE, "dual_arms.py"))


def build(carrier, template, decide, hz=HZ, t0=0.0):
    """Programmed GNSS stream. `decide(k, t)` -> None to DROP the message
    entirely (transport starvation), or a dict of field overrides."""
    t_end = max(float(m["_t_recv"]) for m in carrier)
    period, out, k = 1.0 / hz, list(carrier), 0
    while True:
        t = t0 + k * period
        if t > t_end:
            break
        over = decide(k, t)
        if over is not None:
            m = dict(template)
            m["_t_recv"] = round(t, 6)
            m["time_usec"] = int(round(t * 1e6))
            m.update(over)
            out.append(m)
        k += 1
    out.sort(key=lambda m: float(m["_t_recv"]))
    return out


INVALID = {"fix_type": 1, "satellites_visible": 0, "h_acc": 0, "eph": 65535}
VALID = {}
DEGRADED = {"h_acc": DEGRADED_H_ACC_MM}


def _sched(fn):
    return lambda k, t: fn(k, t)


PATTERNS = {
    "P0_ALL_VALID": (
        "null control: nothing is ever invalid",
        _sched(lambda k, t: VALID)),
    "P1_BURST_BELOW_TAU": (
        "one contiguous invalid interval SHORTER than the 0.5 s timeout",
        _sched(lambda k, t: INVALID if ONSET <= t < ONSET + 0.2 else VALID)),
    "P1_BURST_ABOVE_TAU": (
        "one contiguous invalid interval LONGER than the timeout",
        _sched(lambda k, t: INVALID if ONSET <= t < ONSET + 2.0 else VALID)),
    "P2_ALTERNATING": (
        "every other observation invalid: high density, short intervals",
        _sched(lambda k, t: INVALID if (t >= ONSET and k % 2 == 0) else VALID)),
    "P4_CLUSTERED": (
        "4 invalid in every 10: sustained bursts with valid gaps",
        _sched(lambda k, t: INVALID if (t >= ONSET and k % 10 < 4) else VALID)),
    "P5_PERMANENT": (
        "invalid from onset to the end: SUSTAINED, no valid gaps",
        _sched(lambda k, t: INVALID if t >= ONSET else VALID)),
    "T_TRANSPORT_STARVED": (
        "transport control: the receiver is HEALTHY but no message is "
        "delivered after onset",
        _sched(lambda k, t: None if t >= ONSET else VALID)),
    "G_DEGRADED_BUT_VALID": (
        "every observation reports a 3D fix, with a degraded h_acc observed "
        "in the real jam recording",
        _sched(lambda k, t: DEGRADED if t >= ONSET else VALID)),
}

CONFUSION_CONDITIONS = {
    "SENSOR_INVALID": "P5_PERMANENT",
    "TRANSPORT_MISSING": "T_TRANSPORT_STARVED",
    "SENSOR_DEGRADED_BUT_VALID": "G_DEGRADED_BUT_VALID",
    "ALL_VALID_NOMINAL": "P0_ALL_VALID",
}
# STALE_RETAINED is not a separate INPUT condition: it is the DOWNSTREAM state
# that both SENSOR_INVALID and TRANSPORT_MISSING produce on the S0 path. It is
# recorded as an outcome below rather than driven as an input.

ARMS = A.ARMS
# split arm -> its matched coupled control (same terms, D = A)
COUPLED_CONTROL = {"S2a": "S1Da", "S2b": "S1Db", "S2c": "S1D",
                   "S2b2": "S1Db", "S2c2": "S1D"}


def signature(rows):
    """The downstream vocabulary, post-onset, as an arm can express it."""
    post = [r for r in rows if r["t"] >= ONSET + 1.0]
    if not post:
        return {}

    def frac(key):
        vals = [r[key] for r in post if r[key] is not None]
        return round(sum(1 for v in vals if v > 0) / len(vals), 4) if vals \
            else None

    def mode(key, gate_key):
        """Mean consistency over ticks where the term was ACTUALLY admitted.

        Averaging a consistency the arm's gate discarded would credit it with
        information it never used -- which is exactly the confusion this
        matrix exists to detect.
        """
        vals = [r[key] for r in post
                if r[key] is not None and (r[gate_key] or 0.0) > 0.0]
        if not vals:
            return None
        return round(sum(vals) / len(vals), 4)
    # longest CONSECUTIVE run with A closed. This turns out to matter more
    # than the closed FRACTION: the frozen diagnosis smoother is a ~15-tick
    # EWMA, so evidence that alternates faster than that averages away.
    longest, run = 0, 0
    for r in post:
        run = run + 1 if r["fresh_gps"] == 0.0 else 0
        longest = max(longest, run)
    return {
        "A_open_frac": round(sum(r["fresh_gps"] for r in post) / len(post), 4),
        "longest_A_closed_run_ticks": longest,
        "longest_A_closed_run_s": round(longest * 0.04, 4),
        "D_status_open_frac": frac("d_status"),
        "D_hacc_open_frac": frac("d_hacc"),
        "mean_c_status": mode("c_status", "d_status"),
        "mean_c_hacc": mode("c_hacc", "d_hacc"),
        "top_cause_mode": max(
            {c: sum(1 for r in post if r["post_top_cause"] == c)
             for c in {r["post_top_cause"] for r in post}}.items(),
            key=lambda kv: kv[1])[0],
        "final_post_gps_fault": post[-1]["post_gps_fault"],
        "gps_fault_top_share": round(
            sum(1 for r in post if r["post_top_cause"] == "gps_fault")
            / len(post), 4),
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    cap = H.load_fixture(FIXTURE)
    carrier, gps = H.carrier_and_gps(cap["messages"])
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)

    rows, sigs = [], {}
    for pname, (desc, sched) in PATTERNS.items():
        msgs = build(carrier, template, sched)
        n_inv = sum(1 for m in msgs
                    if m.get("mavpackettype") == "GPS_RAW_INT"
                    and float(m["_t_recv"]) >= ONSET
                    and int(m.get("fix_type", 0) or 0) < 3)
        n_msg = sum(1 for m in msgs
                    if m.get("mavpackettype") == "GPS_RAW_INT"
                    and float(m["_t_recv"]) >= ONSET)
        print(f"\n{pname}  ({n_inv}/{n_msg} post-onset observations invalid)")
        sigs[pname] = {}
        for arm in ARMS:
            out = R.replay(msgs, arm)
            s = R.summarise(out, t_from=ONSET)
            sig = signature(out["rows"])
            sigs[pname][arm] = sig
            row = {"pattern": pname, "description": desc, "arm": arm,
                   "n_gps_msgs_post_onset": n_msg,
                   "n_invalid_post_onset": n_inv}
            row.update({k: v for k, v in s.items() if k != "arm"})
            row.update({f"sig_{k}": v for k, v in sig.items()})
            rows.append(row)
            print(f"  {arm:<4} A_open={sig.get('A_open_frac')}  "
                  f"D_top_share={s['D_top_share']}  "
                  f"post={s['D_final_post_gps_fault']}  "
                  f"top={sig.get('top_cause_mode')}")

    cols = list(rows[0].keys())
    with open(os.path.join(OUT, "TEMPORAL_PATTERN_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ---- does the split matter more when invalidity is SUSTAINED? --------
    def _get(pname, arm, key="D_top_share"):
        return next(r for r in rows
                    if r["pattern"] == pname and r["arm"] == arm)[key]

    split_gain = {}
    for pname in PATTERNS:
        base = next(r for r in rows
                    if r["pattern"] == pname and r["arm"] == "S1")
        entry = {
            "invalid_density": (round(base["n_invalid_post_onset"]
                                      / base["n_gps_msgs_post_onset"], 4)
                                if base["n_gps_msgs_post_onset"] else None),
            "A_open_frac_S1": base["sig_A_open_frac"],
            "D_top_share_S1": base["D_top_share"],
            "terms": {},
        }
        for split, coupled in COUPLED_CONTROL.items():
            d_split, d_coupled = _get(pname, split), _get(pname, coupled)
            entry["terms"][split] = {
                "coupled_control": coupled,
                "D_top_share_coupled": d_coupled,
                "D_top_share_split": d_split,
                # what the evidence term buys WITHOUT decoupling
                "detector_gain": round(d_coupled - base["D_top_share"], 6),
                # what decoupling buys on top of it
                "split_gain": round(d_split - d_coupled, 6),
            }
        split_gain[pname] = entry

    # ---- transport control (item 22) ------------------------------------
    tr_rows = []
    for cond, pat in (("SENSOR_INVALID", "P5_PERMANENT"),
                      ("TRANSPORT_MISSING", "T_TRANSPORT_STARVED")):
        for arm in ARMS:
            s = sigs[pat][arm]
            tr_rows.append({"condition": cond, "pattern": pat, "arm": arm,
                            **s})
    with open(os.path.join(OUT, "TRANSPORT_CONTROL_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tr_rows[0].keys()))
        w.writeheader()
        w.writerows(tr_rows)

    # ---- four-state confusion (item 21) ---------------------------------
    conf_rows, alias = [], {}
    for arm in ARMS:
        seen = {}
        for cond, pat in CONFUSION_CONDITIONS.items():
            sig = sigs[pat][arm]
            key = json.dumps({k: sig.get(k) for k in
                              ("A_open_frac", "D_status_open_frac",
                               "D_hacc_open_frac", "mean_c_status",
                               "mean_c_hacc")}, sort_keys=True)
            seen.setdefault(key, []).append(cond)
            conf_rows.append({"arm": arm, "upstream_condition": cond,
                              "pattern": pat, "downstream_signature": key,
                              **sig})
        collisions = {k: v for k, v in seen.items() if len(v) > 1}
        alias[arm] = {
            "distinct_downstream_signatures": len(seen),
            "upstream_conditions": len(CONFUSION_CONDITIONS),
            "aliased_groups": list(collisions.values()),
            "encodes_all_without_aliasing": len(seen) == len(
                CONFUSION_CONDITIONS),
        }
    with open(os.path.join(OUT, "EVIDENCE_STATE_CONFUSION_MATRIX.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(conf_rows[0].keys()))
        w.writeheader()
        w.writerows(conf_rows)

    with open(os.path.join(OUT, "PATTERN_AND_TRANSPORT_SUMMARY.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "artifact": "PATTERN_AND_TRANSPORT_SUMMARY",
            "fixture": "SYNTHETIC GNSS schedule over the "
                       f"{cap['meta']['tag']} non-GPS carrier",
            "onset_s": ONSET, "gnss_hz": HZ,
            "degraded_h_acc_mm": DEGRADED_H_ACC_MM,
            "split_versus_detector_by_pattern": split_gain,
            "aliasing_by_arm": alias,
        }, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("\nDETECTOR GAIN vs SPLIT GAIN, by pattern "
          "(D_top_share; base is S1)")
    for p, g in split_gain.items():
        print(f"  {p:<24} A_open={g['A_open_frac_S1']}  S1={g['D_top_share_S1']}")
        for split, t in g["terms"].items():
            if abs(t["detector_gain"]) < 1e-9 and abs(t["split_gain"]) < 1e-9:
                continue
            print(f"      {split:<5} vs {t['coupled_control']:<5} "
                  f"detector={t['detector_gain']:+.4f}  "
                  f"split={t['split_gain']:+.4f}  "
                  f"(coupled={t['D_top_share_coupled']}, "
                  f"split={t['D_top_share_split']})")
    print("\nALIASING")
    for arm, a in alias.items():
        print(f"  {arm:<4} {a['distinct_downstream_signatures']}/"
              f"{a['upstream_conditions']} distinct   "
              f"aliased={a['aliased_groups']}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
