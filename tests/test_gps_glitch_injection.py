"""The GNSS-glitch injection: onset must not be delayed, ramps must stop.

Two defects motivated these tests, both found against a live simulator and
both invisible to every other check:

  ONSET DELAY. `run_gps_glitch` read its base parameter inside the injection
  timer callback. A robust read drains, requests and waits out ArduPilot's
  ack lag, so the actual write landed 2.487 s after the commanded 20.0 s onset
  in the completed campaign. That campaign stays valid -- its analysis counted
  from the recorded write time, not the commanded one -- but the defect is
  real: a ramp starts late, and on a window shorter than onset + ramp_s it
  runs off the end of the run.

  UNSTOPPABLE RAMP. Teardown called `Timer.cancel()`, which stops a timer that
  has not fired and does nothing at all once the callback is running. A 20 s
  ramp therefore kept writing parameters to the vehicle after the run had
  finished and nobody was measuring.

These tests drive the real functions with a recording fake connection, so they
exercise the actual write path rather than a description of it.
"""

import os
import sys
import threading
import time

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "deploy"))

from shadow_sitl_check import (                              # noqa: E402
    GPS_GLITCH, METRES_PER_DEG_LAT, prepare_gps_glitch, run_gps_glitch)


class FakeMav:
    def __init__(self, conn):
        self.conn = conn

    def param_set_send(self, sysid, compid, name, value, ptype):
        name = name.decode() if isinstance(name, bytes) else name
        self.conn.writes.append((time.time(), name, value))
        # A real vehicle acks the value it stored, and `confirm_param` polls
        # until it sees it. Echoing keeps the readback to one round trip
        # rather than a full timeout.
        self.conn.current = value
        self.conn.pending += 1

    def param_request_read_send(self, *a, **k):
        self.conn.pending += 1


class FakeConn:
    """Records every parameter write and echoes the stored value on read."""

    def __init__(self, base=0.0, read_delay=0.0):
        self.writes = []
        self.mav = FakeMav(self)
        self.target_system = 1
        self.target_component = 1
        self.current = base
        self.read_delay = read_delay
        self.pending = 0

    def recv_match(self, type=None, blocking=False, timeout=None):
        """Answer a request ONCE, then go quiet, like a real link.

        A fake that returns a PARAM_VALUE on every call never lets
        `read_param`'s settle window expire, so every read burns its full
        timeout. Real vehicles answer a request once; modelling that keeps
        these tests fast AND faithful.
        """
        if not blocking:
            return None
        if self.pending <= 0:
            if timeout:
                time.sleep(min(timeout, 0.02))
            return None
        if self.read_delay:
            time.sleep(self.read_delay)
        self.pending -= 1
        conn = self

        class M:
            param_id = GPS_GLITCH["ardupilot"][0]
            param_value = conn.current
        return M()


def _result():
    return {"injection": {}}


class TestOnsetIsNotDelayedByParameterReads:

    def test_prepare_does_the_reading(self):
        conn = FakeConn(base=1.5)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        assert plan["base"] == 1.5
        assert plan["param"] == "SIM_GPS1_GLTCH_X"
        assert plan["target_final"] == pytest.approx(
            1.5 + 50.0 / METRES_PER_DEG_LAT)
        # reading must not have written anything
        assert conn.writes == []

    def test_the_callback_writes_immediately_even_with_a_slow_link(self):
        """A 0.4 s-per-read link must not push the first write out.

        This is the regression: with reads inside the callback the first write
        landed seconds late. With them in `prepare`, the callback's first write
        must happen within a few milliseconds of entry regardless of link
        latency.
        """
        conn = FakeConn(base=0.0, read_delay=0.4)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        t_enter = time.time()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=0.0, at_s=20.0,
                       t_ref=t_enter, result=res, cancel=threading.Event())
        assert conn.writes, "no write was issued"
        first_write_delay = conn.writes[0][0] - t_enter
        assert first_write_delay < 0.05, (
            f"first write {first_write_delay:.3f} s after entry; base reads "
            f"have leaked back into the injection callback")

    def test_commanded_and_observed_times_are_recorded_separately(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 5.0)
        res = _result()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=0.0, at_s=20.0,
                       t_ref=time.time(), result=res)
        inj = res["injection"]
        assert inj["commanded_at_s"] == 20.0
        assert inj["wrote_at_rel_s"] is not None
        # they are different fields precisely so nobody has to assume they agree
        assert "commanded_at_s" in inj and "wrote_at_rel_s" in inj

    def test_a_missing_base_read_fails_loudly_rather_than_injecting_blind(self):
        conn = FakeConn()
        plan = dict(prepare_gps_glitch(conn, "ardupilot", 50.0), base=None,
                    target_final=None)
        res = _result()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=0.0, at_s=20.0,
                       t_ref=time.time(), result=res)
        assert res["injection"]["confirmed"] is False
        assert "could not read" in res["injection"]["error"]
        assert conn.writes == []


