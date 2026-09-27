#!/usr/bin/env python3
"""XSYS-001-A1: the amended trial matrix and execution order.

Deterministic from the constants below; rerunning it must reproduce the
committed CSV files byte for byte (tests/test_xsys_001_a1_amendment.py).

WHAT THE AMENDMENT CHANGES: only how nuisance conditions are generated.

  XSYS-001   condition j = (heading_j, onset_j), onset_j = 30.0 + 0.5 rank_j s,
             arm at 10 s for every flight: the 11 analysis spans overlap in
             simulated time, and launches replay one noise stream in families
  XSYS-001-A1
             condition j = (heading_j, noise segment slot_j):
               heading_j  = 360 j / 11 deg (UNCHANGED)
               slot_j     = rank of j when 0..10 are sorted on
                            SHA-256(SEED_A1 + "/slot/" + j)
               arm_j      = 10 s + S x slot_j       (pre-arm dwell)
               onset_j    = arm_j + 20 s            (every flight: the apparatus timeline)
               end_j      = onset_j + 16 s
             so every condition's analysis span, extended back by the signal
             memory tau_mem, is a disjoint segment of the simulator's single
             noise stream: S = 20 s + tau_mem rounded up to 5 s
             (independence/MEMORY.json, rule frozen in DIAGNOSTIC_SPEC.json)

UNCHANGED: fault levels, motor, benign event, the A/NB flights of a
condition, the A/B/N analysis trials and the matched-pair rule.

  order     all 66 flights sorted on SHA-256(SEED_A1 + "/order/" + flight_id),
            a NEW seed because the design changed
"""
import csv
import hashlib
from pathlib import Path

SEED_A1 = "XSYS-001-A1/2026-09-27"
LEVELS = (0.95, 0.85, 0.75, 0.65, 0.55)          # unchanged
N_CONDITIONS = 11                                  # unchanged
T_FIRST_ARM_S = 10.0
S_SEPARATION_S = 25.0                              # independence/MEMORY.json separation.S_s
TAU_MEM_S = 0.332                                  # independence/MEMORY.json DX6_memory.tau_mem_s
ARM_TO_ONSET_S = 20.0
T_END_AFTER_ONSET_S = 16.0
BENIGN = ("SDLOG_DIRS_MAX", 8)                     # unchanged
WINDOWS = {"T0": (-5.0, 0.0), "T1": (0.0, 0.2), "T2": (0.2, 2.0), "T3": (10.0, 15.0)}   # unchanged
SPAN = (-5.0, 15.0)
LOG_CONFIG = "research/px4_actuator_effectiveness/config/logger_topics.txt"
PREFIX = "XS1A1"

HERE = Path(__file__).resolve().parent


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def slots():
    perm = sorted(range(N_CONDITIONS), key=lambda j: h(f"{SEED_A1}/slot/{j}"))
    return {j: r for r, j in enumerate(perm)}


def build():
    slot = slots()
    flights, analysis = [], []
    for j in range(N_CONDITIONS):
        cid = f"C{j:02d}"
        hd = round(360.0 * j / N_CONDITIONS, 3)
        t_arm = T_FIRST_ARM_S + S_SEPARATION_S * slot[j]
        t_on = t_arm + ARM_TO_ONSET_S
        common = {"nuisance_id": cid, "heading_deg": f"{hd:.3f}",
                  "noise_segment_id": f"SEG{slot[j]:02d}",
                  "noise_segment_sim_s": f"[{t_on + SPAN[0] - TAU_MEM_S:.3f}, {t_on + SPAN[1]:.3f})",
                  "t_arm_s": f"{t_arm:.1f}", "t_onset_s": f"{t_on:.3f}",
                  "t_end_s": f"{t_on + T_END_AFTER_ONSET_S:.3f}", "log_config": LOG_CONFIG,
                  **{f"{w}_abs_s": f"[{t_on + a:.3f}, {t_on + b:.3f})" for w, (a, b) in WINDOWS.items()}}
        nb = f"{PREFIX}-{cid}-NB"
        flights.append({"flight_id": nb, "condition": "NB", "eta": "1.00", "onset_param": BENIGN[0],
                        "onset_value": str(BENIGN[1]), **common})
        analysis.append({"analysis_id": f"{PREFIX}-{cid}-N", "kind": "N", "source_flight_id": nb,
                         "matched_a_flight_id": "", "pair_id": "", "eta": "1.00", "nuisance_id": cid})
        for eta in LEVELS:
            e = f"E{int(round(eta * 100)):03d}"
            fa, pid = f"{PREFIX}-{cid}-A-{e}", f"{PREFIX}-{cid}-P-{e}"
            flights.append({"flight_id": fa, "condition": "A", "eta": f"{eta:.2f}", "onset_param": "SIH_MOT_EFF1",
                            "onset_value": f"{eta:.2f}", **common})
            analysis.append({"analysis_id": f"{PREFIX}-{cid}-A-{e}", "kind": "A", "source_flight_id": fa,
                             "matched_a_flight_id": "", "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
            analysis.append({"analysis_id": f"{PREFIX}-{cid}-B-{e}", "kind": "B", "source_flight_id": nb,
                             "matched_a_flight_id": fa, "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
    order = sorted((f["flight_id"] for f in flights), key=lambda fid: h(f"{SEED_A1}/order/{fid}"))
    return flights, analysis, order


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    flights, analysis, order = build()
    write_csv(HERE / "FLIGHT_MATRIX_A1.csv", flights)
    write_csv(HERE / "ANALYSIS_MATRIX_A1.csv", analysis)
    write_csv(HERE / "EXECUTION_ORDER_A1.csv",
              [{"position": i + 1, "flight_id": fid, "order_key_sha256": h(f"{SEED_A1}/order/{fid}")}
               for i, fid in enumerate(order)])
    print(f"{len(flights)} flights, {len(analysis)} analysis trials, slots {slots()}")


if __name__ == "__main__":
    main()
