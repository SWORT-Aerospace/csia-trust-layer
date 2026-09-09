"""Arrival-time comparison must not flip on a microsecond (HF-016).

THE BUG
-------
The hand-off reconstructor derives a channel's arrival time as
`t_mono - age_s` and used to compare arrivals by ROUNDING both to a 1 ms
grid. That derivation carries sub-millisecond jitter: measured on a PX4 SITL
log, `baro.altitude` produced 1094 samples with only 381 distinct arrival
times, 683 consecutive deltas below 20 ms, median 1 us and **max 126 us**.

Rounding to a grid is boundary-sensitive. Two values 126 us apart land on
different integers whenever they straddle a boundary, which reads as a NEW
ARRIVAL that never happened. Each spurious hand-off perturbs when freshness
is evaluated for that sensor, and freshness is what the categorical decision
rests on.

Measured effect of replacing the rounding with a tolerance comparison:
reconstructed hand-offs moved toward the counts the log implies
(baro 93 -> 89 against 88 implied; mag 1274 -> 1268 against 1266; gps
721 -> 711 against 709) and PX4 replay divergences fell 127 -> 119, with
ArduPilot unchanged at 0.

WHAT THIS DOES NOT FIX, AND THE TESTS SAY SO
---------------------------------------------
119 PX4 divergences remain. Their signature is now SYMMETRIC -- 59 ticks
where the replay has `altitude_baro` live and the recording does not, and 59
where the recording has it and the replay does not -- which is a phase
offset of about one tick at baro's staleness boundary, not a semantic
disagreement. That is a different problem and is recorded as one.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.deploy.profile_core_from_log import (  # noqa: E402
    ARRIVAL_QUANTUM_S, _same_arrivals)


def test_jitter_below_the_tolerance_is_not_a_new_arrival():
    """THE REGRESSION. 126 us was the measured worst case; under a 1 ms
    tolerance it must read as the same arrival however the two values sit
    relative to a grid boundary."""
    for base in (10.0, 10.0004999, 10.0009999, 10.4995, 123.4567):
        a = (("baro.altitude", base),)
        b = (("baro.altitude", base + 126e-6),)
        assert _same_arrivals(a, b), (
            f"126 us of jitter at t={base} read as a new arrival")


def test_the_old_rounding_would_have_flipped_where_the_tolerance_does_not():
    """Shows the defect concretely rather than describing it: two values
    126 us apart that straddle a 1 ms boundary round to DIFFERENT integers,
    which is exactly the spurious hand-off."""
    # Grid boundaries sit at half-quantum offsets, so a pair straddling one
    # must bracket x.xxx5 -- my first attempt at this example did not, and
    # the assertion below caught it.
    lo, hi = 10.0004000, 10.0005260          # 126 us apart, straddles 10000.5
    assert round(lo / ARRIVAL_QUANTUM_S) != round(hi / ARRIVAL_QUANTUM_S), (
        "this pair no longer demonstrates the boundary effect; pick another")
    assert _same_arrivals((("baro.altitude", lo),), (("baro.altitude", hi),))


def test_a_real_new_arrival_is_still_detected():
    """The fix must not make the comparison blind. A genuine baro arrival
    moves the derived time by ~1 s; imu0 by ~40 ms. Both are far above the
    tolerance and must register."""
    for gap in (0.04, 0.0405, 0.0808, 1.0, 1.0014):
        a = (("baro.altitude", 10.0),)
        b = (("baro.altitude", 10.0 + gap),)
        assert not _same_arrivals(a, b), f"a {gap}s gap read as no arrival"


def test_the_boundary_of_the_tolerance_is_where_it_is_declared():
    """Just inside is the same arrival; just outside is a new one. Pins the
    comparison to the declared constant rather than to a magic number."""
    a = (("c", 5.0),)
    assert _same_arrivals(a, (("c", 5.0 + ARRIVAL_QUANTUM_S * 0.9),))
    assert not _same_arrivals(a, (("c", 5.0 + ARRIVAL_QUANTUM_S * 1.1),))


def test_a_different_channel_set_is_never_the_same_arrival():
    """A sensor whose channel set changed has not merely moved in time --
    comparing element-wise across different channels would compare unrelated
    quantities."""
    assert not _same_arrivals((("a", 1.0),), (("b", 1.0),))
    assert not _same_arrivals((("a", 1.0),), (("a", 1.0), ("b", 1.0)))
    assert not _same_arrivals(None, (("a", 1.0),))


def test_no_previous_arrival_is_always_a_new_one():
    """The first hand-off for a sensor must always be emitted."""
    assert not _same_arrivals(None, (("a", 1.0),))
    assert not _same_arrivals((), (("a", 1.0),))
