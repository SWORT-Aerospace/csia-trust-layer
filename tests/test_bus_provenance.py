"""Device identity behind a TCA9548A, and the ways it is lost.

The case that matters is `test_a_stale_channel_produces_a_real_value_from_the
_wrong_device`: a healthy device reporting a true measurement of itself, under
another device's name. Every other test here exists to stop that one from
being reachable without a verdict saying so.
"""
from __future__ import annotations

import pytest

from csia_bus_provenance import (AMBIGUOUS, ASSUMED, ESTABLISHED,
                                 MISATTRIBUTED, NO_RESPONDER,
                                 NOT_ATTRIBUTABLE, UNBOUND, VERIFIED,
                                 Attribution, BusError, Device, Mux,
                                 MuxSimulator, Selection, Topology, accepts,
                                 attribute, channel_mask, channels_in)
from csia_bus_provenance import datasheet as ds
from csia_bus_provenance import simulator as sim

IMU_A = Device(name="imu_a", address=0x68, channel=0)
IMU_B = Device(name="imu_b", address=0x68, channel=1)
BARO = Device(name="baro", address=0x77, channel=2)
MUX = Mux(address=0x70, devices=(IMU_A, IMU_B, BARO), label="mux0")


# --- the datasheet is not evidence ---------------------------------------

def test_the_datasheet_was_not_retrieved_and_the_module_says_so():
    assert ds.DATASHEET_STATUS == "NOT_RETRIEVED"
    assert ds.DATASHEET_SHA256 is None
    assert ds.DATASHEET_ACCESS_RECORD["conclusion"] == (
        "PRIMARY_SOURCE_NOT_RETRIEVED")


def test_unverified_constants_cannot_reach_hardware():
    """The gate is a raise, not a comment. Simulation never calls it."""
    with pytest.raises(ds.DatasheetNotVerified) as excinfo:
        ds.require_verified_datasheet("drive a real bus")
    assert "unverified" in str(excinfo.value)


# --- the topology refuses what no selection could fix ---------------------

def test_two_devices_at_one_address_on_one_channel_is_refused():
    with pytest.raises(ValueError, match="No channel selection can tell them"):
        Mux(address=0x70, devices=(IMU_A, Device("imu_c", 0x68, 0)))


def test_a_device_may_share_an_address_across_channels():
    """The supported configuration, and the reason the part is bought."""
    assert MUX.shared_addresses == frozenset({0x68})


def test_a_device_at_the_mux_address_is_refused():
    """Enabling that channel makes the mux unaddressable."""
    with pytest.raises(ValueError, match="same address as the"):
        Mux(address=0x70, devices=(Device("clash", 0x70, 3),))


def test_a_non_tca9548a_address_is_refused():
    with pytest.raises(ValueError, match="not a TCA9548A address"):
        Mux(address=0x20)


def test_reserved_i2c_addresses_are_refused():
    with pytest.raises(ValueError, match="reserved by I2C"):
        Device("bad", 0x00, 0)


def test_two_muxes_at_one_address_are_refused():
    with pytest.raises(ValueError, match="tie A0/A1/A2 differently"):
        Topology(muxes=(Mux(0x70), Mux(0x70, label="second")))


def test_the_audit_reports_a_mux_that_was_not_needed():
    """A topology with no shared address did not need a mux; saying so is
    more useful than saying nothing."""
    plain = Topology(muxes=(Mux(0x70, devices=(BARO,)),))
    assert plain.audit()["mux_needed"] is False
    assert Topology(muxes=(MUX,)).audit()["mux_needed"] is True


def test_ambiguous_masks_are_enumerated_not_reasoned_about():
    """"We would never write that mask" is a claim about software; this is a
    question about wiring, so all 256 values are checked."""
    masks = MUX.ambiguous_masks()
    assert channel_mask(0, 1) in masks
    assert channel_mask(0) not in masks
    assert channel_mask(0, 2) not in masks
    # Every ambiguous mask must enable both of the colliding channels.
    for mask in masks:
        assert {0, 1} <= set(channels_in(mask))


# --- the bindings ---------------------------------------------------------

