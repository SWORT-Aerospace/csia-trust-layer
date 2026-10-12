"""Replay a MAVLink stream through the frozen core under one validity policy.

RESEARCH-ONLY. Nothing here modifies the frozen core, and the only class that
changes committed behaviour is `PropagateInvalidAdapter`, a subclass that exists
solely to provide the semantic control the brief asks for. `csia/` is untouched.

Three policies, one code path apart:

  DROP                   stock `ArduPilotAdapter`. An invalid fix deletes the
                         two gnss channels, so `to_core_samples` withholds the
                         gps sensor entirely. This is what the deployed v1.1
                         stack does today.
  PROPAGATE_INVALID_HOLD research-only. Same rejection, but a core sample IS
                         emitted carrying the LAST ACCEPTED pos/vel and
                         `valid=False`. Holding the last value rather than
                         substituting zeros is what makes this a ONE-FACTOR
                         control: the only thing that changes downstream is the
                         validity flag, not the numbers the filters see.
  PROPAGATE_INVALID_ZERO research-only reimplementation of what the committed
                         v1 live-MAVLink path already does
                         (`csia/runtime/plugins.py`, X1/X3 in the source
                         trace): emit zeros with `valid=False`. Included
                         because those zeros are NOT inert -- the step
                         detector and the Holt filters are fed before any
                         validity gate is consulted.

Observation, not instrumentation. `gvalid` is not exported by the frozen core,
so it is recomputed here from the live slot using the frozen expression
verbatim (online.py G1). The slot snapshot is taken immediately BEFORE each
`layer.ingest` call, which is exactly the state every tick that call emits will
see: `ingest` runs `_tick` in a loop and only then calls `_apply`.
"""

from __future__ import annotations

import bisect
import gzip
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from csia.aircraft.adapters.ardupilot import ArduPilotAdapter  # noqa: E402

TICK_HZ = 25.0
GPS_STALE_TIMEOUT_S = 0.5      # csia/runtime/online.py G5; asserted below
POLICIES = ("DROP", "PROPAGATE_INVALID_HOLD", "PROPAGATE_INVALID_ZERO")
TRACE_EDGE = "altitude_baro"


def make_adapter(policy, clock):
    if policy == "DROP":
        return ArduPilotAdapter(clock=clock)
    if policy not in POLICIES:
        raise ValueError(policy)
    return PropagateInvalidAdapter(
        payload="hold" if policy.endswith("HOLD") else "zero", clock=clock)


class PropagateInvalidAdapter(ArduPilotAdapter):
    """The semantic control: express OBSERVED_INVALID instead of dropping it.

    The stock adapter deletes the channels and reports NO_3D_FIX, which the
    core hand-off can only render as absence. This subclass keeps the deletion
    (so `status()` and the sentinel counters are unchanged) and ADDITIONALLY
    emits one core sample per rejected message carrying `valid=False`.

    One sample per REJECTED MESSAGE, not one per tick: the stock path emits one
    core sample per accepted message, and matching that cadence keeps emission
    rate out of the comparison.
    """

    def __init__(self, payload="hold", **kw):
        super().__init__(**kw)
        if payload not in ("hold", "zero"):
            raise ValueError(payload)
        self.payload = payload
        self._invalid_seq = 0
        self._invalid_emitted = 0
        self._last_accepted = None

    def _ingest_gps(self, g, t_src):
        fix = g("fix_type", 0)
        invalid = fix is None or fix < 3
        super()._ingest_gps(g, t_src)
        if invalid:
            self._invalid_seq += 1
            return
        p = self._latest.get("gnss.position")
        v = self._latest.get("gnss.velocity")
        if p is not None and v is not None:
            self._last_accepted = (np.array(p[0], float),
                                   np.array(v[0], float))

    def to_core_samples(self, s):
        out = super().to_core_samples(s)
        if any(x[0] == "gps" for x in out):
            return out
        if self._invalid_seq == self._invalid_emitted:
            return out
        if self.payload == "zero":
            pos, vel = np.zeros(3), np.zeros(3)
        elif self._last_accepted is None:
            # Nothing has ever been accepted, so there is no last value to
            # hold. Withhold rather than invent one: that is the honest
            # rendering of "never observed", and it is also what the stock
            # path does.
            return out
        else:
            pos, vel = self._last_accepted
        self._invalid_emitted = self._invalid_seq
        out.append(("gps", s.t_mono, {"pos": np.array(pos, float),
                                      "vel": np.array(vel, float),
                                      "vz_valid": False, "valid": False}))
        return out


