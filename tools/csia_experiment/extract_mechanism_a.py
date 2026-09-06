"""Extract the preregistered Mechanism A quantities from a campaign's logs.

PREREGISTERED IN section 5 of
    research/physical_validation/prereg/MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md

Six quantities, and NOTHING ELSE MAY BE REPORTED AS A RESULT:

  1. gps_gate_weight_sum before and after onset
  2. the trust coefficient of `gps` before and after onset
  3. the rank of the nominal hypothesis, and of gps_fault, at onset and after
  4. RULE-B tick count
  5. first_t -- the first tick at which the gate weight reaches zero
  6. the support/eligibility state IF AND ONLY IF the run records one

This module computes them from the flight logs and REPORTS WHAT IT COULD NOT
FIND rather than filling it in. Quantity 2 is the live case: the trust
coefficient is written per tick only when the driver is given `--trust-trace`,
and a campaign run without it has no trust series. That is reported as
`NOT_CAPTURED` with the reason, never as a number and never as absent.

WHICH EDGES COUNT AS "GPS GATES"
---------------------------------
Read from the frozen trust graph, not listed here: every edge with `gps` as an
endpoint, under the runtime's own edge identifiers -- so
`velocity_gps_doppler_0` and `_1` are two edges, which is what
csia/prediction/comparator.py computes and what appears in the Mechanism A
artifacts.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.capability import edge_id              # noqa: E402
from csia.trust_graph.graph import EDGES                  # noqa: E402

#: Every edge touching the gps node, by the identifier the runtime uses.
GPS_EDGES = tuple(sorted({
    edge_id(relation, (a, b))
    for a, b, relation, _d in EDGES if "gps" in (a, b)}))

NOT_CAPTURED = "NOT_CAPTURED"


def load_log(path: str):
    header, rows = None, []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if i == 0:
                header = obj
            else:
                rows.append(obj)
    return header, rows


def gate_weight_sum(row) -> float:
    """Sum of the WEIGHT half of each gps edge's [consistency, weight] pair."""
    gates = row.get("gates") or {}
    total = 0.0
    for name in GPS_EDGES:
        pair = gates.get(name)
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            total += float(pair[1])
    return total


def gnss_position_missing(row) -> bool:
    """The ORIGINAL campaign's intermediate quantity, and it is NOT the gate.

    research/v1_1/results/mechanism_a_ardupilot.json names it exactly:
    "gnss.position MISSING with NO_3D_FIX", first_t 12.043901, 450 ticks.

    The gate weight is a DIFFERENT quantity that follows it about a second
    later. Reporting one against the other as if they were the same number is
    the RULE-B failure this whole discipline exists to prevent, so both are
    extracted and both are named.
    """
    channels = ((row.get("canonical") or {}).get("channels") or {})
    entry = channels.get("gnss.position")
    if not isinstance(entry, dict):
        return False
    return entry.get("missing") is not None


def ranks(row) -> dict:
    d = (row.get("diagnosis") or {}).get("posterior") or {}
    if not d:
        return {}
    order = sorted(d, key=lambda h: (-d[h], h))
    return {h: i + 1 for i, h in enumerate(order)}


