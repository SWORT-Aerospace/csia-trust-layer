"""Phase 4 campaign — detector alarm times over the declared threshold grids.

ONE PASS PER RUN, EVERY THRESHOLD FROM IT
------------------------------------------
Each run produces one series. All three detectors' statistics are functions
of that series alone, and every threshold in every declared grid is then read
off it: the CUSUM statistic S evolves independently of `h`, trust
independently of θ, and λ independently of τ. So the campaign stores, per
run, the first alarm time for each threshold -- and nothing is recomputed per
threshold.

**Phase 4 measures detector performance and nothing else.** No action, no
policy, no failsafe level and no vehicle outcome appears anywhere in it.

**Nothing flew. Nothing was armed. Nothing was commanded.**

    python research/phase4/campaign4.py --partition development
    python research/phase4/campaign4.py --partition locked \
        --i-am-opening-the-locked-partition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from csia.prediction import PredictionComparator  # noqa: E402
from csia.runtime.failsafe import FailsafeConfig  # noqa: E402
from csia.sensors import (GPS, IMU, Barometer, Battery, Fault,  # noqa: E402
                          Magnetometer, MotorESC, VibrationSensor,
                          generate_flight)
from csia.trust_engine import TrustEngine  # noqa: E402
from csia.trust_graph import build_trust_graph  # noqa: E402
from csia.v1_1.sequential import (CUSUM_K, GATE_EPS,  # noqa: E402
                                  IN_CONTROL, CusumBank)

from csia_consequence import phase4_partitions as parts  # noqa: E402

NODE = "vibration"
DURATION = 60.0
TICK_HZ = 25.0
SETTLE_S = float(FailsafeConfig().arm_time)      # 10.0
DWELL_TICKS = 25                                  # 1.0 s at 25 Hz

#: Declared grids, iterated in declaration order. Never sorted or pruned.
THETA_GRID = [0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.40,
              0.30, 0.20]
H_GRID = [5.0, 10.0, 25.0, 50.0, 100.0, 200.0, 300.0, 500.0, 750.0, 1000.0]
SIGMA_MULTIPLES = [1, 2, 3, 4, 5, 6, 8, 10]

GAIN_GRID = [1.5, 2.0, 2.5, 3.0, 4.0]
ONSET_GRID = [20.0, 25.0, 30.0, 35.0]
FAULT_DURATION_S = 20.0

MU0, SIGMA0 = IN_CONTROL[NODE]
TAU_GRID = [round(MU0 + m * SIGMA0, 9) for m in SIGMA_MULTIPLES]


def _sensors(seed: int) -> dict:
    def s(offset: int) -> int:
        return (seed + offset * 7919) % (2 ** 31 - 1)
    return {"imu0": IMU("imu0", seed=s(1)), "imu1": IMU("imu1", seed=s(2)),
            "baro": Barometer(seed=s(3)), "mag": Magnetometer(seed=s(4)),
            "gps": GPS(seed=s(5)), "motor_esc": MotorESC(seed=s(6)),
            "battery": Battery(seed=s(7)), "vibration": VibrationSensor(seed=s(8))}


def series(seed: int, faults) -> dict:
    truth = generate_flight(duration=DURATION, dt=0.01)
    streams = {n: s.sample(truth, faults) for n, s in _sensors(seed).items()}
    td = PredictionComparator(tick_hz=TICK_HZ).build(streams, DURATION)
    hist = TrustEngine(build_trust_graph()).run(td)
    lam, gate = td.physics[NODE]
    return {"t": np.asarray(td.t, dtype=float),
            "lam": np.asarray(lam, dtype=float),
            "gate": np.asarray(gate, dtype=float),
            "trust": np.asarray(hist.trust[:, hist.col(NODE)], dtype=float)}


def _first_and_after(times, onset):
    """Three alarm times, because no one of them answers every question.

    `first`        the first alarm at all.
    `after_settle` the first alarm at or after SETTLE_S. This is what a false
                   alarm is measured from, and the distinction is not
                   cosmetic: the CUSUM statistic is non-decreasing while a
                   drift persists, so at h = 5 it crosses at 4.92 s and STAYS
                   above h for the whole flight. Measuring false alarms from
                   `first` alone would score that detector as having no false
                   alarm in the horizon, which is the opposite of the truth.
                   Found on a development run, before the locked partition
                   was opened.
    `after_onset`  the first alarm at or after the fault onset, which is the
                   only one a detection delay may be computed from. On a
                   FAULTED run an alarm before the onset is a false alarm,
                   not a detection with negative delay.
    """
    first = float(times[0]) if len(times) else None
    later_settle = [x for x in times if x >= SETTLE_S]
    after_settle = float(later_settle[0]) if later_settle else None
    after = None
    if onset is not None:
        later = [x for x in times if x >= onset]
        after = float(later[0]) if later else None
    return first, after_settle, after


def csia_alarms(s: dict, onset) -> dict:
    """Alarm times per θ. Persistence counted over ACTIVE ticks only.

    A persistence detector latches at the tick the run-length condition is
    met; the counter then resets so a later episode is a separate alarm.
    """
    t, trust, gate = s["t"], s["trust"], s["gate"]
    out = {}
    for theta in THETA_GRID:
        run, times = 0, []
        for k in range(len(t)):
            if gate[k] <= GATE_EPS:
                continue
            if trust[k] < theta:
                run += 1
                if run >= DWELL_TICKS:
                    times.append(float(t[k]))
                    run = 0
            else:
                run = 0
        first, after_settle, after = _first_and_after(times, onset)
        out[repr(theta)] = {"first": first, "after_settle": after_settle,
                            "after_onset": after}
    return out


def cusum_alarms(s: dict, onset) -> tuple:
    """First alarm time per h, from ONE pass of the statistic.

    `CusumBank.update` advances S without reference to h, so the whole grid
    is read from a single S series. The bank is still used for the update
    itself, so the arithmetic is the repository's and not a copy.
    """
    t, lam, gate = s["t"], s["lam"], s["gate"]
    bank = CusumBank(k=CUSUM_K, h=float("inf"))
    S = np.empty(len(t), dtype=float)
    for k in range(len(t)):
        bank.update(NODE, float(lam[k]), bool(gate[k] > GATE_EPS))
        S[k] = bank.S[NODE]
    out = {}
    for h in H_GRID:
        times = t[np.nonzero(S > h)[0]]
        first, after_settle, after = _first_and_after(times, onset)
        out[repr(h)] = {"first": first, "after_settle": after_settle,
                        "after_onset": after}
    return out, S


def binst_alarms(s: dict, onset) -> dict:
    t, lam, gate = s["t"], s["lam"], s["gate"]
    active = gate > GATE_EPS
    out = {}
    for tau in TAU_GRID:
        times = t[np.nonzero(active & (lam > tau))[0]]
        first, after_settle, after = _first_and_after(times, onset)
        out[repr(tau)] = {"first": first, "after_settle": after_settle,
                          "after_onset": after}
    return out


def run_one(seed: int, gain, onset) -> dict:
    """One flight, all three detectors, every declared threshold.

    TIMING IS PER DETECTOR, because that is what was preregistered. The
    series build is timed separately and is SHARED: all three detectors read
    the same `lam`, `gate` and `trust`, so charging it to any one of them
    would be arbitrary. Each detector's own figure covers its full threshold
    grid, which is 12 thresholds for CSIA, 10 for CUSUM and 8 for the bare
    threshold -- so `ns_cusum` is not the cost of one CUSUM, and the write-up
    divides where a per-threshold figure is meant.
    """
    faults = ([] if gain is None else
              [Fault("vibration_anomaly", NODE, onset, FAULT_DURATION_S,
                     {"gain": gain})])
    t0 = time.perf_counter_ns()
    s = series(seed, faults)
    t1 = time.perf_counter_ns()
    cusum, S = cusum_alarms(s, onset)
    t2 = time.perf_counter_ns()
    csia = csia_alarms(s, onset)
    t3 = time.perf_counter_ns()
    binst = binst_alarms(s, onset)
    t4 = time.perf_counter_ns()
    return {
        "seed": seed, "gain": gain, "onset_s": onset,
        "nominal": gain is None,
        "ticks": int(len(s["t"])),
        "alarms": {"CSIA": csia, "CUSUM": cusum, "BINST": binst},
        "cusum_max": round(float(S.max()), 4),
        "trust_min": round(float(s["trust"].min()), 6),
        "active_ticks": int((s["gate"] > GATE_EPS).sum()),
        "ns_series_shared": int(t1 - t0),
        "ns_cusum": int(t2 - t1),
        "ns_csia": int(t3 - t2),
        "ns_binst": int(t4 - t3),
        "ns_total": int(t4 - t0),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partition", default="development")
    ap.add_argument("--i-am-opening-the-locked-partition", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    seeds = parts.seeds(
        args.partition,
        i_am_opening_the_locked_partition=args.i_am_opening_the_locked_partition)
    if args.limit:
        seeds = seeds[:args.limit]

    runs = []
    for seed in seeds:
        runs.append(run_one(seed, None, None))          # nominal
        for gain in GAIN_GRID:                          # declaration order
            for onset in ONSET_GRID:                    # exhaustive
                runs.append(run_one(seed, gain, onset))
        print(f"  seed={seed}", flush=True)

    document = {
        "schema": "csia.phase4.detector_runs/1",
        "phase": "4 -- detector performance",
        "measures": "detector delay and false alarms only; no action, no "
                    "policy, no failsafe level, no vehicle outcome",
        "partition": args.partition,
        "partition_manifest_hash": parts.manifest_hash(),
        "seeds": list(seeds),
        "node": NODE,
        "evidence_level": "DETERMINISTIC_SIMULATION",
        "executed_an_autopilot": False, "armed_a_vehicle": False,
        "touched_hardware": False,
        "pooled_with_consequence_phases": False,
        "settle_s": SETTLE_S, "horizon_s": DURATION, "tick_hz": TICK_HZ,
        "dwell_ticks": DWELL_TICKS,
        "grids": {"CSIA": THETA_GRID, "CUSUM": H_GRID, "BINST": TAU_GRID},
        "grid_order": "declaration order; never sorted, pruned or interpolated",
        "sigma_multiples": SIGMA_MULTIPLES,
        "in_control": {"node": NODE, "mu0": MU0, "sigma0": SIGMA0,
                       "source": "csia/v1_1/sequential.py IN_CONTROL"},
        "cusum_k": CUSUM_K,
        #: Everything else in this document is a deterministic function of
        #: the seed. `ns_total` is a wall-clock measurement and is not: two
        #: passes over the same partition agree on every alarm time and
        #: differ only here. A replay check that demands byte-identity would
        #: therefore always fail, so the fields that may legitimately differ
        #: are DECLARED here and `replay_check4.py` excludes exactly these.
        "environment_specific_fields": [
            "runs[].ns_total", "runs[].ns_series_shared", "runs[].ns_cusum",
            "runs[].ns_csia", "runs[].ns_binst"],
        "timing_note": (
            "per-detector nanoseconds cover that detector's FULL declared "
            "threshold grid on one flight; the series build is shared by all "
            "three and is reported separately rather than charged to one"),
        "fault": {"kind": "vibration_anomaly", "node": NODE,
                  "gain_grid": GAIN_GRID, "onset_grid": ONSET_GRID,
                  "duration_s": FAULT_DURATION_S,
                  "onsets_are_exhaustive_not_sampled": True},
        "runs": runs,
    }
    out = args.out or os.path.join(
        ROOT, "research", "phase4", "results",
        f"PHASE4_RUNS_{args.partition.upper()}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"\nwrote {os.path.relpath(out, ROOT)}  ({len(runs)} runs, sha256 "
          f"{hashlib.sha256(text.encode()).hexdigest()[:16]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
