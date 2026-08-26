"""Do raw GNSS receiver-health fields survive the fix-loss intervention?

WHY THIS EXISTS. The first MAER feasibility audit checked whether the
NORMALIZED CSIA channels (gnss.position/velocity/velocity_z) survive fix loss.
They do not. But that is a fact about the normalization layer, not about the
protocol: both adapters return early on `fix_type < 3` and discard the WHOLE
GPS_RAW_INT message, including `satellites_visible`, `eph`, `epv`, `h_acc`,
`v_acc`, `vel_acc` and `hdg_acc` -- receiver-health metadata carried in the
same message whose lat/lon was invalidated. Those fields are never read at all.

So "the channel is unusable" and "the receiver stopped saying anything about
itself" are different claims, and only the first was established. This probe
tests the second directly, on the raw stream, before normalization.

WHAT IT IS NOT. Not a scored campaign, not a MAER arm, and it changes nothing.
It reproduces the already-established intervention (ArduPilot
SIM_GPS1_ENABLE=0, PX4 SIM_GPS_USED=0) purely to record which raw fields keep
arriving and whether their values remain meaningful or go to a sentinel.

FOUR OUTCOMES ARE DISTINGUISHED PER FIELD, because collapsing them is how a
"nothing survives" conclusion gets reached without evidence:

  A message absent            the message stopped arriving
  B message present, nav invalid   arriving, fix_type < 3
  C present but sentinel      field present and set to its unknown marker
                              (UINT8_MAX / UINT16_MAX / UINT32_MAX / 0xFFFF)
  D present and meaningful    field present, non-sentinel, and its value moves

Estimator-derived quantities are deliberately NOT captured: the independence
contract bars CSIA from consuming the estimator it exists to check.

  python research/maer/maer_raw_gnss_probe.py --platform ardupilot
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

# The exact intervention already established for Mechanism A.
FIX_LOSS = {
    "ardupilot": ("SIM_GPS1_ENABLE", 0.0, "REAL32"),
    "px4": ("SIM_GPS_USED", 0, "INT32"),
}
# Raw receiver messages only. No estimator output.
WATCH_MSGS = ("GPS_RAW_INT", "GPS_STATUS", "GPS2_RAW")
# Field -> the value that means "unknown" in the MAVLink spec.
SENTINELS = {
    "satellites_visible": 255,           # UINT8_MAX
    "eph": 65535, "epv": 65535,          # UINT16_MAX
    "h_acc": 4294967295, "v_acc": 4294967295,
    "vel_acc": 4294967295, "hdg_acc": 4294967295,
    "alt_ellipsoid": 2147483647,
    "yaw": 0,                            # 0 means "not available" for yaw
}
NOMINAL_S = 20.0
LOSS_S = 25.0
SETTLE_S = 3.0


def _capture(conn, seconds, rows):
    """Drain the link for `seconds`, keeping every watched message whole.

    Messages are stored rather than aggregated because the meaningful
    partition is each message's OWN fix_type, not the wall-clock phase it
    arrived in: the injection takes a moment to propagate, so a phase window
    straddles the transition and mixes valid with invalid samples.
    """
    end = time.time() + seconds
    while time.time() < end:
        msg = conn.recv_match(blocking=True, timeout=0.5)
        if msg is None:
            continue
        t = msg.get_type()
        if t not in WATCH_MSGS:
            continue
        d = {k: v for k, v in msg.to_dict().items() if k != "mavpackettype"}
        d["_msg"] = t
        d["_t"] = time.time()
        rows.append(d)


def _summarise(rows, seconds, msg_filter=None):
    """Per-message, per-field survival over the rows given."""
    out = {}
    for r in rows:
        t = r["_msg"]
        if msg_filter and t != msg_filter:
            continue
        rec = out.setdefault(t, {"count": 0, "fields": {}})
        rec["count"] += 1
        for k, v in r.items():
            if k.startswith("_"):
                continue
            f = rec["fields"].setdefault(
                k, {"present": 0, "sentinel": 0, "values": []})
            f["present"] += 1
            if k in SENTINELS and v == SENTINELS[k]:
                f["sentinel"] += 1
            if isinstance(v, (int, float)) and len(f["values"]) < 4000:
                f["values"].append(v)
    for t, rec in out.items():
        rec["hz"] = round(rec["count"] / seconds, 3) if seconds else None
        for k, f in rec["fields"].items():
            vals = f.pop("values")
            f["non_sentinel_fraction"] = (
                round(1.0 - f["sentinel"] / f["present"], 4)
                if f["present"] else None)
            f["min"] = min(vals) if vals else None
            f["max"] = max(vals) if vals else None
            f["distinct"] = len(set(vals)) if vals else 0
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--platform", required=True, choices=list(FIX_LOSS))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    from pymavlink import mavutil

    from csia.simulation.rigs import (LAUNCHERS, connect, provenance_string)

    workdir = os.path.join(ROOT, "research", "maer", ".raw_probe",
                           args.platform)
    proc, conn_str = LAUNCHERS[args.platform](workdir, 1)
    result = {"platform": args.platform,
              "simulator": provenance_string(args.platform),
              "intervention": None, "nominal": None, "fix_loss": None}
    try:
        conn = connect(conn_str, args.platform)
        # GPS_STATUS is not in any default stream set; ask for it explicitly
        # so its absence later means "the vehicle does not send it", not
        # "nobody asked".
        for mid, hz in ((24, 5), (25, 5), (124, 5)):   # RAW_INT, STATUS, GPS2
            conn.mav.command_long_send(conn.target_system,
                                       conn.target_component,
                                       511, 0, mid, int(1e6 / hz),
                                       0, 0, 0, 0, 0)
        time.sleep(SETTLE_S)
        while conn.recv_match(blocking=False) is not None:
            pass

        print(f"=== {args.platform}: {NOMINAL_S:.0f} s nominal")
        nominal_rows = []
        _capture(conn, NOMINAL_S, nominal_rows)
        result["nominal"] = _summarise(nominal_rows, NOMINAL_S)

        name, value, ptype = FIX_LOSS[args.platform]
        print(f"=== injecting {name} = {value}")
        conn.mav.param_set_send(
            conn.target_system, conn.target_component, name.encode(),
            float(value),
            getattr(mavutil.mavlink, f"MAV_PARAM_TYPE_{ptype}"))
        time.sleep(1.5)
        result["intervention"] = {"param": name, "value": value,
                                  "type": ptype}

        print(f"=== {LOSS_S:.0f} s under fix loss")
        loss_rows = []
        _capture(conn, LOSS_S, loss_rows)
        result["fix_loss_whole_window"] = _summarise(loss_rows, LOSS_S)

        # PARTITION BY EACH MESSAGE'S OWN fix_type. The wall-clock window
        # straddles the transition, so summarising it whole mixes valid
        # samples into the invalid-fix statistics and understates nothing
        # while overstating survival.
        invalid = [r for r in loss_rows
                   if r.get("fix_type") is not None and r["fix_type"] < 3]
        still_valid = [r for r in loss_rows
                       if r.get("fix_type") is not None and r["fix_type"] >= 3]
        span = ((invalid[-1]["_t"] - invalid[0]["_t"]) if len(invalid) > 1
                else None)
        result["invalid_fix_only"] = _summarise(invalid, span)
        result["still_valid_in_window"] = len(still_valid)
        # RULE B: the write is not the measurement. The window means nothing
        # unless the vehicle actually reported an invalid fix.
        result["rule_b"] = {
            "messages_with_invalid_fix": len(invalid),
            "messages_still_valid": len(still_valid),
            "invalid_observed": bool(invalid),
            "invalid_span_s": round(span, 2) if span else None}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()

    dest = args.out or os.path.join(
        ROOT, "research", "maer", f"raw_gnss_probe_{args.platform}.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1, sort_keys=True, default=str)
    for phase in ("nominal", "invalid_fix_only"):
        print(f"\n  --- {phase}")
        for msg, rec in sorted((result.get(phase) or {}).items()):
            print(f"    {msg}  {rec['count']} msgs  {rec['hz']} Hz")
    print(f"\n  RULE B: {result.get('rule_b')}")
    print(f"-> {os.path.relpath(dest, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
