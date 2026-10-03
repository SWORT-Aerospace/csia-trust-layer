#!/usr/bin/env python3
"""PRIME E1: build the external pilot bundle, outside git. RESEARCH ONLY.

    .venv/bin/python research/csia_prime/build_pilot_bundle.py [--out DIR]

**What it builds** (default `DIR` = /home/user/prime_raw/pilot_bundle):

| path | for | contents |
|---|---|---|
| `csia_pilot_participant.zip` | the participant | twelve ULogs `P01.ulg`-`P12.ulg` (blinded), the product wheel, the participant documents (`pilot_package/`), the support matrix, the data notice |
| `experimenter/GROUND_TRUTH.json` | the experimenter only | which case each P-number is, its truth, and what blinding removed |
| `experimenter/ASSIGNMENT.json` | the experimenter only | the counterbalanced crossover: per participant, form, order and which logs use the analyzer |
| `experimenter/SCORING_RUBRIC.md` | the experimenter only | the frozen rubric, copied from `pilot_package_experimenter/` |

**In the repository** it writes PILOT_BUNDLE.json: the SHA-256 of every file
in the participant zip, the blinding counts, and whether the product's
conclusions on each blinded log equal those on its source. It holds no
truth, and the P-number of a case is not derivable from it.

**Blinding.** The SITL logs record their own fault injection:
- the in-flight change of `SIH_MOT_EFFn`;
- PX4's `[failure_injection_manager] Injected: ...` message, which CSIA's
  alert list also shows.

Either gives the answer away in both test conditions. The builder removes
exactly those two kinds of record, with pyulog's writer, and nothing else.
It then re-runs the product on the blinded copy. A blinded log whose
conclusions differ from its source's is reported, never used silently.

**Case B of the matched pair** is RB-001's nominal CAL1 with motor_0's logged
RPM scaled by sqrt(0.6) from 70 s: the demo's construction
(`demo_ab.py`), written into a ULog so a participant can open it. RPM is
an integer field; the scaled value is rounded.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
from pyulog import ULog

import common_prime as C

DEFAULT_OUT = C.OUT_RAW / "pilot_bundle"
PARTICIPANT_DOCS = C.HERE / "pilot_package"
EXPERIMENTER_DOCS = C.HERE / "pilot_package_experimenter"
SEED = 20261002                       # the P-number shuffle, fixed before any participant
CORRUPT_T = 70.0                      # case B: seconds from log start, as in demo_ab.py
LEAK_TEXT = ("failure_injection_manager",)
LEAK_PARAM_PREFIX = "SIH_"
PARTICIPANTS = 10                     # the protocol's upper count; more participants repeat the cycle
S1 = C.REPO.parent / "csia_2_2_pilot_raw/S1/S1.ulg"

#: (case key, source, data class, truth). The truth goes to the experimenter key only.
CASES = [
    ("nominal_maneuvering", C.SITL_RB001 / "CAL2.ulg", "SITL",
     {"what": "nominal: repositions with 90 degree yaw changes, no fault", "fault": None,
      "correct": "nothing abnormal attributable; no propulsion symptom"}),
    ("motor_loss_hover_motor_1", C.SITL_2_3 / "V1.ulg", "SITL",
     {"what": "motor_1 at 60 % effect from 50 s, hover", "fault": "physical: motor_1 thrust effectiveness",
      "onset_s_boot": 50.0,
      "correct": "motor_1 lost effect (physical); cause within the propulsion path not separable from this log"}),
    ("matched_A_motor_loss_motor_0", C.SITL_2_3 / "V4.ulg", "SITL",
     {"what": "motor_0 at 60 % effect from 50 s, hover (matched pair, case A)",
      "fault": "physical: motor_0 thrust effectiveness", "onset_s_boot": 50.0,
      "correct": "motor_0 lost effect (physical); RPM deficit is real; cause not separable"}),
    ("matched_B_rpm_corruption_motor_0", C.SITL_RB001 / "CAL1.ulg", "SITL + OFFLINE CORRUPTION",
     {"what": "healthy motor_0; its logged RPM x sqrt(0.6) from 70 s after log start (matched pair, case B)",
      "fault": "telemetry: motor_0 RPM report", "onset_s_log": CORRUPT_T,
      "correct": "motor_0 RPM report wrong; vehicle response nominal; NOT a motor failure"}),
    ("esc_rpm_x10_motor_2", C.SITL_2_3 / "V10.ulg", "SITL",
     {"what": "ESC instance 3 (motor_2) reports RPM x 10 from 50 s; motor healthy",
      "fault": "telemetry: motor_2 RPM report", "onset_s_boot": 50.0,
      "correct": "motor_2 telemetry wrong; motor healthy; NOT a motor failure"}),
    ("esc_telemetry_offline_motor_1", C.SITL_2_3 / "V9.ulg", "SITL",
     {"what": "ESC instance 2 (motor_1) telemetry off from 50 s; motor healthy",
      "fault": "telemetry: motor_1 ESC report lost", "onset_s_boot": 50.0,
      "correct": "motor_1 telemetry lost; motor health unobservable from ESC; vehicle response nominal"}),
    ("gps_loss", C.SITL_2_3 / "V7.ulg", "SITL",
     {"what": "GPS off from 50 s; PX4 blind-land failsafe", "fault": "navigation: GPS", "onset_s_boot": 50.0,
      "correct": "GPS lost; no propulsion fault; navigation outside the propulsion profile"}),
    ("magnetometer_loss", S1, "SITL",
     {"what": "magnetometer off at about 75 s (EKF2 selector on)", "fault": "sensor: magnetometer",
      "onset_s_boot": 74.5, "correct": "magnetometer lost; heading aiding changed; no propulsion fault"}),
    ("motor_loss_hold_motor_2", C.SITL_2_3 / "V12.ulg", "SITL",
     {"what": "motor_2 at 60 % effect from 100 s, in a hold after maneuvers",
      "fault": "physical: motor_2 thrust effectiveness", "onset_s_boot": 100.0,
      "correct": "motor_2 lost effect (physical); cause not separable"}),
    ("motor_loss_maneuvering_motor_2", C.SITL_2_3 / "V13.ulg", "SITL",
     {"what": "motor_2 at 60 % effect from 77 s, mid-maneuver", "fault": "physical: motor_2 thrust effectiveness",
      "onset_s_boot": 77.0,
      "correct": "motor_2 RPM deficit seen; physical confirmation not possible during the maneuver; a "
                 "single confirmed cause is not supported"}),
    ("real_logger_dropouts", C.REAL_PYULOG / "sample.ulg", "REAL",
     {"what": "real AUAV X2.1 (pyulog test log): short flight, 4 logger dropouts, pre-allocation PX4",
      "fault": None, "correct": "no fault known; propulsion evidence partly unavailable; dropouts present"}),
    ("real_unsupported_boat", C.REAL_PX4_DOCS, "REAL",
     {"what": "real FMUv5 boat (PX4 documentation sample log)", "fault": None,
      "correct": "outside scope: not a multirotor; no multirotor conclusion should be drawn"}),
]
NOTICE = """Data notice for the sample logs

