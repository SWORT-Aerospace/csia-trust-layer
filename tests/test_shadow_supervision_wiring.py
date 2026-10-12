"""The overlay reaches the deployment path, and only when asked.

SR-003 added a loss-of-data rule and nothing called it. `ShadowRunner`
constructed a bare `FailsafePolicy()`, so on a real shadow flight SR-001
was still open: the rule existed, was tested, and would never fire.

WHY IT IS OFF BY DEFAULT
------------------------
Shadow mode PRODUCES EVIDENCE. Turning supervision on silently would mean
logs recorded before and after the change describe different systems while
both claiming mode SHADOW, with nothing in the log to tell them apart. So
it is an explicit flag, and the header records which policy was in force.

THE THREE PROPERTIES
--------------------
1. off by default, and the header says so
2. on when asked, and the header says that instead
3. the wrapper is a DROP-IN: every attribute the runner reads off the
   policy still works, forwarded to the frozen policy rather than
   reimplemented
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia.deploy.flight_log import make_header                # noqa: E402
from csia.deploy.shadow import ShadowConfig, ShadowRunner     # noqa: E402
from csia.runtime.failsafe import (FailsafeConfig,            # noqa: E402
                                   FailsafeLevel, FailsafePolicy)
from csia_supervision import SupervisedFailsafe               # noqa: E402

#: Every attribute `ShadowRunner` reads off `self.policy`. If the runner
#: starts using a new one, this list must grow with it -- which is the
#: point: a wrapper that silently lacks an attribute would raise mid-flight.
RUNNER_USES = ("update", "level", "_conditions", "_cond_since")


def test_supervision_is_off_by_default():
    """The default must not change what a shadow flight measures."""
    assert ShadowConfig().data_loss_supervision is False


def test_default_runner_uses_the_bare_frozen_policy():
    runner = ShadowRunner(ShadowConfig())
    assert type(runner.policy) is FailsafePolicy
    assert not hasattr(runner.policy, "frozen_level")


def test_enabling_the_flag_wraps_the_frozen_policy():
    runner = ShadowRunner(ShadowConfig(data_loss_supervision=True))
    assert isinstance(runner.policy, SupervisedFailsafe)
    # WRAPPED, not replaced: the frozen policy is still in there.
    assert type(runner.policy.policy) is FailsafePolicy


@pytest.mark.parametrize("attribute", RUNNER_USES)
def test_the_wrapper_is_a_drop_in_for_everything_the_runner_reads(attribute):
    """A missing attribute would raise on the first tick of a real flight,
    which is the worst possible moment to discover it."""
    supervised = SupervisedFailsafe()
    assert hasattr(supervised, attribute), (
        f"ShadowRunner reads .{attribute} off the policy and the wrapper "
        f"does not provide it")


def test_the_wrapper_forwards_rather_than_reimplements():
    """`_conditions` is the FROZEN policy's own. A second implementation
    would be a copy of the thing under test -- which the runner's own
    docstring warns against."""
    frozen = FailsafePolicy()
    supervised = SupervisedFailsafe(policy=frozen)
    assert supervised.cfg is frozen.cfg
    assert supervised.transitions is frozen.transitions

    # Behavioural, not identity: `_conditions` is a one-line forwarder
    # defined on the wrapper, so its `__self__` is the wrapper. What must
    # hold is that it returns exactly what the frozen policy returns.
    state = _State(20.0, {n: True for n in _State.NODES})
    assert supervised._conditions(state) == frozen._conditions(state)


def test_the_header_records_which_policy_was_in_force():
    """A log that does not name its failsafe describes a system the reader
    cannot identify, and the two are NOT comparable."""
    class _Adapter:
        platform = "ardupilot"
        adapter_version = "test"

        class contract:
            version = 1

    header = make_header(
        adapter=_Adapter(), mode="SHADOW", autopilot_version="x",
        command_authority={}, sensor_availability={}, profile="p",
        vehicle_config={})
    assert header.failsafe_policy == "FROZEN_ONLY"

    supervised = make_header(
        adapter=_Adapter(), mode="SHADOW", autopilot_version="x",
        command_authority={}, sensor_availability={}, profile="p",
        vehicle_config={},
        failsafe_policy="FROZEN_PLUS_DATA_LOSS_SUPERVISION")
    assert supervised.failsafe_policy == "FROZEN_PLUS_DATA_LOSS_SUPERVISION"


def test_the_runner_puts_its_own_flag_in_the_header():
    """The flag and the header must not be able to disagree."""
    import inspect

    from csia.deploy import shadow
    src = inspect.getsource(shadow)
    assert "FROZEN_PLUS_DATA_LOSS_SUPERVISION" in src
    assert "if self.cfg.data_loss_supervision" in src


# ---------------------------------------------------------------------------
# the policy row
# ---------------------------------------------------------------------------

class _State:
    NODES = ("imu0", "imu1", "baro", "mag", "gps", "motor_esc", "battery",
             "vibration")

    def __init__(self, t, fresh, armed=True):
        self.t, self.fresh, self.armed = t, fresh, armed
        self.trust = {n: 0.99 for n in self.NODES}
        self.edges = {}

    def top_causes(self, n=3):
        return [("nominal", 0.99)][:n]


def test_the_policy_row_separates_frozen_from_effective():
    """With supervision on, a reader must always be able to see what the
    FROZEN core decided, separately from what the overlay added."""
    runner = ShadowRunner(ShadowConfig(data_loss_supervision=True))
    dwell = FailsafeConfig().dwell_up

    runner.policy.update(_State(20.0, {"battery": True}))
    runner.policy.update(_State(21.0, {"battery": False}))
    runner.policy.update(_State(21.0 + dwell, {"battery": False}))

    row = runner._policy_row(_State(21.0 + dwell, {"battery": False}))
    assert row["frozen_level"] == "NORMAL"
    assert row["level"] == "CRITICAL"          # effective
    assert row["data_loss"]["level"] == "CRITICAL"
    assert "data_loss_battery" in row["data_loss"]["conditions"]


def test_a_nominal_tick_carries_no_data_loss_block():
    """A clean flight must not pay a dict on every tick, and must not look
    like it had a condition."""
    runner = ShadowRunner(ShadowConfig(data_loss_supervision=True))
    runner.policy.update(_State(20.0, {n: True for n in _State.NODES}))
    row = runner._policy_row(_State(20.0, {n: True for n in _State.NODES}))
    assert "data_loss" not in row
    assert row["frozen_level"] == "NORMAL"
    assert row["level"] == "NORMAL"


def test_the_default_policy_row_is_unchanged():
    """The off-by-default path must produce exactly the record it always
    did -- no new keys, so old and new logs stay comparable."""
    runner = ShadowRunner(ShadowConfig())
    runner.policy.update(_State(20.0, {n: True for n in _State.NODES}))
    row = runner._policy_row(_State(20.0, {n: True for n in _State.NODES}))
    assert set(row) == {"conditions", "dwell_since", "level"}


def test_supervision_never_lowers_the_level_in_the_runner():
    """The safety property, asserted through the runner rather than only on
    the class: whatever the frozen policy reached, the effective level is at
    least that."""
    runner = ShadowRunner(ShadowConfig(data_loss_supervision=True))
    for t in (20.0, 21.0, 25.0, 30.0):
        runner.policy.update(_State(t, {n: True for n in _State.NODES}))
        assert runner.policy.level >= runner.policy.frozen_level
    assert runner.policy.level == FailsafeLevel.NORMAL


def test_the_runner_still_refuses_command_authority_with_supervision_on():
    """Adding a rule must not add a way to act on it. CSIA is advisory."""
    runner = ShadowRunner(ShadowConfig(data_loss_supervision=True))
    assert runner.cfg.mode.may_command is False
    assert not hasattr(runner.policy, "send")
    assert not hasattr(runner.policy, "command")