class TestRampCancellation:

    def test_A_ramp_completes_normally(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=0.4, at_s=0.0,
                       t_ref=time.time(), result=res,
                       cancel=threading.Event(), hz=10.0)
        assert res["injection"]["cancelled"] is False
        assert res["injection"]["writes"] == 4
        # the schedule must be monotone and end at the commanded magnitude
        metres = [w["metres"] for w in res["injection"]["schedule"]]
        assert metres == sorted(metres)
        assert metres[-1] == pytest.approx(50.0)

    def test_B_a_shortened_run_cancels_the_ramp_before_completion(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        cancel = threading.Event()
        th = threading.Thread(
            target=run_gps_glitch,
            args=(conn, "ardupilot", plan, 20.0, 0.0, time.time(), res),
            kwargs={"cancel": cancel, "hz": 10.0}, daemon=True)
        th.start()
        time.sleep(0.35)
        cancel.set()
        th.join(timeout=5.0)
        assert not th.is_alive(), "cancel did not stop the ramp"
        assert res["injection"]["cancelled"] is True
        # it stopped early: nowhere near the 200 writes a full 20 s ramp needs
        assert 0 < res["injection"]["writes"] < 200
        # and a cancelled injection is NOT reported as a confirmed one
        assert res["injection"]["confirmed"] is False
        assert "cancelled" in res["injection"]["error"]

    def test_C_no_parameter_writes_occur_after_cancellation(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        cancel = threading.Event()
        th = threading.Thread(
            target=run_gps_glitch,
            args=(conn, "ardupilot", plan, 20.0, 0.0, time.time(), res),
            kwargs={"cancel": cancel, "hz": 10.0}, daemon=True)
        th.start()
        time.sleep(0.35)
        cancel.set()
        t_cancel = time.time()
        th.join(timeout=5.0)
        assert not th.is_alive()
        after = [w for w in conn.writes if w[0] > t_cancel + 0.15]
        assert not after, (
            f"{len(after)} parameter writes landed more than 150 ms after "
            f"cancellation -- the vehicle was still being driven after "
            f"teardown")

    def test_cancellation_before_the_first_write_writes_nothing(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        cancel = threading.Event()
        cancel.set()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=2.0, at_s=0.0,
                       t_ref=time.time(), result=res, cancel=cancel, hz=10.0)
        assert conn.writes == []
        assert res["injection"]["cancelled"] is True

    def test_a_step_is_also_cancellable(self):
        conn = FakeConn(base=0.0)
        plan = prepare_gps_glitch(conn, "ardupilot", 50.0)
        res = _result()
        cancel = threading.Event()
        cancel.set()
        run_gps_glitch(conn, "ardupilot", plan, ramp_s=0.0, at_s=0.0,
                       t_ref=time.time(), result=res, cancel=cancel)
        assert conn.writes == []
        assert res["injection"]["cancelled"] is True
