"""The amended locked campaign. Opened once, after every choice was frozen.

PREREGISTRATION
---------------
`PREREGISTRATION.md` (84576af) and `PREREGISTRATION_AMENDMENT_1.md` (020b0dd),
with the scope clarification at ef572c0. The design is declared in
`csia_active_evidence/difficulty.py` and the seeds in
`csia_active_evidence/partitions.py`.

WHAT "LOCKED" MEANS HERE
-------------------------
`partitions.AMENDED_LOCKED` is imported DIRECTLY in this file and nowhere
else. `partitions.seeds()` refuses to hand it out and has no override, so the
one greppable import below is the whole of the exposure.

    NOTHING IN THE EXPERIMENT IS MODIFIED AFTER THIS RUNS.

If it crashes or reveals a defect, the partition is marked exposed, the run is
`INVALID_INSTRUMENT`, and a new amendment and a new partition are required
before another final campaign. It is not repaired and reused.

ON THE WORD "effort_drift"
---------------------------
MX-038's `effort_drift` is a COMPONENT RELATION in `csia_components`, gated on
a stationary operating point. It does not exist in the RCEC plant. The
structural role it played there -- a nuisance whose presence or absence
reverses which arms look good -- is played here by the OPEN-CIRCUIT VOLTAGE
DRIFT, which is the term `d_max` bounds and the term a time-correlated probe
aliases. The factorial below varies that, at the three levels
`difficulty.EFFORT_DRIFT_STATES` declares.

    THESE ARE NOT THE SAME OBJECT AND THE RESULT IS REPORTED AS THE DRIFT
    NUISANCE INTERACTION, NOT AS A REPLICATION OF MX-038.

P7 IS A CEILING
---------------
It is a realized-current trajectory no command produces through a bounded
actuator. It is reported in a separate block, marked `NOT_DEPLOYABLE`, and it
is excluded from every "best deployable arm" comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_active_evidence import battery_1rc as B                  # noqa: E402
from csia_active_evidence import battery_multirc as MR             # noqa: E402
from csia_active_evidence import difficulty as DF                  # noqa: E402
from csia_active_evidence import partitions as PT                  # noqa: E402
from csia_active_evidence import polarization as PZ                # noqa: E402
from csia_active_evidence import rcec                              # noqa: E402
from csia_active_evidence import rcec_selector as RS               # noqa: E402
from csia_active_evidence import realized_moments as RM            # noqa: E402
from csia_active_evidence import waveform_compensation as WC       # noqa: E402
from tools.research import rcec_campaign as C                      # noqa: E402

#: THE ONE PLACE THE SEALED PARTITION IS OPENED.
from csia_active_evidence.partitions import AMENDED_LOCKED         # noqa: E402

INSTRUMENT = "tools.research.rcec_locked_campaign"
SCHEMA = "csia.active_evidence.rcec_locked/1"

DELTAS = (0.002, 0.004, 0.006, 0.010, 0.020, 0.040)
PLANTS = {"simple": (B, {"r1_scale": 0.0}),
          "one_rc": (B, {"r1_scale": 1.0}),
          "multi_rc": (MR, {})}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def source_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True)
    return out.stdout.strip() or "UNKNOWN"


def config_hash(plant: str, drift: str, extra: dict) -> str:
    return _sha(json.dumps({"plant": plant, "drift": drift, **extra},
                           sort_keys=True, default=str))


def _proposal(arm, *, lag, cycles=3, seed=4242):
    common = dict(start=C.ACTION_START, duration=C.ACTION_DURATION,
                  amplitude=C.AMPLITUDE, hz=C.HZ, lag=lag,
                  authority_a=C.AUTHORITY_A, seed=seed)
    if arm == "P0_passive":
        return RS.p0_passive(), None
    if arm == "P1_palindromic":
        return RS.p1_palindromic(**common, cycles=cycles), None
    if arm == "P2_compensated":
        return RS.p2_compensated(**common), None
    if arm == "P3_shaped":
        return _p3(), None
    if arm == "P4_feedback":
        p, probe = RS.p4_feedback(**common)
        return p, probe
    if arm == "P5_random_safe":
        return RS.p5_random_safe(**common), None
    if arm == "P6_mission":
        return RS.p6_mission(**common), None
    if arm == "P7_oracle":
        return RS.p7_oracle(**common), None
    raise KeyError(arm)


_P3_CACHE = {}


def _p3():
    """Frozen before the locked partition was opened. Chosen on diagnostic
    seeds by the repaired objective; not re-searched here."""
    if "p" not in _P3_CACHE:
        _P3_CACHE["p"] = RS.p3_shaped(
            start=C.ACTION_START, duration=C.ACTION_DURATION, hz=C.HZ,
            plant=None, budget_eval=C.p3_objective,
            candidates=C.p3_candidates())
    return _P3_CACHE["p"]


def _run_once(arm, proposal, probe, seed, plant_mod, plant_kw, *,
              r0_delta, drift_v_per_s, sensing=None, loop=None,
              authorized=None):
    kw = dict(plant_kw)
    kw["r0_delta"] = r0_delta
    kw["ocv_drift_v_per_s"] = drift_v_per_s
    if sensing is not None:
        kw["sensing"] = sensing
    if loop is not None:
        kw["loop"] = loop
    command = (authorized if authorized is not None else proposal.command)
    if probe is not None:
        tr = plant_mod.simulate(probe.demand, duration=C.DURATION, seed=seed,
                                observer=lambda t, i, v: probe.observe(t, i),
                                **kw)
    else:
        tr = plant_mod.simulate(command, duration=C.DURATION, seed=seed, **kw)
    return tr.window(C.ACTION_START, C.ACTION_START + C.ACTION_DURATION)


def _budget(drift_v_per_s: float, target: float) -> rcec.ErrorBudget:
    return C.budget(target_delta_r=target,
                    d_max=max(drift_v_per_s, 1e-9))


def _record(arm, proposal, w, cert, *, plant, drift_state, drift_v,
            r0_delta, seed, cfg, runtime_s, predicted):
    m = RM.moments(w.t, w.i_meas) if w.n >= 3 else None
    terms = cert.terms or {}
    u_r = cert.resolution.get("k_sigma_SE")
    b_total = terms.get("B_total")
    m_r = (DF.resolution_margin(r0_delta if r0_delta > 0 else C.TARGET_DELTA_R,
                                b_total, u_r)
           if isinstance(b_total, float) and u_r is not None else None)
    return {
        "arm": arm, "plant": plant, "drift_state": drift_state,
        "drift_v_per_s": drift_v, "r0_delta": r0_delta, "seed": int(seed),
        "config_hash": cfg,
        "proposed_command_digest": (rcec.digest(proposal.samples)
                                    if proposal.samples is not None
                                    else "NONE"),
        "authorized_command_digest": (rcec.digest(proposal.samples)
                                      if proposal.samples is not None
                                      else "NONE"),
        "realized_mean_i": float(np.mean(w.i_meas)) if w.n else None,
        "realized_peak_i": float(np.max(np.abs(w.i_meas))) if w.n else None,
        "predicted_s_ii": predicted.get("s_ii"),
        "predicted_drift_lever": predicted.get("lever"),
        "realized_s_ii": m.s_ii if m else None,
        "realized_s_ti": m.s_ti if m else None,
        "realized_drift_lever": m.lever_arm_s if m else None,
        "B_drift": terms.get("B_drift"), "B_EIV": terms.get("B_EIV"),
        "B_dynamic": terms.get("B_dynamic"),
        "B_mismatch": terms.get("B_mismatch"),
        "B_sampling": terms.get("B_sampling"),
        "B_hysteresis": terms.get("B_hysteresis"),
        "B_total": b_total, "U_R": u_r, "M_R": m_r,
        "M_R_class": DF.classify_margin(m_r) if m_r is not None else None,
        "state": cert.state, "reason": list(cert.reasons),
        "energy_as": proposal.nominal_energy_as,
        "mission_deviation_as": (0.0 if arm in ("P0_passive", "P6_mission")
                                 else proposal.nominal_energy_as),
        "min_safety_margin_a": (float(C.AUTHORITY_A
                                      - np.max(np.abs(w.i_meas)))
                                if w.n else None),
        "saturated_fraction": float(np.mean(w.saturated)) if w.n else None,
        "runtime_s": runtime_s,
        "rng_streams": ["process", "voltage_sensor", "current_sensor",
                        "controller", "environment", "telemetry"],
        "deployable": arm not in DF.NOT_DEPLOYABLE,
    }


def factorial(seeds, quick=False) -> list:
    """strategy x drift state x plant x delta x seed. The declared design."""
    rows = []
    lag = WC.estimate_lag(B.simulate, seeds=PT.seeds("amended_calibration"))
    deltas = DELTAS[::2] if quick else DELTAS
    use = seeds[:4] if quick else seeds
    for plant_name, (mod, kw) in PLANTS.items():
        for drift_state in DF.EFFORT_DRIFT_STATES:
            dv = DF.EFFORT_DRIFT_MAGNITUDE[drift_state] or 0.0
            for arm in DF.STRATEGIES:
                proposal, probe = _proposal(arm, lag=lag)
                pred = {}
                if proposal.samples is not None:
                    ps = proposal.samples
                    tt = RS.window_times(C.ACTION_START, proposal.duration_s
                                         or C.ACTION_DURATION, C.HZ)
                    n = min(ps.size, tt.size)
                    pm = RM.moments(tt[:n], 20.0 + ps[:n])
                    pred = {"s_ii": pm.s_ii, "lever": pm.lever_arm_s}
                cfg = config_hash(plant_name, drift_state,
                                  {"arm": arm, "lag": lag.tau_s})
                for delta in deltas:
                    for seed in use:
                        _, pr = _proposal(arm, lag=lag)
                        t0 = time.time()
                        w = _run_once(arm, proposal, pr, int(seed), mod, kw,
                                      r0_delta=delta, drift_v_per_s=dv)
                        cert = rcec.certify(w.t, w.i_meas, w.v_meas,
                                            _budget(dv, delta)) if w.n >= 3 \
                            else rcec.certify([0., 1., 2.], [0., 0., 0.],
                                              [0., 0., 0.], _budget(dv, delta))
                        rows.append(_record(
                            arm, proposal, w, cert, plant=plant_name,
                            drift_state=drift_state, drift_v=dv,
                            r0_delta=delta, seed=seed, cfg=cfg,
                            runtime_s=time.time() - t0, predicted=pred))
    return rows


def detection_frontier(rows) -> dict:
    """Smallest delta at which an arm resolves, per plant and drift state."""
    out = {}
    for r in rows:
        key = f"{r['plant']}/{r['drift_state']}/{r['arm']}"
        out.setdefault(key, {})
        d = str(r["r0_delta"])
        out[key].setdefault(d, {"n": 0, "resolvable": 0, "certified": 0,
                                "margins": []})
        c = out[key][d]
        c["n"] += 1
        if r["state"] == rcec.CERTIFIED:
            c["certified"] += 1
        if r["M_R"] is not None:
            c["margins"].append(r["M_R"])
            if r["M_R"] > 0:
                c["resolvable"] += 1
    frontier = {}
    for key, per in out.items():
        stats = {}
        smallest = None
        for d in sorted(per, key=float):
            c = per[d]
            frac = c["resolvable"] / c["n"] if c["n"] else 0.0
            stats[d] = {
                "n": c["n"], "certified": c["certified"],
                "resolvable_fraction": frac,
                "median_margin": (statistics.median(c["margins"])
                                  if c["margins"] else None),
                "worst_margin": min(c["margins"]) if c["margins"] else None,
            }
            if frac >= 0.9 and smallest is None:
                smallest = float(d)
        frontier[key] = {"by_delta": stats,
                         "smallest_resolvable_delta": smallest}
    return frontier


def confusion(rows) -> dict:
    out = {}
    for r in rows:
        out[r["state"]] = out.get(r["state"], 0) + 1
    return out


def false_certificates(rows) -> list:
    """A CERTIFIED run whose margin says the target is not resolvable."""
    bad = []
    for r in rows:
        if r["state"] == rcec.CERTIFIED and r["M_R"] is not None \
                and r["M_R"] < 0:
            bad.append(r)
    return bad


def drift_interaction(frontier) -> dict:
    """The contrast that must not be averaged away."""
    out = {}
    for plant in PLANTS:
        def score(arm, state):
            k = f"{plant}/{state}/{arm}"
            s = frontier.get(k, {}).get("smallest_resolvable_delta")
            return s if s is not None else float("inf")
        deployable = [a for a in DF.STRATEGIES
                      if a not in DF.NOT_DEPLOYABLE and a != "P0_passive"]
        best_absent = min(score(a, "absent") for a in deployable)
        best_elev = min(score(a, "elevated") for a in deployable)
        pas_absent = score("P0_passive", "absent")
        pas_elev = score("P0_passive", "elevated")
        out[plant] = DF.interaction(
            active_with=-best_elev, passive_with=-pas_elev,
            active_without=-best_absent, passive_without=-pas_absent)
        out[plant]["best_active_absent_delta"] = best_absent
        out[plant]["best_active_elevated_delta"] = best_elev
        out[plant]["passive_absent_delta"] = pas_absent
        out[plant]["passive_elevated_delta"] = pas_elev
    return out


def ablations(seeds) -> dict:
    """Clipping, abort, sensing defects, lag error, unmodelled fault."""
    lag = WC.estimate_lag(B.simulate, seeds=PT.seeds("amended_calibration"))
    p, _ = _proposal("P1_palindromic", lag=lag, cycles=6)
    seed = int(seeds[0])
    out = {}

    w = _run_once("P1_palindromic", p, None, seed, B, {"r1_scale": 1.0},
                  r0_delta=0.010, drift_v_per_s=0.008)
    d = rcec.digest(p.samples)
    out["execution"] = {
        "full": rcec.certify(w.t, w.i_meas, w.v_meas, _budget(0.008, 0.010),
                             execution=rcec.Execution(d, d, True)).state,
        "clipped": rcec.certify(w.t, w.i_meas, w.v_meas,
                                _budget(0.008, 0.010),
                                execution=rcec.Execution(
                                    d, rcec.digest(p.samples * 0.4), True)
                                ).state,
        "aborted": rcec.certify(w.t, w.i_meas, w.v_meas,
                                _budget(0.008, 0.010),
                                execution=rcec.Execution(
                                    d, d, False, aborted_at_s=3.0)).state,
    }

    sens = {}
    for label, kw in (("nominal", {}),
                      ("bias_i 1.0A", {"bias_i": 1.0}),
                      ("scale_i 2%", {"scale_i": 0.02}),
                      ("sigma_i 0.2A", {"sigma_i": 0.2}),
                      ("delay 40ms", {"delay_s": 0.04}),
                      ("dropout 20%", {"dropout": 0.20}),
                      ("quantum_i 0.05A", {"quantum_i": 0.05})):
        s = B.Sensing(**{**B.SYNTHETIC_SENSING, **kw})
        ww = _run_once("P1_palindromic", p, None, seed, B, {"r1_scale": 1.0},
                       r0_delta=0.010, drift_v_per_s=0.008, sensing=s)
        cc = rcec.certify(ww.t, ww.i_meas, ww.v_meas, _budget(0.008, 0.010)) \
            if ww.n >= 3 else None
        sens[label] = {"state": cc.state if cc else "NO_WINDOW",
                       "M_R": (DF.resolution_margin(
                           0.010, cc.terms.get("B_total", 0.0),
                           cc.resolution.get("k_sigma_SE", 0.0))
                           if cc and isinstance(cc.terms.get("B_total"), float)
                           else None)}
    out["sensing"] = sens

    lagr = {}
    for ratio in (0.25, 0.5, 1.0, 2.0, 4.0):
        model = WC.LagModel(tau_s=lag.tau_s * ratio, rms_residual_a=0.0,
                            fitted_on_seeds=lag.fitted_on_seeds)
        p2 = RS.p2_compensated(start=C.ACTION_START,
                               duration=C.ACTION_DURATION,
                               amplitude=C.AMPLITUDE, hz=C.HZ, lag=model,
                               authority_a=C.AUTHORITY_A)
        ww = _run_once("P2_compensated", p2, None, seed, B,
                       {"r1_scale": 1.0}, r0_delta=0.010, drift_v_per_s=0.008)
        cc = rcec.certify(ww.t, ww.i_meas, ww.v_meas, _budget(0.008, 0.010))
        mm = RM.moments(ww.t, ww.i_meas)
        lagr[str(ratio)] = {"state": cc.state, "realized_s_ii": mm.s_ii,
                            "realized_lever": mm.lever_arm_s,
                            "lever_sign": int(np.sign(mm.lever_arm_s))}
    out["lag_error"] = lagr

    unk = {}
    for ring in (0.0, 0.10, 0.40):
        ww = _run_once("P1_palindromic", p, None, seed, B, {"r1_scale": 1.0},
                       r0_delta=0.0, drift_v_per_s=0.008)
        tr = B.simulate(p.command, duration=C.DURATION, seed=seed,
                        r1_scale=1.0, unmodelled_ringing=ring)
        ww = tr.window(C.ACTION_START, C.ACTION_START + C.ACTION_DURATION)
        cc = rcec.certify(ww.t, ww.i_meas, ww.v_meas, _budget(0.008, 0.010))
        unk[str(ring)] = cc.state
    out["unmodelled_fault_routing"] = unk
    return out


def run(seeds, quick=False) -> dict:
    started = time.time()
    rows = factorial(seeds, quick=quick)
    front = detection_frontier(rows)
    fc = false_certificates(rows)
    return {
        "schema": SCHEMA,
        "preregistration": "PREREGISTRATION.md @ 84576af",
        "amendment": "PREREGISTRATION_AMENDMENT_1.md @ 020b0dd",
        "scope_clarification": "POLARIZATION_BOUND_SCOPE.md @ ef572c0",
        "source_sha": source_sha(),
        "partition_manifest_sha256": PT.manifest_hash(),
        "locked_partition": "amended_locked",
        "locked_seeds": list(seeds),
        "deltas": list(DELTAS[::2] if quick else DELTAS),
        "plants": list(PLANTS),
        "drift_states": list(DF.EFFORT_DRIFT_STATES),
        "strategies": list(DF.STRATEGIES),
        "not_deployable": list(DF.NOT_DEPLOYABLE),
        "rows": rows,
        "n_rows": len(rows),
        "detection_frontier": front,
        "certificate_confusion": confusion(rows),
        "false_certificates": fc,
        "false_certificate_count": len(fc),
        "drift_nuisance_interaction": drift_interaction(front),
        "ablations": ablations(seeds),
        "effort_drift_note": (
            "MX-038's effort_drift is a component relation that does not "
            "exist in this plant. The structural role it played is taken "
            "here by the open-circuit voltage drift. These are not the same "
            "object and this is not a replication of MX-038."),
        "what_this_is_not": (
            "E0, simulation only, synthetic pack. The polarization bound is "
            "exhaustive over a discrete 105-point grid and sampled beyond "
            "it; see POLARIZATION_BOUND_SCOPE.md. No novelty is claimed: "
            "scholarly access is denied by organization policy."),
        "elapsed_s": time.time() - started,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--dry-run-seeds", default=None,
                    help="debug on a non-locked partition")
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    if args.dry_run_seeds:
        seeds = PT.seeds(args.dry_run_seeds)
        print(f"DRY RUN on partition {args.dry_run_seeds!r}: {list(seeds)}")
    else:
        seeds = AMENDED_LOCKED
        print(f"OPENING THE SEALED PARTITION: {list(seeds)}")

    doc = run(seeds, quick=args.quick)
    doc["dry_run_partition"] = args.dry_run_seeds
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        from tools.evidence_guard import protected_write
        with protected_write(args.out, regenerate=args.regenerate) as fh:
            fh.write(text)
        print(f"wrote {args.out}")
    print(f"\nrows {doc['n_rows']}  elapsed {doc['elapsed_s']:.1f}s")
    print(f"false certificates: {doc['false_certificate_count']}")
    print(f"confusion: {json.dumps(doc['certificate_confusion'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
