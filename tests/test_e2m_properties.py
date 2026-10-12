"""Properties of the E2M acquisition layer, over generated input.

The example-based tests in `test_e2m_acquisition.py` check the cases I thought
of. These check the ones I did not. Two of them exist because the mutation
baseline found survivors -- `ID-05` (a CONFLICTED identity was not asserted to
be contradicted) and `CRC-02` (the missing-delimiter guard was redundant with
the CRC-length check, so removing it changed no observable behaviour).

Convention follows `tests/test_mission_properties.py`: plain `@given`, default
settings, composite strategies for the domain types.
"""
from __future__ import annotations

import json

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from csia_bus_provenance import (AMBIGUOUS, ASSUMED as BUS_ASSUMED,
                                 MISATTRIBUTED as BUS_MISATTRIBUTED,
                                 NOT_ATTRIBUTABLE, UNBOUND, VERIFIED, Device,
                                 Mux, Selection, attribute, channel_mask)
from csia_e2m import identity
from csia_e2m.logging import RunLogger
from csia_e2m.protocol import (NO_MEASUREMENT, OK, ProtocolError, Record,
                               STATUSES, crc16_ccitt, decode)
from csia_e2m.replay import replay

# --- strategies -----------------------------------------------------------

channels = st.integers(min_value=0, max_value=7)
sensor_ids = st.from_regex(r"\A[a-z][a-z0-9_]{0,10}\Z", fullmatch=True)
units = st.sampled_from(["milliC", "milliV", "milliA", "mbar"])


@st.composite
def records(draw, status=None):
    # `status` is a STRATEGY when supplied, not a value -- it has to be drawn
    # from like any other. Passing it through unread produced Records whose
    # status was a strategy object, which the constructor rightly refused.
    state = draw(status if status is not None else st.sampled_from(STATUSES))
    return Record(
        seq=draw(st.integers(min_value=0, max_value=10**6)),
        sweep=draw(st.integers(min_value=0, max_value=10**4)),
        commanded_channel=draw(channels),
        readback_channel=draw(st.one_of(st.just(-1), channels)),
        sensor=draw(sensor_ids),
        status=state,
        milli=draw(st.integers(min_value=-10**7, max_value=10**7)),
        unit=draw(units) if state == OK else "",
        controller_us=draw(st.integers(min_value=0, max_value=2**31)),
        i2c_error=draw(st.integers(min_value=0, max_value=8)),
        retries=draw(st.integers(min_value=0, max_value=5)))


# --- frame integrity ------------------------------------------------------

@given(record=records())
def test_every_frame_round_trips(record):
    assert decode(record.encode()) == record


@given(record=records(), index=st.integers(min_value=0),
       bit=st.integers(min_value=0, max_value=6))
def test_any_single_bit_corruption_is_detected(record, index, bit):
    """Not 'usually detected'. The frame is ASCII, so flipping a bit in any
    byte either breaks the CRC, breaks the field grammar, or changes a value
    the CRC then disagrees with -- and in every case decode must refuse."""
    line = record.encode()
    index %= len(line)
    mutated = bytearray(line.encode("ascii"))
    mutated[index] ^= 1 << bit
    corrupted = mutated.decode("ascii", errors="replace")
    assume(corrupted != line)
    with pytest.raises(ProtocolError):
        decode(corrupted)


@given(record=records(), cut=st.integers(min_value=0))
def test_no_truncation_decodes_as_a_valid_frame(record, cut):
    """A board resetting mid-write emits a prefix. No prefix may parse."""
    line = record.encode()
    cut %= len(line)
    with pytest.raises(ProtocolError):
        decode(line[:cut])


@given(record=records(), extra=st.text(alphabet="0123456789ABCDEF,",
                                       min_size=1, max_size=6))
def test_trailing_bytes_do_not_decode(record, extra):
    with pytest.raises(ProtocolError):
        decode(record.encode() + extra)


