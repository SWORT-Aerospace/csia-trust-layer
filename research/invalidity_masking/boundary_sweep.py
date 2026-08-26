"""Where is the boundary, and does arrangement matter at fixed density?

NON_SCORED SYNTHETIC FIXTURE. The GPS validity schedule is programmed; the rest
of the telemetry is the real ArduPilot carrier from NON_SCORED_TEST_FIXTURE_M1
with every GPS_RAW_INT removed and replaced. The GPS payload is one genuinely
valid fix from that recording, held constant.

SCOPE, stated up front so no number here is read for more than it is worth.
This fixture measures THE GATE and nothing else. The source trace (facts
G1-G4) shows the gate is a function of which samples are accepted and when --
never of their values -- so a constant payload costs the gate measurement
nothing. It would make trust and posterior numbers meaningless, so this script
reports none; those come from the real recording in
invalid_message_gate_trace.py.

Writes:
  results/TEMPORAL_PATTERN_DEFINITIONS.json
  results/BOUNDARY_SWEEP_RESULTS.csv
  results/ARRANGEMENT_AT_FIXED_DENSITY.csv

  python research/invalidity_masking/boundary_sweep.py
"""

from __future__ import annotations

import bisect
import csv
import importlib.util
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

FIXTURE = os.path.join(ROOT, "research", "maer", "results", "scored", "raw",
                       "NON_SCORED_TEST_FIXTURE_M1.json.gz")
OUT = os.path.join(_HERE, "results")
ONSET_S = 12.0                    # well clear of the core's 3 s warm-up gate
TICK_S = 0.04                     # 25 Hz; the quantisation of last_t


def _load(name, fname):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = _load("_masking_harness", "masking_harness.py")
TAU = H.GPS_STALE_TIMEOUT_S


# ----------------------------------------------------------- patterns
def p0_all_valid():
    return lambda k, t: False


def p1_single_burst(d):
    return lambda k, t: ONSET_S <= t < ONSET_S + d


def p2_periodic_interleave(n_invalid, n_valid):
    period = n_invalid + n_valid

    def sched(k, t):
        if t < ONSET_S:
            return False
        return (k % period) < n_invalid
    return sched


def p3_random_dropout(p, seed):
    rng = random.Random(seed)
    draws = {}

    def sched(k, t):
        if t < ONSET_S:
            return False
        if k not in draws:
            draws[k] = rng.random() < p
        return draws[k]
    return sched


def p4_clustered_bursts(d, gap, count):
    windows = [(ONSET_S + i * (d + gap), ONSET_S + i * (d + gap) + d)
               for i in range(count)]

    def sched(k, t):
        return any(a <= t < b for a, b in windows)
    return sched


def p5_permanent():
    return lambda k, t: t >= ONSET_S


PATTERNS = {
    "P0_ALL_VALID": {
        "role": "NULL CONTROL. No observation is ever invalid, so nothing can "
                "be masked and the gate must never close.",
        "params": {},
        "factory": lambda: p0_all_valid(),
    },
    "P1_SINGLE_BURST": {
        "role": "One contiguous invalid interval of commanded duration d. The "
                "sweep varies d across the predicted boundary.",
        "params": {"d_s": "swept"},
        "factory": None,               # parameterised by the sweep
    },
    "P2_PERIODIC_INTERLEAVE": {
        "role": "n_invalid rejected messages for every n_valid accepted one, "
                "repeating. High invalid DENSITY, short invalid INTERVALS.",
        "params": {"n_invalid": 4, "n_valid": 1},
        "factory": lambda: p2_periodic_interleave(4, 1),
    },
    "P3_RANDOM_DROPOUT": {
        "role": "Each message independently invalid with probability p. Fixed "
                "seed, so the realised schedule is reproducible.",
        "params": {"p": 0.5, "seed": 20260826},
        "factory": lambda: p3_random_dropout(0.5, 20260826),
    },
    "P4_CLUSTERED_BURSTS": {
        "role": "Repeated invalid bursts, each shorter than the timeout, "
                "separated by a single accepted message.",
        "params": {"d_s": 0.4, "gap_s": 0.2, "count": 20},
        "factory": lambda: p4_clustered_bursts(0.4, 0.2, 20),
    },
    "P5_PERMANENT": {
        "role": "NULL CONTROL at the other extreme. Invalid from onset to the "
                "end of the recording: the gate MUST close, exactly one "
                "timeout after the last accepted sample.",
        "params": {},
        "factory": lambda: p5_permanent(),
    },
}


