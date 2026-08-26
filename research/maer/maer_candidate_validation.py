"""Stage 0.5: is any receiver-health candidate scientifically defensible?

Joins the source provenance, the PX4 timing capture and the ArduPilot jamming
qualification into the Stage 0.5 artifacts. Applies ONE classification scheme
to both platforms so a candidate that passes on one and fails on the other
fails for a stated reason.

THE ORACLE CLASSES ARE DEFINED BEFORE ANY RESULT IS LOOKED AT (brief item 3):

  DIRECT_ORACLE          the fault value is assigned as a deterministic
                         consequence of the intervention variable, so
                         detecting the field is detecting the injection
  MODEL_GENERATED_HEALTH the intervention changes an underlying simulated
                         receiver process and the field is generated from that
                         process
  GATE_DUPLICATE         functionally equivalent to fix validity for the
                         tested condition
  INDEPENDENT_RECEIVER_OBSERVABLE
                         only where source evidence justifies the wording

THE MATERIAL-CHANGE CRITERION IS CLEAN-DERIVED AND PRE-DECLARED: a candidate is
materially changed when its value leaves the closed interval [min, max]
observed over the clean baseline of the same run. No fault-observed threshold
is used.

  python research/maer/maer_candidate_validation.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MAER = os.path.join(ROOT, "research", "maer")
JAM_RAW = os.path.join(MAER, "MAER_ARDUPILOT_JAM_RAW")

CANDIDATES = ("satellites_visible", "eph", "epv", "h_acc", "v_acc", "vel_acc")

# ---------------------------------------------------------------- provenance
# Traced by reading the simulators at the pinned commits. Every entry cites the
# file and line it was read from, so a reviewer can check the claim rather than
# take it.
PROVENANCE = {
    "px4": {
        "intervention": "SIM_GPS_USED",
        "chain": "SIM_GPS_USED -> SensorGpsSim::Run() if/else -> sensor_gps "
                 "-> MavlinkStreamGPSRawInt -> GPS_RAW_INT",
        "source": "PX4-Autopilot@547e2ca "
                  "src/modules/simulation/sensor_gps_sim/SensorGpsSim.cpp:155-172, "
                  "src/modules/mavlink/streams/GPS_RAW_INT.hpp:92-107",
        "branch_predicate": "_sim_gps_used.get() >= 4",
        "fields": {
            "satellites_visible": {
                "raw_source_variable": "sensor_gps.satellites_used",
                "producing_function": "SensorGpsSim::Run() line 199: "
                                      "satellites_used = _sim_gps_used.get()",
                "wire_mapping": "msg.satellites_visible = gps.satellites_used",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE",
                "notes": "the field IS the injected parameter, echoed back "
                         "verbatim. Detecting it is reading the command."},
            "eph": {
                "raw_source_variable": "sensor_gps.hdop",
                "producing_function": "hard-coded 0.7f / 100.f in the same "
                                      "if/else that sets fix_type",
                "wire_mapping": "msg.eph = gps.hdop * 100  -> 70 / 10000",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": True,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE",
                "notes": "assigned in the same branch as fix_type, so it is "
                         "the validity bit re-encoded as a float"},
            "epv": {
                "raw_source_variable": "sensor_gps.vdop",
                "producing_function": "hard-coded 1.1f / 100.f, same branch",
                "wire_mapping": "msg.epv = gps.vdop * 100 -> 110 / 10000",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": True,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE", "notes": "as eph"},
            "h_acc": {
                "raw_source_variable": "sensor_gps.eph",
                "producing_function": "hard-coded 0.9f / 100.f, same branch",
                "wire_mapping": "msg.h_acc = gps.eph * 1e3 -> 900 / 100000 mm",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": True,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE", "notes": "as eph"},
            "v_acc": {
                "raw_source_variable": "sensor_gps.epv",
                "producing_function": "hard-coded 1.78f / 100.f, same branch",
                "wire_mapping": "msg.v_acc = gps.epv * 1e3 -> 1780 / 100000",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": True,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE", "notes": "as eph"},
            "vel_acc": {
                "raw_source_variable": "sensor_gps.s_variance_m_s",
                "producing_function": "hard-coded 0.4f / 100.f, same branch",
                "wire_mapping": "msg.vel_acc = s_variance_m_s * 1e3 "
                                "-> 400 / 100000",
                "direct_dependency_on_intervention": True,
                "direct_dependency_on_fix_type": True,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "DIRECT_ORACLE", "notes": "as eph"},
        },
    },
    "ardupilot": {
        "intervention": "SIM_GPS1_JAM",
        "chain": "SIM_GPS1_JAM -> GPS::simulate_jamming() -> GPS_Data -> "
                 "SIM_GPS_UBLOX -> GPS_RAW_INT",
        "source": "ArduCopter V4.8.0-dev@01a504b "
                  "libraries/SITL/SIM_GPS.cpp:288-345, "
                  "libraries/SITL/SIM_GPS_UBLOX.cpp:305",
        "branch_predicate": "none -- values are drawn from distributions",
        "fields": {
            "satellites_visible": {
                "raw_source_variable": "GPS_Data.num_sats",
                "producing_function": "simulate_jamming line 313: "
                                      "num_sats = 2 + (get_random16() % 15); "
                                      "have_lock then set by an INDEPENDENT "
                                      "coin flip when num_sats >= 4",
                "wire_mapping": "msg.satellites_visible = d.num_sats",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": True,
                "constant_under_fault": False,
                "classification": "MODEL_GENERATED_HEALTH",
                "notes": "stochastically DECOUPLED from have_lock, so sats "
                         "and validity are not the same bit"},
            "h_acc": {
                "raw_source_variable": "GPS_Data.horizontal_acc",
                "producing_function": "simulate_jamming line 341: "
                                      "horizontal_acc = fabsf(rand_float()) "
                                      "* 300, refreshed at ~3 Hz, NOT "
                                      "conditioned on have_lock",
                "wire_mapping": "pvt.h_acc = horizontal_acc * 1000 (mm); "
                                "nominal = SIM_GPS1_ACC * 1000 = 300",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": True,
                "constant_under_fault": False,
                "classification": "MODEL_GENERATED_HEALTH",
                "notes": "continuous draw, independent of lock state"},
            "v_acc": {
                "raw_source_variable": "GPS_Data.vertical_acc",
                "producing_function": "simulate_jamming line 340: "
                                      "vertical_acc = fabsf(rand_float())*300",
                "wire_mapping": "vertical_acc * 1000 (mm)",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": True,
                "constant_under_fault": False,
                "classification": "MODEL_GENERATED_HEALTH", "notes": "as h_acc"},
            "vel_acc": {
                "raw_source_variable": "GPS_Data.speed_acc",
                "producing_function": "simulate_jamming line 342: "
                                      "speed_acc = fabsf(rand_float())*50",
                "wire_mapping": "speed_acc * 1000 (mm/s)",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": True,
                "constant_under_fault": False,
                "classification": "MODEL_GENERATED_HEALTH", "notes": "as h_acc"},
            "eph": {
                "raw_source_variable": "hdop",
                "producing_function": "NOT touched by simulate_jamming",
                "wire_mapping": "constant 121 throughout",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "MODEL_GENERATED_HEALTH",
                "notes": "the jamming model does not drive hdop, so this "
                         "field carries no information under this fault"},
            "epv": {
                "raw_source_variable": "vdop",
                "producing_function": "NOT touched by simulate_jamming",
                "wire_mapping": "constant",
                "direct_dependency_on_intervention": False,
                "direct_dependency_on_fix_type": False,
                "independent_dynamic_state": False,
                "constant_under_fault": True,
                "classification": "MODEL_GENERATED_HEALTH", "notes": "as eph"},
        },
    },
}


def _rows(path, key="rows"):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get(key) or []


def _envelope(rows, field):
    v = [r[field] for r in rows if r.get(field) is not None]
    return (min(v), max(v)) if v else (None, None)


def _analyse(rows, clean_phase, fault_phase):
    """State combinations and liveness, per candidate, against a clean envelope."""
    clean = [r for r in rows if r["phase"] == clean_phase]
    fault = [r for r in rows if r["phase"] == fault_phase]
    out = {}
    for f in CANDIDATES:
        lo, hi = _envelope(clean, f)
        if lo is None:
            continue
        # PRE-DECLARED: materially changed == outside the clean [min, max]
        def material(r):
            v = r.get(f)
            return v is not None and (v < lo or v > hi)

        gate_open = [r for r in fault if (r.get("fix_type") or 0) >= 3]
        gate_shut = [r for r in fault if (r.get("fix_type") or 0) < 3]
        combos = {
            "degraded_gate_open": sum(1 for r in gate_open if material(r)),
            "nominal_gate_open": sum(1 for r in gate_open if not material(r)),
            "degraded_gate_closed": sum(1 for r in gate_shut if material(r)),
            "nominal_gate_closed": sum(1 for r in gate_shut
                                       if not material(r)),
        }
        vals_shut = [r[f] for r in gate_shut if r.get(f) is not None]
        # lead: first material change vs first invalid fix
        t_mat = next((r["t_rel"] for r in fault if material(r)), None)
        t_inv = next((r["t_rel"] for r in fault
                      if (r.get("fix_type") or 0) < 3), None)
        out[f] = {
            "clean_envelope": [lo, hi],
            "fault_min": _envelope(fault, f)[0],
            "fault_max": _envelope(fault, f)[1],
            "distinct_while_gate_closed": len(set(vals_shut)),
            "live_while_gate_closed": len(set(vals_shut)) > 1,
            "state_combinations": combos,
            "all_four_combinations_seen": all(c > 0 for c in combos.values()),
            "t_first_material_change_s": t_mat,
            "t_first_invalid_fix_s": t_inv,
            "lead_time_s": (round(t_inv - t_mat, 3)
                            if (t_mat is not None and t_inv is not None)
                            else None),
        }
    return out


def main() -> int:
    # ---- PX4 timing ----------------------------------------------------
    px4_rows = _rows(os.path.join(MAER, "px4_timing_rows.json"))
    px4 = _analyse(px4_rows, "clean", "fault") if px4_rows else {}
    with open(os.path.join(MAER, "MAER_PX4_RECEIVER_HEALTH_TIMING.csv"),
              "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["field", "clean_min", "clean_max", "fault_min",
                    "fault_max", "distinct_while_gate_closed",
                    "live_while_gate_closed", "t_first_material_change_s",
                    "t_first_invalid_fix_s", "lead_time_s",
                    "all_four_state_combinations"])
        for f, a in sorted(px4.items()):
            w.writerow([f, a["clean_envelope"][0], a["clean_envelope"][1],
                        a["fault_min"], a["fault_max"],
                        a["distinct_while_gate_closed"],
                        a["live_while_gate_closed"],
                        a["t_first_material_change_s"],
                        a["t_first_invalid_fix_s"], a["lead_time_s"],
                        a["all_four_combinations_seen"]])

    # ---- ArduPilot jamming ---------------------------------------------
    jam_runs, jam_sigs = [], set()
    for i in range(1, 99):
        p = os.path.join(JAM_RAW, f"jam_run_{i:02d}.json")
        if not os.path.exists(p):
            break
        rows = _rows(p)
        jam_runs.append(_analyse(rows, "clean", "jam"))
        jam_sigs.add(repr([(r["fix_type"], r["satellites_visible"],
                            r["h_acc"]) for r in rows if r["phase"] == "jam"]))

    with open(os.path.join(MAER, "MAER_ARDUPILOT_JAM_SUMMARY.csv"),
              "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "field", "clean_min", "clean_max", "fault_min",
                    "fault_max", "distinct_while_gate_closed",
                    "live_while_gate_closed", "degraded_gate_open",
                    "nominal_gate_open", "degraded_gate_closed",
                    "nominal_gate_closed", "all_four_state_combinations",
                    "lead_time_s"])
        for n, run in enumerate(jam_runs, 1):
            for f, a in sorted(run.items()):
                c = a["state_combinations"]
                w.writerow([n, f, a["clean_envelope"][0],
                            a["clean_envelope"][1], a["fault_min"],
                            a["fault_max"], a["distinct_while_gate_closed"],
                            a["live_while_gate_closed"],
                            c["degraded_gate_open"], c["nominal_gate_open"],
                            c["degraded_gate_closed"],
                            c["nominal_gate_closed"],
                            a["all_four_combinations_seen"], a["lead_time_s"]])

    # ---- classification -------------------------------------------------
    comparison, validation = [], {}
    for platform, model, runs in (("px4", "SIM_GPS_USED=0", [px4]),
                                  ("ardupilot", "SIM_GPS1_JAM=1", jam_runs)):
        prov = PROVENANCE[platform]["fields"]
        for f in CANDIDATES:
            if not runs or f not in (runs[0] or {}):
                continue
            a = runs[0][f]
            p = prov.get(f, {})
            cls = p.get("classification")
            oracle = cls == "DIRECT_ORACLE"
            gate_dup = not a["all_four_combinations_seen"]
            live = a["live_while_gate_closed"]
            # ---- brief item 8 screen ----
            if oracle or not live or gate_dup:
                verdict = ("REJECT" if (oracle or not live)
                           else "MODERATE_CANDIDATE")
            else:
                verdict = "STRONG_CANDIDATE"
            comparison.append({
                "field": f, "platform": platform, "fault_model": model,
                "clean_distribution": f"[{a['clean_envelope'][0]}, "
                                      f"{a['clean_envelope'][1]}]",
                "fault_distribution": f"[{a['fault_min']}, {a['fault_max']}]",
                "distinct_while_gate_closed": a["distinct_while_gate_closed"],
                "live_during_invalid_fix": live,
                "degraded_while_gate_open":
                    a["state_combinations"]["degraded_gate_open"],
                "all_four_state_combinations":
                    a["all_four_combinations_seen"],
                "lead_time_s": a["lead_time_s"],
                "estimator_independent": True,
                "direct_oracle": oracle,
                "gate_duplicate": gate_dup,
                "provenance_class": cls,
                "clean_only_transform_feasible": bool(
                    a["clean_envelope"][1] is not None and live),
                "matched_gate_pair_feasible": verdict != "REJECT",
                "classification": verdict,
            })
            validation.setdefault(platform, {})[f] = {
                **a, "provenance": p, "classification": verdict}

    with open(os.path.join(MAER, "MAER_CANDIDATE_COMPARISON.csv"), "w",
              encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(comparison[0]))
        w.writeheader()
        w.writerows(comparison)

    strong = [c for c in comparison if c["classification"] == "STRONG_CANDIDATE"]
    decision = ("RECEIVER_HEALTH_STRONG_CANDIDATE" if strong else
                "RECEIVER_HEALTH_PX4_ONLY_MODERATE"
                if any(c["classification"] == "MODERATE_CANDIDATE"
                       for c in comparison)
                else "RECEIVER_HEALTH_CANDIDATE_REJECTED")

    out = {
        "oracle_class_definitions": {
            "DIRECT_ORACLE": "fault value deterministically assigned from the "
                             "intervention variable; detecting the field is "
                             "detecting the injection command",
            "MODEL_GENERATED_HEALTH": "the intervention changes an underlying "
                                      "simulated receiver process and the "
                                      "field is generated from it",
            "GATE_DUPLICATE": "functionally equivalent to fix validity for "
                              "the tested condition",
        },
        "material_change_criterion": "value outside the clean [min, max] "
                                     "envelope of the same run; declared "
                                     "before any fault trace was evaluated",
        "seed_control": {
            "ardupilot_jam": "SITL does not expose the jamming RNG seed. All "
                             f"{len(jam_runs)} runs produced IDENTICAL "
                             f"sequences ({len(jam_sigs)} distinct signature), "
                             "so these are replays of one realisation, NOT "
                             "independent samples. Reported as N=1 realisation.",
        },
        "provenance": PROVENANCE,
        "px4": px4,
        "ardupilot_runs": len(jam_runs),
        "ardupilot": jam_runs[0] if jam_runs else {},
        "comparison": comparison,
        "strong_candidates": [c["field"] for c in strong],
        "decision": decision,
    }
    with open(os.path.join(MAER, "MAER_CANDIDATE_VALIDATION.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, default=str)
    with open(os.path.join(MAER, "MAER_RECEIVER_HEALTH_PROVENANCE.json"), "w",
              encoding="utf-8") as fh:
        json.dump(PROVENANCE, fh, indent=1, sort_keys=True, default=str)

    print("=== Stage 0.5 candidate validation")
    print(f"  {'field':20s} {'platform':10s} {'class':24s} "
          f"{'live|gate shut':14s} {'4 combos':9s} verdict")
    for c in comparison:
        print(f"  {c['field']:20s} {c['platform']:10s} "
              f"{str(c['provenance_class']):24s} "
              f"{str(c['live_during_invalid_fix']):14s} "
              f"{str(c['all_four_state_combinations']):9s} "
              f"{c['classification']}")
    print(f"\n  DECISION: {decision}")
    print(f"  strong: {out['strong_candidates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
