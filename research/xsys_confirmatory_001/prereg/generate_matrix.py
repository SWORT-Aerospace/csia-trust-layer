#!/usr/bin/env python3
"""XSYS-001: generate the complete trial matrix and the execution order.

Deterministic from the constants below; rerunning it must reproduce the
committed CSV files byte for byte (tests/test_xsys_001_preregistration.py
checks this).

DESIGN
  fault levels      eta in {0.95, 0.85, 0.75, 0.65, 0.55}; motor 0 (SIH_MOT_EFF1)
  nuisance          11 conditions j = 0..10 (prereg/POWER.json: the smallest
                    count for which a pair resolution rate of 0.80 still
                    supports the primary hypothesis):
                      heading_j = 360 j / 11 degrees, to 0.001 (SIH_LOC_YAW0)
                      onset_j   = 30.0 s + 0.5 s * pi(j), pi a permutation of
                                  0..10 obtained by sorting j on
                                  SHA-256(SEED + "/offset/" + j)
  flights           per condition: 5 fault flights (A, one per level) and
                    1 nominal flight (NB, benign onset event) -> 66 flights
  analysis trials   per condition: 5 A, 5 B (each built from NB + the A of the
                    same level), 1 N (NB unmodified) -> 121
  order             all 66 flights sorted on SHA-256(SEED + "/order/" + flight_id)
"""
import csv
import hashlib
from pathlib import Path

SEED = "XSYS-001/2026-09-26"
LEVELS = (0.95, 0.85, 0.75, 0.65, 0.55)
N_CONDITIONS = 11
ONSET_BASE_S = 30.0
ONSET_STEP_S = 0.5
T_ARM_S = 10.0
T_END_AFTER_ONSET_S = 16.0
BENIGN = ("SDLOG_DIRS_MAX", 8)
WINDOWS = {"T0": (-5.0, 0.0), "T1": (0.0, 0.2), "T2": (0.2, 2.0), "T3": (10.0, 15.0)}
LOG_CONFIG = "research/px4_actuator_effectiveness/config/logger_topics.txt"

HERE = Path(__file__).resolve().parent


def h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def offsets():
    perm = sorted(range(N_CONDITIONS), key=lambda j: h(f"{SEED}/offset/{j}"))
    # perm[r] is the condition that receives rank r
    rank = {j: r for r, j in enumerate(perm)}
    return {j: ONSET_STEP_S * rank[j] for j in range(N_CONDITIONS)}


def build():
    off = offsets()
    flights, analysis = [], []
    for j in range(N_CONDITIONS):
        cid = f"C{j:02d}"
        hd = round(360.0 * j / N_CONDITIONS, 3)
        t_on = round(ONSET_BASE_S + off[j], 3)
        common = {"nuisance_id": cid, "heading_deg": f"{hd:.3f}", "onset_offset_s": f"{off[j]:.1f}",
                  "t_arm_s": f"{T_ARM_S:.1f}", "t_onset_s": f"{t_on:.3f}",
                  "t_end_s": f"{t_on + T_END_AFTER_ONSET_S:.3f}", "log_config": LOG_CONFIG,
                  **{f"{w}_abs_s": f"[{t_on + a:.3f}, {t_on + b:.3f})" for w, (a, b) in WINDOWS.items()}}
        nb = f"XS1-{cid}-NB"
        flights.append({"flight_id": nb, "condition": "NB", "eta": "1.00", "onset_param": BENIGN[0],
                        "onset_value": str(BENIGN[1]), **common})
        analysis.append({"analysis_id": f"XS1-{cid}-N", "kind": "N", "source_flight_id": nb,
                         "matched_a_flight_id": "", "pair_id": "", "eta": "1.00", "nuisance_id": cid})
        for eta in LEVELS:
            e = f"E{int(round(eta * 100)):03d}"
            fa, pid = f"XS1-{cid}-A-{e}", f"XS1-{cid}-P-{e}"
            flights.append({"flight_id": fa, "condition": "A", "eta": f"{eta:.2f}", "onset_param": "SIH_MOT_EFF1",
                            "onset_value": f"{eta:.2f}", **common})
            analysis.append({"analysis_id": f"XS1-{cid}-A-{e}", "kind": "A", "source_flight_id": fa,
                             "matched_a_flight_id": "", "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
            analysis.append({"analysis_id": f"XS1-{cid}-B-{e}", "kind": "B", "source_flight_id": nb,
                             "matched_a_flight_id": fa, "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
    order = sorted((f["flight_id"] for f in flights), key=lambda fid: h(f"{SEED}/order/{fid}"))
    return flights, analysis, order


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main():
    flights, analysis, order = build()
    write_csv(HERE / "FLIGHT_MATRIX.csv", flights)
    write_csv(HERE / "ANALYSIS_MATRIX.csv", analysis)
    write_csv(HERE / "EXECUTION_ORDER.csv",
              [{"position": i + 1, "flight_id": fid, "order_key_sha256": h(f"{SEED}/order/{fid}")}
               for i, fid in enumerate(order)])
    print(f"{len(flights)} flights, {len(analysis)} analysis trials, offsets {offsets()}")


if __name__ == "__main__":
    main()
