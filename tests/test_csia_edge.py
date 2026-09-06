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
    contradiction and was doing exactly that before this was fixed.

    The labels asserted here are the RUNTIME's identifiers, not invented ones:
    csia/prediction/comparator.py has computed `velocity_gps_doppler_0` and
    `_1` all along, and they are the strings in `gps_gates` in every
    Mechanism-A trial artifact. A capability report and a trial artifact now
    name the same edge the same way.
    """
    report = negotiate(ArduPilotAdapter(), load(MINIMAL))
    absent = set(report.structurally_absent_relations)
    unknown = set(report.unknown_relations)
    assert not (absent & unknown), (
        f"the same label appears in two capability buckets: "
        f"{sorted(absent & unknown)}")
    assert "velocity_gps_doppler_1" in absent
    assert "velocity_gps_doppler_0" in unknown


# --------------------------------------------------------------------- §11
# THE THREE GUARDS THE DEFECT ASKED FOR
#
# FL-004 was found by reading output, not by a test. These are the tests that
# would have found it, generalised past the one relation that exhibited it.

def _all_reports():
    """Every shipped profile against its own platform's adapter."""
    import glob

    from csia.aircraft.adapters.px4 import PX4Adapter
    adapters = {"ardupilot": ArduPilotAdapter, "px4": PX4Adapter}
    for path in sorted(glob.glob(os.path.join(PROFILES, "*.yaml"))):
        profile = load(path)
        yield path, negotiate(adapters[profile.autopilot](), profile)


def test_no_edge_id_lands_in_two_mutually_exclusive_buckets():
    """The four summary buckets partition the edges; they do not overlap.

    active / inactive / structurally_absent / unknown are mutually exclusive
    CLAIMS: "feeding evidence", "declared and dark", "never going to exist",
    "too early to say". An identifier in two of them at once is not a
    conservative report, it is an unreadable one -- and a reader resolving the
    contradiction guesses, which is the failure this whole module exists to
    prevent.

    Checked across every shipped profile rather than the one that happened to
    exhibit it, because the next duplicate name will be on some other airframe.
    """
    for path, report in _all_reports():
        buckets = {
            "active": set(report.active_relations),
            "inactive": set(report.inactive_relations),
            "structurally_absent": set(report.structurally_absent_relations),
            "unknown": set(report.unknown_relations),
        }
        names = sorted(buckets)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                overlap = buckets[a] & buckets[b]
                assert not overlap, (
                    f"{os.path.basename(path)}: {sorted(overlap)} appears in "
                    f"both '{a}' and '{b}'. Two mutually exclusive claims "
                    f"about one edge.")


def test_every_edge_id_the_summary_emits_exists_in_the_runtime():
    """A disambiguating label must be the runtime's, not a display string.

    The first fix for FL-004 synthesised `velocity_gps_doppler(imu0,gps)`.
    It read fine and was disjoint and was still wrong: no artifact, log or
    module anywhere in the repository contains that string, so a capability
    report could not be joined to a trial artifact. This asserts the labels
    are the ones the frozen core actually computes.
    """
    from csia.aircraft import capability as cap_mod

    core = ""
    for rel in ("csia/prediction/comparator.py", "csia/runtime/online.py",
                "csia/trust_graph/graph.py"):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            core += fh.read()

    emitted = set()
    for _path, report in _all_reports():
        for key in ("active_relations", "inactive_relations",
                    "structurally_absent_relations", "unknown_relations"):
            emitted.update(getattr(report, key))

    missing = sorted(e for e in emitted if f'"{e}"' not in core)
    assert not missing, (
        f"capability summary emits identifiers absent from the frozen core: "
        f"{missing}. A label the runtime never writes cannot be joined to a "
        f"trial artifact, which is the only reason to disambiguate at all.")

    # And the mapping itself must not have drifted from the runtime.
    for value in cap_mod.EDGE_ID.values():
        assert f'"{value}"' in core, \
            f"EDGE_ID maps to {value!r}, which the frozen core does not define"


def test_a_new_duplicate_relation_name_cannot_slip_through_unmapped():
    """Fails CLOSED when the frozen graph gains another ambiguous name.

    EDGE_ID is a hand-maintained mapping, and FL-001 is this program's
    standing evidence that hand-maintained lists decay silently. Derive the
    set of names needing an entry from EDGES rather than trusting the mapping
    to be complete.
    """
    from collections import Counter

    from csia.aircraft.capability import EDGE_ID
    from csia.trust_graph.graph import EDGES

    edges = {(rel, (a, b)) for a, b, rel, _d in EDGES}
    repeated = {rel for rel, n in Counter(r for r, _e in edges).items() if n > 1}

    unmapped = sorted(
        f"{rel}{endpoints}" for rel, endpoints in edges
        if rel in repeated and (rel, endpoints) not in EDGE_ID)
    assert not unmapped, (
        f"the trust graph gives these edges a name it also gives another "
        f"edge, and no EDGE_ID entry disambiguates them: {unmapped}. Add the "
        f"identifier the runtime uses -- do not invent one.")

    stale = sorted(k for k in EDGE_ID if k[0] not in repeated)
    assert not stale, (
        f"EDGE_ID carries entries for names that are no longer ambiguous: "
        f"{stale}. Harmless today, misleading later.")
