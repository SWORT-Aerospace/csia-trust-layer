"""Field-survival matrix for raw GNSS receiver health under fix loss.

Joins the two probe captures into the audit artifacts. Applies ONE candidate
screen to both platforms, so a candidate that passes on one and fails on the
other fails for a stated reason rather than by inconsistent bookkeeping.

The screen is the brief's Item 8, and it deliberately does NOT require proven
diagnostic accuracy -- this is feasibility.

  python research/maer/maer_raw_gnss_audit.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAER = os.path.join(ROOT, "research", "maer")

# The position/velocity solution itself. Excluded by Item 8: a candidate must
# not be "the same lat/lon/velocity declared invalid".
SOLUTION_FIELDS = {"lat", "lon", "alt", "alt_ellipsoid", "vel", "cog", "yaw"}
# Item 7: fix_type IS the validity event. It is gate-event evidence, not a
# fault-specific discriminating residual, and must not be counted as one.
GATE_EVENT_FIELDS = {"fix_type"}
# Bookkeeping, not receiver health.
NON_HEALTH = {"time_usec"}

# GPS_RAW_INT is the RAW receiver message: PX4 populates it from the sensor_gps
# uORB topic published by the GPS driver, ArduPilot from the AP_GPS backend.
# Neither is an estimator output, so neither is barred by the independence
# contract -- which names estimator.variances specifically. The adapters simply
# never read these fields.
ESTIMATOR_DERIVED = {}          # none of the captured messages are


def load(platform):
    p = os.path.join(MAER, f"raw_gnss_probe_{platform}.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def record_is_live(summary, msg):
    """Does the receiver's own timestamp advance? A frozen record is a fossil.

    This is the check that separates "the message still arrives" from "the
    message still says something". ArduPilot under SIM_GPS1_ENABLE=0
    re-transmits the last sample verbatim: every field is present and
    non-sentinel, and time_usec never moves.
    """
    f = ((summary.get(msg) or {}).get("fields") or {}).get("time_usec") or {}
    return (f.get("distinct") or 0) > 1


def main() -> int:
    rows, per_platform = [], {}
    for platform in ("ardupilot", "px4"):
        d = load(platform)
        if not d:
            continue
        nominal = d.get("nominal") or {}
        loss = d.get("invalid_fix_only") or {}
        msgs_nominal = set(nominal)
        msgs_loss = set(loss)
        live = {m: record_is_live(loss, m) for m in msgs_loss}
        candidates = []

        for msg in sorted(msgs_nominal | msgs_loss):
            n_rec = nominal.get(msg) or {}
            l_rec = loss.get(msg) or {}
            n_count = n_rec.get("count") or 0
            l_count = l_rec.get("count") or 0
            for field in sorted(set(n_rec.get("fields") or {})
                                | set(l_rec.get("fields") or {})):
                nf = (n_rec.get("fields") or {}).get(field) or {}
                lf = (l_rec.get("fields") or {}).get(field) or {}
                present_frac = (round(lf.get("present", 0) / l_count, 4)
                                if l_count else 0.0)
                nonsent = lf.get("non_sentinel_fraction")
                pre = (f"min={nf.get('min')} max={nf.get('max')} "
                       f"distinct={nf.get('distinct')}")
                post = (f"min={lf.get('min')} max={lf.get('max')} "
                        f"distinct={lf.get('distinct')}")
                changed = (nf.get("min"), nf.get("max")) != (lf.get("min"),
                                                             lf.get("max"))
                is_health = field not in (SOLUTION_FIELDS | GATE_EVENT_FIELDS
                                          | NON_HEALTH)
                estimator = field in ESTIMATOR_DERIVED
                # ---- Item 8 screen ----------------------------------------
                cand = bool(
                    is_health                       # receiver health, not the
                                                    # invalidated solution
                    and not estimator               # independence contract
                    and present_frac > 0.5          # available meaningfully
                    and nonsent == 1.0              # not an unknown marker
                    and live.get(msg)               # the record still updates
                    and changed                     # moves at the fault
                )
                if cand:
                    candidates.append(field)
                rows.append({
                    "platform": platform,
                    "message": msg,
                    "field": field,
                    "nominal_msg_rate_hz": n_rec.get("hz"),
                    "fix_loss_msg_rate_hz": l_rec.get("hz"),
                    "nominal_present_fraction": (
                        round(nf.get("present", 0) / n_count, 4)
                        if n_count else 0.0),
                    "fix_loss_present_fraction": present_frac,
                    "fix_loss_non_sentinel_fraction": nonsent,
                    "record_live_under_fix_loss": live.get(msg, False),
                    "pre_fault_distribution": pre,
                    "post_fault_distribution": post,
                    "estimator_derived": estimator,
                    "independence_contract_allowed": not estimator,
                    "candidate_for_research_relation": cand,
                })

        per_platform[platform] = {
            "intervention": d.get("intervention"),
            "simulator": d.get("simulator"),
            "rule_b": d.get("rule_b"),
            "messages_nominal": sorted(msgs_nominal),
            "messages_surviving_fix_loss": sorted(msgs_loss),
            "messages_requested_but_never_seen": sorted(
                {"GPS_STATUS", "GPS2_RAW"} - msgs_nominal - msgs_loss),
            "record_live_under_fix_loss": live,
            "candidate_fields": sorted(set(candidates)),
        }

    dest_csv = os.path.join(MAER, "MAER_RAW_GNSS_SURVIVAL.csv")
    with open(dest_csv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    any_cand = {p: v["candidate_fields"] for p, v in per_platform.items()}
    reopened = any(any_cand.values())
    out = {
        "question": "does any contract-permitted raw GNSS receiver-health "
                    "observable remain available AND potentially "
                    "discriminating during the tested fix-loss intervention?",
        "screen": {
            "receiver_health_not_the_invalidated_solution": sorted(
                SOLUTION_FIELDS),
            "gate_event_not_a_residual": sorted(GATE_EVENT_FIELDS),
            "present_fraction_min": 0.5,
            "non_sentinel_required": 1.0,
            "record_must_be_live": "time_usec must advance -- a re-transmitted "
                                   "frozen sample is present but says nothing",
            "must_change_at_the_fault": True,
        },
        "platforms": per_platform,
        "candidate_fields_by_platform": any_cand,
        "verdict": ("MAER_STRUCTURAL_RESCUE_REOPENED" if reopened
                    else "MAER_STRUCTURAL_RESCUE_CONFIRMED_INFEASIBLE"),
    }
    dest_json = os.path.join(MAER, "MAER_RAW_GNSS_AUDIT.json")
    with open(dest_json, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)

    print("=== raw GNSS receiver-health survival")
    for p, v in sorted(per_platform.items()):
        print(f"\n  {p}  ({v['intervention']['param']}="
              f"{v['intervention']['value']})")
        print(f"    messages surviving fix loss : "
              f"{v['messages_surviving_fix_loss']}")
        print(f"    requested but never seen    : "
              f"{v['messages_requested_but_never_seen']}")
        print(f"    record live under fix loss  : "
              f"{v['record_live_under_fix_loss']}")
        print(f"    RULE B                      : {v['rule_b']}")
        print(f"    CANDIDATE FIELDS            : {v['candidate_fields']}")
    print(f"\n  VERDICT: {out['verdict']}")
    print(f"-> {os.path.relpath(dest_json, ROOT)}")
    print(f"-> {os.path.relpath(dest_csv, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
