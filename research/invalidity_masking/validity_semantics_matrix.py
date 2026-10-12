"""What each layer can say about three different facts, on each ingest path.

The three facts a GPS receiver can present, which are NOT the same fact:

  OBSERVED_VALID    a message arrived and reported a 3D fix
  OBSERVED_INVALID  a message arrived and reported it has no fix
  NOT_OBSERVED      no message arrived at all

Every cell cites a fact_id from SOURCE_TO_GATE_TRACE.json; the script refuses
to emit the matrix if a cited fact is not in that file, so the matrix cannot
drift away from the verified source.

The matrix's central claim -- that OBSERVED_INVALID and NOT_OBSERVED become
the same thing at the core slot on the deployed path -- is then TESTED rather
than asserted, by replaying two streams that differ only in whether the
invalid messages are present at all.

Writes:
  results/VALIDITY_SEMANTICS_MATRIX.csv
  results/INDISTINGUISHABILITY_CHECK.json

  python research/invalidity_masking/validity_semantics_matrix.py
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUT = os.path.join(_HERE, "results")
TRACE = os.path.join(OUT, "SOURCE_TO_GATE_TRACE.json")
FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
ONSET_S = 12.0


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", "masking_harness.py")

# path, layer, raw_fact, what that layer holds, distinguishable_from, cites
MATRIX = [
    # ---------------- v1.1 aircraft adapter: the deployed path ----------
    ("v1_1_AIRCRAFT_ADAPTER", "L1_PROTOCOL", "OBSERVED_VALID",
     "GPS_RAW_INT with fix_type >= 3", "all three", "P1_FIX_TYPE_READ"),
    ("v1_1_AIRCRAFT_ADAPTER", "L1_PROTOCOL", "OBSERVED_INVALID",
     "GPS_RAW_INT with fix_type < 3", "all three", "P2_INVALID_PREDICATE"),
    ("v1_1_AIRCRAFT_ADAPTER", "L1_PROTOCOL", "NOT_OBSERVED",
     "no GPS_RAW_INT on the link", "all three", "P1_FIX_TYPE_READ"),

    ("v1_1_AIRCRAFT_ADAPTER", "L2_ADAPTER", "OBSERVED_VALID",
     "gnss.position/velocity present in _latest, usable",
     "all three", "H3_GPS_CORE_MAP"),
    ("v1_1_AIRCRAFT_ADAPTER", "L2_ADAPTER", "OBSERVED_INVALID",
     "channels DELETED from _latest; _sentinel_at records NO_3D_FIX and "
     "sentinel_counts increments",
     "all three -- the adapter DOES keep the distinction",
     "A1_FORGET_POSITION;A3_REJECT_REASON"),
    ("v1_1_AIRCRAFT_ADAPTER", "L2_ADAPTER", "NOT_OBSERVED",
     "channels absent from _latest with no sentinel record; ages out to "
     "MissingReason.STALE or NOT_RECEIVED",
     "all three", "H1_ALL_CHANNELS_REQUIRED"),

    ("v1_1_AIRCRAFT_ADAPTER", "L3_CORE_HANDOFF", "OBSERVED_VALID",
     "one core sample ('gps', t, {..., valid: True})",
     "valid vs the other two", "H2_VALID_IS_HARDCODED_TRUE"),
    ("v1_1_AIRCRAFT_ADAPTER", "L3_CORE_HANDOFF", "OBSERVED_INVALID",
     "NO core sample is emitted",
     "NOT distinguishable from NOT_OBSERVED",
     "H1_ALL_CHANNELS_REQUIRED;H3_GPS_CORE_MAP"),
    ("v1_1_AIRCRAFT_ADAPTER", "L3_CORE_HANDOFF", "NOT_OBSERVED",
     "NO core sample is emitted",
     "NOT distinguishable from OBSERVED_INVALID",
     "H1_ALL_CHANNELS_REQUIRED"),

    ("v1_1_AIRCRAFT_ADAPTER", "L4_CORE_SLOT", "OBSERVED_VALID",
     "valid=True, seen=True, last_t=tick time, latest updated",
     "valid vs the other two", "C4_APPLY_SETS_SEEN;C5_APPLY_SETS_LAST_T;"
     "C6_APPLY_SETS_VALID"),
    ("v1_1_AIRCRAFT_ADAPTER", "L4_CORE_SLOT", "OBSERVED_INVALID",
     "UNCHANGED: valid stays True, last_t stays at the last accepted sample",
     "NOT distinguishable from NOT_OBSERVED", "C6_APPLY_SETS_VALID"),
    ("v1_1_AIRCRAFT_ADAPTER", "L4_CORE_SLOT", "NOT_OBSERVED",
     "UNCHANGED: valid stays True, last_t stays at the last accepted sample",
     "NOT distinguishable from OBSERVED_INVALID", "C6_APPLY_SETS_VALID"),

    ("v1_1_AIRCRAFT_ADAPTER", "L5_GATE", "OBSERVED_VALID",
     "gvalid=1, fresh=1", "valid vs a LONG absence only",
     "G1_GVALID_HAS_NO_STALENESS;G2_FRESH_HAS_STALENESS"),
    ("v1_1_AIRCRAFT_ADAPTER", "L5_GATE", "OBSERVED_INVALID",
     "gvalid=1 always; fresh=1 until 0.5 s after the last ACCEPTED sample",
     "NOT distinguishable from NOT_OBSERVED, and not distinguishable from "
     "OBSERVED_VALID at all within the timeout",
     "G1_GVALID_HAS_NO_STALENESS;G2_FRESH_HAS_STALENESS;G5_GPS_TIMEOUT_VALUE"),
    ("v1_1_AIRCRAFT_ADAPTER", "L5_GATE", "NOT_OBSERVED",
     "gvalid=1 always; fresh=1 until 0.5 s after the last ACCEPTED sample",
     "NOT distinguishable from OBSERVED_INVALID",
     "G1_GVALID_HAS_NO_STALENESS;G2_FRESH_HAS_STALENESS"),

    # ---------------- v1 live MAVLink path -------------------------------
    ("v1_MAVLINK_PLUGIN", "L3_CORE_HANDOFF", "OBSERVED_VALID",
     "one core sample with valid=True", "all three",
     "X2_V1_MAVLINK_INVALID_PREDICATE"),
    ("v1_MAVLINK_PLUGIN", "L3_CORE_HANDOFF", "OBSERVED_INVALID",
     "one core sample with valid=False and ZERO pos/vel",
     "all three", "X1_V1_MAVLINK_PROPAGATES_INVALID;X3_V1_MAVLINK_ZERO_PAYLOAD"),
    ("v1_MAVLINK_PLUGIN", "L3_CORE_HANDOFF", "NOT_OBSERVED",
     "no core sample", "all three", "X1_V1_MAVLINK_PROPAGATES_INVALID"),
    ("v1_MAVLINK_PLUGIN", "L4_CORE_SLOT", "OBSERVED_INVALID",
     "valid=False, last_t ADVANCES, and the step detector plus the Holt "
     "filters are fed the zeros before any validity gate is consulted",
     "all three, but at the cost of injecting a fictitious position step",
     "C6_APPLY_SETS_VALID;S1_STEP_PEAK_UNCONDITIONAL;S2_HIST_FED_UNCONDITIONAL;"
     "S3_GPS_IN_HIST_CHANNELS"),
    ("v1_MAVLINK_PLUGIN", "L5_GATE", "OBSERVED_INVALID",
     "gvalid=0 on the NEXT tick; no timeout involved",
     "all three", "G1_GVALID_HAS_NO_STALENESS"),

    # ---------------- v1 ULog replay path --------------------------------
    ("v1_ULOG_SOURCE", "L3_CORE_HANDOFF", "OBSERVED_INVALID",
     "one core sample with valid = (fix_type >= 3) and the REAL pos/vel",
     "all three", "X4_ULOG_PROPAGATES_INVALID"),
    ("v1_ULOG_SOURCE", "L5_GATE", "OBSERVED_INVALID",
     "gvalid=0 on the NEXT tick; no timeout involved",
     "all three", "G1_GVALID_HAS_NO_STALENESS;C6_APPLY_SETS_VALID"),
]

COLS = ["ingest_path", "layer", "raw_fact", "what_that_layer_holds",
        "distinguishable_from", "cites"]


def indistinguishability_check(messages):
    """Test the matrix's central claim instead of asserting it.

    Stream A: GPS messages keep arriving, all invalid from onset.
    Stream B: GPS messages simply stop at onset.

    On the deployed path the core should see EXACTLY the same thing. If the
    per-tick rows differ anywhere, the claim is false and this reports where.
    """
    carrier, gps = H.carrier_and_gps(messages)
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)

    stream_a = H.synth_stream(carrier, template,
                              lambda k, t: t >= ONSET_S, hz=5.0)
    # same schedule, but the invalid messages are simply not delivered
    stream_b = [m for m in stream_a
                if not (m.get("mavpackettype") == "GPS_RAW_INT"
                        and int(m.get("fix_type", 0) or 0) < 3)]

    a = H.replay(stream_a, "DROP")["rows"]
    b = H.replay(stream_b, "DROP")["rows"]
    # `raw_obs_invalid` and `last_raw_fix_type` describe the INPUT, not the
    # core, so they are excluded: they differ by construction.
    keys = [k for k in a[0]
            if k not in ("raw_obs_invalid", "last_raw_fix_type",
                         "last_raw_obs_t")]
    same_len = len(a) == len(b)
    diffs = []
    for ra, rb in zip(a, b):
        for k in keys:
            if ra[k] != rb[k]:
                diffs.append({"t": ra["t"], "field": k,
                              "observed_invalid": ra[k], "not_observed": rb[k]})

    # and what the ADAPTER retained, which the hand-off did not pass on
    now = {"t": 0.0}
    ad_a = H.make_adapter("DROP", lambda: now["t"])
    for m in stream_a:
        now["t"] = float(m["_t_recv"])
        ad_a.ingest(m)
    now = {"t": 0.0}
    ad_b = H.make_adapter("DROP", lambda: now["t"])
    for m in stream_b:
        now["t"] = float(m["_t_recv"])
        ad_b.ingest(m)

    return {
        "claim": "on the deployed v1.1 path, OBSERVED_INVALID and "
                 "NOT_OBSERVED produce identical core state",
        "n_ticks_observed_invalid_stream": len(a),
        "n_ticks_not_observed_stream": len(b),
        "same_tick_count": same_len,
        "fields_compared": keys,
        "n_differing_cells": len(diffs),
        "first_differences": diffs[:10],
        "core_state_identical": same_len and not diffs,
        "adapter_retained_the_distinction": {
            "observed_invalid_sentinel_counts": ad_a.sentinel_counts(),
            "not_observed_sentinel_counts": ad_b.sentinel_counts(),
            "differ": ad_a.sentinel_counts() != ad_b.sentinel_counts(),
        },
    }


def main() -> int:
    with open(TRACE, encoding="utf-8") as fh:
        trace = json.load(fh)
    known = {f["fact_id"] for f in trace["facts"]}
    missing = set()
    for row in MATRIX:
        for fid in row[5].split(";"):
            if fid not in known:
                missing.add(fid)
    if missing:
        print("MATRIX CITES FACTS THAT ARE NOT IN THE VERIFIED TRACE:")
        for m in sorted(missing):
            print("  " + m)
        return 1

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "VALIDITY_SEMANTICS_MATRIX.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(COLS)
        w.writerows(MATRIX)
    print(f"  {len(MATRIX)} matrix cells, every citation resolved against "
          f"{len(known)} verified source facts")

    cap = H.load_fixture(FIXTURE)
    chk = indistinguishability_check(cap["messages"])
    with open(FIXTURE, "rb") as fh:
        chk["fixture_sha256"] = hashlib.sha256(fh.read()).hexdigest()
    chk["fixture"] = cap["meta"]["tag"]
    chk["note"] = ("SYNTHETIC_VALIDITY_SCHEDULE over the recording's non-GPS "
                   "carrier: the two streams must differ ONLY in whether the "
                   "invalid messages are delivered.")
    with open(os.path.join(OUT, "INDISTINGUISHABILITY_CHECK.json"), "w",
              encoding="utf-8") as fh:
        json.dump(chk, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"  core state identical: {chk['core_state_identical']} "
          f"({chk['n_differing_cells']} differing cells over "
          f"{chk['n_ticks_observed_invalid_stream']} ticks x "
          f"{len(chk['fields_compared'])} fields)")
    print(f"  adapter retained the distinction: "
          f"{chk['adapter_retained_the_distinction']['differ']}")
    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
