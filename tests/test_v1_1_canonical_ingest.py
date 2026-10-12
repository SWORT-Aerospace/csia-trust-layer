"""Gate B and Gate C for the v1.1 canonical-ingestion phase.

These are regression tests for the five rules in
`engineering/v1_1/CANONICAL_INGEST_SPEC.md` and for the four defects in
`engineering/v1_1/KNOWN_DEFECTS_PRE_FIX.md`.

They exist because every one of these behaviours was WRONG in v1 and was
wrong quietly: a fabricated current, a stale magnetic field, a -1 A reading
marked valid, and a sentinel reported as a link problem. None of them raised
anything.
"""

from __future__ import annotations

import json
import os

import pytest

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
from csia.runtime.plugins import map_mavlink

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENG = os.path.join(ROOT, "engineering", "v1_1")


class Msg:
    def __init__(self, type_name, **fields):
        self._t = type_name
        self.__dict__.update(fields)

    def get_type(self):
        return self._t


def _adapter():
    t = {"v": 0.0}

    def clock():
        return t["v"]
    a = ArduPilotAdapter(clock=clock)
    return a, t


def _bat(cur, ms):
    return Msg("BATTERY_STATUS", voltages=[4000, 4000, 4000] + [65535] * 7,
               current_battery=cur, time_boot_ms=ms)


# ------------------------------------------------------------------ RULE R1
def test_a_sentinel_supersedes_an_earlier_value():
    """R1, and defect D1. The producer's latest statement wins."""
    a, t = _adapter()
    a.ingest(_bat(500, 0))
    t["v"] = 0.02
    a.ingest(_bat(-1, 20))
    cv = a.sample(t_mono=0.02).get("battery.current")
    assert cv.value is None, "the retained 5.00 A is being served again"
    assert not cv.usable


def test_a_value_supersedes_an_earlier_sentinel():
    """R1, the direction v1 already had. It must not regress."""
    a, t = _adapter()
    a.ingest(_bat(-1, 0))
    t["v"] = 0.02
    a.ingest(_bat(500, 20))
    cv = a.sample(t_mono=0.02).get("battery.current")
    assert cv.value == 5.0
    assert cv.usable


# ------------------------------------------------------------------ RULE R2
def test_a_disowned_value_reports_sentinel_not_stale():
    """R2, and the sharpest half of defect D1: v1 eventually dropped the
    channel, but blamed the link for what the producer had said."""
    a, t = _adapter()
    a.ingest(_bat(500, 0))
    t["v"] = 0.10
    a.ingest(_bat(-1, 100))
    t["v"] = 0.30
    cv = a.sample(t_mono=0.30).get("battery.current")
    assert cv.missing.value == "SENTINEL", cv.missing


def test_gnss_no_fix_keeps_its_own_reason():
    """NO_3D_FIX is not folded into SENTINEL. This is the D5 control."""
    a, t = _adapter()
    a.ingest(Msg("GPS_RAW_INT", fix_type=3, lat=473000000, lon=85000000,
                 alt=500000, vel=0, cog=0, time_usec=0))
    t["v"] = 0.02
    a.ingest(Msg("GPS_RAW_INT", fix_type=1, lat=473000000, lon=85000000,
                 alt=500000, vel=0, cog=0, time_usec=20000))
    cv = a.sample(t_mono=0.02).get("gnss.position")
    assert cv.value is None
    assert cv.missing.value == "NO_3D_FIX", cv.missing


# ------------------------------------------------------------------ RULE R3
def test_no_path_converts_the_battery_sentinel_into_a_number():
    """R3, and defects D3/D4. Three decoders, one raw condition, one answer."""
    out = map_mavlink(_bat(-1, 1000), {})
    bat = [o for o in out if o[0] == "battery"][0][2]
    assert bat["current"] is None, "the clamp is back"
    assert bat["current_valid"] is False
    assert bat["valid"] is False

    a, _t = _adapter()
    a.ingest(_bat(-1, 0))
    assert a.sample(t_mono=0.0).get("battery.current").value is None


def test_the_magnetometer_all_zero_triple_is_not_dropped_in_silence():
    """R3, and defect D2 -- the quietest of the four: v1 recognised the
    sentinel and recorded nothing at all, not even a counter."""
    a, t = _adapter()
    a.ingest(Msg("RAW_IMU", xacc=0, yacc=0, zacc=-1000, xgyro=0, ygyro=0,
                 zgyro=0, xmag=200, ymag=100, zmag=400, time_usec=0))
    t["v"] = 0.02
    a.ingest(Msg("RAW_IMU", xacc=0, yacc=0, zacc=-1000, xgyro=0, ygyro=0,
                 zgyro=0, xmag=0, ymag=0, zmag=0, time_usec=20000))
    assert a.sentinel_counts().get("mag.field_ut") == 1
    cv = a.sample(t_mono=0.02).get("mag.field_ut")
    assert cv.value is None
    assert cv.missing.value == "SENTINEL"


