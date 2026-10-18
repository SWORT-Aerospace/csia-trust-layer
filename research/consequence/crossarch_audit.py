"""Phase 6 — cross-architecture audit of PX4 and ArduPilot source.

WHAT THIS IS, AND THE CORRECTION THAT PRECEDES IT
--------------------------------------------------
`PHASE_STATUS.md` said phase 6 was `BLOCKED_BY_SOURCE_ACCESS` because "no PX4
or ArduPilot source tree exists in this environment". **That was wrong, and it
was wrong because of how it was checked.** The search ran `find` over the CSIA
repository, found only prior audit *documents*, and concluded there was no
source. Both trees were sitting in the container outside the repository, at
`/home/user/px4` and `/home/user/ardupilot/ardupilot`. The error is left in the
record (see `PHASE2_GATE_FINDINGS.md` and the status file's correction note)
rather than edited away, because it is the same failure mode this whole phase
is about: a negative conclusion drawn from a search whose scope was narrower
than the claim.

WHAT IT DOES
------------
It does NOT parse C++. Parsing C++ badly and reporting the result as an audit
would be worse than not auditing. Every finding below was read by hand, and
what this module does is:

  1. pin each finding to a file, a line and the VERBATIM text at that line;
  2. re-read both source trees and refuse to emit anything if a single anchor
     has moved or changed, so a stale finding cannot survive a tree update;
  3. record each tree's commit SHA, so the audit names exactly what it read.

EVIDENCE LEVEL
--------------
`SOURCE_ANALYSIS`, for every finding, without exception. Nothing here ran. No
autopilot executed anything. No SITL was started. The preregistration's H5
vocabulary allows `RUNTIME_REPRODUCED` and `RUNTIME_NOT_REPRODUCED`; **neither
is used**, because reaching them requires executing the relevant autopilot
path and this module executes nothing.

WHAT MAY NOT BE CONCLUDED FROM IT
---------------------------------
Prevalence. Universality. That these are bugs. That PX4 or ArduPilot are
unsafe. The audit covers ONE subsystem family -- airspeed and the wind/sideslip
relations that constrain it -- in two stacks at two commits. A finding is a
statement about (path, regime) in that subsystem and nothing wider. The
preregistration is explicit: "No universality claim may be drawn from any
number of audited paths."

And one finding is an ArduPilot source COMMENT that states the mechanism
outright. That cuts against novelty, not for it, and it is reported first for
that reason.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# --- classification vocabulary, fixed by the preregistration ---------------
STRUCTURALLY_PRESENT = "STRUCTURALLY_PRESENT"
STRUCTURALLY_ABSENT = "STRUCTURALLY_ABSENT"
RUNTIME_REPRODUCED = "RUNTIME_REPRODUCED"
RUNTIME_NOT_REPRODUCED = "RUNTIME_NOT_REPRODUCED"
UNVERIFIED = "UNVERIFIED"
BLOCKED_BY_SOURCE_ACCESS = "BLOCKED_BY_SOURCE_ACCESS"

CLASSIFICATIONS = (STRUCTURALLY_PRESENT, STRUCTURALLY_ABSENT,
                   RUNTIME_REPRODUCED, RUNTIME_NOT_REPRODUCED, UNVERIFIED,
                   BLOCKED_BY_SOURCE_ACCESS)

#: What the gating variable IS. The distinction matters more than the
#: classification: a gate on vehicle state is a design choice with a reason,
#: while a gate on the suspect signal itself is self-referential and cannot
#: report its own failure.
VEHICLE_STATE = "VEHICLE_STATE"
SELF_REFERENTIAL = "SELF_REFERENTIAL"
DATA_HEALTH = "DATA_HEALTH"
GATE_KINDS = (VEHICLE_STATE, SELF_REFERENTIAL, DATA_HEALTH)

#: What happens on the nominally independent path that might cover the gate.
ALSO_GATED = "ALSO_GATED"              # shares the same gating condition
REACTS = "REACTS"                      # would raise an equivalent warning
NONE_FOUND = "NONE_FOUND"              # searched, found nothing
NOT_SEARCHED_EXHAUSTIVELY = "NOT_SEARCHED_EXHAUSTIVELY"
COVERAGE_VERDICTS = (ALSO_GATED, REACTS, NONE_FOUND,
                     NOT_SEARCHED_EXHAUSTIVELY)

PX4 = "PX4"
ARDUPILOT = "ArduPilot"

DEFAULT_TREES = {
    PX4: os.environ.get("CSIA_PX4_TREE", "/home/user/px4"),
    ARDUPILOT: os.environ.get("CSIA_ARDUPILOT_TREE",
                              "/home/user/ardupilot/ardupilot"),
}


class AnchorMoved(RuntimeError):
    """A recorded line no longer holds the text the finding was read from."""


class Finding:
    """One audited path. Every field is either verbatim source or a hand
    judgement that says so."""

    def __init__(self, fid, stack, path, line, anchor, regime, gate_kind,
                 relation_lost, independent_path, coverage, classification,
                 note, annotation=""):
        if classification not in CLASSIFICATIONS:
            raise ValueError(f"bad classification {classification!r}")
        if gate_kind not in GATE_KINDS:
            raise ValueError(f"bad gate kind {gate_kind!r}")
        if coverage not in COVERAGE_VERDICTS:
            raise ValueError(f"bad coverage verdict {coverage!r}")
        self.fid = fid
        self.stack = stack
        self.path = path
        self.line = line
        self.anchor = anchor
        self.regime = regime
        self.gate_kind = gate_kind
        self.relation_lost = relation_lost
        self.independent_path = independent_path
        self.coverage = coverage
        self.classification = classification
        self.note = note
        self.annotation = annotation

    def as_dict(self) -> dict:
        return {"id": self.fid, "stack": self.stack, "file": self.path,
                "line": self.line, "anchor": self.anchor,
                "regime": self.regime, "gate_variable_kind": self.gate_kind,
                "diagnostic_relation_lost": self.relation_lost,
                "independent_path_considered": self.independent_path,
                "independent_path_verdict": self.coverage,
                "classification": self.classification,
                "evidence_level": "SOURCE_ANALYSIS",
                "note": self.note, "annotation": self.annotation}


FINDINGS = (
    # --- reported first on purpose: the mechanism, in ArduPilot's own words
    Finding(
        "AP-COMMENT", ARDUPILOT, "libraries/AP_Airspeed/AP_Airspeed.cpp", 739,
        "The EKF3 innovation check only applies to the active sensor so a "
        "bad sensor will appear good after some time because",
        "sensor deselected while the vehicle is disarmed",
        SELF_REFERENTIAL,
        "the EKF innovation that would condemn the sensor is only computed "
        "for the sensor the EKF is using",
        "none needed -- the source states the effect itself",
        NONE_FOUND, STRUCTURALLY_PRESENT,
        "Not a defect and not a discovery. ArduPilot documents the "
        "feedback-loss mechanism in a comment and then works around it, by "
        "re-selecting the user's primary sensor whenever the vehicle is "
        "disarmed. It is reported first because it bears directly on novelty: "
        "the pattern this phase enumerates is known to at least one autopilot "
        "community and written down in its source.",
        annotation="ACKNOWLEDGED_IN_SOURCE"),

    # --- ArduPilot, airspeed health
    Finding(
        "AP-1", ARDUPILOT, "libraries/AP_Airspeed/AP_Airspeed_Health.cpp", 38,
        "if (state[i].airspeed <= 0) {",
        "differential pressure reads at or below the zero point",
        SELF_REFERENTIAL,
        "check_sensor_ahrs_wind_max_failures returns before computing "
        "test_ratio, speed_diff or health_probability",
        "AP_Airspeed::check_sensor_failures is the only periodic health path "
        "for this sensor",
        NONE_FOUND, STRUCTURALLY_PRESENT,
        "The guard is commented `// invalid estimate` and reads as input "
        "hygiene. Structurally it is the sharpest case in this audit: a "
        "fully blocked or disconnected pitot reports approximately zero "
        "airspeed, and approximately zero airspeed is the condition under "
        "which the health check declines to run. The data is fresh, the "
        "sensor is `healthy` in the driver sense, and no counter moves in "
        "either direction."),
    Finding(
        "AP-2", ARDUPILOT, "libraries/AP_Airspeed/AP_Airspeed_Health.cpp", 60,
        "state[i].failures.test_ratio = 0.0f;",
        "EKF airspeed innovation unavailable or older than 1 s",
        DATA_HEALTH,
        "the EKF-consistency term of the health probability",
        "the wind_max plausibility term, which still runs on GPS speed",
        REACTS, STRUCTURALLY_PRESENT,
        "A missing innovation becomes a test ratio of exactly zero, which is "
        "the most consistent value there is, so `data_is_inconsistent` is "
        "false and `health_probability` grows by the 0.98 coefficient. This "
        "is the repository's own evidence-semantics finding 2 -- an absence "
        "collapsing into a usable value -- in another codebase. The "
        "plausibility term does still run, which is why the coverage verdict "
        "is REACTS and not NONE_FOUND: the sensor can still be condemned on "
        "air-to-ground speed difference alone."),

    # --- ArduPilot, EKF3 wind states
    Finding(
        "AP-3", ARDUPILOT,
        "libraries/AP_NavEKF3/AP_NavEKF3_Control.cpp", 62,
        "const bool canEstimateWind = ((finalInflightYawInit && "
        "dragFusionEnabled) || assume_zero_sideslip()) &&",
        "on ground, or aiding mode AID_NONE",
        VEHICLE_STATE,
        "wind states stop being estimated, so no airspeed-versus-groundspeed "
        "residual exists to test against",
        "AP_Airspeed health, which asks the AHRS for exactly that residual",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "The two paths are not independent. AP_Airspeed_Health asks "
        "`AP::ahrs().airspeed_health_data()` for an innovation the EKF only "
        "produces while wind states are being estimated, and this line is "
        "what stops them being estimated on the ground. AP-2 then turns the "
        "missing innovation into a passing score."),
    Finding(
        "AP-4", ARDUPILOT,
        "libraries/AP_NavEKF3/AP_NavEKF3_AirDataFusion.cpp", 195,
        "const bool f_beta_feasible = (assume_zero_sideslip() && "
        "!inhibitWindStates);",
        "wind states inhibited (see AP-3)",
        VEHICLE_STATE,
        "synthetic sideslip fusion, the second air-data relation",
        "airspeed fusion, gated by the same inhibitWindStates",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "Both air-data relations hang off one flag, so they fail together "
        "rather than covering one another."),

    # --- PX4, airspeed validator
    Finding(
        "PX4-1", PX4, "src/modules/airspeed_selector/AirspeedValidator.cpp",
        228,
        "if (!_innovation_check_enabled || !_in_fixed_wing_flight || "
        "(time_now - _time_wind_estimator_initialized) < 5_s) {",
        "not in fixed-wing flight",
        VEHICLE_STATE,
        "the innovation check, and `_innovations_check_failed` is set false "
        "rather than left unknown",
        "the other three validator checks",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "Not merely skipped: assigned false, which is the value that means "
        "'this check passed'."),
    Finding(
        "PX4-2", PX4, "src/modules/airspeed_selector/AirspeedValidator.cpp",
        213,
        "_data_stuck_test_failed = hrt_elapsed_time(&_time_last_unequal_data) "
        "> DATA_STUCK_TIMEOUT && _in_fixed_wing_flight;",
        "not in fixed-wing flight",
        VEHICLE_STATE,
        "stuck-data detection",
        "the other three validator checks",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "A sensor emitting an unchanging value -- the classic frozen reading "
        "-- cannot be declared stuck on the ground. The conjunction is with "
        "vehicle state, not with data age."),
    Finding(
        "PX4-3", PX4, "src/modules/airspeed_selector/AirspeedValidator.cpp",
        279,
        "_load_factor_ratio = 0.5f; // reset if not in fixed-wing flight "
        "(and not in takeoff condition)",
        "not in fixed-wing flight",
        VEHICLE_STATE,
        "the load-factor plausibility check",
        "the other three validator checks",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "Precisely: the else-branch resets `_load_factor_ratio` to the 0.5 "
        "midpoint and does NOT touch `_load_factor_check_failed`, which "
        "therefore holds whatever it last held. So the flag is sticky across "
        "a flight -- an in-flight failure is not cleared by landing, which is "
        "the safer behaviour -- but on a vehicle that has not yet flown it is "
        "still at its default false, and the ratio has been reset below the "
        "1.1 threshold for whenever the check next runs. The ground regime is "
        "the one this finding is about."),
    Finding(
        "PX4-4", PX4, "src/modules/airspeed_selector/AirspeedValidator.cpp",
        296,
        "if (!_in_fixed_wing_flight || tecs_dt > 500_ms || "
        "!PX4_ISFINITE(_IAS) || !PX4_ISFINITE(throttle_fw)",
        "not in fixed-wing flight",
        VEHICLE_STATE,
        "the first-principle check (airspeed derivative against throttle and "
        "pitch)",
        "the other three validator checks",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "This is the check that WOULD catch a blocked pitot in flight, and "
        "it is the reason PX4-6's in-flight regime is classified separately. "
        "On the ground it returns early."),
    Finding(
        "PX4-5", PX4, "src/modules/airspeed_selector/AirspeedValidator.cpp",
        348,
        "} else if (! _data_stuck_test_failed && !_innovations_check_failed",
        "not in fixed-wing flight, so all four flags are false",
        VEHICLE_STATE,
        "nothing further -- this is where the four gated checks are combined",
        "none; this is the combining step",
        NONE_FOUND, STRUCTURALLY_PRESENT,
        "The consequence of PX4-1 through PX4-4 taken together. With every "
        "check gated off, all four flags are false, the else-branch runs, and "
        "`_time_checks_passed` is stamped with the current time. 'No check "
        "failed' is recorded as 'all checks passed'. The four inputs are not "
        "independent of each other; they share one gate."),
    Finding(
        "PX4-6", PX4,
        "src/modules/ekf2/EKF/aid_sources/airspeed/airspeed_fusion.cpp", 102,
        "const bool is_airspeed_significant = "
        "airspeed_sample.true_airspeed > _params.ekf2_arsp_thr;",
        "measured true airspeed at or below EKF2_ARSP_THR (default 2.0 m/s)",
        SELF_REFERENTIAL,
        "airspeed fusion, and after 10 s of not fusing, "
        "`_control_status.flags.fuse_aspd` clears",
        "AirspeedValidator::check_first_principle",
        REACTS, STRUCTURALLY_PRESENT,
        "Self-referential in the same way as AP-1: a blocked pitot reads "
        "low, and reading low is what suspends the relation. The coverage "
        "verdict is REACTS rather than NONE_FOUND because the first-principle "
        "check is a genuinely independent path IN FLIGHT -- it uses throttle, "
        "pitch and the IAS derivative, not the EKF. On the ground it is "
        "PX4-4. The regime matters and the classification is per regime, not "
        "per file."),
    Finding(
        "PX4-7", PX4,
        "src/modules/ekf2/EKF/aid_sources/airspeed/airspeed_fusion.cpp", 98,
        "const bool continuing_conditions_passing = "
        "_control_status.flags.in_air && (_control_status.flags.fixed_wing",
        "not in air, or not fixed-wing / in transition",
        VEHICLE_STATE,
        "airspeed fusion entirely, via stopAirspeedFusion()",
        "the airspeed_selector validator, gated on _in_fixed_wing_flight",
        ALSO_GATED, STRUCTURALLY_PRESENT,
        "`updateAirspeed()` is still called each cycle before this branch, so "
        "the innovation is still computed and published in "
        "`estimator_aid_src_airspeed`. What disappears is the effect on the "
        "estimate and the `fuse_aspd` flag, not the number in the log. A "
        "consumer that reads the innovation directly is not occluded; one "
        "that reads the status flag is."),
)


def tree_sha(tree: str) -> str:
    proc = subprocess.run(["git", "-C", tree, "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AnchorMoved(f"{tree} is not a git checkout: {proc.stderr}")
    return proc.stdout.strip()


def verify(trees=None) -> dict:
    """Re-read every anchor. Raise unless all of them are still there.

    The anchor is checked at its recorded line first and then, if it moved,
    anywhere in the file -- which is reported as a MOVED anchor rather than
    silently accepted, because a finding whose line number is wrong is a
    finding nobody can check by opening the file.
    """
    trees = dict(DEFAULT_TREES if trees is None else trees)
    missing = [s for s, t in trees.items() if not os.path.isdir(t)]
    if missing:
        raise AnchorMoved(f"source tree(s) absent: {missing}")
    out = {}
    for f in FINDINGS:
        full = os.path.join(trees[f.stack], f.path)
        with open(full, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
        if not 1 <= f.line <= len(lines):
            raise AnchorMoved(f"{f.fid}: {f.path} has no line {f.line}")
        if f.anchor in lines[f.line - 1]:
            out[f.fid] = "AT_RECORDED_LINE"
            continue
        elsewhere = [i + 1 for i, ln in enumerate(lines) if f.anchor in ln]
        if elsewhere:
            raise AnchorMoved(
                f"{f.fid}: anchor is at line(s) {elsewhere}, not {f.line}. "
                f"Update the finding rather than the check.")
        raise AnchorMoved(
            f"{f.fid}: anchor not found anywhere in {f.path}. The tree has "
            f"changed under the audit; re-read the path by hand.")
    return out


def report(trees=None) -> dict:
    trees = dict(DEFAULT_TREES if trees is None else trees)
    anchors = verify(trees)
    by_class = {}
    by_gate_kind = {}
    by_coverage = {}
    for f in FINDINGS:
        by_class[f.classification] = by_class.get(f.classification, 0) + 1
        by_gate_kind[f.gate_kind] = by_gate_kind.get(f.gate_kind, 0) + 1
        by_coverage[f.coverage] = by_coverage.get(f.coverage, 0) + 1
    return {
        "schema": "csia.consequence.crossarch_audit/1",
        "phase": "6 -- cross-architecture audit (H5)",
        "evidence_level": "SOURCE_ANALYSIS",
        "executed_anything": False,
        "source_trees": {stack: {"path": path, "commit": tree_sha(path)}
                         for stack, path in sorted(trees.items())},
        "subsystem_audited": "airspeed, and the wind/sideslip relations that "
                             "constrain it",
        "anchor_verification": anchors,
        "findings": [f.as_dict() for f in FINDINGS],
        "counts": {"total": len(FINDINGS), "by_classification": by_class,
                   "by_gate_variable_kind": by_gate_kind,
                   "by_independent_path_verdict": by_coverage},
        "h5_outcome": (
            "H5 is not killed: paths could be classified. It predicted "
            "nothing about prevalence and none is reported."),
        "what_this_is_not": (
            "Not a prevalence measurement, not a universality claim, not a "
            "bug report, not a safety judgement about either autopilot, and "
            "not a novelty claim -- AP-COMMENT is one of these projects "
            "stating the mechanism in its own source. One subsystem family, "
            "two stacks, two commits, read by hand."),
        "not_reached": {
            "RUNTIME_REPRODUCED": "requires executing the autopilot path; "
                                  "nothing here was executed",
            "RUNTIME_NOT_REPRODUCED": "same",
        },
    }


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = argv[0] if argv else None
    try:
        document = report()
    except AnchorMoved as error:
        print(f"REFUSING TO EMIT: {error}", file=sys.stderr)
        return 1
    text = json.dumps(document, indent=1, sort_keys=True) + "\n"
    if out:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {out}")
    else:
        print(text)
    counts = document["counts"]
    print(f"findings {counts['total']}  "
          f"by classification {counts['by_classification']}  "
          f"by gate kind {counts['by_gate_variable_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
