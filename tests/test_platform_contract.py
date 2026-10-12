"""Per-platform contract rows: they may narrow, and they may never widen.

Qualification is per platform instance -- CHANNEL_SEMANTICS.yaml has said so
since it was written, and the measurements finally forced the mechanism. PX4
SIH models one IMU, so `imu1.*` is not a message we failed to receive; it does
not exist there. Its BATTERY_STATUS carries the documented -1 sentinel, so
battery current is not "not received", it is not measured. Grading those the
same as a channel that should be present and is absent made every PX4 run FAIL
for reasons true of the airframe rather than of CSIA.

The danger is obvious and these tests are the guard against it: a per-platform
row is the easiest imaginable way to re-admit a stub. Write a platform row,
the guard disappears, the tests go green, and W-5 comes back. So:

  * a platform row can only REMOVE a channel from evidence, never add one;
  * every platform row must carry a reason AND an evidence path;
  * the base contract, and every other platform, are untouched.
"""

import os
import sys

import pytest
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.aircraft.qualification import (                       # noqa: E402
    CONTRACT_PATH, ChannelContract, SemanticContract,
    default_contract, platform_rows_in_force)
from csia.aircraft.sample import Quality                        # noqa: E402


BASE_ROW = {
    "channel": "esc.rpm",
    "qualification": "STUB_OR_NONINFORMATIVE",
    "csia_may_use": False,
}
ADMISSIBLE_ROW = {
    "channel": "imu0.accel",
    "qualification": "INFORMATIVE",
    "csia_may_use": True,
}


def test_a_platform_row_cannot_admit_what_the_base_contract_blocks():
    """The load-bearing rule. Without it this mechanism erases W-5."""
    row = dict(BASE_ROW, platform_qualification={"px4": {
        "qualification": "INFORMATIVE",
        "csia_may_use": True,
        "reason": "it moves on PX4",
        "evidence": "somewhere.json",
    }})
    with pytest.raises(ValueError, match="may not make a channel admissible"):
        ChannelContract(row, platform="px4")


def test_a_platform_row_may_narrow_an_admissible_channel():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE",
        "csia_may_use": False,
        "reason": "PX4 SIH models one IMU",
        "evidence": "research/v1_1/results/qualification_px4.json",
    }})
    c = ChannelContract(row, platform="px4")
    assert c.quality is Quality.UNAVAILABLE
    assert c.admissible is False
    assert c.base_quality is Quality.INFORMATIVE      # base is preserved


def test_a_platform_row_without_a_reason_is_refused():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE", "evidence": "x.json"}})
    with pytest.raises(ValueError, match="without a reason"):
        ChannelContract(row, platform="px4")


def test_a_platform_row_without_evidence_is_refused():
    # A qualification decision with no measurement behind it is an opinion,
    # and an opinion in a committed contract is indistinguishable from a
    # measurement.
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE", "reason": "because"}})
    with pytest.raises(ValueError, match="without an evidence path"):
        ChannelContract(row, platform="px4")


def test_a_row_for_another_platform_does_not_apply():
    row = dict(ADMISSIBLE_ROW, platform_qualification={"px4": {
        "qualification": "UNAVAILABLE",
        "csia_may_use": False,
        "reason": "PX4 only",
        "evidence": "x.json",
    }})
    c = ChannelContract(row, platform="ardupilot")
    assert c.quality is Quality.INFORMATIVE
    assert c.platform_row is None


def test_the_unnarrowed_contract_is_unchanged():
    """`default_contract()` with no platform must behave exactly as before."""
    base = default_contract()
    assert platform_rows_in_force(base) == {}
    assert len(base.admissible_channels()) == 12


def test_ardupilot_carries_no_narrowings_today():
    ap = default_contract("ardupilot")
    assert platform_rows_in_force(ap) == {}
    assert ap.admissible_channels() == default_contract().admissible_channels()


def test_px4_narrowings_are_exactly_the_measured_ones():
    px4 = default_contract("px4")
    assert set(platform_rows_in_force(px4)) == {
        "imu1.accel", "imu1.gyro", "battery.current",
        "esc.current", "esc.rpm"}
    for ch in ("imu1.accel", "imu1.gyro", "battery.current"):
        assert px4.channels[ch].quality is Quality.UNAVAILABLE
        assert px4.channels[ch].admissible is False


def test_px4_esc_rpm_varies_and_is_still_not_admissible():
    """The measurement said it moves. That is not the same as usable.

    INFORMATIVE requires VALIDATED_SEMANTICS *and* demonstrated variation.
    Nobody has read the PX4 source for this field's units or indexing, so
    admitting it on the strength of "it moves" would be W-5's mistake with
    the sign reversed.
    """
    px4 = default_contract("px4")
    row = px4.channels["esc.rpm"]
    assert row.quality is Quality.AVAILABLE_UNVALIDATED
    assert row.admissible is False
    assert "to_promote" in row.platform_row