@given(body=st.text(alphabet="ABC0123,", min_size=0, max_size=40))
def test_a_frame_with_no_crc_delimiter_is_named_as_such(body):
    """Kills mutation survivor CRC-02.

    Removing the `"*" not in line` guard left every input still raising, so
    the mutant survived -- the guard was redundant for CONTROL FLOW. It is not
    redundant for DIAGNOSIS: an operator at a bench needs 'no CRC delimiter'
    rather than 'CRC field ... is not four hex digits' about a field that does
    not exist. Pinning the message makes the guard load-bearing.
    """
    assume("*" not in body)
    with pytest.raises(ProtocolError, match="no CRC delimiter"):
        decode(body if body.strip() else "nonempty")


@given(payload=st.binary(min_size=0, max_size=512))
def test_crc_is_always_sixteen_bits(payload):
    assert 0 <= crc16_ccitt(payload) <= 0xFFFF


# --- missingness ----------------------------------------------------------

@given(record=records(status=st.sampled_from(sorted(NO_MEASUREMENT))))
def test_a_non_ok_record_never_reports_a_measurement(record):
    assert record.has_measurement is False


@given(milli=st.integers(min_value=-10**6, max_value=10**6),
       status=st.sampled_from(sorted(NO_MEASUREMENT)))
def test_missing_never_becomes_zero_through_replay(tmp_path_factory, milli,
                                                   status):
    """The value on the wire is irrelevant when the status says there is no
    measurement -- including when it happens to be 0."""
    tmp = tmp_path_factory.mktemp("miss")
    row = {"type": "record", "host_monotonic_ns": 1, "controller_us": 1,
           "seq": 1, "sweep": 0, "commanded_channel": 0,
           "readback_channel": 0, "sensor": "s", "status": status,
           "milli": milli, "unit": "", "i2c_error": 0, "retries": 0}
    path = tmp / "r.jsonl"
    path.write_text(json.dumps(row))
    observation = list(replay(path))[0]
    assert observation.observed is False
    assert observation.value_milli is None


# --- sequence gaps --------------------------------------------------------

@given(first=st.integers(min_value=0, max_value=500),
       gap=st.integers(min_value=2, max_value=50))
def test_a_sequence_gap_is_always_recorded_explicitly(tmp_path_factory, first,
                                                      gap):
    tmp = tmp_path_factory.mktemp("seq")
    ticks = iter(range(10**9, 10**9 + 1000))
    logger = RunLogger(path=tmp / "r.jsonl", run_id="p", device="FAKE",
                       baud=0, clock=lambda: next(ticks))
    logger.open()
    base = Record(seq=first, sweep=0, commanded_channel=0,
                  readback_channel=0, sensor="s", status=OK, milli=1,
                  unit="milliC", controller_us=1, i2c_error=0, retries=0)
    logger.ingest(base.encode())
    from dataclasses import replace as _replace
    logger.ingest(_replace(base, seq=first + gap).encode())
    manifest = logger.close()
    assert len(manifest["sequence_gaps"]) == 1
    assert manifest["sequence_gaps"][0]["missing"] == gap - 1


# --- replay determinism ---------------------------------------------------

@given(rows=st.integers(min_value=1, max_value=25))
def test_replay_is_deterministic(tmp_path_factory, rows):
    tmp = tmp_path_factory.mktemp("det")
    path = tmp / "r.jsonl"
    payload = []
    for index in range(rows):
        payload.append(json.dumps(
            {"type": "record", "host_monotonic_ns": 1000 + index * 10,
             "controller_us": index, "seq": index, "sweep": index // 3,
             "commanded_channel": index % 8, "readback_channel": index % 8,
             "sensor": f"s{index % 3}", "status": OK, "milli": 100 + index,
             "unit": "milliC", "i2c_error": 0, "retries": 0}))
    path.write_text("\n".join(payload))
    first = [o.as_dict() for o in replay(path)]
    second = [o.as_dict() for o in replay(path)]
    assert first == second


# --- identity -------------------------------------------------------------

@given(commanded=st.one_of(st.none(), channels),
       readback=st.one_of(st.none(), channels),
       declared=st.one_of(st.none(), sensor_ids),
       acknowledged=st.booleans())
