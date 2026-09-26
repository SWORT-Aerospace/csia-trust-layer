#!/usr/bin/env python3
"""Which command sample drives each SIH rotor update, identified from the logs.

For every step in flight and every motor, the candidate commands are those
stamped at the step time, one step earlier and two steps earlier. A step is
IDENTIFIABLE when the candidates differ by more than 0.01 in command units, so
that the rotor equation u[k] = u[k-1] + (dt/tau)(eta c - u[k-1]) can tell them
apart; eta is 1 before the change and the set value after it, motor 1 only.
Reports how many identifiable updates used each command age: the transport
delay from COMMAND to PHYSICAL rotor state.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sihlog

ALPHA = 0.08


def tally(path):
    meta = json.loads(Path(path).with_suffix(".json").read_text())
    tr = sihlog.load(path)
    t, ct, C, U = tr.t_us, tr.raw["cmd_sim_t"], tr.raw["cmd_sim"], tr.s["u_rotor"]
    arm = sihlog.arm_time_us(tr)
    ch = sihlog.eta_change(tr)
    k1 = sihlog.first_step_after(tr, ch[0]) if ch else len(t)
    eta = ch[1] if ch else 1.0
    idx = {int(s): i for i, s in enumerate(ct)}
    out = {0: 0, 4000: 0, 8000: 0}
    for k in range(1, len(t)):
        if t[k] < arm + 1_000_000 or U[k - 1].max() <= 0:
            continue
        cand = {dly: idx.get(int(t[k] - dly)) for dly in out}
        cand = {dly: j for dly, j in cand.items() if j is not None}
        if len(cand) < 2:
            continue
        for m in range(4):
            e = eta if (k >= k1 and m == 0) else 1.0
            vals = {dly: C[j, m] for dly, j in cand.items()}
            if max(vals.values()) - min(vals.values()) < 0.01:
                continue
            err = {dly: abs(U[k, m] - (U[k - 1, m] + ALPHA * (e * v - U[k - 1, m]))) for dly, v in vals.items()}
            out[min(err, key=err.get)] += 1
    return {"name": Path(path).stem, "eta": meta["eta"], "command_age_us_counts": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ulogs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = [tally(p) for p in a.ulogs]
    tot = {k: sum(r["command_age_us_counts"][k] for r in rows) for k in (0, 4000, 8000)}
    n = sum(tot.values())
    res = {"total_identifiable_updates": n, "by_command_age_us": tot,
           "fraction": {k: v / n for k, v in tot.items()}, "per_trial": rows}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("total_identifiable_updates", "by_command_age_us", "fraction")}, indent=1))


if __name__ == "__main__":
    main()