# --------------------------------------------------------------- replay
def _gps_schedule(messages):
    """(times, fix_types) of every GPS_RAW_INT in receive order."""
    ts, fixes = [], []
    for m in messages:
        if m.get("mavpackettype") == "GPS_RAW_INT":
            ts.append(float(m["_t_recv"]))
            fixes.append(int(m.get("fix_type", 0) or 0))
    return ts, fixes


def replay(messages, policy):
    """Drive the frozen core from `messages` under one validity policy."""
    from csia.runtime.online import STALE_TIMEOUT_S, OnlineTrustLayer
    assert STALE_TIMEOUT_S["gps"] == GPS_STALE_TIMEOUT_S, (
        "the gps staleness timeout moved; this harness cites it as a constant")

    now = {"t": 0.0}
    adapter = make_adapter(policy, lambda: now["t"])
    layer = OnlineTrustLayer(tick_hz=TICK_HZ, field_mode=True)

    gps_t, gps_fix = _gps_schedule(messages)
    rows, next_tick, dt = [], 0.0, 1.0 / TICK_HZ

    for m in messages:
        t = float(m["_t_recv"])
        now["t"] = t
        adapter.ingest(m)
        while next_tick <= t:
            now["t"] = next_tick
            smp = adapter.sample(t_mono=next_tick)
            for sensor, ts, chans in adapter.to_core_samples(smp):
                slot = layer.slots["gps"]
                # frozen expression, online.py G1, evaluated on the live slot
                snap = (bool(slot.valid), bool(slot.seen), float(slot.last_t))
                for st in (layer.ingest(sensor, ts, chans) or []):
                    rows.append(_row(st, snap, gps_t, gps_fix))
            next_tick += dt

    return {"policy": policy, "n_ticks": len(rows), "rows": rows}


def _row(st, snap, gps_t, gps_fix):
    valid, seen, last_t = snap
    tau = float(st.t)
    gvalid = 1.0 if (valid and seen) else 0.0
    # last raw observation at or before this tick, and whether it was invalid
    i = bisect.bisect_right(gps_t, tau) - 1
    if i >= 0:
        last_fix, last_obs_t = gps_fix[i], gps_t[i]
        obs_invalid = 1 if last_fix < 3 else 0
    else:
        last_fix, last_obs_t, obs_invalid = -1, None, 0
    fresh_gps = 1.0 if st.fresh.get("gps") else 0.0
    edge = st.edges.get(TRACE_EDGE)
    post = getattr(st, "posterior", None) or {}
    top = max(post.items(), key=lambda kv: kv[1]) if post else (None, None)
    return {
        "t": round(tau, 6),
        "slot_valid": int(valid),
        "slot_seen": int(seen),
        "slot_last_t": round(last_t, 6) if last_t > -1e8 else None,
        "slot_age_s": (round(tau - last_t, 6) if last_t > -1e8 else None),
        "gvalid": gvalid,
        "fresh_gps": fresh_gps,
        f"gate_{TRACE_EDGE}": (None if edge is None else round(float(edge[1]), 6)),
        "last_raw_fix_type": last_fix,
        "last_raw_obs_t": (None if last_obs_t is None else round(last_obs_t, 6)),
        "raw_obs_invalid": obs_invalid,
        "trust_gps": round(float(st.trust.get("gps", float("nan"))), 6),
        "post_gps_fault": (round(float(post["gps_fault"]), 6)
                           if "gps_fault" in post else None),
        "post_nominal": (round(float(post["nominal"]), 6)
                         if "nominal" in post else None),
        "post_top_cause": top[0],
        "post_top_p": (None if top[1] is None else round(float(top[1]), 6)),
    }