def test_identity_is_never_physically_verified_without_physical_evidence(
        commanded, readback, declared, acknowledged):
    """The core invariant of the owner's §11, over the whole input space
    reachable without an attestation or a native identity register."""
    assessment = identity.assess(
        commanded_channel=commanded, readback_channel=readback,
        declared_sensor=declared, write_acknowledged=acknowledged)
    assert assessment.state != identity.PHYSICALLY_VERIFIED
    assert assessment.establishes_attribution is False


@given(state=st.sampled_from([identity.ASSUMED, identity.COMMAND_CONFIRMED,
                              identity.READBACK_CONFIRMED,
                              identity.TOPOLOGY_DECLARED,
                              identity.UNOBSERVED]))
def test_no_weak_identity_state_establishes_attribution(state):
    assert identity.IdentityAssessment(state).establishes_attribution is False


@given(native=sensor_ids, expected=sensor_ids, commanded=channels)
def test_a_native_identity_mismatch_is_always_misattribution(native, expected,
                                                             commanded):
    assume(native != expected)
    assessment = identity.assess(
        commanded_channel=commanded, readback_channel=commanded,
        declared_sensor="declared", native_identity=native,
        expected_native_identity=expected)
    assert assessment.state == identity.MISATTRIBUTED
    assert assessment.contradicted is True


@given(native=sensor_ids, attested=sensor_ids, commanded=channels)
def test_operator_versus_device_disagreement_is_always_contradicted(
        native, attested, commanded):
    """Kills mutation survivor ID-05. Nothing previously asserted that a
    CONFLICTED identity counts as contradicted, so dropping CONFLICTED from
    that set changed no test outcome."""
    assume(native != attested)
    assessment = identity.assess(
        commanded_channel=commanded, readback_channel=commanded,
        declared_sensor="declared", native_identity=native,
        operator_attestation=attested)
    assert assessment.state == identity.CONFLICTED
    assert assessment.contradicted is True
    assert assessment.establishes_attribution is False


def test_conflicted_is_in_the_contradicted_set():
    """The same invariant stated directly, so the set cannot be narrowed."""
    assert identity.CONFLICTED in identity.CONTRADICTED
    assert identity.MISATTRIBUTED in identity.CONTRADICTED


# --- topology -------------------------------------------------------------

@given(channel=st.integers(min_value=-2000, max_value=2000))
def test_an_out_of_range_channel_can_never_build_a_device(channel):
    if 0 <= channel <= 7:
        assert Device("d", 0x68, channel).channel == channel
    else:
        with pytest.raises(ValueError, match="channel"):
            Device("d", 0x68, channel)


@given(address=st.integers(min_value=0x00, max_value=0x7F))
def test_only_the_tca9548a_address_range_builds_a_mux(address):
    if 0x70 <= address <= 0x77:
        assert Mux(address).address == address
    else:
        with pytest.raises(ValueError):
            Mux(address)


@given(a=channels, b=channels)
def test_two_devices_sharing_an_address_are_never_attributed(a, b):
    """Whenever both colliding channels are enabled, the verdict is AMBIGUOUS
    and neither candidate is returned as the source."""
    assume(a != b)
    left, right = Device("left", 0x68, a), Device("right", 0x68, b)
    mux = Mux(0x70, (left, right))
    mask = channel_mask(a, b)
    selection = Selection(0x70, mask, at_s=0.0, readback=mask,
                          readback_at_s=0.0)
    verdict = attribute(mux, 0x68, selection, expected=left)
    assert verdict.binding == AMBIGUOUS
    assert verdict.device is None
    assert verdict.identity_established is False


@given(selection_present=st.booleans(), channel=channels)
def test_a_binding_is_established_only_when_verified(selection_present,
                                                     channel):
    device = Device("only", 0x68, channel)
    mux = Mux(0x70, (device,))
    selection = (Selection(0x70, channel_mask(channel), at_s=0.0,
                           readback=channel_mask(channel), readback_at_s=0.0)
                 if selection_present else None)
    verdict = attribute(mux, 0x68, selection, expected=device)
    if selection_present:
        assert verdict.binding == VERIFIED
        assert verdict.identity_established is True
    else:
        assert verdict.binding == UNBOUND
        assert verdict.identity_established is False