def extract(path: str, onset_s: float) -> dict:
    header, rows = load_log(path)
    if not rows:
        return {"log": os.path.basename(path), "error": "no tick rows"}

    # ONLY TICK ROWS. A flight log's last line carries no `t_mono`, and the
    # first version defaulted it to 0.0 -- which gave that row a hugely
    # negative relative time, swept it into the "before" bucket, and made it
    # `before[-1]`. Every "before" reading was therefore taken from a row with
    # no gates at all and came back 0.0 on BOTH arms, which read as the
    # mechanism being present before the injection. Caught by plotting the
    # series instead of trusting the summary.
    ticks = [r for r in rows if "t_mono" in r]
    if not ticks:
        return {"log": os.path.basename(path), "error": "no rows carry t_mono"}
    t0 = ticks[0]["t_mono"]

    def rel(row):
        return row["t_mono"] - t0

    # WINDOWS, NOT SINGLE TICKS. One tick either side of onset is a fragile
    # estimator of a quantity that is being claimed to have changed.
    before = [r for r in ticks if onset_s - 2.0 <= rel(r) < onset_s]
    after = [r for r in ticks if rel(r) >= onset_s + 2.0]
    # SEPARATE FROM THE SETTLED WINDOW. first_t and the RULE-B count must be
    # measured from the ONSET, not from the edge of the 2 s settling window --
    # measuring them over `after` reported the collapse at 14.00 s when the
    # series shows it at 13.04 s, i.e. it reported the window boundary as if
    # it were the measurement.
    post_onset = [r for r in ticks if rel(r) >= onset_s]
    rows = ticks

    out = {
        "log": os.path.basename(path),
        "flight_id": (header or {}).get("flight_id"),
        "autopilot_version": (header or {}).get("autopilot_version"),
        "frozen_core_tag": (header or {}).get("frozen_core_tag"),
        "ticks": len(rows),
        "onset_s": onset_s,
        "gps_edges_counted": list(GPS_EDGES),
    }

    # 1. gate weight sum, as the median over a 2 s window either side
    def median(values):
        vs = sorted(values)
        if not vs:
            return NOT_CAPTURED
        mid = len(vs) // 2
        return round(vs[mid] if len(vs) % 2 else (vs[mid - 1] + vs[mid]) / 2, 6)

    out["gps_gate_weight_sum_before"] = median(
        gate_weight_sum(r) for r in before)
    out["gps_gate_weight_sum_after"] = median(gate_weight_sum(r) for r in after)
    out["window_s"] = {"before": [onset_s - 2.0, onset_s],
                       "after": [onset_s + 2.0, round(rel(ticks[-1]), 3)]}
    out["n_before"] = len(before)
    out["n_after"] = len(after)

    # 5. first tick at which the gps gate weight reaches zero, after onset
    first_zero = next((round(rel(r), 6) for r in post_onset
                       if gate_weight_sum(r) == 0.0), None)
    out["first_t_gate_zero"] = first_zero
    out["first_t_note"] = ("seconds after CSIA started listening, measured "
                           "from the onset tick, not from the settling window")

    # 4. RULE-B: ticks over which the intermediate quantity is observed, i.e.
    #    ticks after onset with the gps gate weight at zero.
    out["rule_b_ticks"] = sum(1 for r in post_onset
                              if gate_weight_sum(r) == 0.0)
    out["post_onset_ticks"] = len(post_onset)

    # THE ORIGINAL CAMPAIGN'S INTERMEDIATE QUANTITY, extracted separately so
    # the two campaigns can be compared on the SAME quantity. The original
    # reports first_t 12.043901 and 450 ticks for gnss.position going MISSING;
    # that is not the gate-weight collapse and must not be set against it.
    out["first_t_gnss_position_missing"] = next(
        (round(rel(r), 6) for r in post_onset if gnss_position_missing(r)),
        None)
    out["gnss_position_missing_ticks"] = sum(
        1 for r in post_onset if gnss_position_missing(r))
    out["intermediate_quantities_note"] = (
        "TWO DISTINCT QUANTITIES. `gnss.position MISSING` is the canonical "
        "channel going away; `gps_gate_weight_sum == 0` is the diagnostic "
        "gate closing. The second follows the first. The original n=1 "
        "artifact reports the FIRST (first_t 12.043901, 450 ticks).")

    # 3. ranks
    out["ranks_before"] = ranks(before[-1]) if before else {}
    out["ranks_after"] = ranks(after[-1]) if after else {}

    # 2. trust -- ONLY if the run recorded it.
    trust_seen = any("trust" in r for r in rows[:50])
    out["trust_before"] = out["trust_after"] = NOT_CAPTURED
    out["trust_note"] = (
        "the per-tick trust coefficient is written only when the driver is "
        "given --trust-trace; this campaign was run without it, so there is "
        "no trust series to read. NOT inferred from anything else."
        if not trust_seen else None)

    # 6. support state -- recorded if present, NOT_RECORDED if not.
    out["support_state"] = "NOT_RECORDED"
    for row in rows:
        if "support" in row or "eligibility" in row:
            out["support_state"] = "PRESENT"
            break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--logs", default=os.path.join(
        ROOT, "logs", "shadow-sitl-ardupilot"))
    ap.add_argument("--campaign", default=os.path.join(
        ROOT, "campaigns", "physical_validation", "mechanism_a_repeat_ap"))
    ap.add_argument("--onset", type=float, default=12.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    # Match manifests to logs by flight_id: the manifest records it, the log
    # header carries it. Matching by filename order would silently pair a
    # FAULT trial with a CONTROL log.
    by_flight = {}
    for path in sorted(glob.glob(os.path.join(args.logs, "*.jsonl"))):
        try:
            header, _ = load_log(path)
        except (OSError, json.JSONDecodeError):
            continue
        if header and header.get("flight_id"):
            by_flight[header["flight_id"]] = path

    results, unmatched = [], []
    for manifest_path in sorted(glob.glob(os.path.join(args.campaign,
                                                       "MECHA-*.json"))):
        with open(manifest_path, encoding="utf-8") as fh:
            man = json.load(fh)
        record = man["record"]
        flight_id = record.get("measured_flight_id")
        log = by_flight.get(flight_id)
        if not log:
            unmatched.append({"trial": man["trial_id"],
                              "flight_id": flight_id,
                              "why": "no flight log with this flight_id"})
            continue
        row = extract(log, args.onset)
        row["trial_id"] = man["trial_id"]
        row["arm"] = record.get("arm")
        row["state"] = man["adjudication"]["state"]
        results.append(row)

    summary = {
        "schema": "csia.research.mechanism_a_repeat_quantities/1",
        "prereg": ("research/physical_validation/prereg/"
                   "MECHANISM_A_REPEATED_CURRENT_STACK_PREREG.md"),
        "gps_edges_counted": list(GPS_EDGES),
        "matched": len(results),
        "unmatched": unmatched,
        "unmatched_note": (
            "A trial whose flight log cannot be found contributes NOTHING. It "
            "is listed rather than dropped, because a denominator that "
            "silently shrinks to what was matchable is the defect the whole "
            "campaign discipline exists to prevent."),
        "trials": results,
    }
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