# ----------------------------------------------------------- model check
def model_prediction(rows, accepted_t):
    """Continuous-time retained-state model vs what the core actually did.

    Predicted: the gate is open at t iff an accepted sample exists at or before
    t and t - t_last_accepted <= TAU. Measured: `fresh_gps`.

    The core stamps a sample with the TICK it was handed over on, not the
    message receive time, so the two can disagree within one tick period around
    a transition. Disagreements are therefore reported with their distance to
    the nearest predicted transition rather than simply counted.
    """
    edges = []                       # predicted transition times
    for i, ta in enumerate(accepted_t):
        nxt = accepted_t[i + 1] if i + 1 < len(accepted_t) else float("inf")
        if ta + TAU < nxt:
            edges.append(ta + TAU)   # open -> closed
            edges.append(nxt)        # closed -> open (if finite)
    edges = [e for e in edges if e != float("inf")]
    edges.sort()

    agree = 0
    disagreements = []
    for r in rows:
        t = r["t"]
        i = bisect.bisect_right(accepted_t, t) - 1
        pred = 1.0 if (i >= 0 and t - accepted_t[i] <= TAU) else 0.0
        if pred == r["fresh_gps"]:
            agree += 1
        else:
            j = bisect.bisect_left(edges, t)
            near = min([abs(t - e) for e in edges[max(0, j - 1):j + 1]],
                       default=float("inf"))
            disagreements.append((t, pred, r["fresh_gps"], near))
    n = len(rows)
    far = [d for d in disagreements if d[3] > TICK_S + 1e-9]
    return {
        "n_ticks": n,
        "n_agree": agree,
        "agreement_fraction": round(agree / n, 6) if n else None,
        "n_disagree": len(disagreements),
        "n_disagree_beyond_one_tick_of_a_transition": len(far),
        "max_disagreement_distance_s": (
            round(max((d[3] for d in disagreements), default=0.0), 6)),
    }


# ----------------------------------------------------------- runner
def run_schedule(carrier, template, sched, hz):
    msgs = H.synth_stream(carrier, template, sched, hz=hz)
    out = H.replay(msgs, "DROP")
    rows = [r for r in out["rows"] if r["t"] >= ONSET_S]
    accepted_t = sorted(float(m["_t_recv"]) for m in msgs
                        if m.get("mavpackettype") == "GPS_RAW_INT"
                        and int(m.get("fix_type", 0) or 0) >= 3)
    inv = [r for r in rows if r["raw_obs_invalid"] == 1]
    masked = [r for r in inv if r["fresh_gps"] == 1.0]
    n_msgs = sum(1 for m in msgs if m.get("mavpackettype") == "GPS_RAW_INT"
                 and float(m["_t_recv"]) >= ONSET_S)
    n_inv_msgs = sum(1 for m in msgs
                     if m.get("mavpackettype") == "GPS_RAW_INT"
                     and float(m["_t_recv"]) >= ONSET_S
                     and int(m.get("fix_type", 0) or 0) < 3)
    gaps = [b - a for a, b in zip(accepted_t, accepted_t[1:]) if b >= ONSET_S]
    return {
        "gps_hz": hz,
        "n_gps_msgs_post_onset": n_msgs,
        "n_invalid_msgs_post_onset": n_inv_msgs,
        "invalid_message_density": (round(n_inv_msgs / n_msgs, 6)
                                    if n_msgs else None),
        "max_accepted_gap_s": round(max(gaps), 6) if gaps else None,
        "n_ticks_post_onset": len(rows),
        "n_ticks_last_obs_invalid": len(inv),
        "n_masked_ticks": len(masked),
        "masking_fraction": (round(len(masked) / len(inv), 6) if inv else None),
        "n_ticks_gate_closed": sum(1 for r in rows if r["fresh_gps"] == 0.0),
        "gate_closed_seconds": round(
            sum(1 for r in rows if r["fresh_gps"] == 0.0) * TICK_S, 6),
        "model": model_prediction(rows, accepted_t),
    }


