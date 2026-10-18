#!/usr/bin/env python3
"""EXPLORATORY. XSYS-001 state-conditioned evidence validity (Part 50).

    .venv/bin/python research/csia_semantic_core_2_1_shadow/xsys_state_conditioned.py

NOT CONFIRMATORY. It does not alter, re-score or re-interpret the sealed
XSYS-001 result. It reads the committed blind inputs
(`research/xsys_001_confirmatory_campaign/stage1_inputs/blind/*.npz`), the
frozen calibration from the sealed STAGE1.json, and the sealed Stage 2 labels
(RESULTS.json) only to grade. It writes nothing but
XSYS_STATE_CONDITIONED_RESULTS.json.

The frozen feature functions (`research/xsys_confirmatory_001/pipeline/
xsys_features.py`) and the frozen adapter's `localize_subject` are imported
unchanged. The only addition is a set of sliding 0.2 s windows, placed in
the imported module's WINDOWS table in memory, so that the frozen statistics
can be computed at more times than the preregistered T1 and T3.

The question: could an OBSERVABLE controller state (the compensation
witness, from the allocator output) have said when the dynamics evidence
(W_DYN) stopped being admissible, better than the preregistered fixed rule?

At every evaluation time t (0.2 s to 15 s after onset, every 0.1 s), motor 0,
each trial is localized under four dynamics-validity rules:

    NO_VALIDITY   dynamics from the current 0.2 s window, always used
    FIXED_TIME    dynamics only from T1 = [0, 0.2) s (the preregistered rule);
                  the T1 value is kept for every later t
    STATE_0.2S    dynamics from the current window while every compensation
                  witness since onset, computed over the same 0.2 s windows,
                  has affirmed "not compensating" (True); from the first
                  window whose witness is False (compensating) or None (cannot
                  tell), no newer dynamics are admitted and the last
                  admissible value is kept. If the very first window is not
                  affirmed, the rule has no dynamics at all.
    STATE_1S      the same, with the compensation witness computed over the
                  trailing 1 s (or [0, t) before t = 1 s)

and two evidence sets:

    DYN_ONLY      local RPM symptom + dynamics: isolates the validity question
    WITH_CTRL     the same + compensation as evidence, from the trailing 1 s

The frozen witnesses were calibrated on the preregistered windows (T1 = 0.2 s
for dynamics, T3 = 5 s for compensation); applying the compensation witness
to shorter windows is outside its calibrated regime, which is part of what
this exploration measures. The frozen fixed-time pipeline (V3 at C3) is
reproduced as a check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PIPE = REPO / "research/xsys_confirmatory_001/pipeline"
CAMP = REPO / "research/xsys_001_confirmatory_campaign"
for p in (str(REPO), str(PIPE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import xsys_features as F  # noqa: E402
import xsys_v2_adapter as A  # noqa: E402

OUT = HERE / "XSYS_STATE_CONDITIONED_RESULTS.json"
STEP = 0.1
WIDTH = 0.2
LONG = 1.0
TIMES = [round(0.2 + STEP * k, 1) for k in range(int((15.0 - 0.2) / STEP) + 1)]
RULES = ("NO_VALIDITY", "FIXED_TIME", "STATE_0.2S", "STATE_1S")
EVIDENCE = ("DYN_ONLY", "WITH_CTRL")
TRUTH = {"PHYSICAL_ACTUATOR_DEGRADATION": A.H_ACT, "RPM_TELEMETRY_CORRUPTION": A.H_SEN}


def window_name(t_end, long=False):
    return f"{'L' if long else 'S'}{t_end:.1f}"


def install_windows():
    for t in TIMES:
        F.WINDOWS[window_name(t)] = (round(t - WIDTH, 6), t)
        F.WINDOWS[window_name(t, True)] = (round(max(0.0, t - LONG), 6), t)


def localize(rpm, dyn, ctrl, stats):
    recs = A.records_for("motor_0", rpm, dyn, ctrl, stats,
                         {"rpm": "S", "dyn": "S", "ctrl": "S"})
    loc = A.localize_subject(recs, "motor_0")
    return None if loc is None else (loc.verdict, tuple(loc.supported))


def grade(truth, out):
    if truth is None:
        return "NO_SYMPTOM_OK" if out is None else "SPURIOUS"
    if out is None:
        return "MISSED"
    verdict, sup = out
    if verdict == "SUPPORTED":
        return "CORRECT_UNIQUE" if sup == (truth,) else "WRONG"
    return "AMBIGUOUS"


def series(ob, cal):
    """Per evaluation time: the frozen statistics and witnesses, motor 0."""
    t = ob["t_rel"]
    rho, _ = F.rpm_ratio(ob["rpm_obs"][:, 0], ob["cmd_sim"][:, 0])
    ax = F.loss_axis(ob["rotor_px"][0], ob["rotor_py"][0])
    L1, ok1 = F.local_deficit(rho, ob["cmd_sim"][:, 0], t, "T1")
    D1, okd1 = F.dynamics_statistic(ob["gyro"], t, ax, "T1")
    dyn_t1 = F.dynamics_witness(D1, okd1, L1 if ok1 else float("nan"), cal)
    out = []
    for te in TIMES:
        w, wl = window_name(te), window_name(te, True)
        L, ok = F.local_deficit(rho, ob["cmd_sim"][:, 0], t, w)
        D, okd = F.dynamics_statistic(ob["gyro"], t, ax, w)
        C, okc = F.compensation_statistic(ob["cmd_alloc"], t, 0, w)
        Cl, okcl = F.compensation_statistic(ob["cmd_alloc"], t, 0, wl)
        Lg = L if ok else float("nan")
        out.append({"t": te, "L": L, "D": D, "C": C, "C_1s": Cl,
                    "rpm": F.rpm_witness(L, ok, cal["delta_rpm"]),
                    "dyn": F.dynamics_witness(D, okd, Lg, cal),
                    "ctrl_0.2s": F.compensation_witness(C, okc, Lg, cal),
                    "ctrl_1s": F.compensation_witness(Cl, okcl, Lg, cal)})
    return dyn_t1, out


def dyn_under(rule, dyn_t1, ser):
    """The dynamics value each rule admits, per evaluation time."""
    if rule == "NO_VALIDITY":
        return [x["dyn"] for x in ser]
    if rule == "FIXED_TIME":
        return [dyn_t1] * len(ser)
    key = "ctrl_0.2s" if rule == "STATE_0.2S" else "ctrl_1s"
    out, closed, last = [], False, None
    for x in ser:
        closed = closed or x[key] is not True
        if not closed:
            last = x["dyn"]
        out.append(last)
    return out


def main():
    install_windows()
    stage1 = json.loads((CAMP / "stage1/STAGE1.json").read_text())
    cal = stage1["calibration"]
    labels = json.loads((CAMP / "stage2/RESULTS.json").read_text())["trials"]
    by_oid = {v["opaque_id"]: v for v in labels.values()}
    cells = [(e, r) for e in EVIDENCE for r in RULES]
    tallies = {f"{e}/{r}": {t: {} for t in TIMES} for e, r in cells}
    per_trial = []
    reproduce_v3 = {"checked": 0, "matches": 0}
    for oid, lab in sorted(by_oid.items()):
        ob = dict(np.load(CAMP / "stage1_inputs/blind" / f"{oid}.npz"))
        truth = TRUTH.get(lab["truth"])
        dyn_t1, ser = series(ob, cal)
        row = {"opaque_id": oid, "kind": lab["kind"], "eta": lab["eta"], "dyn_T1": dyn_t1,
               "first_ctrl_false_0.2s": next((x["t"] for x in ser if x["ctrl_0.2s"] is False), None),
               "first_ctrl_false_1s": next((x["t"] for x in ser if x["ctrl_1s"] is False), None),
               "first_dynamics_nominal_s": next((x["t"] for x in ser if x["dyn"] is True), None),
               "wrong": {}, "correct_unique": {}}
        for e, r in cells:
            dyns = dyn_under(r, dyn_t1, ser)
            k = f"{e}/{r}"
            row["wrong"][k] = row["correct_unique"][k] = 0
            for x, dyn in zip(ser, dyns):
                ctrl = x["ctrl_1s"] if e == "WITH_CTRL" else None
                g = grade(truth, localize(x["rpm"], dyn, ctrl,
                                          {"L": x["L"], "D": x["D"], "C": x["C_1s"]}))
                tallies[k][x["t"]][g] = tallies[k][x["t"]].get(g, 0) + 1
                row["wrong"][k] += int(g == "WRONG")
                row["correct_unique"][k] += int(g == "CORRECT_UNIQUE")
        per_trial.append(row)
        f = stage1["trials"][oid]["features"]["motor_0"]
        if lab["kind"] in ("A", "B"):
            reproduce_v3["checked"] += 1
            got = localize(f["rpm_T3"], f["dyn_T1"], f["ctrl_T3"],
                           {"L": f["L_T3"], "D": f["D_T1"], "C": f["C_T3"]})
            reproduce_v3["matches"] += int(grade(truth, got) == "CORRECT_UNIQUE"
                                           and lab["outcomes"]["C3/V3_TEMPORAL"] == "UNIQUE_CORRECT")
    graded = [r for r in per_trial if r["kind"] in ("A", "B")]
    n_eval = len(graded) * len(TIMES)

    def times(key, kind=None):
        vals = [r[key] for r in per_trial if kind is None or r["kind"] == kind]
        got = [v for v in vals if v is not None]
        return {"min": min(got) if got else None, "max": max(got) if got else None,
                "never": sum(v is None for v in vals)}

    summary = {
        "label": "EXPLORATORY - not a confirmatory result; XSYS-001's sealed result is unchanged",
        "evaluation_times_s": [TIMES[0], TIMES[-1], STEP], "window_s": WIDTH,
        "state_window_long_s": LONG, "trials": len(per_trial),
        "graded_trial_times": n_eval,
        "reproduces_sealed_V3_at_C3": reproduce_v3,
        "by_cell": {k: {"wrong_trial_times": sum(r["wrong"][k] for r in graded),
                        "trials_ever_wrong": sum(1 for r in graded if r["wrong"][k]),
                        "trials_ever_wrong_A": sum(1 for r in graded if r["wrong"][k] and r["kind"] == "A"),
                        "trials_ever_wrong_B": sum(1 for r in graded if r["wrong"][k] and r["kind"] == "B"),
                        "correct_unique_trial_times": sum(r["correct_unique"][k] for r in graded)}
                    for k in tallies},
        "A_first_dynamics_nominal_s": times("first_dynamics_nominal_s", "A"),
        "A_first_ctrl_false_0.2s": times("first_ctrl_false_0.2s", "A"),
        "A_first_ctrl_false_1s": times("first_ctrl_false_1s", "A"),
        "B_first_ctrl_false_0.2s": times("first_ctrl_false_0.2s", "B"),
        "B_first_ctrl_false_1s": times("first_ctrl_false_1s", "B"),
        "N_first_ctrl_false_0.2s": times("first_ctrl_false_0.2s", "N"),
        "A_compensation_1s_seen_no_later_than_dynamics_turned_nominal": sum(
            1 for r in per_trial if r["kind"] == "A" and r["first_ctrl_false_1s"] is not None
            and (r["first_dynamics_nominal_s"] is None
                 or r["first_ctrl_false_1s"] <= r["first_dynamics_nominal_s"])),
    }
    summary["tallies_at"] = {str(te): {k: tallies[k][te] for k in tallies}
                             for te in (0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0)}
    OUT.write_text(json.dumps({"summary": summary, "per_trial": per_trial},
                              indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "tallies_at"},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
