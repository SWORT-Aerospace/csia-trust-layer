"""Does the COUPLED arm carry LIVE mechanism information during A = 0?

Items 6, 7, 10, 11. This is the decisive cheap test, and it is built to KILL
the architectural claim rather than support it.

The Stage-2 measurement showed C0 differs between mechanisms in `trust_gps` on
every scored tick. That looked like a leak worth exploiting. But a field that
DIFFERS is not a field that INFORMS: `trust_gps` freezes when A closes, so its
difference is inherited from before the scored interval. The question this
script answers is which -- for every field the coupled arm exposes, not just
the two the exploratory work happened to record.

Classification, per field, over the matched A = 0 interval:

  CONSTANT             identical in both mechanisms, never changes
  FROZEN_STATE         never changes in either mechanism, but the two frozen
                       values differ -- inherited, not live
  PRE_CLOSURE_HISTORY  changes, but its discriminating power was already
                       fully determined at A-closure
  LIVE_INFORMATION     changes during A = 0 in a mechanism-dependent way, and
                       the discrimination grows after closure
  UNKNOWN              none of the above fits

If ANY field is LIVE_INFORMATION with usable discrimination, the coupled
architecture already has what the split was proposed to provide, and the
architectural claim is refuted (CASE A).

Nothing here touches the frozen counterexample generator or the frozen core;
the replay loop is written out locally so `dual_replay.py` keeps its hash.

  python research/dual_admissibility_confirmatory/live_vs_inherited.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
DEV = os.path.join(ROOT, "research", "dual_admissibility")
FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
TAU = 0.5
MARGIN = 0.2
TICK_HZ = 25.0
# onsets swept to ask whether ONE threshold can generalise. Development data,
# so a PASS here proves nothing; a FAILURE is decisive, because held-out data
# cannot be kinder than the data a threshold was fitted on.
ONSETS = (12.0, 15.0, 18.0, 21.0, 24.0, 27.0)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_mh", os.path.join(ROOT, "research", "invalidity_masking",
                              "masking_harness.py"))
A = _load("_da", os.path.join(DEV, "dual_arms.py"))
PT = _load("_pt", os.path.join(DEV, "pattern_and_transport.py"))


def replay_full(messages, arm):
    """Local replay recording the FULL posterior, not a two-cause slice.

    The exploratory row only kept gps_fault and nominal. temp_gps -- which is
    ungated (online.py:630) and therefore still live while A is closed -- feeds
    `unexpected_maneuver`, so a two-cause slice cannot see the very leak this
    script exists to find.
    """
    from csia.runtime.online import OnlineTrustLayer

    now = {"t": 0.0}
    adapter = H.make_adapter(A.policy_for(arm), lambda: now["t"])
    layer = OnlineTrustLayer(tick_hz=TICK_HZ, field_mode=True)
    diag = A.DiagArm(arm)
    diag.bind_clock(lambda: layer.next_tick)
    layer.diag = diag

    rows, next_tick, dt = [], 0.0, 1.0 / TICK_HZ
    for m in messages:
        t = float(m["_t_recv"])
        now["t"] = t
        adapter.ingest(m)
        if m.get("mavpackettype") == "GPS_RAW_INT":
            diag.sidecar.observe(m, t)
        while next_tick <= t:
            now["t"] = next_tick
            smp = adapter.sample(t_mono=next_tick)
            for sensor, ts, chans in adapter.to_core_samples(smp):
                for st in (layer.ingest(sensor, ts, chans) or []):
                    d = diag.rows[-1] if diag.rows else {}
                    row = {"t": round(float(st.t), 6),
                           "A": 1.0 if st.fresh.get("gps") else 0.0,
                           "trust_gps": float(st.trust["gps"]),
                           "d_status": d.get("d_status"),
                           "c_status": d.get("c_status")}
                    for cause, p in (st.posterior or {}).items():
                        row[f"post_{cause}"] = float(p)
                    for n2 in ("gps", "mag", "battery", "vibration"):
                        comp = (st.components or {}).get(n2, {})
                        row[f"temp_{n2}_component"] = comp.get("temp")
                    rows.append(row)
            next_tick += dt
    return rows


def pair(carrier, template, onset):
    """One matched mechanism pair at a given onset."""
    def sensor(k, t):
        return PT.INVALID if t >= onset else PT.VALID

    def transport(k, t):
        return None if t >= onset else PT.VALID
    return (PT.build(carrier, template, sensor),
            PT.build(carrier, template, transport))


def classify(vs, vt):
    """LIVE vs inherited, for one field over the matched interval."""
    changes_s = sum(1 for a, b in zip(vs, vs[1:]) if a != b)
    changes_t = sum(1 for a, b in zip(vt, vt[1:]) if a != b)
    diffs = [abs(a - b) for a, b in zip(vs, vt)]
    d0, dN = diffs[0], diffs[-1]
    frozen = changes_s == 0 and changes_t == 0
    if max(diffs) == 0.0:
        kind = "CONSTANT"
    elif frozen:
        kind = "FROZEN_STATE"
    elif dN > d0 + 1e-12:
        kind = "LIVE_INFORMATION"
    elif changes_s + changes_t > 0:
        kind = "PRE_CLOSURE_HISTORY"
    else:
        kind = "UNKNOWN"
    return {
        "classification": kind,
        "value_changes_sensor": changes_s,
        "value_changes_transport": changes_t,
        "range_sensor": round(max(vs) - min(vs), 9),
        "range_transport": round(max(vt) - min(vt), 9),
        "separation_at_closure": round(d0, 9),
        "separation_at_end": round(dN, 9),
        "max_separation": round(max(diffs), 9),
        "discrimination_already_determined_at_closure": bool(dN <= d0 + 1e-12),
    }


def best_threshold(vs, vt):
    """Best single-threshold accuracy on this one pair (an upper bound)."""
    lo, hi = min(vs + vt), max(vs + vt)
    if hi <= lo:
        return 0.5
    best = 0.0
    for i in range(401):
        th = lo + (hi - lo) * i / 400.0
        for sign in (1, -1):
            corr = (sum(1 for v in vs if sign * (v - th) > 0)
                    + sum(1 for v in vt if sign * (v - th) < 0))
            best = max(best, corr / (2 * len(vs)))
    return round(best, 4)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    cap = H.load_fixture(FIXTURE)
    carrier, gps = H.carrier_and_gps(cap["messages"])
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)

    per_onset, field_rows = {}, []
    for onset in ONSETS:
        s_msgs, t_msgs = pair(carrier, template, onset)
        s = {r["t"]: r for r in replay_full(s_msgs, "S1")}
        t = {r["t"]: r for r in replay_full(t_msgs, "S1")}
        lo = onset + TAU + MARGIN
        scored = [k for k in sorted(set(s) & set(t)) if k >= lo]
        mism = [k for k in scored if s[k]["A"] != t[k]["A"]]
        fields = [f for f in s[scored[0]]
                  if f not in ("t", "d_status", "c_status")
                  and s[scored[0]][f] is not None
                  and t[scored[0]][f] is not None]

        entry = {"onset_s": onset, "scored_ticks": len(scored),
                 "A_mismatches": len(mism),
                 "A_zero_throughout": all(s[k]["A"] == 0.0 for k in scored)
                 and all(t[k]["A"] == 0.0 for k in scored),
                 "fields": {}}
        for f in fields:
            vs = [s[k][f] for k in scored]
            vt = [t[k][f] for k in scored]
            info = classify(vs, vt)
            info["best_threshold_accuracy_this_pair"] = best_threshold(vs, vt)
            info["frozen_value_sensor"] = round(vs[-1], 9)
            info["frozen_value_transport"] = round(vt[-1], 9)
            entry["fields"][f] = info
            field_rows.append({"onset_s": onset, "field": f, **info})
        per_onset[onset] = entry
        live = [f for f, v in entry["fields"].items()
                if v["classification"] == "LIVE_INFORMATION"]
        print(f"  onset {onset:>5.1f}s  scored={len(scored):<4} "
              f"A-mismatch={len(mism):<3} LIVE fields={live or 'none'}")

    # ---- does ONE threshold generalise across onsets? -------------------
    generalise = {}
    all_fields = sorted({r["field"] for r in field_rows})
    for f in all_fields:
        pts = [(per_onset[o]["fields"][f]["frozen_value_sensor"],
                per_onset[o]["fields"][f]["frozen_value_transport"])
               for o in ONSETS]
        sv = [p[0] for p in pts]
        tv = [p[1] for p in pts]
        # one threshold, applied to every onset
        lo, hi = min(sv + tv), max(sv + tv)
        best, best_th = 0.0, None
        for i in range(801):
            th = lo + (hi - lo) * i / 800.0 if hi > lo else lo
            for sign in (1, -1):
                corr = (sum(1 for v in sv if sign * (v - th) > 0)
                        + sum(1 for v in tv if sign * (v - th) < 0))
                acc = corr / (2 * len(sv))
                if acc > best:
                    best, best_th = acc, round(th, 9)
        generalise[f] = {
            "sensor_values_by_onset": sv,
            "transport_values_by_onset": tv,
            "best_single_threshold_across_onsets": best_th,
            "best_accuracy_across_onsets": round(best, 4),
            "classes_separable_by_one_threshold": bool(best == 1.0),
            "classes_interleave": bool(best < 1.0),
        }

    payload = {
        "artifact": "LIVE_VS_INHERITED_INFORMATION",
        "status": "DEVELOPMENT DATA. Asymmetric test: a FAILURE to generalise "
                  "here is decisive, because held-out data cannot be kinder "
                  "than the data a threshold was fitted on. A success here "
                  "would prove nothing and would require held-out "
                  "confirmation.",
        "arm": "C0 (coupled, = exploratory S1)",
        "scored_interval_rule": "t >= onset + tau + margin",
        "tau_s": TAU, "margin_s": MARGIN, "onsets_s": list(ONSETS),
        "per_onset": {str(k): v for k, v in per_onset.items()},
        "single_threshold_generalisation": generalise,
    }
    with open(os.path.join(OUT, "LIVE_VS_INHERITED_INFORMATION.json"), "w",
              encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    cols = ["onset_s", "field", "classification", "value_changes_sensor",
            "value_changes_transport", "range_sensor", "range_transport",
            "separation_at_closure", "separation_at_end", "max_separation",
            "discrimination_already_determined_at_closure",
            "best_threshold_accuracy_this_pair", "frozen_value_sensor",
            "frozen_value_transport"]
    with open(os.path.join(OUT, "LIVE_VS_INHERITED_INFORMATION.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(field_rows)

    print("\nSINGLE THRESHOLD ACROSS ONSETS (C0's best case)")
    for f, g in sorted(generalise.items(),
                       key=lambda kv: -kv[1]["best_accuracy_across_onsets"]):
        if g["best_accuracy_across_onsets"] > 0.5:
            print(f"  {f:<34} acc={g['best_accuracy_across_onsets']:.4f} "
                  f"separable={g['classes_separable_by_one_threshold']}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/"
          f"LIVE_VS_INHERITED_INFORMATION.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