def test_every_committed_platform_row_carries_reason_and_evidence():
    with open(CONTRACT_PATH, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    seen = 0
    for row in doc["channels"]:
        for platform, pq in (row.get("platform_qualification") or {}).items():
            seen += 1
            assert pq.get("reason"), f"{row['channel']}/{platform}: no reason"
            assert pq.get("evidence"), f"{row['channel']}/{platform}: no evidence"
            assert pq.get("measured"), \
                f"{row['channel']}/{platform}: no measurement recorded"
    assert seen, "no platform rows found; this test would pass vacuously"


def test_every_platform_row_points_at_a_result_file_that_exists():
    # An evidence path nobody can open is the same as no evidence.
    with open(CONTRACT_PATH, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    for row in doc["channels"]:
        for platform, pq in (row.get("platform_qualification") or {}).items():
            path = os.path.join(ROOT, pq["evidence"])
            assert os.path.exists(path), \
                f"{row['channel']}/{platform}: evidence {pq['evidence']} missing"


def test_narrowing_reaches_the_adapter():
    """The point of the exercise: the PX4 adapter must see the PX4 rows."""
    from csia.aircraft.adapters import get_adapter
    assert get_adapter("px4").contract.channels["imu1.accel"].admissible is False
    assert get_adapter("ardupilot").contract.channels["imu1.accel"].admissible


def test_a_narrowed_channel_is_delivered_as_missing_not_as_a_value():
    px4 = SemanticContract(platform="px4")
    cv = px4.qualify("battery.current", 12.5, unit="A")
    assert cv.value is None
    assert cv.missing is not None


# --------------------------------------------------------------------------
# Freshness derives from the contract, not from a hand-written restatement.

def test_max_age_derives_from_the_declared_rate_per_platform():
    """A hand table cannot express a per-platform rate.

    PX4 publishes ESC_STATUS at ~1 Hz; the row claimed 10 and the table gave
    every platform 0.50 s, so PX4's ESC channels would have read STALE for
    about half of every publish period.
    """
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.adapters.base import MAX_AGE_MARGIN
    px4 = get_adapter("px4")
    ap = get_adapter("ardupilot")
    assert px4.max_age["esc.rpm"] == MAX_AGE_MARGIN / 1.0
    assert ap.max_age["esc.rpm"] == MAX_AGE_MARGIN / 10.0
    assert px4.max_age["esc.rpm"] > ap.max_age["esc.rpm"]


def test_every_declared_rate_yields_a_max_age_of_five_periods():
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.adapters.base import MAX_AGE_MARGIN
    for platform in ("ardupilot", "px4"):
        ad = get_adapter(platform)
        for channel, row in ad.contract.channels.items():
            rate = (row.raw.get(f"producer_{platform}") or {}).get("rate_hz")
            if rate:
                assert ad.max_age[channel] == MAX_AGE_MARGIN / float(rate), \
                    f"{platform}/{channel}"


def test_an_explicit_max_age_still_overrides_the_derivation():
    from csia.aircraft.adapters import get_adapter
    ad = get_adapter("px4", max_age={"esc.rpm": 0.25})
    assert ad.max_age["esc.rpm"] == 0.25


def test_px4_esc_at_its_real_rate_is_not_stale_between_publications():
    """The regression, with a controlled clock rather than an argument."""
    from csia.aircraft.adapters import get_adapter
    clock = {"t": 0.0}
    ad = get_adapter("px4", clock=lambda: clock["t"])
    ad.ingest({"mavpackettype": "ESC_STATUS", "index": 0,
               "time_usec": 1_000_000,
               "rpm": [5000] * 4 + [0] * 4,
               "current": [1.0] * 4 + [0.0] * 4,
               "voltage": [15.0] * 8})
    # One full publish period at the MEASURED 0.97 Hz, plus margin.
    for age in (0.6, 1.03, 2.0):
        clock["t"] = age
        cv = ad.sample(t_mono=age).esc["esc.rpm"]
        assert cv.note != f"age {age:.2f}s exceeds 0.50s"
        assert "exceeds" not in cv.note, f"stale at {age}s: {cv.note}"


def test_the_declared_px4_rates_match_what_was_measured():
    """Guard against the drift returning.

    Rates are quoted from the committed PX4 qualification result, which runs
    at speedup 1 so wall rates equal real rates. ArduPilot runs at speedup 10
    and is deliberately NOT checked here: comparing an accelerated wall rate
    against a real-time declaration is a category error.
    """
    import json
    path = os.path.join(ROOT, "research", "v1_1", "results",
                        "qualification_px4.json")
    if not os.path.exists(path):
        pytest.skip("no PX4 qualification result committed")
    result = json.load(open(path, encoding="utf-8"))
    contract = default_contract("px4")
    seconds = result.get("seconds") or 0
    checked = 0
    for row in result.get("rows", []):
        n = row.get("samples") or 0
        if not n or not seconds:
            continue
        declared = (contract.channels[row["channel"]].raw
                    .get("producer_px4") or {}).get("rate_hz")
        if not declared:
            continue
        measured = n / seconds
        checked += 1
        assert 0.5 * declared <= measured <= 2.0 * declared, (
            f"{row['channel']}: declared {declared} Hz, measured "
            f"{measured:.2f} Hz -- MaxAge derives from the declaration, so "
            f"this decides staleness")
    assert checked >= 8, "too few channels checked; the guard would be vacuous"


# --------------------------------------------------------------------------
# Dead vocabulary is a trap: unused, so nothing catches it drifting.

def test_stale_duplicate_constants_stay_deleted():
    """Three module-level names were defined, referenced NOWHERE, and wrong.

    * `csia.runtime.plugins.MAVLINK_MESSAGE_MAP` claimed imu0 comes from
      HIGHRES_IMU and the mag from a "SCALED_IMU3/MAG" that is not a MAVLink
      message. On ArduPilot 4.8 both ride inside RAW_IMU.
    * `csia.metrics.latency._ISOLATION_OUTCOMES` was a four-item vocabulary
      beside the ten-member IsolationOutcome enum actually in use.
    * `csia.simulation.rigs.PASSIVE_LINKS` said an ArduPilot shadow monitor
      listens on tcp:5762. After the telemetry-tee work, 5762 is the RIG's
      command link -- exactly backwards.

    An unused constant cannot be wrong in a way any test notices, which is
    why all three were still asserting a superseded architecture.
    """
    import csia.metrics.latency as latency
    import csia.runtime.plugins as plugins
    import csia.simulation.rigs as rigs
    assert not hasattr(plugins, "MAVLINK_MESSAGE_MAP")
    assert not hasattr(latency, "_ISOLATION_OUTCOMES")
    assert not hasattr(rigs, "PASSIVE_LINKS")


def test_the_qualification_context_is_recorded_everywhere_it_matters():
    """The contract says a bench must RE-RUN the probe, not inherit a row.

    A reader can only honour that if the evidence says which context produced
    it. It said nothing: `context` was set on the contract and read only to
    build a report string.
    """
    from csia.aircraft.adapters import get_adapter
    from csia.aircraft.qualification import CONTEXT_SIMULATOR
    meta = get_adapter("px4").sample(t_mono=0.0).metadata
    assert meta["qualification_context"] == CONTEXT_SIMULATOR


def test_an_unknown_context_is_refused_rather_than_stamped():
    # A typo would otherwise be written into every flight log as though it
    # meant something.
    from csia.aircraft.qualification import SemanticContract
    with pytest.raises(ValueError, match="unknown qualification context"):
        SemanticContract(context="SIMULATO")


def test_context_is_recorded_not_enforced_and_the_code_says_so():
    """Guard against the reverse mistake: someone reading `context` as a gate.

    Enforcement lives in platform_qualification rows. If that ever changes,
    this test should be the thing that makes the change deliberate.
    """
    from csia.aircraft.qualification import (
        CONTEXT_HARDWARE, CONTEXT_SIMULATOR, SemanticContract)
    sim = SemanticContract(context=CONTEXT_SIMULATOR, platform="px4")
    hw = SemanticContract(context=CONTEXT_HARDWARE, platform="px4")
    assert sim.admissible_channels() == hw.admissible_channels()


# --------------------------------------------------------------------------
# Documented numbers must match the result file they claim to quote.

def test_px4_doc_sample_counts_match_the_committed_result():
    """The document drifts from the evidence on every re-run.

    docs/simulation/PX4_CURRENT.md section 2.2 says it is "From
    research/v1_1/results/qualification_px4.json". It was hand-copied, so it
    said what a previous run had produced -- and after the sampling fix it
    still carried counts inflated by up to 445x, in the very section that
    explains that defect.

    Only `n=` is checked. It is the claim that was wrong by orders of
    magnitude, it is what an evidence base is judged on, and unlike range/sd
    it does not invite rounding arguments.
    """
    import json
    import re
    doc = os.path.join(ROOT, "docs", "simulation", "PX4_CURRENT.md")
    res = os.path.join(ROOT, "research", "v1_1", "results",
                       "qualification_px4.json")
    if not (os.path.exists(doc) and os.path.exists(res)):
        pytest.skip("document or result missing")
    with open(res, encoding="utf-8") as fh:
        rows = {r["channel"]: r for r in json.load(fh).get("rows", [])}
    with open(doc, encoding="utf-8") as fh:
        text = fh.read()

    wrong, checked = [], 0
    for channel, row in rows.items():
        m = re.search(r"n=(\d+)", row.get("detail", "") or "")
        if not m:
            continue
        pat = re.compile(
            rf"^\|\s*\*?\*?`?{re.escape(channel)}`?\*?\*?\s*\|.*?n=(\d+)", re.M)
        hit = pat.search(text)
        if not hit:
            continue
        checked += 1
        if hit.group(1) != m.group(1):
            wrong.append(f"{channel}: doc says n={hit.group(1)}, "
                         f"result says n={m.group(1)}")
    assert checked >= 8, (
        f"only {checked} table rows matched; the parser has drifted from the "
        f"document's shape and this guard is no longer checking anything")
    assert not wrong, (
        "PX4_CURRENT.md quotes sample counts that do not match "
        f"qualification_px4.json: {wrong}")