@given(binding=st.sampled_from([AMBIGUOUS, BUS_MISATTRIBUTED, UNBOUND]))
def test_no_opt_in_rescues_a_binding_that_establishes_nothing(binding):
    from csia_bus_provenance import accepts
    assert accepts(binding, allow_assumed=True) is False
    assert binding in NOT_ATTRIBUTABLE


@given(allow=st.booleans())
def test_assumed_is_accepted_only_on_an_explicit_opt_in(allow):
    from csia_bus_provenance import accepts
    assert accepts(BUS_ASSUMED, allow_assumed=allow) is allow


# --- the CRC-field case hole ----------------------------------------------
# `test_any_single_bit_corruption_is_detected` asserts a UNIVERSAL claim, and
# for a while the claim was false. `int(given, 16)` is case-insensitive, so
# flipping bit 5 of an uppercase hex letter in the CRC field -- 'B' 0x42 ->
# 'b' 0x62 -- left the parsed value identical and the frame decoded as valid.
#
# The property test found it, and found it INTERMITTENTLY: the flip has to
# land on one of the field's A-F digits at bit 5, about 0.4% of examples, so a
# default 100-example run failed roughly a third of the time. It first showed
# up in a mutation sandbox, where the unmutated baseline refused to report.
# The three tests below make the same evidence deterministic, so a future
# regression fails every run rather than one run in three.

def _canonical_record(**over):
    fields = dict(seq=1, sweep=0, commanded_channel=2, readback_channel=2,
                  sensor="bme280", status=OK, milli=23150, unit="milliC",
                  controller_us=1234, i2c_error=0, retries=0)
    fields.update(over)
    return Record(**fields)


def test_the_exact_counterexample_is_refused():
    """The frame that used to decode. Pinned literally, not regenerated."""
    line = _canonical_record().encode()
    body, _, given = line.rpartition("*")
    assert given.isupper() or given.isdigit(), given
    lowered = f"{body}*{given.lower()}"
    assume_changed = lowered != line
    assert assume_changed, "pick a record whose CRC has a letter in it"
    assert int(given, 16) == int(given.lower(), 16)   # why it slipped through
    with pytest.raises(ProtocolError, match="UPPERCASE"):
        decode(lowered)


@pytest.mark.parametrize("sensor,status,milli,unit", [
    ("bme280", OK, 23150, "milliC"),
    ("mpu6050", "ERR_SENSOR_NACK", 0, "milliG"),
    ("ina219", OK, -1000, "milliA"),
])
def test_every_single_bit_flip_is_refused_exhaustively(sensor, status, milli,
                                                       unit):
    """Not sampled. Every bit of every byte of the frame, one at a time.

    Hypothesis says 'no counterexample was found in 100 tries'. This says
    'there is none', for these frames, which is the claim the docstring of
    `test_any_single_bit_corruption_is_detected` actually makes.
    """
    line = _canonical_record(sensor=sensor, status=status, milli=milli,
                             unit=unit).encode()
    undetected = []
    for index in range(len(line)):
        for bit in range(7):
            raw = bytearray(line.encode("ascii"))
            raw[index] ^= 1 << bit
            corrupted = raw.decode("ascii", errors="replace")
            if corrupted == line:
                continue
            try:
                decode(corrupted)
            except ProtocolError:
                continue
            undetected.append((index, line[index], bit, corrupted))
    assert undetected == [], undetected


def test_a_lowercase_crc_is_refused_for_every_hex_letter():
    """Each of a-f, in each of the four positions, on a frame that admits it."""
    seen = set()
    for seq in range(4000):
        line = _canonical_record(seq=seq).encode()
        body, _, given = line.rpartition("*")
        for position, char in enumerate(given):
            if char not in "ABCDEF" or (position, char) in seen:
                continue
            seen.add((position, char))
            mutated = given[:position] + char.lower() + given[position + 1:]
            with pytest.raises(ProtocolError, match="UPPERCASE"):
                decode(f"{body}*{mutated}")
    # 4 positions x 6 letters. If the search did not reach them all, the
    # coverage claim in the name is false and the test says so.
    assert len(seen) == 24, sorted(seen)
