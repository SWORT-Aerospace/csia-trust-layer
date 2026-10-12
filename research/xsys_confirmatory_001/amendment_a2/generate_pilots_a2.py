#!/usr/bin/env python3
"""XSYS-001-A2: the fresh NOMINAL-ONLY validation pilot matrix (frozen before any
A2 pilot is flown). Deterministic; rerunning reproduces PILOT_MATRIX_A2.csv.

REFERENCE  two long nominal hovers, the Q1 protocol of A1: arm 10 s, benign
           SDLOG_DIRS_MAX event at 30 s, end 400 s. Spans for the independent
           reference: t0 = arm + 20 s + 25 s x k, k = 0..14.
CANDIDATE  eight nominal flights flown EXACTLY as the A1 segmentation schedules a
           condition: arm = 10 s + 25 s x slot, onset (benign event) = arm + 20 s,
           end = onset + 16 s. Slots include adjacent pairs and both extremes.
Headings are quarter-steps of the confirmatory set (360 j / 44 deg) that are neither
confirmatory headings (multiples of 360/11) nor A1 pilot headings, so no
confirmatory condition tuple and no A1 pilot is reproduced.
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
Q = 360.0 / 44.0                                   # quarter-step, 8.182 deg
REFERENCE = [("A2P-R1-REFHOVER", 1), ("A2P-R2-REFHOVER", 23)]          # 8.182, 188.182 deg
CANDIDATES = [(0, 22), (1, 26), (2, 30), (3, 34), (5, 38), (7, 42), (9, 3), (10, 7)]
# (slot, quarter-step index): 180.000 212.727 245.455 278.182 310.909 343.636 24.545 57.273 deg


def rows():
    out = []
    for pid, q in REFERENCE:
        out.append({"pilot_id": f"{pid}-H{round(q * Q):03d}", "role": "REFERENCE", "heading_deg": f"{q * Q:.3f}",
                    "slot": "", "t_arm_s": "10.0", "t_onset_s": "30.000", "t_end_s": "400.000",
                    "onset_param": "SDLOG_DIRS_MAX", "onset_value": "8"})
    for i, (slot, q) in enumerate(CANDIDATES, 1):
        arm = 10.0 + 25.0 * slot
        out.append({"pilot_id": f"A2P-D{i}-SLOT{slot:02d}-H{round(q * Q):03d}", "role": "CANDIDATE",
                    "heading_deg": f"{q * Q:.3f}", "slot": str(slot), "t_arm_s": f"{arm:.1f}",
                    "t_onset_s": f"{arm + 20.0:.3f}", "t_end_s": f"{arm + 36.0:.3f}",
                    "onset_param": "SDLOG_DIRS_MAX", "onset_value": "8"})
    return out


def main():
    r = rows()
    with open(HERE / "PILOT_MATRIX_A2.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(r[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(r)
    print(len(r), "pilot flights")


if __name__ == "__main__":
    main()
