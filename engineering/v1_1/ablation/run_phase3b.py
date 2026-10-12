"""Phase 3B: TRUST vs SEQUENTIAL vs COMBINED, five matched arms.

Engineering only. CUSUM is established prior art (Page 1954); no algorithmic
novelty is claimed anywhere in this file.

ORDER OF OPERATIONS, and it matters (sections 6 and 8):
  1. the mechanism coverage matrix is built and written FIRST, from the
     frozen fault kinds and the frozen scenario catalogue, before any arm
     runs;
  2. the response-event definitions below are frozen before results;
  3. only then are the arms executed.

    python engineering/v1_1/ablation/run_phase3b.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.abspath(os.path.join(_HERE, ".."))
ROOT = os.path.abspath(os.path.join(ENG, "..", ".."))
for p in (ROOT, _HERE, os.path.join(ENG, "support")):
    if p not in sys.path:
        sys.path.insert(0, p)

from csia.diagnosis.bayes import CausalDiagnosis                  # noqa: E402
from csia.runtime.failsafe import FailsafeConfig, FailsafePolicy  # noqa: E402
from csia.runtime.online import TrustState                        # noqa: E402
from csia.scenarios import run_pipeline, run_scenario             # noqa: E402
from csia.sensors.faults import KNOWN_KINDS, Fault                # noqa: E402
from csia.trust_engine.engine import TrustEngine                  # noqa: E402
from csia.trust_graph.graph import build_trust_graph              # noqa: E402
from flat import FlatTrustEngine                                  # noqa: E402
import b4_verify as B4                                            # noqa: E402
import support as S                                               # noqa: E402

ARMS = ("T0_TRUST_FLAT", "T1_TRUST_GRAPH", "T2_SEQUENTIAL_ONLY",
        "T3_TRUST_FLAT_PLUS_SEQ", "T4_TRUST_GRAPH_PLUS_SEQ")
HAS_TRUST = {"T0_TRUST_FLAT": "FLAT", "T1_TRUST_GRAPH": "GRAPH",
             "T2_SEQUENTIAL_ONLY": None,
             "T3_TRUST_FLAT_PLUS_SEQ": "FLAT",
             "T4_TRUST_GRAPH_PLUS_SEQ": "GRAPH"}
HAS_SEQ = {"T0_TRUST_FLAT": False, "T1_TRUST_GRAPH": False,
           "T2_SEQUENTIAL_ONLY": True, "T3_TRUST_FLAT_PLUS_SEQ": True,
           "T4_TRUST_GRAPH_PLUS_SEQ": True}

# ---------------------------------------------------------------------------
# Section 6: the mechanism coverage matrix. Frozen from the FROZEN fault kinds
# (csia/sensors/faults.py KNOWN_KINDS) and the FROZEN scenario catalogue.
# `run` is the scenario name, or a (kind, target, start, dur, params) tuple
# built from an existing kind with declared parameters -- never a new kind.
# ---------------------------------------------------------------------------
MECHANISMS = {
    "CLEAN": {"run": "clean", "truth": None, "window": None,
              "status": "APPLICABLE"},
    "GNSS_STEP_SMALL": {
        "run": None, "truth": "gps_fault", "window": None,
        "status": "INAPPLICABLE",
        "why": "no step/offset injector exists. KNOWN_KINDS = "
               "{bias_drift, dropout, emi_spike, gps_spoof, "
               "vibration_anomaly, power_sag}; gps_spoof takes a DRIFT "
               "velocity and is therefore a ramp. Section 5/28 forbid "
               "building new injection machinery in this phase."},
    "GNSS_STEP_LARGE": {
        "run": None, "truth": "gps_fault", "window": None,
        "status": "INAPPLICABLE", "why": "as GNSS_STEP_SMALL"},
    "GNSS_RAMP_SLOW": {
        "run": ("gps_spoof", "gps", 20.0, 15.0, {"drift": (1.0, 0.3, 0.0)}),
        "truth": "gps_fault", "window": (20.0, 35.0), "status": "APPLICABLE",
        "why": "declared parameter variation of the frozen gps_spoof kind; "
               "slower drift than the catalogue scenario"},
    "GNSS_RAMP_FAST": {
        "run": "gps_spoof", "truth": "gps_fault", "window": (20.0, 35.0),
        "status": "APPLICABLE",
        "why": "the catalogue scenario: ~3.2 m/s position walk"},
    "GNSS_FIX_LOSS": {
        "run": "gps_dropout", "truth": None, "window": (25.0, 33.0),
        "status": "APPLICABLE",
        "why": "absence, not a nameable sensor fault; truth is None on "
               "purpose (section 13)"},
    "GNSS_TRANSPORT_STARVATION": {
        "run": None, "truth": None, "window": None,
        "status": "INAPPLICABLE",
        "why": "in this simulator the `dropout` kind IS transport starvation "
               "at the CSIA boundary -- no samples arrive and freshness "
               "lapses. It is the same injection as GNSS_FIX_LOSS and is not "
               "counted twice."},
    "IMU0_BIAS_DRIFT": {
        "run": "imu0_bias_drift", "truth": "imu0_bias_drift",
        "window": (20.0, 40.0), "status": "APPLICABLE"},
    "DUAL_IMU_FAILURE": {
        "run": "dual_imu_failure", "truth": None, "window": (27.0, 55.0),
        "status": "APPLICABLE",
        "why": "two simultaneous faults against a single-fault model; truth "
               "is None because no modeled hypothesis is correct"},
    "MAG_DEGRADED": {
        "run": "mag_emi", "truth": "mag_interference", "window": (25.0, 33.0),
        "status": "APPLICABLE"},
    "MAG_INVALID": {
        "run": None, "truth": None, "window": None, "status": "INAPPLICABLE",
        "why": "the all-zero magnetometer sentinel is an INGEST-layer "
               "condition fixed in Phase 1 and regression-tested there "
               "(tests/test_v1_1_canonical_ingest.py). No invalid-mag fault "
               "kind exists in KNOWN_KINDS."},
    "BATTERY_SENTINEL": {
        "run": None, "truth": None, "window": None, "status": "INAPPLICABLE",
        "why": "as MAG_INVALID: ingest-layer, fixed and regression-tested in "
               "Phase 1. It reaches diagnosis only as gate -> 0."},
    "POWER_SAG": {
        "run": "power_sag", "truth": "power_fault", "window": (30.0, 36.0),
        "status": "APPLICABLE"},
    "VIBRATION_ANOMALY": {
        "run": "vibration_anomaly", "truth": "vibration_anomaly",
        "window": (28.0, 40.0), "status": "APPLICABLE"},
    "BARO_FAULT": {
        "run": None, "truth": None, "window": None, "status": "INAPPLICABLE",
        "why": "no baro fault kind in KNOWN_KINDS, and baro's clean-arm "
               "sigma0 is degenerate so it carries no sequential residual "
               "either (B4_CONSTANT_VERIFICATION.json)."},
}

# ---------------------------------------------------------------------------
# Section 8: response events, frozen before results.
#
#   DETECTION_RESPONSE   first assurance change attributable to the fault.
#                        Trust arms: first FailsafeLevel change at/after
#                        onset. T2: first CUSUM crossing. Combined: earliest
#                        of the two.
#   DIAGNOSTIC_RESPONSE  first tick the correct cause is top-ranked AND the
#                        leader is identifiable. Shared across arms.
#   SUPPORT_RESPONSE     first tick support correctly reports loss of
#                        identifiability. Shared across arms.
#   SEQUENTIAL_RESPONSE  first CUSUM crossing.
#
# No response is RIGHT-CENSORED. It is recorded as None with censored=True,
# and NEVER replaced by the window end as an ordinary latency.
# ---------------------------------------------------------------------------
CENSORED = None


def _git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "UNKNOWN"


def _sha_arr(*arrays) -> str:
    h = hashlib.sha256()
    for a in arrays:
        h.update(np.ascontiguousarray(a, dtype=float).tobytes())
    return h.hexdigest()


def _hashes(td):
    """Section 4: the three required matching hashes."""
    raw = _sha_arr(td.t, *[td.edges[k][2] for k in sorted(td.edges)])
    canon = _sha_arr(*[np.asarray(td.fresh[n], float)
                       for n in sorted(td.fresh)],
                     *[td.physics[n][0] for n in sorted(td.physics)])
    relbank = _sha_arr(*[td.edges[k][2] for k in sorted(td.edges)],
                       *[np.asarray(td.edges[k][3], float) * np.ones(len(td.t))
                         for k in sorted(td.edges)])
    return {"raw_trace_sha256": raw, "canonical_input_sha256": canon,
            "relation_bank_sha256": relbank}


def _build(mech):
    """Run the pipeline for a mechanism row. Returns td or None."""
    spec = MECHANISMS[mech]
    run = spec["run"]
    if run is None:
        return None
    if isinstance(run, str):
        _t, _f, td, _h, _d = run_scenario(run)
        return td
    kind, target, start, dur, params = run
    assert kind in KNOWN_KINDS, kind
    td, _hist, _diag = run_pipeline(
        faults=[Fault(kind, target, start, dur, params)])
    return td


def _trust_levels(td, names, engine_cls, post, causes):
    hist = engine_cls(build_trust_graph()).run(td)
    pol = FailsafePolicy(FailsafeConfig())
    levels = []
    for k in range(len(td.t)):
        st = TrustState(t=float(td.t[k]),
                        trust={n: float(hist.trust[k, i])
                               for i, n in enumerate(names)},
                        evidence={}, components={},
                        posterior={c: float(post[k, ci])
                                   for ci, c in enumerate(causes)},
                        fresh={n: bool(td.fresh[n][k]) for n in names},
                        armed=True)
        pol.update(st)
        levels.append(int(pol.level))
    return hist, np.asarray(levels)


def _seq_alarms(td, stats):
    """B4 CUSUM per node. Returns {node: first_index} for crossings."""
    streams = B4.lam_streams(td)
    first = {}
    for n, (mu0, sd0) in stats.items():
        if n not in streams:
            continue
        lam, act = streams[n]
        z = (lam - mu0) / sd0
        idx, cnt = B4.cusum_alarms(z, act, k=B4.B4_K, h=B4.B4_H_HISTORICAL)
        if cnt:
            first[n] = idx
    return first


def _first_change_after(levels, t, onset):
    for k in range(len(levels)):
        if t[k] < onset:
            continue
        if levels[k] != levels[0] and (k == 0 or levels[k] != levels[k - 1]):
            return k
    return None


def main() -> int:
    graph = build_trust_graph()
    names = list(graph.nodes)

    # ---- 1. coverage matrix, written BEFORE any arm runs ----------------
    cov_rows = []
    for mech, spec in MECHANISMS.items():
        applicable = spec["status"] == "APPLICABLE"
        seq_node = {"GNSS_RAMP_SLOW": "gps", "GNSS_RAMP_FAST": "gps",
                    "GNSS_FIX_LOSS": "gps", "MAG_DEGRADED": "mag",
                    "POWER_SAG": "battery", "VIBRATION_ANOMALY": "vibration",
                    "CLEAN": None}.get(mech)
        cov_rows.append({
            "mechanism": mech,
            "status": spec["status"],
            "scenario_or_fault": (spec["run"] if isinstance(spec["run"], str)
                                  else ("constructed" if spec["run"]
                                        else "NONE")),
            "platform": "ardupilot-derived deterministic simulator",
            "injection_supported": applicable,
            "trust_relation_available": applicable,
            "diagnosis_relation_available": applicable,
            "support_analysis_available": applicable,
            "sequential_residual_available": bool(seq_node) and applicable,
            "sequential_node": seq_node or "",
            "note": spec.get("why", ""),
        })
    with open(os.path.join(ENG, "MECHANISM_COVERAGE_MATRIX.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cov_rows[0]))
        w.writeheader()
        w.writerows(cov_rows)

    # ---- 2. clean-arm in-control statistics for the sequential channel --
    _t, _f, td_clean, _h, _d = run_scenario("clean")
    clean_streams = B4.lam_streams(td_clean)
    stats = {}
    for n, (lam, act) in clean_streams.items():
        v = lam[act]
        if v.size >= 2 and v.std(ddof=1) > 1e-12:
            stats[n] = (float(v.mean()), float(v.std(ddof=1)))

    # ---- 3. the arms ----------------------------------------------------
    rows, per_mech, compute = [], {}, {}
    for mech, spec in MECHANISMS.items():
        if spec["status"] != "APPLICABLE":
            continue
        td = _build(mech)
        h = _hashes(td)
        diag = CausalDiagnosis().run(td)
        post, causes = diag.posterior, diag.causes
        dec, sup = S.support_series(td, stride=1)
        truth, win = spec["truth"], spec["window"]
        onset = win[0] if win else 0.0

        # attribution eligibility (section 15) -- SHARED across arms, because
        # neither the graph nor the sequential channel feeds the frozen
        # diagnosis.
        cls = {"CORRECT_UNIQUE": 0, "SAFE_AMBIGUITY": 0, "WRONG_UNIQUE": 0,
               "UNSUPPORTED_UNIQUE": 0, "UNAVAILABLE": 0}
        v1_would_be_unsupported_unique = 0
        diag_resp = supp_resp = None
        for r in sup:
            if win and not (win[0] <= r.t <= win[1]):
                continue
            if not r.evidence_available:
                cls["UNAVAILABLE"] += 1
            elif not r.leader_identifiable:
                cls["SAFE_AMBIGUITY"] += 1
                # v1 had no support state: it would have presented this
                # leader as an ordinary unique diagnosis.
                v1_would_be_unsupported_unique += 1
                if supp_resp is None:
                    supp_resp = r.t
            elif truth is not None and r.leader == truth:
                cls["CORRECT_UNIQUE"] += 1
                if diag_resp is None:
                    diag_resp = r.t
            elif r.leader == "nominal":
                pass                       # identifiable, still nominal
            else:
                cls["WRONG_UNIQUE"] += 1

        seq_first = _seq_alarms(td, stats)
        seq_t = (min(float(td.t[i]) for i in seq_first.values())
                 if seq_first else CENSORED)

        arm_levels = {}
        for arm in ARMS:
            kind = HAS_TRUST[arm]
            det_t = CENSORED
            if kind:
                eng = TrustEngine if kind == "GRAPH" else FlatTrustEngine
                t0 = time.perf_counter()
                hist, levels = _trust_levels(td, names, eng, post, causes)
                compute.setdefault(arm, []).append(
                    (time.perf_counter() - t0) * 1e6 / len(td.t))
                arm_levels[arm] = levels
                k = _first_change_after(levels, td.t, onset)
                det_t = float(td.t[k]) if k is not None else CENSORED
            if HAS_SEQ[arm]:
                cands = [x for x in (det_t, seq_t) if x is not None]
                det_t = min(cands) if cands else CENSORED

            rows.append({
                "mechanism": mech, "arm": arm,
                "coverage": ("TRUST+SEQ" if kind and HAS_SEQ[arm] else
                             "TRUST" if kind else
                             ("SEQ" if seq_first else "NO_SEQUENTIAL_COVERAGE")),
                "raw_trace_sha256": h["raw_trace_sha256"][:16],
                "canonical_input_sha256": h["canonical_input_sha256"][:16],
                "relation_bank_sha256": h["relation_bank_sha256"][:16],
                "detection_response_s": det_t,
                "detection_censored": det_t is CENSORED,
                "sequential_response_s": (seq_t if HAS_SEQ[arm] else ""),
                "sequential_censored": (seq_t is CENSORED
                                        if HAS_SEQ[arm] else ""),
                "diagnostic_response_s": diag_resp,
                "diagnostic_censored": diag_resp is None,
                "support_response_s": supp_resp,
                "correct_unique": cls["CORRECT_UNIQUE"],
                "safe_ambiguity": cls["SAFE_AMBIGUITY"],
                "wrong_unique": cls["WRONG_UNIQUE"],
                "unsupported_unique": cls["UNSUPPORTED_UNIQUE"],
                "unavailable": cls["UNAVAILABLE"],
                "v1_would_be_unsupported_unique": v1_would_be_unsupported_unique,
            })

        per_mech[mech] = {
            "hashes": h, "truth": truth, "window": win,
            "attribution": cls,
            "v1_would_be_unsupported_unique": v1_would_be_unsupported_unique,
            "sequential_nodes_alarming": sorted(seq_first),
            "sequential_response_s": seq_t,
            "sequential_covered": bool(seq_first),
            "assurance_levels_identical_flat_vs_graph": bool(np.array_equal(
                arm_levels.get("T0_TRUST_FLAT", np.zeros(1)),
                arm_levels.get("T1_TRUST_GRAPH", np.zeros(1)))),
            "detection_by_arm": {a: next(
                r["detection_response_s"] for r in rows
                if r["mechanism"] == mech and r["arm"] == a) for a in ARMS},
        }

    with open(os.path.join(ENG, "PHASE3B_ARCHITECTURE_RESULTS.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # ---- 4. paired differences (section 17) -----------------------------
    pairs = [("T1_TRUST_GRAPH", "T0_TRUST_FLAT", "graph contribution"),
             ("T2_SEQUENTIAL_ONLY", "T0_TRUST_FLAT", "sequential vs flat trust"),
             ("T3_TRUST_FLAT_PLUS_SEQ", "T0_TRUST_FLAT",
              "sequential on flat trust"),
             ("T4_TRUST_GRAPH_PLUS_SEQ", "T1_TRUST_GRAPH",
              "sequential on graph trust"),
             ("T4_TRUST_GRAPH_PLUS_SEQ", "T3_TRUST_FLAT_PLUS_SEQ",
              "graph after sequential is present")]
    pd_rows = []
    for a, b, label in pairs:
        for mech, d in per_mech.items():
            ta, tb = d["detection_by_arm"][a], d["detection_by_arm"][b]
            if ta is None and tb is None:
                delta, note = "", "both right-censored"
            elif ta is None:
                delta, note = "", f"{a} right-censored, {b} responded"
            elif tb is None:
                delta, note = "", f"{b} right-censored, {a} responded"
            else:
                delta, note = round(ta - tb, 4), ""
            pd_rows.append({"comparison": f"{a} - {b}", "meaning": label,
                            "mechanism": mech,
                            f"detection_{a}": ta, f"detection_{b}": tb,
                            "delta_s": delta, "note": note})
    with open(os.path.join(ENG, "PHASE3B_PAIRED_DIFFERENCES.csv"), "w",
              newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["comparison", "meaning",
                                           "mechanism", "delta_s", "note"])
        w.writeheader()
        for r in pd_rows:
            w.writerow({k: r.get(k, "") for k in
                        ["comparison", "meaning", "mechanism", "delta_s",
                         "note"]})

    # ---- 5. clean controls, compute, state ------------------------------
    clean = {m: v for m, v in per_mech.items() if m == "CLEAN"}
    clean_out = {
        "artifact": "PHASE3B_CLEAN_RESULTS",
        "sequential_alarms_on_clean": len(
            clean["CLEAN"]["sequential_nodes_alarming"]) if clean else None,
        "assurance_transitions_on_clean_flat_vs_graph_identical":
            clean["CLEAN"]["assurance_levels_identical_flat_vs_graph"]
            if clean else None,
        "clean_attribution": clean["CLEAN"]["attribution"] if clean else None,
        "note": "deterministic replay control, NOT a field false-alarm rate",
    }
    comp = {"artifact": "PHASE3B_COMPUTE",
            "note": "Python microbenchmark. Paired distributions overlap; "
                    "do not read small differences as meaningful. The "
                    "embedded implementation is benchmarked separately.",
            "us_per_tick": {a: {"median": round(float(np.median(v)), 2),
                                "min": round(float(np.min(v)), 2),
                                "n": len(v)}
                            for a, v in compute.items()}}
    mem = {
        "artifact": "PHASE3B_MEMORY_STATE",
        "mutable_runtime_state_floats": {
            "trust_recursion_alpha_beta": 2 * len(names),
            "trust_carried_between_ticks_for_propagation": len(names),
            "sequential_cusum_S_per_covered_node": len(stats),
            "diagnosis_smoothed_per_hypothesis": len(CausalDiagnosis().causes),
        },
        "bytes_at_8_per_float": {
            "trust_recursion_alpha_beta": 16 * len(names),
            "propagation_only": 8 * len(names),
            "sequential": 8 * len(stats),
            "diagnosis_smoothing": 8 * len(CausalDiagnosis().causes),
        },
        "planned_c_structs_phase5": {
            "csia_trust_t": "float alpha[N_NODES]; float beta[N_NODES]; "
                            "float trust[N_NODES];",
            "csia_cusum_t": "float S[N_SEQ_NODES];",
            "csia_diag_t": "float smoothed[N_HYP];",
            "note": "propagation removal deletes only the inter-node read of "
                    "trust[] inside the neighbour weight; trust[] itself is "
                    "still reported and still needed.",
        },
    }

    summary = {
        "artifact": "PHASE3B_SUMMARY",
        "csia_sha": _git("rev-parse", "HEAD"),
        "generation_command":
            "python engineering/v1_1/ablation/run_phase3b.py",
        "arms": list(ARMS),
        "cusum": {"k": B4.B4_K, "h": B4.B4_H_HISTORICAL,
                  "in_control_nodes": sorted(stats)},
        "per_mechanism": per_mech,
    }

    for name, obj in (("PHASE3B_CLEAN_RESULTS.json", clean_out),
                      ("PHASE3B_COMPUTE.json", comp),
                      ("PHASE3B_MEMORY_STATE.json", mem),
                      ("PHASE3B_SUMMARY.json", summary)):
        with open(os.path.join(ENG, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True, default=str)
            fh.write("\n")

    # ---- report ---------------------------------------------------------
    print(f"  applicable mechanisms: "
          f"{sum(1 for s in MECHANISMS.values() if s['status']=='APPLICABLE')}"
          f" / {len(MECHANISMS)}")
    print(f"  sequential in-control nodes: {sorted(stats)}")
    print("\n  mechanism              T0/T1 trust     T2 seq      "
          "safe_amb  correct_uniq")
    for m, d in per_mech.items():
        t0 = d["detection_by_arm"]["T0_TRUST_FLAT"]
        t1 = d["detection_by_arm"]["T1_TRUST_GRAPH"]
        t2 = d["detection_by_arm"]["T2_SEQUENTIAL_ONLY"]
        f = lambda x: ("censored" if x is None else f"{x:.2f}")   # noqa: E731
        print(f"    {m:<22} {f(t0)}/{f(t1):<10} {f(t2):<10} "
              f"{d['attribution']['SAFE_AMBIGUITY']:<9} "
              f"{d['attribution']['CORRECT_UNIQUE']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
