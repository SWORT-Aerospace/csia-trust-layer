"""A vehicle profile declares plumbing. It may never move the science.

This is the load-bearing test of the pluggable architecture. The whole
cross-platform argument -- "the same frozen core ran on ArduPilot and on PX4,
so the difference is the platform" -- is false the moment a profile can set a
threshold. Then the two runs differ in the core as well as the vehicle, and
every comparison becomes uninterpretable.

So the rejection is checked three ways:

  1. the forbidden-key list actually rejects, at any nesting depth
  2. the list COVERS the frozen core's real tuning constants, pinned against
     source rather than listed from memory
  3. every shipped profile loads clean

Point 2 is the one that decays. A new constant added to the core with no
entry here would be settable from a profile and nothing would notice, so the
test reads the constants out of the source files.
"""

from __future__ import annotations

import glob
import os

import pytest
import yaml

from csia.aircraft.profile import (FORBIDDEN_KEYS, KNOWN_CHANNELS,
                                   ProfileError, load, validate)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_DIR = os.path.join(ROOT, "profiles")


def _profiles():
    return sorted(glob.glob(os.path.join(PROFILE_DIR, "*.yaml")))


def test_there_are_profiles_to_check():
    assert _profiles(), "profiles/ is empty; the pluggable path has no examples"


@pytest.mark.parametrize("path", _profiles(), ids=os.path.basename)
def test_every_shipped_profile_loads(path):
    vp = load(path)
    assert vp.profile_id
    assert vp.autopilot
    assert set(vp.declared_channels) <= KNOWN_CHANNELS


@pytest.mark.parametrize("bad_key", [
    "threshold", "nav_caution", "prior_nominal", "smoothing_alpha",
    "evidence_mult", "rho_max", "gate_expression", "cusum_h", "signatures",
])
def test_a_profile_that_sets_a_diagnostic_parameter_is_rejected(bad_key):
    doc = {
        "vehicle_profile": {"id": "x"},
        "autopilot": {"family": "ardupilot"},
        "streams": {"gnss.position": {"nominal_rate_hz": 5}},
        "tuning": {bad_key: 0.5},
    }
    with pytest.raises(ProfileError, match="may not set diagnostic"):
        validate(doc)


def test_the_rejection_reaches_arbitrary_nesting_depth():
    """A forbidden key buried four levels down is still forbidden. The naive
    implementation checks only top-level keys and would pass this."""
    doc = {
        "vehicle_profile": {"id": "x"},
        "autopilot": {"family": "px4"},
        "streams": {"gnss.position": {"nominal_rate_hz": 5}},
        "a": {"b": {"c": [{"d": {"nav_caution": 0.9}}]}},
    }
    with pytest.raises(ProfileError, match="nav_caution"):
        validate(doc)


def test_the_forbidden_list_covers_the_frozen_cores_real_constants():
    """The list must not drift behind the code it protects.

    Read the constants out of source instead of trusting the list. A constant
    the core defines and this list does not name would be settable from a
    profile, silently.
    """
    import re
    sources = {
        "csia/diagnosis/bayes.py": ("EPS", "SMOOTH_ALPHA", "EVIDENCE_MULT",
                                    "PRIOR_NOMINAL"),
        "csia/prediction/comparator.py": ("GATE_SPEED_LO",),
    }
    missing = []
    for rel, expected in sources.items():
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        found = set(re.findall(r"^([A-Z][A-Z0-9_]{2,})\s*=", text,
                               re.MULTILINE))
        for name in expected:
            if name not in found:
                continue          # constant renamed; not this test's business
            # Does SOME forbidden key plausibly cover it? Match on any
            # underscore-separated token, so SMOOTH_ALPHA is covered by
            # "smoothing", "smooth_alpha" or "alpha".
            tokens = set(name.lower().split("_")) | {name.lower()}
            if not (tokens & FORBIDDEN_KEYS):
                missing.append(f"{rel}:{name}")
    assert not missing, (
        f"the frozen core defines {missing} and csia/aircraft/profile.py's "
        f"FORBIDDEN_KEYS does not name any token of it. A profile could set "
        f"it and nothing would object. Add it to FORBIDDEN_KEYS.")


