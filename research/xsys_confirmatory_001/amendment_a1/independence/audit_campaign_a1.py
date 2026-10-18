#!/usr/bin/env python3
"""XSYS-001-A1 preregistered independence audit of the CONFIRMATORY campaign.

Custodian side, report-only, outcome-blind. After the campaign, before or
beside stage 0, it re-checks criterion C1 (no shared noise draws between the
spans of different nuisance conditions, every lag) on the campaign's own
NOMINAL flights: the NB flight of each condition. It reads only the gyro
noise residual and the onset event of those flights, never an A flight,
never a CSIA output, never a label beyond the matrix.

Consequence (frozen in the amendment): the result is reported beside the
primary result. A failure is reported as a violation of the independence
assumption in the campaign. It does not exclude trials, re-run anything or
change the primary analysis.

Usage: audit_campaign_a1.py --flights <campaign dir> --out INDEPENDENCE_AUDIT_A1.json
"""
import argparse
import csv
import json
from itertools import combinations
from pathlib import Path

from pyulog import ULog

import independence_diagnostics as ID

A1 = ID.HERE.parent
TAU_MEM_S = json.loads((ID.HERE / "MEMORY.json").read_text())["DX6_memory"]["tau_mem_s"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flights", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(A1 / "FLIGHT_MATRIX_A1.csv")) if r["condition"] == "NB"]
    nb = {}
    missing = []
    for r in rows:
        p = Path(a.flights) / f"{r['flight_id']}.ulg"
        if not p.exists():
            missing.append(r["flight_id"])
            continue
        f = ID.Flight(p)
        ev = ID.XE.onset_time(ULog(str(p)), "SDLOG_DIRS_MAX")
        if ev is None:
            missing.append(r["flight_id"])
            continue
        f.t0_us = ev[1]
        nb[r["nuisance_id"]] = f
    pairs = {f"{x}|{y}": ID.identity_global(nb[x], nb[x].span_mask(nb[x].t0_us, TAU_MEM_S),
                                            nb[y], nb[y].span_mask(nb[y].t0_us, TAU_MEM_S))
             for x, y in combinations(sorted(nb), 2)}
    ok = all(v["I"] <= 0.001 for v in pairs.values())
    out = {"label": "XSYS-001-A1 INDEPENDENCE AUDIT - REPORT ONLY - OUTCOME-BLIND",
           "criterion": "C1: I(a,b) <= 0.001 for every pair of conditions (NB flights), spans extended back by tau_mem",
           "tau_mem_s": TAU_MEM_S, "conditions_audited": sorted(nb), "not_audited": missing,
           "pairs": pairs, "max_I": max((v["I"] for v in pairs.values()), default=None),
           "C1_holds_in_campaign": ok if pairs else None,
           "consequence": "reported beside the primary result; never an exclusion or a re-analysis"}
    Path(a.out).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print(json.dumps({k: out[k] for k in ("max_I", "C1_holds_in_campaign", "not_audited")}))


if __name__ == "__main__":
    main()
