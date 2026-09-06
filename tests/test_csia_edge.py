"""csia-edge: the pre-flight answer, and the two ways it could lie.

The whole value of a `validate` step is that it is honest about what it did
NOT check. Two failure modes matter more than any feature:

  1. reporting a structurally absent relation as a fault, or as healthy;
  2. letting a green validate be read as "the vehicle is wired up correctly",
     when nothing was connected.

Both are tested below. So is the seam between the two config formats this
repository now has, because two files that can disagree about the autopilot
family eventually will.
"""

from __future__ import annotations

import json
import os

import pytest
import yaml

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
from csia.aircraft.capability import Capability, negotiate
from csia.aircraft.profile import load
from csia.deploy import edge

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = os.path.join(ROOT, "profiles")
REF_AP = os.path.join(PROFILES, "reference_quad_ardupilot.yaml")
MINIMAL = os.path.join(PROFILES, "minimal_single_imu_ardupilot.yaml")


def _run(argv, capsys):
    code = edge.main(argv)
    return code, capsys.readouterr()


def test_validate_succeeds_on_every_shipped_profile(capsys):
    import glob
    for path in sorted(glob.glob(os.path.join(PROFILES, "*.yaml"))):
        code, _ = _run(["validate", "--profile", path, "--json"], capsys)
        assert code == 0, f"{os.path.basename(path)} failed validation"


def test_validate_emits_machine_readable_output(capsys):
    code, cap = _run(["validate", "--profile", REF_AP, "--json"], capsys)
    assert code == 0
    out = json.loads(cap.out)
    assert out["profile"]["profile_id"] == "reference_quad_ardupilot"
    assert len(out["profile_sha256"]) == 64
    assert out["adapter"]["platform"] == "ardupilot"
    assert set(out["capability"]["summary"]) == {
        "active", "inactive", "structurally_absent", "unknown"}


def test_validate_says_plainly_that_it_checked_no_liveness(capsys):
    """The failure mode that costs a flight: reading a green static check as
    confirmation that the cables are in."""
    _, cap = _run(["validate", "--profile", REF_AP, "--json"], capsys)
    out = json.loads(cap.out)
    assert out["liveness_checked"] is False
    assert "No vehicle was contacted" in out["note"]


def test_a_structurally_absent_relation_is_not_a_failure(capsys):
    """The single-IMU board cannot feed four relations. That is the honest
    answer for that airframe, not an error, and exit code must say so."""
    code, cap = _run(["validate", "--profile", MINIMAL, "--json"], capsys)
    assert code == 0
    out = json.loads(cap.out)
    assert out["capability"]["summary"]["structurally_absent"]
    assert not out["capability"]["summary"]["inactive"], (
        "a relation the airframe cannot feed must not be reported INACTIVE; "
        "inactive means declared-and-not-arriving, which may be a fault")


def test_an_invalid_profile_fails_with_a_distinct_code(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({
        "vehicle_profile": {"id": "x"},
        "autopilot": {"family": "ardupilot"},
        "streams": {"gnss.position": {"nominal_rate_hz": 5}},
        "tuning": {"nav_caution": 0.9},
    }), encoding="utf-8")
    code, cap = _run(["validate", "--profile", str(bad)], capsys)
    assert code == 2
    assert "may not set diagnostic" in cap.err


def test_a_config_conflict_is_reported_not_silently_resolved(tmp_path, capsys):
    """Two files that can disagree about the autopilot family eventually do.

    Preferring one silently would decode a PX4 stream with the ArduPilot
    dialect and report channels missing that were arriving all along.
    """
    dep = tmp_path / "deployment.yaml"
    dep.write_text(yaml.safe_dump({
        "vehicle": {"id": "X"},
        "autopilot": {"stack": "px4"},
        "csia": {"mode": "SHADOW"},
    }), encoding="utf-8")

    code, cap = _run(["validate", "--profile", REF_AP,
                      "--deployment", str(dep), "--json"], capsys)
    assert code == 3, "a config conflict must not exit 0"
    out = json.loads(cap.out)
    assert any("autopilot" in c for c in out["config_conflicts"])
    assert any("different message" in c for c in out["config_conflicts"])


def test_an_agreeing_deployment_config_produces_no_conflict(tmp_path, capsys):
    dep = tmp_path / "deployment.yaml"
    dep.write_text(yaml.safe_dump({
        "vehicle": {"id": "X"},
        "autopilot": {"stack": "ardupilot"},
        "csia": {"mode": "SHADOW"},
    }), encoding="utf-8")
    code, cap = _run(["validate", "--profile", REF_AP,
                      "--deployment", str(dep), "--json"], capsys)
    assert code == 0
    assert json.loads(cap.out)["config_conflicts"] == []


def test_a_commanding_mode_in_the_deployment_config_is_flagged(tmp_path,
                                                              capsys):
    dep = tmp_path / "deployment.yaml"
    dep.write_text(yaml.safe_dump({
        "autopilot": {"stack": "ardupilot"},
        "csia": {"mode": "CONTROL"},
    }), encoding="utf-8")
    _, cap = _run(["validate", "--profile", REF_AP,
                   "--deployment", str(dep), "--json"], capsys)
    assert any("command authority" in c
               for c in json.loads(cap.out)["config_conflicts"])


def test_run_refuses_to_reimplement_the_runtime(capsys):
    """`csia-edge run` must delegate, not duplicate.

    A second runtime is the exact defect this program avoided in P1: two
    stacks and a silent question about which one flies.
    """
    code, cap = _run(["run", "--profile", REF_AP], capsys)
    assert code == 4
    assert "csia-shadow" in cap.err
    assert "does not reimplement" in cap.err


def test_no_run_mode_carries_command_authority():
    assert "control" not in edge.RUN_MODES
    assert set(edge.RUN_MODES) == {"validate", "shadow", "record", "replay"}


def test_an_unknown_autopilot_family_selects_no_adapter():
    """Falling back to another platform's dialect would invent faults."""
    from csia.aircraft.profile import ProfileError
    with pytest.raises(ProfileError, match="no adapter"):
        edge._adapter_for("betaflight")


def test_an_ambiguous_relation_name_is_disambiguated_in_the_summary():
    """`velocity_gps_doppler` names two edges. On a single-IMU airframe one
    instance is INAPPLICABLE and the other UNKNOWN, and a summary keyed on
    the bare name puts the same string in two buckets -- which reads as a
    contradiction and was doing exactly that before this was fixed."""
    report = negotiate(ArduPilotAdapter(), load(MINIMAL))
    absent = set(report.structurally_absent_relations)
    unknown = set(report.unknown_relations)
    assert not (absent & unknown), (
        f"the same label appears in two capability buckets: "
        f"{sorted(absent & unknown)}")
    assert "velocity_gps_doppler(imu1,gps)" in absent
    assert "velocity_gps_doppler(imu0,gps)" in unknown