# --------------------------------------------------------------- metrics
def summarise(out, t_from=0.0):
    """Masking metrics over ticks with t >= t_from."""
    rows = [r for r in out["rows"] if r["t"] >= t_from]
    invalid_rows = [r for r in rows if r["raw_obs_invalid"] == 1]
    masked = [r for r in invalid_rows if r["fresh_gps"] == 1.0]
    gvalid_masked = [r for r in invalid_rows if r["gvalid"] == 1.0]
    return {
        "policy": out["policy"],
        "n_ticks": len(rows),
        "n_ticks_last_obs_invalid": len(invalid_rows),
        "n_ticks_gvalid_zero": sum(1 for r in rows if r["gvalid"] == 0.0),
        "n_ticks_effective_gate_zero": sum(
            1 for r in rows if r["fresh_gps"] == 0.0),
        "n_masked_ticks": len(masked),
        "masking_fraction": (round(len(masked) / len(invalid_rows), 6)
                             if invalid_rows else None),
        "gvalid_masking_fraction": (
            round(len(gvalid_masked) / len(invalid_rows), 6)
            if invalid_rows else None),
        "min_trust_gps": (round(min(r["trust_gps"] for r in rows), 6)
                          if rows else None),
        "final_trust_gps": (rows[-1]["trust_gps"] if rows else None),
        "max_post_gps_fault": (
            round(max(r["post_gps_fault"] for r in rows
                      if r["post_gps_fault"] is not None), 6)
            if any(r["post_gps_fault"] is not None for r in rows) else None),
        "final_post_gps_fault": (rows[-1]["post_gps_fault"] if rows else None),
        "min_post_nominal": (
            round(min(r["post_nominal"] for r in rows
                      if r["post_nominal"] is not None), 6)
            if any(r["post_nominal"] is not None for r in rows) else None),
        "n_ticks_top_cause_gps_fault": sum(
            1 for r in rows if r["post_top_cause"] == "gps_fault"),
        # How stale was the observation the OPEN gate was vouching for? This
        # is the quantity masking actually moves: not whether GPS evidence is
        # counted, but how old the measurement behind it is allowed to be.
        "max_slot_age_with_open_gate_s": (
            round(max(r["slot_age_s"] for r in rows
                      if r["fresh_gps"] == 1.0 and r["slot_age_s"] is not None),
                  6)
            if any(r["fresh_gps"] == 1.0 and r["slot_age_s"] is not None
                   for r in rows) else None),
    }


# --------------------------------------------------------------- fixtures
def load_fixture(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def carrier_and_gps(messages):
    """Split a recording into non-GPS carrier and its GPS_RAW_INT messages."""
    carrier = [m for m in messages if m.get("mavpackettype") != "GPS_RAW_INT"]
    gps = [m for m in messages if m.get("mavpackettype") == "GPS_RAW_INT"]
    return carrier, gps


def synth_stream(carrier, template, schedule, hz=5.0, t0=0.0, t_end=None):
    """Real non-GPS telemetry + a PROGRAMMED GPS validity schedule.

    `template` is one genuinely valid GPS_RAW_INT from the recording; its
    payload is held constant and only `fix_type` and the timestamps vary. This
    fixture is for measuring the GATE, which the source trace shows depends on
    nothing but which samples are accepted and when (facts G1-G4). It is NOT
    suitable for trust or posterior numbers, and the sweep does not report any.

    `schedule(k, t)` -> True if the k-th GPS message is to be INVALID.
    """
    if t_end is None:
        t_end = max(float(m["_t_recv"]) for m in carrier)
    period = 1.0 / hz
    out = list(carrier)
    k = 0
    while True:
        # t0 + k*period, NOT an accumulator: accumulating 0.2 sixty times
        # lands at 11.999999999999995, which silently shifts a commanded
        # window by one message and makes the realised schedule disagree with
        # the commanded one.
        t = t0 + k * period
        if t > t_end:
            break
        m = dict(template)
        m["_t_recv"] = round(t, 6)
        m["time_usec"] = int(round(t * 1e6))
        if schedule(k, t):
            m["fix_type"] = 1
            m["satellites_visible"] = 0
            m["h_acc"] = 0
            m["eph"] = 65535
        out.append(m)
        k += 1
    out.sort(key=lambda m: float(m["_t_recv"]))
    return out