def main() -> int:
    cap = H.load_fixture(FIXTURE)
    carrier, gps = H.carrier_and_gps(cap["messages"])
    template = next(m for m in gps if int(m.get("fix_type", 0) or 0) >= 3
                    and int(m.get("satellites_visible", 0) or 0) >= 10)
    print(f"  carrier: {len(carrier)} non-GPS messages from "
          f"{cap['meta']['tag']}; template fix_type="
          f"{template['fix_type']} sats={template['satellites_visible']}")

    os.makedirs(OUT, exist_ok=True)

    # ---- pattern definitions, emitted from the code that runs them -------
    defs = {
        "artifact": "TEMPORAL_PATTERN_DEFINITIONS",
        "fixture": "SYNTHETIC_VALIDITY_SCHEDULE over the "
                   f"{cap['meta']['tag']} non-GPS carrier",
        "onset_s": ONSET_S,
        "gps_stale_timeout_s": TAU,
        "tick_s": TICK_S,
        "scope": "gate only; payload is constant, so trust and posterior "
                 "numbers are not reported from this fixture",
        "patterns": {k: {"role": v["role"], "params": v["params"]}
                     for k, v in PATTERNS.items()},
    }
    with open(os.path.join(OUT, "TEMPORAL_PATTERN_DEFINITIONS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(defs, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # ---- the sweep -------------------------------------------------------
    rows = []
    for hz in (5.0, 50.0):
        p = 1.0 / hz
        for mult in (0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00):
            d = round(mult * TAU, 6)
            r = run_schedule(carrier, template, p1_single_burst(d), hz)
            # Continuous-time prediction for the masked fraction of the ticks
            # whose most recent observation is invalid, computed from the
            # REALISED gap between the bracketing accepted samples rather than
            # from the commanded duration: the schedule quantises the command
            # to message boundaries, and reporting against the command would
            # charge that quantisation to the model.
            g = r["max_accepted_gap_s"] or 0.0
            pred = (min(1.0, max(0.0, (TAU - p) / (g - p)))
                    if g > p else 1.0)
            r.update({"pattern": "P1_SINGLE_BURST",
                      "commanded_burst_s": d,
                      "burst_over_tau": mult,
                      "message_period_s": round(p, 6),
                      "predicted_masking_fraction": round(pred, 6)})
            rows.append(r)
            print(f"  P1 {hz:>5.1f} Hz d={d:.3f}s ({mult:.2f} tau): masked "
                  f"{r['masking_fraction']} (pred {pred:.6f})  gate closed "
                  f"{r['gate_closed_seconds']:.2f} s  model agree "
                  f"{r['model']['agreement_fraction']}")

    for name, spec in PATTERNS.items():
        if spec["factory"] is None:
            continue
        for hz in (5.0, 50.0):
            r = run_schedule(carrier, template, spec["factory"](), hz)
            r.update({"pattern": name, "commanded_burst_s": None,
                      "burst_over_tau": None,
                      "message_period_s": round(1.0 / hz, 6),
                      "predicted_masking_fraction": None})
            rows.append(r)
            print(f"  {name:<24} {hz:>5.1f} Hz: density "
                  f"{r['invalid_message_density']}  masked "
                  f"{r['masking_fraction']}  gate closed "
                  f"{r['gate_closed_seconds']:.2f} s  model agree "
                  f"{r['model']['agreement_fraction']}")

    flat = []
    for r in rows:
        f = {k: v for k, v in r.items() if k != "model"}
        for k, v in r["model"].items():
            f[f"model_{k}"] = v
        flat.append(f)
    order = ["pattern", "gps_hz", "message_period_s", "commanded_burst_s",
             "burst_over_tau", "n_gps_msgs_post_onset",
             "n_invalid_msgs_post_onset", "invalid_message_density",
             "max_accepted_gap_s", "n_ticks_post_onset",
             "n_ticks_last_obs_invalid", "n_masked_ticks", "masking_fraction",
             "predicted_masking_fraction", "n_ticks_gate_closed",
             "gate_closed_seconds"]
    order += [k for k in flat[0] if k not in order]
    with open(os.path.join(OUT, "BOUNDARY_SWEEP_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=order)
        w.writeheader()
        w.writerows(flat)

    # ---- arrangement at FIXED density ------------------------------------
    # H2. All three schedules invalidate the SAME NUMBER of messages out of the
    # same post-onset stream; only the arrangement moves. Indexing is by
    # message number rather than by time so the densities match exactly.
    hz = 5.0
    t_end = max(float(m["_t_recv"]) for m in carrier)
    k_onset = int(-(-ONSET_S * hz // 1))          # ceil
    n_post = int(t_end * hz) + 1 - k_onset
    n_invalid = int(round(0.40 * n_post))

    def _rel(k):
        return k - k_onset

    def one_burst(k, t):
        return 0 <= _rel(k) < n_invalid

    def clustered(k, t):
        return _rel(k) >= 0 and (_rel(k) % 10) < 4

    def interleaved(k, t):
        return _rel(k) >= 0 and (_rel(k) % 5) < 2

    arrangements = [
        ("ONE_CONTIGUOUS_BURST", one_burst),
        ("CLUSTERED_4_IN_10", clustered),
        ("INTERLEAVED_2_IN_5", interleaved),
    ]
    arows = []
    for label, sched in arrangements:
        r = run_schedule(carrier, template, sched, hz)
        r["arrangement"] = label
        arows.append(r)
        print(f"  arrangement {label:<22} density "
              f"{r['invalid_message_density']}  masked "
              f"{r['masking_fraction']}  gate closed "
              f"{r['gate_closed_seconds']:.2f} s")
    aflat = []
    for r in arows:
        f = {k: v for k, v in r.items() if k != "model"}
        for k, v in r["model"].items():
            f[f"model_{k}"] = v
        aflat.append(f)
    acols = ["arrangement"] + [k for k in aflat[0] if k != "arrangement"]
    with open(os.path.join(OUT, "ARRANGEMENT_AT_FIXED_DENSITY.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=acols)
        w.writeheader()
        w.writerows(aflat)

    print(f"  -> {os.path.relpath(OUT, ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
