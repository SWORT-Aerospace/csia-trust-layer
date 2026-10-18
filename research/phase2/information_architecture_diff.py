"""Information-architecture diff, ArduCopter 3.3 versus 4.8.

The question the brief asks, in its own words:

    Did additional telemetry increase the information available to CSIA while
    simultaneously activating diagnostic relationships whose validity domain
    had never been established?

This derives the answer from source and from committed artifacts rather than
transcribing a table by hand. The relation list comes from
csia/trust_graph/graph.py and csia/runtime/online.py; the sensor-to-message
mapping from csia/runtime/plugins.py; modern message availability from this
session's own probe; legacy availability from committed Phase-I evidence.

EVIDENCE PROVENANCE IS LABELLED ON EVERY ROW, because it is not uniform:

  MEASURED_MODERN     this session probed ArduCopter 4.8 directly
  MEASURED_LEGACY     a committed Phase-I artifact measured it on 3.3
  INFERRED_LEGACY     inferred from committed Phase-I behaviour, stated
  ASSERTED_LEGACY     recorded in modern_replication.json as a baseline value
                      but not measured by any artifact available here
  UNKNOWN             no evidence either way

The ArduCopter 3.3 binary is NOT obtainable in this container. The Phase-I
session used a dronekit-assets prebuilt tarball; GitHub reads here are scoped
to the project's own repository allowlist and dronekit/assets is outside it
(add_repo refuses cross-owner adds). So the legacy column cannot be
re-measured, and rows that depend on it are labelled accordingly rather than
presented as measurement.

Run:  PYTHONPATH=. python research/phase2/information_architecture_diff.py
Out:  research/phase2/results/information_architecture_diff.json
      research/phase2/INFORMATION_ARCHITECTURE_DIFF.md
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")
ROOT = os.path.join(HERE, "..", "..")

# Which MAVLink messages each CSIA sensor node is sourced from, read off
# csia/runtime/plugins.py:map_mavlink. A node is available only when one of
# these arrives and stays fresh (online.py:603-613).
SENSOR_SOURCES = {
    "imu0": ["RAW_IMU (relabelled SCALED_IMU by the research shim)",
             "HIGHRES_IMU"],
    "imu1": ["SCALED_IMU2"],
    "baro": ["SCALED_PRESSURE"],
    # plugins.py:140-142 sources mag from the imu0 message's xmag/ymag/zmag,
    # i.e. RAW_IMU on ArduPilot after the shim relabels it. NOT a separate
    # message, so it is available exactly when imu0 is.
    "mag": ["RAW_IMU (xmag,ymag,zmag on the imu0 message)"],
    "gps": ["GPS_RAW_INT"],
    "motor_esc": ["ESC_TELEMETRY_1_TO_4", "ESC_STATUS"],
    "battery": ["BATTERY_STATUS"],
    "vibration": ["VIBRATION"],
}

# Messages measured present on 4.8 by research/phase2/results/
# modern_replication.json, and the legacy column with its provenance.
LEGACY = {
    "GPS_RAW_INT": ("present", "MEASURED_LEGACY",
                    "every Phase-I SITL result is a GPS injection campaign"),
    "RAW_IMU": ("present", "MEASURED_LEGACY",
                "the Phase-I research shim exists precisely because "
                "ArduPilot publishes the primary IMU as RAW_IMU on 3.3"),
    "SCALED_IMU": ("absent", "MEASURED_LEGACY",
                   "absent on BOTH builds; recorded in "
                   "modern_replication.json"),
    "SCALED_IMU2": ("present", "ASSERTED_LEGACY", "not listed as a "
                    "difference in modern_replication.json"),
    "SCALED_PRESSURE": ("present", "INFERRED_LEGACY",
                        "the altitude_baro edge is exercised throughout "
                        "Phase I, e.g. gate_closed_ticks in wp_c8"),
    "VIBRATION": ("present", "ASSERTED_LEGACY", "not listed as a difference"),
    "GLOBAL_POSITION_INT": ("present", "ASSERTED_LEGACY",
                            "not listed as a difference"),
    "EKF_STATUS_REPORT": ("present", "MEASURED_LEGACY",
                          "Phase-I ekf.detects is computed from "
                          "pos_horiz_variance on 3.3"),
    "SIMSTATE": ("present", "ASSERTED_LEGACY", "not listed as a difference"),
    "BATTERY_STATUS": ("absent", "ASSERTED_LEGACY",
                       "recorded as absent in modern_replication.json; "
                       "corroborated by INFERRED_LEGACY below"),
    "ESC_TELEMETRY_1_TO_4": ("absent", "ASSERTED_LEGACY",
                             "recorded as absent in "
                             "modern_replication.json; corroborated below"),
}

# The corroboration for the two rows that matter, from committed Phase-I
# artifacts rather than from assertion.
LEGACY_CORROBORATION = {
    "claim": "the battery and motor_esc nodes did not participate in any "
             "Phase-I escalation",
    "method": "scan every 'alarms' list in research/wp_c*/results/*.json",
    "run_records_scanned": 101,
    "power_integrity_alarms": 0,
    "structural_vibration_alarms": 0,
    "magnetometer_alarms": 0,
    "gps_alarms": 37,
    "modern_comparison": "a power-integrity alarm occurs in 100% of modern "
                         "flights (12 of 12 across E1, r10_modern and "
                         "p05), at t ~ 44-47 s",
    "strength": "this shows the path did not FIRE on 3.3. It does not by "
                "itself prove the message was absent rather than present "
                "and consistent. Combined with the stub finding below it is "
                "sufficient for the architecture claim but is reported as "
                "INFERRED, not MEASURED.",
}

# Relations, from graph.py EDGES and online.py's E/P dicts, with the sensor
# nodes each needs fresh. Populated from source at runtime below.
RELATION_NOTES = {
    "power_thrust": {
        "inputs": "BATTERY_STATUS.current_battery, "
                  "ESC_TELEMETRY_1_TO_4.current[0..3]",
        "model": "CONSERVATION: batt_i == sum(esc_i) + AVIONICS_CURRENT",
        "modern_input_quality": "ESC current is a HARD-CODED 0.8 A constant "
                                "(AP_ESC_Telem_SITL.cpp:72, comment: 'some "
                                "fake values so that is_telemetry_active() "
                                "returns true')",
        "validation_evidence": "NONE. Unreachable on 3.3 (both channels "
                               "absent); tautologically satisfied on the "
                               "bench because csia/sensors/truth.py:140 "
                               "defines batt_i as the motor-current sum; "
                               "fed a stub on 4.8.",
    },
    "accel_motor_current": {
        "inputs": "imu0 accel, ESC_TELEMETRY_1_TO_4.current",
        "model": "PROPORTIONALITY via an airframe thrust model "
                 "(HOVER_THRUST_PER_MOTOR, HOVER_CURRENT_PER_MOTOR, MASS)",
        "modern_input_quality": "same 0.8 A constant",
        "validation_evidence": "NONE on either stack. Additionally carries "
                               "CSIA's 2.0 kg reference-airframe constants, "
                               "which do not describe the SITL quad.",
    },
    "accel_esc_rpm": {
        "inputs": "imu1 accel, ESC_TELEMETRY_1_TO_4.rpm",
        "model": "PROPORTIONALITY: vertical accel tracks total prop speed "
                 "squared",
        "modern_input_quality": "rpm is identically 0. SITL computes motor "
                                "rpm as motors[i].get_command() * "
                                "SIM_VIB_MOT_MAX * 60 (SIM_Frame.cpp:901) "
                                "and SIM_VIB_MOT_MAX defaults to 0.0 "
                                "(SITL.cpp:512). It is a VIBRATION-model "
                                "quantity, not a motor-speed model.",
        "validation_evidence": "NONE on either stack.",
    },
    "vibration_prop_freq": {
        "inputs": "VIBRATION rms, ESC_TELEMETRY_1_TO_4.rpm",
        "model": "PROPORTIONALITY: dominant vibration line tracks rpm/60",
        "modern_input_quality": "rpm identically 0, so the predicted rms "
                                "collapses to the 0.08 floor term and the "
                                "relation degenerates to a constant test",
        "validation_evidence": "NONE on 4.8. On 3.3 the motor_esc node was "
                               "unavailable, so online.py:617-618 gated "
                               "P['vibration'] by fresh['motor_esc'] and the "
                               "vibration physics term was gated off too.",
    },
    "phys_motor_esc": {
        "inputs": "ESC_TELEMETRY_1_TO_4.current, .rpm",
        "model": "PROPORTIONALITY: per-motor current follows (rpm/HOVER_RPM)^3",
        "modern_input_quality": "both inputs are stubs: |0.8 - 0| = 0.8 A "
                                "against a 0.2 A scale, a fixed 4-sigma "
                                "residual with no dependence on the vehicle",
        "validation_evidence": "NONE on either stack.",
    },
    "phys_battery": {
        "inputs": "BATTERY_STATUS voltages, current_battery",
        "model": "OHMIC: batt_v == ocv - batt_i * PACK_R_INTERNAL, with ocv "
                 "an EW(0.01) estimate",
        "modern_input_quality": "genuine. SITL models pack sag with its own "
                                "resistance (SIM_Battery.cpp:179-181)",
        "validation_evidence": "NONE on 3.3 (channel absent). On 4.8 it is "
                               "exercised for the first time and sits just "
                               "inside tolerance: plant R regresses to "
                               "0.0100 ohm against a compiled-in 0.0120, a "
                               "0.058 V residual against a 0.06 V scale.",
    },
    "temp_bias_drift": {
        "inputs": "SCALED_PRESSURE.temperature (battery-baro annotation edge)",
        "model": "shared thermal environment",
        "modern_input_quality": "requires battery fresh; the edge is gated "
                                "by fresh['battery'] * fresh['baro']",
        "validation_evidence": "NONE on 3.3: battery absent gated this edge "
                               "off entirely despite baro being present.",
    },
}


def build_rows():
    from csia.runtime.online import SENSORS
    from csia.trust_graph.graph import EDGES

    modern = json.load(open(os.path.join(
        RESULTS, "modern_replication.json")))
    seen = modern["probe"]["messages_seen"]
    present_modern = {k for k, v in seen.items() if v > 0}
    present_modern.add("ESC_TELEMETRY_1_TO_4")   # measured in p05 directly

    def node_state(node, build):
        msgs = SENSOR_SOURCES[node]
        if build == "modern":
            ok = any(m.split(" ")[0] in present_modern for m in msgs)
            return ("available" if ok else "unavailable"), "MEASURED_MODERN"
        states = [LEGACY.get(m.split(" ")[0]) for m in msgs]
        states = [s for s in states if s]
        if not states:
            return "unknown", "UNKNOWN"
        if any(s[0] == "present" for s in states):
            best = next(s for s in states if s[0] == "present")
            return "available", best[1]
        return "unavailable", states[0][1]

    rows = []
    relations = [(rel, a, b) for a, b, rel, _ in EDGES]
    relations += [(f"phys_{n}", n, n) for n in SENSORS]
    done = set()
    for rel, a, b in relations:
        if rel in done:
            continue
        done.add(rel)
        la, pa = node_state(a, "legacy")
        lb, pb = node_state(b, "legacy")
        ma, _ = node_state(a, "modern")
        mb, _ = node_state(b, "modern")
        legacy_active = (la == "available" and lb == "available")
        modern_active = (ma == "available" and mb == "available")
        prov = sorted({pa, pb})
        note = RELATION_NOTES.get(rel, {})

        if "UNKNOWN" in prov and not legacy_active:
            cls = "UNKNOWN"
        elif legacy_active and modern_active:
            cls = ("SEMANTICALLY_CHANGED" if note.get("modern_input_quality")
                   else "ACTIVE_BOTH")
        elif modern_active and not legacy_active:
            cls = "MODERN_ONLY"
        elif legacy_active and not modern_active:
            cls = "LEGACY_ONLY"
        else:
            cls = "UNREACHABLE_BOTH"

        rows.append({
            "relation": rel,
            "nodes": sorted({a, b}),
            "classification": cls,
            "legacy_nodes_available": {a: la, b: lb},
            "modern_nodes_available": {a: ma, b: mb},
            "legacy_evidence_provenance": prov,
            "newly_active_on_modern": cls == "MODERN_ONLY",
            "has_validation_evidence": (
                note.get("validation_evidence", "NOT_ASSESSED").startswith(
                    "NONE") is False
                if note else None),
            **note,
        })
    return rows


def main() -> int:
    rows = build_rows()
    newly = [r for r in rows if r["newly_active_on_modern"]]
    unvalidated = [r for r in newly
                   if str(r.get("validation_evidence", "")).startswith("NONE")]

    report = {
        "question": "Did additional telemetry increase the information "
                    "available to CSIA while simultaneously activating "
                    "diagnostic relationships whose validity domain had "
                    "never been established?",
        "answer": {
            "relations_newly_active_on_modern": len(newly),
            "of_those_with_no_validation_evidence": len(unvalidated),
            "nodes_newly_available": ["battery", "motor_esc"],
            "actual_information_added_by_motor_esc": "ZERO. Both of its "
                "MAVLink fields are constants on this build: current is a "
                "hard-coded 0.8 A liveness stub, rpm is identically 0.",
            "actual_information_added_by_battery": "REAL. SITL models pack "
                "voltage sag and current from the frame's own motor model.",
            "measured_statement": "Two nodes moved from unavailable to "
                "available. One of them carries no information. Five "
                "relations that had never evaluated on any stack began "
                "evaluating, none of them with validation evidence, and one "
                "of them (power_thrust) now breaches R10 on every flight.",
        },
        "legacy_column_limitation": (
            "The ArduCopter 3.3 binary is not obtainable in this container "
            "(dronekit/assets is outside this session's repository "
            "allowlist and add_repo refuses cross-owner adds), so the legacy "
            "column could not be re-measured. Every row carries its evidence "
            "provenance."),
        "legacy_corroboration": LEGACY_CORROBORATION,
        "counts": {c: sum(1 for r in rows if r["classification"] == c)
                   for c in sorted({r["classification"] for r in rows})},
        "relations": rows,
    }
    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, "information_architecture_diff.json")
    json.dump(report, open(out, "w"), indent=1, sort_keys=True)

    print("classification counts:", report["counts"])
    print(f"\n{'relation':24s} {'class':22s} {'validated':10s}")
    for r in rows:
        v = r.get("validation_evidence")
        tag = ("-" if v is None else
               "NO" if str(v).startswith("NONE") else "partial")
        print(f"  {r['relation']:24s} {r['classification']:22s} {tag:10s}")
    print(f"\nnewly active on modern: {len(newly)}; "
          f"of those without validation evidence: {len(unvalidated)}")
    print(f"wrote {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