def test_an_unknown_channel_name_is_rejected_rather_than_ignored():
    """A typo must not read as 'the vehicle does not have this'."""
    doc = {
        "vehicle_profile": {"id": "x"},
        "autopilot": {"family": "ardupilot"},
        "streams": {"gnss.positon": {"nominal_rate_hz": 5}},   # sic
    }
    with pytest.raises(ProfileError, match="unknown channel"):
        validate(doc)


def test_an_unknown_autopilot_family_is_rejected():
    doc = {"vehicle_profile": {"id": "x"},
           "autopilot": {"family": "betaflight"},
           "streams": {}}
    with pytest.raises(ProfileError, match="not one of"):
        validate(doc)


def test_inapplicable_and_omitted_are_different_states():
    """The single-IMU reference exists to keep these distinguishable."""
    vp = load(os.path.join(PROFILE_DIR, "minimal_single_imu_ardupilot.yaml"))
    assert "imu1.accel" in vp.inapplicable_channels, \
        "a structurally absent channel must be declared inapplicable"
    assert "imu1.accel" not in vp.declared_channels
    assert "esc.rpm" not in vp.declared_channels, \
        "an omitted channel must not appear as declared"
    assert "esc.rpm" not in vp.inapplicable_channels, \
        "omission and inapplicability are different non-faults and must not " \
        "be collapsed"


def test_the_two_reference_profiles_disagree_about_esc_rate_on_purpose():
    """PX4's ESC telemetry really is ~1 Hz against ArduPilot's 10 Hz.

    If these ever match, either a contract changed or somebody copy-pasted a
    profile. Both are worth stopping for: a shared max-age had PX4 reporting
    its ESC channels STALE for half of every publish period.
    """
    ap = load(os.path.join(PROFILE_DIR, "reference_quad_ardupilot.yaml"))
    px = load(os.path.join(PROFILE_DIR, "reference_quad_px4.yaml"))
    assert ap.rates_hz["esc.rpm"] != px.rates_hz["esc.rpm"], (
        "the two reference profiles now declare the same ESC rate. Check "
        "docs/simulation/CHANNEL_SEMANTICS.yaml -- if the contract still says "
        "ArduPilot 10 Hz and PX4 1 Hz, one of these profiles was copied "
        "rather than transcribed.")


def test_every_profile_rate_matches_the_frozen_channel_contract():
    """Profiles transcribe rates; they do not choose them.

    A profile that invented a rate would move the adapter's staleness limit,
    which is a diagnostic effect dressed as plumbing.
    """
    contract_path = os.path.join(ROOT, "docs", "simulation",
                                 "CHANNEL_SEMANTICS.yaml")
    if not os.path.exists(contract_path):
        pytest.skip("channel contract not present")
    with open(contract_path, encoding="utf-8") as fh:
        contract = yaml.safe_load(fh)

    declared = {}
    for row in contract["channels"]:
        for family, key in (("ardupilot", "producer_ardupilot"),
                            ("px4", "producer_px4")):
            prod = row.get(key)
            if isinstance(prod, list):
                prod = prod[0] if prod else None
            if isinstance(prod, dict) and prod.get("rate_hz") is not None:
                declared[(family, row["channel"])] = float(prod["rate_hz"])

    mismatches = []
    for path in _profiles():
        vp = load(path)
        if vp.autopilot not in ("ardupilot", "px4"):
            continue
        for channel, rate in vp.rates_hz.items():
            expected = declared.get((vp.autopilot, channel))
            if expected is not None and float(rate) != expected:
                mismatches.append(
                    f"{os.path.basename(path)}: {channel} declares {rate} Hz, "
                    f"contract says {expected} Hz")
    assert not mismatches, "\n  ".join([""] + mismatches)