def test_a_verified_selection_attributes_the_read():
    selection = Selection(0x70, channel_mask(0), at_s=1.0,
                          readback=channel_mask(0), readback_at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == VERIFIED
    assert verdict.device == IMU_A
    assert verdict.identity_established is True


def test_no_readback_is_assumed_not_verified():
    """The write may have NACKed. Nobody looked, so nobody knows."""
    selection = Selection(0x70, channel_mask(0), at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == ASSUMED
    assert "never read back" in verdict.why


def test_a_read_with_no_selection_is_unbound():
    verdict = attribute(MUX, 0x68, None, expected=IMU_A)
    assert verdict.binding == UNBOUND
    assert verdict.candidates == ()


def test_a_selection_for_another_mux_does_not_bind_this_read():
    selection = Selection(0x71, channel_mask(0), at_s=1.0,
                          readback=channel_mask(0), readback_at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == UNBOUND


def test_writes_since_readback_invalidate_it():
    """The readback described the register then, not now."""
    selection = Selection(0x70, channel_mask(0), at_s=1.0,
                          readback=channel_mask(0), readback_at_s=1.0,
                          writes_since=1)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == ASSUMED
    assert "since the readback" in verdict.why


def test_an_aged_binding_degrades():
    selection = Selection(0x70, channel_mask(0), at_s=1.0,
                          readback=channel_mask(0), readback_at_s=1.0)
    fresh = attribute(MUX, 0x68, selection, expected=IMU_A, read_at_s=1.2,
                      max_binding_age_s=0.5)
    aged = attribute(MUX, 0x68, selection, expected=IMU_A, read_at_s=9.0,
                     max_binding_age_s=0.5)
    assert fresh.binding == VERIFIED
    assert aged.binding == ASSUMED


def test_two_enabled_channels_make_the_source_undeterminable():
    selection = Selection(0x70, channel_mask(0, 1), at_s=1.0,
                          readback=channel_mask(0, 1), readback_at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == AMBIGUOUS
    assert {d.name for d in verdict.candidates} == {"imu_a", "imu_b"}


def test_ambiguity_is_carried_never_resolved():
    """Objective 3 is to preserve unresolved ambiguity. Returning the likelier
    device would be hiding it behind a plausible name."""
    selection = Selection(0x70, channel_mask(0, 1), at_s=1.0,
                          readback=channel_mask(0, 1), readback_at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.device is None
    assert len(verdict.candidates) == 2
    assert verdict.identity_established is False
    assert verdict.establishes_nothing is True


def test_ambiguity_outranks_staleness():
    """A read two devices could have answered is not made attributable by
    having been taken promptly."""
    selection = Selection(0x70, channel_mask(0, 1), at_s=1.0,
                          readback=channel_mask(0, 1), readback_at_s=1.0,
                          writes_since=3)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A, read_at_s=99.0,
                        max_binding_age_s=0.1)
    assert verdict.binding == AMBIGUOUS


def test_no_device_on_the_enabled_channel_is_not_a_silent_pass():
    selection = Selection(0x70, channel_mask(5), at_s=1.0,
                          readback=channel_mask(5), readback_at_s=1.0)
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == NO_RESPONDER
    assert verdict.establishes_nothing is True


def test_only_a_measured_register_establishes_identity():
    """ASSUMED is not an establishment. An earlier draft of this module had it
    counted as one, and the counterexample below is what refuted that."""
    assert ESTABLISHED == frozenset({VERIFIED})
    assert ASSUMED not in ESTABLISHED
    for binding in (AMBIGUOUS, MISATTRIBUTED, NO_RESPONDER, UNBOUND):
        assert binding in NOT_ATTRIBUTABLE


def test_accepting_an_assumed_binding_must_be_said_out_loud():
    """The cost appears in the caller's source, not defaulted in ours."""
    assert accepts(VERIFIED) is True
    assert accepts(ASSUMED) is False
    assert accepts(ASSUMED, allow_assumed=True) is True
    # No opt-in rescues a binding that establishes nothing.
    for binding in (AMBIGUOUS, MISATTRIBUTED, NO_RESPONDER, UNBOUND):
        assert accepts(binding, allow_assumed=True) is False


# --- the case the package exists for --------------------------------------

def test_a_stale_channel_produces_a_real_value_from_the_wrong_device():
    """The defect this package exists to make visible.

    The host selects channel 1 and reads 0x68. The write never landed, so the
    mux is still on channel 0 and `imu_a` answers. `imu_b`'s name is attached
    to `imu_a`'s measurement. Both devices are healthy, the value is true, and
    nothing in the bytes is wrong -- the information needed to catch it was
    never on the bus.
    """
    mux = MuxSimulator(MUX)
    mux.select(0, at_s=0.0)                       # legitimately on channel 0
    assert mux.responders(0x68) == (IMU_A,)

    mux.fault = sim.WRITE_IGNORED
    selection = mux.select(1, at_s=1.0)           # believes it moved to ch 1

    # Ground truth: imu_a is still the responder, not imu_b.
    assert mux.responders(0x68) == (IMU_A,)

    verdict = attribute(MUX, 0x68, selection, expected=IMU_B)
    assert verdict.binding == MISATTRIBUTED
    assert verdict.candidates == (IMU_A,)
    assert verdict.expected == IMU_B
    assert verdict.establishes_nothing is True
    assert "channel 0" in verdict.why


def test_without_readback_the_same_misattribution_is_invisible():
    """The counterexample that corrected this module's own design.

    Identical physical situation to the test above, verify=False. Ground truth
    is unchanged -- imu_a answers while the caller expects imu_b -- but with no
    readback the evidence to detect it was never collected, so the verdict can
    only be ASSUMED. MISATTRIBUTED is not reachable without a readback.

    An earlier draft counted ASSUMED as attributable, which meant the default
    path accepted imu_a's measurement under imu_b's name. It now establishes
    nothing unless the caller opts in explicitly, and that opt-in is what this
    test prices.
    """
    mux = MuxSimulator(MUX)
    mux.select(0, at_s=0.0)
    mux.fault = sim.WRITE_IGNORED
    selection = mux.select(1, at_s=1.0, verify=False)

    assert mux.responders(0x68) == (IMU_A,)      # ground truth: wrong device
    verdict = attribute(MUX, 0x68, selection, expected=IMU_B)

    assert verdict.binding == ASSUMED            # not MISATTRIBUTED: unseen
    assert verdict.identity_established is False
    assert verdict.accepted_by() is False
    assert verdict.accepted_by(allow_assumed=True) is True   # and WRONG


# --- the simulator's faults ----------------------------------------------

def test_a_brownout_disconnects_every_channel_while_the_host_believes_otherwise():
    mux = MuxSimulator(MUX)
    mux.select(0, at_s=0.0)
    mux.brownout(at_s=1.0)
    assert mux.register == ds.POR_CONTROL_REGISTER
    assert mux.responders(0x68) == ()
    stale = Selection(0x70, channel_mask(0), at_s=0.0,
                      readback=channel_mask(0), readback_at_s=0.0)
    # Judged on the host's record alone, the read still looks fine; the
    # register it describes no longer exists. This is what the age limit and
    # re-verification are for.
    assert attribute(MUX, 0x68, stale, expected=IMU_A).binding == VERIFIED


def test_an_extra_enabled_channel_creates_ambiguity_from_a_clean_command():
    mux = MuxSimulator(MUX, fault=sim.EXTRA_CHANNEL, extra_channel=1)
    selection = mux.select(0, at_s=0.0)
    assert set(channels_in(mux.register)) == {0, 1}
    verdict = attribute(MUX, 0x68, selection, expected=IMU_A)
    assert verdict.binding == AMBIGUOUS


def test_a_silent_mux_raises_rather_than_returning_a_plausible_register():
    mux = MuxSimulator(MUX, fault=sim.MUX_SILENT)
    with pytest.raises(BusError):
        mux.select(0, at_s=0.0)
    with pytest.raises(BusError):
        mux.read_register(at_s=0.0)


def test_the_simulator_is_deterministic_and_reads_no_clock():
    def run():
        mux = MuxSimulator(MUX)
        mux.select(0, at_s=0.0)
        mux.select(1, at_s=1.0)
        mux.brownout(at_s=2.0)
        return mux.log
    assert run() == run()


def test_an_unknown_fault_is_refused():
    with pytest.raises(ValueError, match="unknown fault"):
        MuxSimulator(MUX, fault="GREMLINS")


# --- authority and hardware boundaries ------------------------------------

def test_the_package_declares_no_actuator_authority():
    import csia_bus_provenance as pkg
    assert pkg.HAS_ACTUATOR_AUTHORITY is False
    assert pkg.HARDWARE_VALIDATED is False
    assert pkg.LAYER == "acquisition"


def test_no_module_imports_a_hardware_interface():
    """The owner authorization holds the hardware prohibition by there being
    no path, not by a promise. This is that assertion, mechanically."""
    import ast
    import pathlib

    forbidden = {"smbus", "smbus2", "periphery", "serial", "spidev",
                 "RPi", "board", "busio", "adafruit_tca9548a", "gpiozero"}
    root = pathlib.Path(__file__).resolve().parents[1] / "csia_bus_provenance"
    offenders = []
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name.split(".")[0] in forbidden:
                    offenders.append(f"{path.name}: {name}")
    assert offenders == [], offenders


def test_the_attribution_serialises_without_losing_the_ambiguity():
    selection = Selection(0x70, channel_mask(0, 1), at_s=1.0,
                          readback=channel_mask(0, 1), readback_at_s=1.0)
    payload = attribute(MUX, 0x68, selection, expected=IMU_A).as_dict()
    assert payload["binding"] == "AMBIGUOUS"
    assert payload["identity_established"] is False
    assert payload["establishes_nothing"] is True
    assert len(payload["candidates"]) == 2
    assert payload["enabled_channels"] == [0, 1]


def test_a_readback_without_a_timestamp_is_refused():
    """It could not be ordered against the read it is supposed to justify."""
    with pytest.raises(ValueError, match="cannot be ordered"):
        Selection(0x70, channel_mask(0), at_s=1.0, readback=channel_mask(0))


def test_attribution_never_consults_simulator_ground_truth():
    """`attribute` decides from the host's records. If it could see the
    simulator's register, every test above would be vacuous."""
    import inspect

    from csia_bus_provenance import provenance
    source = inspect.getsource(provenance)
    assert "MuxSimulator" not in source
    assert "simulator" not in source.replace("csia_bus_provenance.simulator",
                                             "")
    assert isinstance(attribute(MUX, 0x68, None), Attribution)