# ------------------------------------------------------------------ RULE R4
def test_voltage_survives_an_unmeasured_current():
    """R4. A pack can report voltage with no current shunt fitted."""
    a, _t = _adapter()
    a.ingest(_bat(-1, 0))
    s = a.sample(t_mono=0.0)
    assert s.get("battery.voltage").value == pytest.approx(12.0)
    assert s.get("battery.current").value is None

    bat = [o for o in map_mavlink(_bat(-1, 1000), {})
           if o[0] == "battery"][0][2]
    assert bat["voltage"] == pytest.approx(12.0)


# ------------------------------------------------------------------ RULE R5
def test_a_sentinel_ages_out_like_a_value():
    """R5. Without this, one sentinel would silence a channel for ever."""
    a, t = _adapter()
    a.ingest(_bat(-1, 0))
    t["v"] = 5.0
    cv = a.sample(t_mono=5.0).get("battery.current")
    assert cv.value is None
    assert cv.missing.value != "SENTINEL", (
        "a sentinel from 5 s ago is still being reported as current")


# ------------------------------------------------- the frozen core is safe
def test_the_battery_sensor_is_withheld_rather_than_fabricated():
    """A partial sensor is not a degraded sensor. The frozen core must see
    the battery as unavailable, which is behaviour it already had."""
    a, _t = _adapter()
    a.ingest(_bat(-1, 0))
    s = a.sample(t_mono=0.0)
    assert "battery" not in {name for name, _t, _c in a.to_core_samples(s)}


# ------------------------------------------------------------ Gate C record
def test_the_pre_and_post_fix_records_exist_and_differ():
    """Item 4: the defect must have been reproduced BEFORE it was fixed.
    Two records with different hashes are the evidence that it was."""
    pre_p = os.path.join(ENG, "KNOWN_DEFECTS_PRE_FIX.json")
    post_p = os.path.join(ENG, "KNOWN_DEFECTS_POST_FIX.json")
    for p in (pre_p, post_p):
        assert os.path.exists(p), p
    pre = json.load(open(pre_p, encoding="utf-8"))
    post = json.load(open(post_p, encoding="utf-8"))
    assert pre["sha256_of_cases"] != post["sha256_of_cases"]
    assert set(pre["cases"]) == set(post["cases"])

    # the four defects moved, and the control did not
    for case in ("D1_battery_sentinel_ardupilot", "D2_mag_all_zero_ardupilot",
                 "D3_ulog_battery_current", "D4_plugins_battery_current"):
        assert pre["cases"][case] != post["cases"][case], case
    assert (pre["cases"]["D5_gnss_no_fix_ardupilot"]
            == post["cases"]["D5_gnss_no_fix_ardupilot"]), (
        "the GNSS control changed; the v1.1 edit broke a path that worked")


def test_the_pre_fix_record_still_shows_the_defects():
    """The historical record must not be quietly regenerated against fixed
    code. If this fails, the evidence that the defects were real is gone."""
    pre = json.load(open(os.path.join(ENG, "KNOWN_DEFECTS_PRE_FIX.json"),
                         encoding="utf-8"))["cases"]
    assert pre["D1_battery_sentinel_ardupilot"]["observed"]["value"] == 5.0
    assert pre["D2_mag_all_zero_ardupilot"]["observed"]["present"] is True
    assert pre["D3_ulog_battery_current"]["first_event"]["current"] == -1.0
    assert pre["D4_plugins_battery_current"]["first_event"]["current"] == 0.0


def test_the_frozen_core_was_not_touched_by_phase_one():
    """Gate A, restated here so a Phase 1 regression names Phase 1."""
    import subprocess
    frozen = ["csia/trust_engine", "csia/diagnosis", "csia/runtime/online.py",
              "csia/runtime/failsafe.py", "csia/scenarios.py",
              "csia/profiles.py"]
    r = subprocess.run(["git", "diff", "--stat",
                        "csia-v1.0-research-final", "--", *frozen],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip("frozen tag not available in this clone")
    assert r.stdout.strip() == "", r.stdout


# ----------------------------------------------------- the semantics file
def test_every_semantics_rule_carries_evidence():
    """Item 5: every rule must point to source or schema evidence."""
    yaml_p = os.path.join(ENG, "channel_semantics",
                          "canonical_channel_semantics.yaml")
    assert os.path.exists(yaml_p)
    text = open(yaml_p, encoding="utf-8").read()
    for ch in ("battery.current", "battery.voltage", "mag.field_ut",
               "gnss.position"):
        assert ch in text, ch
    # the two machine-readable producer declarations must both be cited
    assert 'invalid="-1"' in text
    assert "[@invalid -1]" in text
    # and the one rule that has NO schema backing must say so
    assert "consumer convention" in text.lower()
