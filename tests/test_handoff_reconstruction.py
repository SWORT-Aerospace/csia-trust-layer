"""The replay must rebuild the hand-offs the live run actually performed.

HF-010. `PlatformAdapter.to_core_samples` gates on channel ARRIVAL TIME;
the replay used to gate on channel VALUE. Two identical consecutive
readings have different arrival times and equal values, so the live run
hands the sensor over and the replay does not.

Measured on a committed 751-tick log: 1454 hand-offs by value against 3527
by arrival. The value method misses 58.8% of them, which is the mechanism
behind HF-004's DIVERGENT decision replay -- a sensor never handed over is
an edge never made live.

These tests pin the reconstruction against the REAL committed logs, not
against synthetic ticks, because the property that matters is agreement
with what a vehicle actually produced.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.deploy.profile_core_from_log import (ARRIVAL_QUANTUM_S,  # noqa: E402
                                                GATE_ARRIVAL, GATE_VALUE,
                                                HandoffReconstructor,
                                                load_ticks)

LOGS = {
    "ardupilot": "logs/shadow-sitl-ardupilot/"
                 "20260825T005244Z-8c32ffe5.part000.jsonl",
    "px4": "logs/shadow-sitl-px4/20260825T005931Z-1b4add14.part000.jsonl",
}


def _ticks(platform):
    path = os.path.join(ROOT, LOGS[platform])
    if not os.path.exists(path):
        pytest.skip(f"committed log missing: {LOGS[platform]}")
    return list(load_ticks(path))


def _count(platform, gate):
    reconstructor = HandoffReconstructor(gate=gate)
    return sum(len(reconstructor.samples_for_tick(t))
               for t in _ticks(platform))


@pytest.mark.parametrize("platform", sorted(LOGS))
def test_the_arrival_gate_finds_more_handoffs_than_the_value_gate(platform):
    """The whole point: the value gate under-counts, on both platforms."""
    assert _count(platform, GATE_ARRIVAL) > _count(platform, GATE_VALUE)


def test_the_undercount_is_large_not_slight():
    """It was documented as a SLIGHT under-count. It is not slight.

    If this ratio ever drops toward 1.0 the two reconstructions have
    converged and HF-010's premise needs re-checking.
    """
    value = _count("ardupilot", GATE_VALUE)
    arrival = _count("ardupilot", GATE_ARRIVAL)
    assert arrival / value > 1.5, (
        f"value={value} arrival={arrival}: the gap HF-010 measured has "
        f"closed; re-read the ledger entry before trusting either number")


@pytest.mark.parametrize("platform", sorted(LOGS))
def test_a_held_value_is_not_re_handed_over_every_tick(platform):
    """THE DEFECT IN MY FIRST VERSION OF THIS FIX.

    Reconstructed arrival is `t_mono - age_s`, two independently rounded
    quantities, so a HELD value's arrival wobbles by microseconds rather
    than repeating exactly. Compared at full precision every stamp looks
    new and the gate emits every sensor every tick -- over-counting, not
    reconstruction. That version made the PX4 decision replay WORSE (144
    divergent to 282).

    A faithful reconstruction must hand over strictly fewer times than
    "every mapped sensor, every tick".
    """
    from csia.aircraft.adapters.base import PlatformAdapter
    ticks = _ticks(platform)
    ceiling = len(ticks) * len(PlatformAdapter.CORE_MAP)
    assert _count(platform, GATE_ARRIVAL) < ceiling, (
        "the arrival gate fired on every sensor every tick, which means it "
        "is keying on float jitter rather than on arrival")


def test_the_quantum_sits_between_the_jitter_and_the_real_gaps():
    """The quantum is derived from two MEASURED populations, and this test
    re-measures them so the derivation cannot go stale.

    held-value arrival jitter  vs  real inter-arrival gaps. If they ever
    stop being cleanly separated, the quantisation is no longer justified
    and the choice becomes a tuning knob -- which is when this fails.
    """
    for platform in sorted(LOGS):
        series: dict = {}
        for tick in _ticks(platform):
            for channel, cv in tick["canonical"]["channels"].items():
                if cv.get("usable") and cv.get("age_s") is not None:
                    series.setdefault(channel, []).append(
                        (tick["t_mono"] - cv["age_s"], cv["value"]))

        jitter, gaps = [], []
        for rows in series.values():
            for i in range(1, len(rows)):
                delta = abs(rows[i][0] - rows[i - 1][0])
                if rows[i][1] == rows[i - 1][1] and delta < 1e-3:
                    jitter.append(delta)
                elif delta > 1e-3:
                    gaps.append(delta)

        assert jitter and gaps, f"{platform}: nothing measured"
        worst_jitter, smallest_gap = max(jitter), min(gaps)
        assert worst_jitter < ARRIVAL_QUANTUM_S < smallest_gap, (
            f"{platform}: quantum {ARRIVAL_QUANTUM_S} no longer sits between "
            f"jitter {worst_jitter:.3e} and gap {smallest_gap:.4f}")


def test_both_gates_remain_selectable():
    """The old reconstruction is kept so the two can be COMPARED. Silently
    replacing a measurement path is how a number changes without anyone
    being able to say why."""
    assert GATE_VALUE != GATE_ARRIVAL
    for gate in (GATE_VALUE, GATE_ARRIVAL):
        assert HandoffReconstructor(gate=gate).gate == gate
    with pytest.raises(ValueError, match="unknown gate"):
        HandoffReconstructor(gate="whatever")


def test_decision_replay_reports_which_gate_it_used():
    """A result that does not name its reconstruction cannot be compared
    against another one."""
    import inspect

    from tools.assurance import decision_replay
    src = inspect.getsource(decision_replay)
    assert '"reconstruction_gate": gate' in src
    assert "gate: str = \"arrival\"" in src
