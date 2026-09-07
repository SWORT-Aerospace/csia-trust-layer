"""Generate the remaining mission-layer artifacts in one deterministic pass.

    conformance      the seven bad references plus two controls
    reconfiguration  the evidence-preserving transition analysis
    forge_seed       the compiled tables and the independent check
    graphs           the three graph levels, derived
    metrics          the definitions, with no numbers attached

Each is written separately rather than as one blob, because they are consulted
separately and a reader wanting the conformance result should not have to
parse a benchmark.

    python tools/xr/mission_artifacts.py --out-dir research/mission/results
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia_mission import graphs as G                        # noqa: E402
from csia_mission.bad_references import ALL_REFERENCES      # noqa: E402
from csia_mission.conformance import run_all                # noqa: E402
from csia_mission.forge_seed import (check_compiled,        # noqa: E402
                                     compile_contracts)
from csia_mission.metrics import definitions_doc            # noqa: E402
from csia_mission.reconfiguration import (Configuration,    # noqa: E402
                                          analyse_all)
from csia_mission.xr1_contracts import (CAPABILITIES,       # noqa: E402
                                        EVIDENCE, PRODUCTS,
                                        vehicle_profile)

#: DECLARED CONFIGURATIONS. Each says what evidence it provides; nothing is
#: inferred from a CAD model or a bounding box.
CONFIGURATIONS = {
    "FULL_PAYLOAD": Configuration.of(
        "FULL_PAYLOAD", EVIDENCE,
        "every declared sensor present and streaming"),
    "CAMERA_STOWED": Configuration.of(
        "CAMERA_STOWED",
        [e for e in EVIDENCE if not e.startswith("camera.rgb")
         and e != "visual_odometry.supported"],
        "RGB camera stowed to reduce drag. Visual odometry goes with it."),
    "THERMAL_ONLY": Configuration.of(
        "THERMAL_ONLY",
        [e for e in EVIDENCE if not e.startswith("camera.rgb")],
        "RGB module removed, thermal retained, visual odometry retained "
        "from a separate sensor"),
    "GNSS_DENIED": Configuration.of(
        "GNSS_DENIED",
        [e for e in EVIDENCE if not e.startswith("gnss.")],
        "operating where no GNSS solution is available"),
    "MINIMAL_F1": Configuration.of(
        "MINIMAL_F1",
        ["attitude.supported", "imu.primary.supported", "airspeed.supported",
         "baro.altitude.supported", "gnss.position.supported",
         "gnss.velocity.supported", "mag.field.supported",
         "timebase.supported", "power.telemetry.supported",
         "comms.telemetry_link.supported", "camera.rgb.available",
         "camera.rgb.calibration_valid"],
        "the first-flight minimum configuration"),
}

#: (from, to, the capability the transition is FOR)
TRANSITIONS = (
    # THE SELF-OCCLUSION CASE. Stowing the camera to extend endurance, when
    # visual odometry is one of the two evidence paths relative_navigation
    # names -- and the OTHER path, the reference IMU, is still there. So this
    # should NOT be self-occluding, and the analysis has to say so rather
    # than flagging every reduction.
    ("FULL_PAYLOAD", "CAMERA_STOWED", "relative_navigation"),
    # The same stow, but performed IN ORDER TO do local mapping, which needs
    # RGB_capture. That one destroys what it is for.
    ("FULL_PAYLOAD", "CAMERA_STOWED", "local_mapping"),
    ("FULL_PAYLOAD", "GNSS_DENIED", "absolute_navigation"),
    ("FULL_PAYLOAD", "GNSS_DENIED", "relative_navigation"),
    ("FULL_PAYLOAD", "THERMAL_ONLY", "thermal_capture"),
    ("MINIMAL_F1", "FULL_PAYLOAD", "local_mapping"),
)


def build_all() -> dict:
    tables = compile_contracts(CAPABILITIES, PRODUCTS, vehicle_profile())
    return {
        "conformance": run_all(ALL_REFERENCES),
        "reconfiguration": analyse_all(CONFIGURATIONS, CAPABILITIES,
                                       TRANSITIONS),
        "forge_seed": {
            "tables": tables.to_dict(),
            "independent_check": check_compiled(tables, CAPABILITIES,
                                                PRODUCTS),
        },
        "graphs": G.build(CAPABILITIES, PRODUCTS),
        "metric_definitions": definitions_doc(),
    }


def determinism_check(runs: int = 3) -> dict:
    """Compile the same inputs N times and compare the output hashes.

    Determinism is a CLAIM about the compiler, so it gets a measurement
    rather than a docstring. Same process, repeated -- which catches
    iteration-order dependence and nothing about cross-host stability. The
    portability contract's separate levels apply to that, and this does not
    pretend to cover it.
    """
    hashes = []
    for _ in range(runs):
        t = compile_contracts(CAPABILITIES, PRODUCTS, vehicle_profile())
        hashes.append(t.output_hash)
    return {
        "runs": runs,
        "output_hashes": hashes,
        "identical": len(set(hashes)) == 1,
        "scope": ("SAME PROCESS, REPEATED. This detects iteration-order "
                  "dependence. It says nothing about cross-host or "
                  "cross-version stability, which is a portability question "
                  "and is not being answered here."),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--regenerate", action="store_true")
    args = ap.parse_args(argv)

    docs = build_all()
    docs["forge_seed"]["determinism"] = determinism_check()

    names = {
        "conformance": "MISSION_CONFORMANCE.json",
        "reconfiguration": "RECONFIGURATION_ANALYSIS.json",
        "forge_seed": "FORGE_SEED_TABLES.json",
        "graphs": "MISSION_GRAPHS.json",
        "metric_definitions": "MISSION_METRIC_DEFINITIONS.json",
    }

    if args.out_dir:
        from tools.evidence_guard import protected_write
        os.makedirs(args.out_dir, exist_ok=True)
        for key, filename in sorted(names.items()):
            path = os.path.join(args.out_dir, filename)
            text = json.dumps(docs[key], indent=2, sort_keys=True,
                              default=str) + "\n"
            with protected_write(path, regenerate=args.regenerate) as fh:
                fh.write(text)
            print(f"wrote {path}")
    else:
        print(json.dumps(docs, indent=2, sort_keys=True, default=str))

    c = docs["conformance"]
    f = docs["forge_seed"]
    r = docs["reconfiguration"]
    print(f"\nconformance: {sum(1 for x in c['rows'] if x['correct'])}"
          f"/{len(c['rows'])} judged correctly, suite_correct="
          f"{c['suite_correct']}\n"
          f"forge-seed: deterministic="
          f"{f['determinism']['identical']}, independent check agrees="
          f"{f['independent_check']['agrees']}\n"
          f"reconfiguration: {r['transitions_analysed']} transitions, "
          f"self-occluding: {r['self_occluding']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