- Logs marked SITL were produced by this program in PX4 software-in-the-loop
  simulation (PX4 547e2ca, SIH quadrotor). They are not real flights.
- SITL logs may carry injected faults of any kind, introduced in the
  simulator or by modifying a logged field afterwards. Which logs, and
  which faults, is what the session asks you to determine.
- Logs marked REAL:
  - one is a PX4/pyulog test log (BSD-3-Clause, (c) the PX4 development team);
  - one is the PX4 documentation sample log
    sample_log_boat_testing_2022-7-28-13-31-16.ulg (PX4 user guide,
    CC-BY-4.0, (c) the PX4 contributors).
- Records that would reveal how a SITL fault was injected were removed from
  the SITL logs. Apart from that and the injected faults, nothing was changed.
- Not for redistribution outside the pilot.
"""


def blind(src: Path, dst: Path, corrupt: bool) -> dict:
    """Write a copy of `src` without the injection records; return what was removed."""
    u = ULog(str(src))
    params = [c for c in u.changed_parameters if c[1].startswith(LEAK_PARAM_PREFIX)]
    msgs = [m for m in u.logged_messages if any(s in m.message for s in LEAK_TEXT)]
    u.changed_parameters[:] = [c for c in u.changed_parameters if not c[1].startswith(LEAK_PARAM_PREFIX)]
    u.logged_messages[:] = [m for m in u.logged_messages if not any(s in m.message for s in LEAK_TEXT)]
    tagged = 0
    for k, lst in list(getattr(u, "logged_messages_tagged", {}).items()):
        keep = [m for m in lst if not any(s in m.message for s in LEAK_TEXT)]
        tagged += len(lst) - len(keep)
        u.logged_messages_tagged[k] = keep
    corrupted = 0
    if corrupt:
        for d in u.data_list:
            if d.name == "esc_status":
                after = d.data["timestamp"].astype(np.int64) >= int(u.start_timestamp) + int(CORRUPT_T * 1e6)
                f = d.data["esc[0].esc_rpm"]
                d.data["esc[0].esc_rpm"] = np.where(after, np.round(f * np.sqrt(0.6)), f).astype(f.dtype)
                corrupted += int(after.sum())
    u.write_ulog(str(dst))
    raw = dst.read_bytes()
    check = ULog(str(dst))
    leaks = ([s for s in LEAK_TEXT if s.encode() in raw]
             + [c[1] for c in check.changed_parameters if c[1].startswith(LEAK_PARAM_PREFIX)])
    return {"removed_parameter_changes": [[round(t * 1e-6, 3), k, v] for t, k, v in params],
            "removed_messages": [[round(m.timestamp * 1e-6, 3), m.message] for m in msgs],
            "removed_tagged_messages": tagged, "corrupted_samples": corrupted, "leaks_after_blinding": leaks}


def assure(path: Path, out: Path) -> dict:
    t0 = time.monotonic()
    r = subprocess.run([sys.executable, "-m", "csia_evidence_assurance", "assure", str(path), "--out", str(out)],
                       cwd=C.REPO, capture_output=True, text=True)
    m = json.loads((out / "report.json").read_text())
    s = (out / "assurance_summary.txt").read_text()
    m.get("inputs", {}).pop("ulog", None)
    return {"exit": r.returncode, "report": m, "seconds": round(time.monotonic() - t0, 1),
            "what_happened": s.split("WHAT HAPPENED?\n")[1].split("WHEN DID")[0].strip().splitlines(),
            "support": json.loads((out / "support.json").read_text())["support"]["status"],
            "attribution": m["summary"]["attribution"]["verdict"]}


def wheel(dst: Path) -> Path:
    subprocess.run([sys.executable, "-m", "pip", "wheel", "-q", "--no-deps", str(C.REPO), "-w", str(dst)],
                   check=True, capture_output=True, text=True)
    return next(dst.glob("csia*.whl"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    out = ap.parse_args().out
    if out.exists():
        shutil.rmtree(out)
    (out / "experimenter").mkdir(parents=True)
    order = list(range(len(CASES)))
    random.Random(SEED).shuffle(order)
    key, files, checks = {}, {}, {}
    demo_b = json.loads((C.HERE / "DEMO_AB.json").read_text())["cases"]["B"]
    zpath = out / "csia_pilot_participant.zip"
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        td = Path(td)
        for pos, i in enumerate(order, start=1):
            name, src, data, truth = CASES[i]
            pid = f"P{pos:02d}"
            dst = td / f"{pid}.ulg"
            corrupt = name.startswith("matched_B")
            shown = "REAL" if data == "REAL" else "SITL"      # what a participant is told
            if data.startswith("SITL"):
                record = blind(src, dst, corrupt)
            else:
                shutil.copyfile(src, dst)
                record = {"copied_unchanged": True}
            after = assure(dst, td / f"{pid}_out")
            before = assure(src, td / f"{pid}_src") if not corrupt else None
            if corrupt:
                # The demo's facts: no symptom (only UNCONFIRMED and attribution lines), attribution as there.
                no_symptom = all(ln.lstrip("- ").startswith(("UNCONFIRMED", "attribution"))
                                 for ln in after["what_happened"])
                same = {"compared_with": "DEMO_AB.json case B (the in-memory demo)",
                        "conclusions_equal": no_symptom and after["attribution"] == demo_b["attribution"]["verdict"],
                        "report_identical_except_input": None}
            else:
                diff = sorted(k for k in after["report"] if after["report"][k] != before["report"].get(k))
                same = {"compared_with": "the source log",
                        "conclusions_equal": (after["what_happened"] == before["what_happened"]
                                              and after["attribution"] == before["attribution"]
                                              and after["support"] == before["support"]),
                        "report_identical_except_input": not diff, "differing_report_keys": diff}
            z.write(dst, f"logs/{pid}.ulg")
            files[f"logs/{pid}.ulg"] = C.sha(dst)
            key[pid] = {"case": name, "source": src.name, "source_sha256": C.sha(src), "data": data,
                        "truth": truth, "blinding": record, "product_on_blinded_log": {
                            "what_happened": after["what_happened"], "attribution": after["attribution"],
                            "support": after["support"]}, "blinded_vs_source": same}
            checks[pid] = {"data": shown, "exit_code": after["exit"], "assure_seconds": after["seconds"],
                           "leaks_after_blinding": record.get("leaks_after_blinding", []),
                           "conclusions_equal": same["conclusions_equal"],
                           "report_identical_except_input": same["report_identical_except_input"]}
            print(pid, name, data, same["conclusions_equal"], same["report_identical_except_input"], flush=True)
            dst.unlink()
        whl = wheel(td / "wheel")
        z.write(whl, f"install/{whl.name}")
        files[f"install/{whl.name}"] = C.sha(whl)
        with zipfile.ZipFile(whl) as w:
            names = w.namelist()
        wheel_check = {"file": whl.name,
                       "has_support_matrix": any(n.endswith("support_matrix.json") for n in names),
                       "has_research_tests_or_truth": any(n.startswith(("research/", "tests/"))
                                                          or "GROUND_TRUTH" in n for n in names),
                       "has_csia_assure_entry_point": "csia-assure" in _entry_points(whl)}
        for f in sorted(PARTICIPANT_DOCS.glob("*.md")):
            z.write(f, f.name)
            files[f.name] = C.sha(f)
        sm = C.REPO / "csia_evidence_assurance/support_matrix.json"
        z.write(sm, "SUPPORT_MATRIX.json")
        files["SUPPORT_MATRIX.json"] = C.sha(sm)
        z.writestr("DATA_NOTICE.txt", NOTICE)
        participant_listing = {"logs": {pid: c["data"] for pid, c in sorted(checks.items())}}
        z.writestr("LOGS.json", json.dumps(participant_listing, indent=1, sort_keys=True) + "\n")
    C.write_json(out / "experimenter/GROUND_TRUTH.json", {
        "label": "EXPERIMENTER ONLY. Never give this file, or the repository, to a participant.",
        "seed": SEED, "cases": key})
    C.write_json(out / "experimenter/ASSIGNMENT.json", assignment(sorted(key)))
    for f in sorted(EXPERIMENTER_DOCS.glob("*.md")):
        shutil.copyfile(f, out / "experimenter" / f.name)
    C.write_json(C.HERE / "PILOT_BUNDLE.json", {
        "label": "PRIME E1: the participant bundle as built (outside git); no truth here",
        "bundle": str(zpath), "bundle_sha256_note": "the zip itself is not byte-stable (zip timestamps); its members are",
        "participant_files_sha256": files, "wheel": wheel_check,
        "logs": dict(sorted(checks.items())),
        "all_blinded_without_leaks": all(not c["leaks_after_blinding"] for c in checks.values()),
        "all_conclusions_equal": all(c["conclusions_equal"] for c in checks.values()),
        "all_exit_zero": all(c["exit_code"] == 0 for c in checks.values())})


def assignment(pids: list, participants: int = PARTICIPANTS) -> dict:
    """The crossover (EXTERNAL_PILOT_PACKAGE.md section 4): form X uses the analyzer on odd
    P-numbers, form Y on even ones; forms alternate by participant; each participant's order is
    the P-list rotated by their index, so no log is always first."""
    out = {}
    for k in range(participants):
        form = "X" if k % 2 == 0 else "Y"
        order = pids[k % len(pids):] + pids[:k % len(pids)]
        out[f"participant_{k + 1:02d}"] = {
            "form": form, "order": order,
            "analyzer": [p for p in order if (int(p[1:]) % 2 == 1) == (form == "X")]}
    return {"rule": assignment.__doc__.strip(), "participants": out}


def _entry_points(whl: Path) -> str:
    with zipfile.ZipFile(whl) as w:
        n = next((n for n in w.namelist() if n.endswith("entry_points.txt")), None)
        return w.read(n).decode() if n else ""


if __name__ == "__main__":
    main()
