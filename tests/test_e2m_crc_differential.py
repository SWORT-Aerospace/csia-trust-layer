"""The firmware's CRC and the host's CRC, compared instead of assumed.

`csia_e2m/protocol.py` claims its CRC loop and the firmware's "cannot drift
apart through a library version" because they are the same eight lines. That
was an assertion. Two separate source files in two languages are exactly the
place where "the same" quietly stops being true, and this repository does not
accept that kind of claim anywhere else.

So the C is compiled and run for real. If `cc` is missing the tests SKIP with
the blocker named -- they do not pass, and equivalence is not claimed.

The harness carries a verbatim copy of the firmware function between marker
comments, and `test_the_harness_has_not_drifted_from_the_firmware` diffs the
two token-for-token. Without that, the harness could agree with Python while
the firmware disagreed with both, and the differential would prove nothing
about the thing that actually runs on the board.
"""
from __future__ import annotations

import pathlib
import random
import re
import shutil
import subprocess

import pytest

from csia_e2m.protocol import Record, crc16_ccitt

ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS_C = ROOT / "hardware/host_tests/crc_harness.c"
FIRMWARE = (ROOT / "hardware/arduino/e2m_mux_acquisition"
            / "e2m_mux_acquisition.ino")

_CC = shutil.which("cc") or shutil.which("gcc")
requires_cc = pytest.mark.skipif(
    _CC is None,
    reason="no C compiler on PATH; the firmware CRC cannot be built, so "
           "equivalence with the Python CRC is NOT claimed. A skip is not a "
           "pass.")


def _extract(text: str, begin: str, end: str) -> str:
    body = text.split(begin, 1)[1].split(end, 1)[0]
    # Compare tokens, not whitespace: indentation differs between a C file
    # and a C block inside an .ino, and that difference is not drift.
    return re.sub(r"\s+", " ", body).strip()


def test_the_harness_has_not_drifted_from_the_firmware():
    """The harness stands in for the firmware. If it has been edited apart
    from it, every differential result below is about the wrong function."""
    harness = _extract(HARNESS_C.read_text(),
                       "/* ---- BEGIN COPY FROM e2m_mux_acquisition.ino ---- */",
                       "/* ---- END COPY FROM e2m_mux_acquisition.ino ---- */")
    firmware = _extract(
        FIRMWARE.read_text(),
        "static uint16_t crc16_ccitt(const char *data, size_t len) {",
        "\n}")
    # Re-attach the signature the firmware split on, so both sides are the
    # complete function.
    firmware = ("static uint16_t crc16_ccitt(const char *data, size_t len) { "
                + firmware + " }")
    assert harness == firmware, (
        "the host harness and the firmware CRC have diverged:\n"
        f"harness : {harness}\nfirmware: {firmware}")


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    if _CC is None:                       # pragma: no cover
        pytest.skip("no C compiler")
    binary = tmp_path_factory.mktemp("crc") / "crc_harness"
    proc = subprocess.run(
        [_CC, "-O2", "-Wall", "-Wextra", "-Werror", "-o", str(binary),
         str(HARNESS_C)], capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"firmware CRC harness did not compile:\n{proc.stderr}")
    return binary


def _c_crc(binary, payloads):
    """One process, many payloads, so the comparison is cheap."""
    stdin = "\n".join(p.hex() for p in payloads) + "\n"
    proc = subprocess.run([str(binary)], input=stdin, capture_output=True,
                          text=True)
    assert proc.returncode == 0, proc.stderr
    return [int(v, 16) for v in proc.stdout.split()]


@requires_cc
def test_the_standard_check_vector(harness):
    """CRC-16/CCITT-FALSE is defined by this vector. If both sides agree on
    the wrong algorithm they would still agree; this is what rules that out."""
    assert crc16_ccitt(b"123456789") == 0x29B1
    assert _c_crc(harness, [b"123456789"]) == [0x29B1]


@requires_cc
def test_the_named_edge_payloads(harness):
    payloads = [
        b"",                       # empty: init value, unmasked
        b"\x00",                   # one zero byte
        b"\xff",                   # one all-ones byte
        b"\x00" * 64,              # all-zero
        b"\xff" * 64,              # all-0xFF
        b"\x00" * 255,
        b"\xff" * 255,
        bytes(range(256)),         # every byte value
    ]
    assert _c_crc(harness, payloads) == [crc16_ccitt(p) for p in payloads]


@requires_cc
def test_real_frames_agree(harness):
    """The payloads that actually cross the wire, not just synthetic bytes."""
    frames = []
    for channel in range(8):
        record = Record(seq=channel, sweep=1, commanded_channel=channel,
                        readback_channel=channel, sensor=f"ch{channel}",
                        status="OK", milli=25000 + channel, unit="milliC",
                        controller_us=123456 + channel, i2c_error=0, retries=0)
        frames.append(record.payload().encode("ascii"))
    assert _c_crc(harness, frames) == [crc16_ccitt(f) for f in frames]


@requires_cc
def test_maximum_length_frame(harness):
    """The firmware's line buffer is 160 bytes. A payload at and beyond that
    boundary must still agree -- the C uses size_t and the Python is
    unbounded, and that is where an integer assumption would show."""
    for length in (159, 160, 161, 1024):
        payload = bytes((i * 7 + 13) & 0xFF for i in range(length))
        assert _c_crc(harness, [payload]) == [crc16_ccitt(payload)]


@requires_cc
def test_single_bit_mutations_agree_and_change_the_crc(harness):
    """Two properties at once: the implementations agree on every mutant, and
    a one-bit change actually moves the CRC. The second matters -- a CRC that
    agreed but never changed would pass the first and detect nothing."""
    base = Record(seq=7, sweep=2, commanded_channel=3, readback_channel=3,
                  sensor="ch3", status="OK", milli=25999, unit="milliC",
                  controller_us=987654, i2c_error=0,
                  retries=0).payload().encode("ascii")
    original = crc16_ccitt(base)
    mutants = []
    for index in range(len(base)):
        for bit in (0, 3, 7):
            mutated = bytearray(base)
            mutated[index] ^= 1 << bit
            mutants.append(bytes(mutated))
    assert _c_crc(harness, mutants) == [crc16_ccitt(m) for m in mutants]
    assert all(crc16_ccitt(m) != original for m in mutants), (
        "a single-bit change left the CRC unmoved")


@requires_cc
def test_truncations_agree(harness):
    base = Record(seq=11, sweep=0, commanded_channel=1, readback_channel=-1,
                  sensor="ch1", status="ERR_SENSOR_NACK", milli=0, unit="",
                  controller_us=4242, i2c_error=2,
                  retries=3).payload().encode("ascii")
    cuts = [base[:n] for n in range(len(base) + 1)]
    assert _c_crc(harness, cuts) == [crc16_ccitt(c) for c in cuts]


@requires_cc
def test_randomised_payloads_agree(harness):
    """Deterministic seed: a differential test that cannot be re-run on the
    same inputs cannot be used to investigate a disagreement."""
    rng = random.Random(20260918)
    payloads = [bytes(rng.randrange(256) for _ in range(rng.randrange(0, 300)))
                for _ in range(400)]
    assert _c_crc(harness, payloads) == [crc16_ccitt(p) for p in payloads]
