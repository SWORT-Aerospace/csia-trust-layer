#!/usr/bin/env python3
"""Matrices that map the APPARATUS sweep onto the XSYS-001 structure, for a
pipeline dry run only. Nothing here is confirmatory.

  nuisance condition  apparatus repeat r1..r3
  A flights           sweep_eta{090,080,070,060,050}_r{r}   (the apparatus levels)
  NB flight           sweep_eta100_r{r}; the apparatus set an UNCHANGED value
                      at onset, which publishes no parameter_update, so t0 is
                      taken from the driver's send time (dry run only)
"""
import csv
import json
import sys
from pathlib import Path

LEVELS = (0.90, 0.80, 0.70, 0.60, 0.50)


def main():
    runs, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    flights, analysis = [], []
    for r in (1, 2, 3):
        cid = f"R{r}"
        nb = f"sweep_eta100_r{r}"
        js = json.loads((runs / f"{nb}.json").read_text())
        flights.append({"flight_id": nb, "condition": "NB", "eta": "1.00", "heading_deg": "0.0",
                        "dry_run_t0_from_driver_ms": str(js["events_ms"]["eta_set"][0])})
        analysis.append({"analysis_id": f"DRY-{cid}-N", "kind": "N", "source_flight_id": nb,
                         "matched_a_flight_id": "", "pair_id": "", "eta": "1.00", "nuisance_id": cid})
        for eta in LEVELS:
            e = f"{int(round(eta * 100)):03d}"
            fa = f"sweep_eta{e}_r{r}"
            flights.append({"flight_id": fa, "condition": "A", "eta": f"{eta:.2f}", "heading_deg": "0.0",
                            "dry_run_t0_from_driver_ms": ""})
            pid = f"DRY-{cid}-P-{e}"
            analysis.append({"analysis_id": f"DRY-{cid}-A-{e}", "kind": "A", "source_flight_id": fa,
                             "matched_a_flight_id": "", "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
            analysis.append({"analysis_id": f"DRY-{cid}-B-{e}", "kind": "B", "source_flight_id": nb,
                             "matched_a_flight_id": fa, "pair_id": pid, "eta": f"{eta:.2f}", "nuisance_id": cid})
    for name, rows in (("DRY_RUN_FLIGHT_MATRIX.csv", flights), ("DRY_RUN_ANALYSIS_MATRIX.csv", analysis)):
        with open(out / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(len(flights), "flights", len(analysis), "analysis trials")


if __name__ == "__main__":
    main()
