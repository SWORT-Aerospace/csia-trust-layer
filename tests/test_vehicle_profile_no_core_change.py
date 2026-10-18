"""Adding a vehicle must not require editing the frozen core.

Program section 43. This is the claim the pluggable architecture exists to
support, and it is the one a reviewer will test first, because it is cheap to
test and expensive to fake.

THE TEST IS THE WORKFLOW
------------------------
Rather than asserting something about the design, it performs the whole
documented integration for a vehicle that has never existed -- a hexacopter on
PX4 with no ESC telemetry -- and then checks the frozen core is byte-identical
to the frozen tag afterwards.

    1. write a profile          (a file in profiles/, nothing else)
    2. load and validate it
    3. negotiate capabilities against an adapter
    4. assert zero diff across every FROZEN_PATHS entry

If step 4 ever fails, either the workflow silently touched the core or
somebody added a step that does. Both are the same defect from a reviewer's
side: the cross-platform comparison stops meaning what it says.
"""

from __future__ import annotations

import os
import subprocess

import pytest
import yaml

from csia.aircraft.adapters.px4 import PX4Adapter
from csia.aircraft.capability import Capability, negotiate
from csia.aircraft.profile import validate

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: The frozen scientific core, named here rather than imported so this test
#: keeps working if the extension metadata is absent.
FROZEN_PATHS = (
    "csia/trust_engine",
    "csia/diagnosis",
    "csia/runtime/online.py",
    "csia/runtime/failsafe.py",
    "csia/scenarios.py",
    "csia/profiles.py",
)
FROZEN_TAG = "csia-v1.0-research-final"

#: A vehicle that exists nowhere in this repository. Deliberately not a quad,
#: deliberately missing channels a quad reference profile declares, so a test
#: that passed by accident on a copied file would fail here.
NEW_VEHICLE = {
    "vehicle_profile": {
        "id": "test_hexa_px4_no_esc",
        "airframe": "hexa_x",
        "description": "A hexacopter that has never been integrated before.",
    },
    "autopilot": {"family": "px4", "version_observed_at_runtime": True},
    "transport": {"mavlink": {"port": "udp:0.0.0.0:14551", "baud": 921600,
                              "sysid": 7, "transmit": False}},
    "streams": {
        "imu0.accel": {"nominal_rate_hz": 50},
        "imu0.gyro": {"nominal_rate_hz": 50},
        "imu1.accel": {"nominal_rate_hz": 25},
        "imu1.gyro": {"nominal_rate_hz": 25},
        "mag.field_ut": {"nominal_rate_hz": 14},
        "baro.altitude": {"nominal_rate_hz": 10},
        "gnss.position": {"nominal_rate_hz": 5},
        "gnss.velocity": {"nominal_rate_hz": 5},
        "battery.voltage": {"nominal_rate_hz": 10},
        "battery.current": {"nominal_rate_hz": 10},
        "vehicle_status.armed": {"nominal_rate_hz": 1},
        # No ESC telemetry bus on this build, and no vibration channel.
    },
    "functions": {"position_hold": "expected"},
    "experiment": {"fault_injector": {"enabled": False, "channels": {}}},
    "safety": {"shadow_only": True},
}


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True)


def _frozen_core_diff():
    """Empty string when the core matches the frozen tag."""
    if _git("rev-parse", "--verify", "--quiet",
            f"{FROZEN_TAG}^{{commit}}").returncode != 0:
        pytest.skip(f"{FROZEN_TAG} not present in this clone (shallow?)")
    out = []
    for path in FROZEN_PATHS:
        proc = _git("diff", "--stat", FROZEN_TAG, "--", path)
        if proc.stdout.strip():
            out.append(f"{path}: {proc.stdout.strip()}")
    return "\n  ".join(out)


def test_integrating_a_brand_new_vehicle_touches_no_core_file(tmp_path):
    """The whole documented workflow, then the diff."""
    before = _frozen_core_diff()
    assert not before, (
        f"the frozen core already differs from {FROZEN_TAG} BEFORE this test "
        f"ran, so the test cannot attribute anything:\n  {before}")

    # STEP 1 -- write a profile. This is the only file a user creates.
    path = tmp_path / "test_hexa_px4_no_esc.yaml"
    path.write_text(yaml.safe_dump(NEW_VEHICLE, sort_keys=False),
                    encoding="utf-8")

    # STEP 2 -- load and validate.
    profile = validate(yaml.safe_load(path.read_text(encoding="utf-8")),
                       source_path=str(path))
    assert profile.profile_id == "test_hexa_px4_no_esc"
    assert profile.autopilot == "px4"

    # STEP 3 -- negotiate against a real adapter. No adapter code was written
    # for this airframe; the PX4 adapter serves it unchanged.
    report = negotiate(PX4Adapter(), profile=profile)
    assert report.profile_id == "test_hexa_px4_no_esc"

    # The hexa has no ESC bus, so the relations that span it are structurally
    # absent -- and reported as such rather than as faults.
    by_name = {r.relation: r for r in report.relations}
    assert by_name["power_thrust"].capability is Capability.NOT_CONFIGURED
    assert by_name["vibration_prop_freq"].capability is \
        Capability.NOT_CONFIGURED
    assert "power_thrust" not in report.inactive_relations

    # STEP 4 -- the claim.
    after = _frozen_core_diff()
    assert not after, (
        "integrating a new vehicle modified the FROZEN SCIENTIFIC CORE:\n  "
        + after + "\n\nAdding a vehicle must require a profile and nothing "
        "else. If a core edit was genuinely necessary, the pluggable "
        "architecture does not hold and the paper may not claim it does.")


def test_the_airframe_string_reaches_no_diagnostic_decision():
    """`hexa_x` versus `quad_x` must change nothing the core computes.

    The trust-graph relations span SENSORS, not motors. If the airframe label
    could move a relation, every airframe would need its own validation.
    """
    quad = dict(NEW_VEHICLE)
    quad["vehicle_profile"] = dict(NEW_VEHICLE["vehicle_profile"],
                                   id="test_quad", airframe="quad_x")
    hexa = NEW_VEHICLE

    adapter = PX4Adapter()
    a = negotiate(adapter, validate(quad)).to_dict()
    b = negotiate(adapter, validate(hexa)).to_dict()
    a.pop("profile_id"), b.pop("profile_id")
    assert a == b, (
        "changing only the airframe label changed the capability report. The "
        "diagnostic relations span sensors, not motors -- if the airframe "
        "reaches a diagnostic decision, every airframe needs separate "
        "validation and the pluggable claim is much weaker than stated.")


def test_no_shipped_profile_names_a_frozen_core_file():
    """A profile that pointed at a core file would be configuring the science
    by reference rather than by key, which the key blacklist would not
    catch."""
    import glob
    offenders = []
    for p in sorted(glob.glob(os.path.join(ROOT, "profiles", "*.yaml"))):
        text = open(p, encoding="utf-8").read()
        for frozen in FROZEN_PATHS:
            # The docstring-style comments in the profiles legitimately
            # mention the architecture; only a VALUE may not name a core path.
            doc = yaml.safe_load(text)
            if frozen in yaml.safe_dump(doc):
                offenders.append(f"{os.path.basename(p)} -> {frozen}")
    assert not offenders, "\n  ".join([""] + offenders)
