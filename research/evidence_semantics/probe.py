"""Stage-indexed evidence-semantic probe over the three committed ingest paths.

WHAT THIS IS. The previous package compared ingest paths only at the END of
the pipeline: same word in, same downstream state out? That answers "do they
differ" and nothing else. This probe reads a canonical evidence token at
EVERY pipeline stage, so a difference can be located at the transformation
that produced it, and a LOSS can be located at the transformation that
destroyed it.

Nothing here is a model. Every token is read out of the real
`ArduPilotAdapter`, the real `map_mavlink`, the real `UlogSource._build_events`,
the real `OnlineTrustLayer` and the real `FailsafePolicy`.

STAGES (see CANONICAL_STATE_MODEL.md for the token alphabet):

  T1_protocol     what the wire says, with the receiver-side absence timeout
  T2_decode       what the decoder made of the last message
  T3_ingest       adapter retained state (`_latest` / `_sentinel_at`)
  T4_channel      the ChannelValue the adapter would serve
  T5_core_bridge  what crossed into the frozen core this tick
  T6_slot         the core's per-sensor slot (seen / valid / last_t)
  T7_admissible   `fresh[sensor]` -- the operational admissibility variable
  T8_evidence     the trust engine's evidence mass for the sensor
  T9_assurance    the FailsafePolicy level and issued actions

Paths B and C HAVE NO T3/T4. That is not a probe limitation, it is the
finding: they push decoder output straight at the core, so there is no stage
in them where a semantic state could be represented at all.

  python research/evidence_semantics/probe.py        # smoke test
"""

from __future__ import annotations

import os
import sys
import types

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

HZ = 5.0                  # message rate for the word under test
WARMUP_S = 12.0           # MUST exceed FailsafeConfig.arm_time (10.0 s):
                          # below it the policy returns [] and T9 measures
                          # nothing at all (csia/runtime/failsafe.py:199)
TAIL_S = 3.0              # > dwell_up (1.0 s) so a dwelled condition can
                          # actually escalate inside the observed window
TICK_HZ = 25.0
ABSENCE_TIMEOUT_FACTOR = 1.5   # ARINC 429 receiver convention: ~1.5x refresh

STAGES = ("T1_protocol", "T2_decode", "T3_ingest", "T4_channel",
          "T5_core_bridge", "T6_slot", "T7_admissible", "T8_evidence",
          "T9_assurance")

NA = "~"          # this path has no such stage
NONE_TOK = "-"    # stage exists, nothing to report yet

GPS_BASE = {"mavpackettype": "GPS_RAW_INT", "lat": 473977418, "lon": 85455938,
            "alt": 55000, "eph": 121, "epv": 200, "vel": 0, "cog": 0,
            "fix_type": 6, "satellites_visible": 12, "h_acc": 300,
            "v_acc": 400, "vel_acc": 100, "hdg_acc": 0,
            "alt_ellipsoid": 55000, "yaw": 0}
GPS_INVALID = {"fix_type": 1, "satellites_visible": 0, "h_acc": 0,
               "eph": 65535}

BAT_BASE = {"mavpackettype": "BATTERY_STATUS",
            "voltages": [12000] * 4 + [65535] * 6, "current_battery": 500,
            "time_boot_ms": 0, "id": 0, "battery_function": 0, "type": 0,
            "temperature": 32767, "current_consumed": 0, "energy_consumed": 0,
            "battery_remaining": 80, "time_remaining": 0, "charge_state": 1,
            "voltages_ext": [0] * 4, "mode": 0, "fault_bitmask": 0}
BAT_SENTINEL = {"current_battery": -1}     # MAVLink "not measured"

# SCALED_IMU carries the magnetometer. An all-zero triple is the source's
# own way of saying "no magnetometer": both committed MAVLink decoders test
# for it explicitly (ardupilot.py:143 `if any(mag)`, plugins.py:140).
MAG_BASE = {"mavpackettype": "SCALED_IMU", "time_boot_ms": 0,
            "xacc": 0, "yacc": 0, "zacc": 1000,
            "xgyro": 0, "ygyro": 0, "zgyro": 0,
            "xmag": 2000, "ymag": 500, "zmag": 4000}
MAG_ABSENT = {"xmag": 0, "ymag": 0, "zmag": 0}

FAMILIES = {
    # family -> (alphabet, core sensor, adapter channel, mavlink type)
    "gnss": ("VIN", "gps", "gnss.position", "GPS_RAW_INT"),
    "battery": ("VXN", "battery", "battery.current", "BATTERY_STATUS"),
    "mag": ("VZN", "mag", "mag.field_ut", "SCALED_IMU"),
}

# Message rate PER FAMILY. It is not cosmetic: the frozen core's watchdog is
# STALE_TIMEOUT_S = {'gps': 0.5, 'battery': 0.5, 'mag': 0.1}
# (csia/runtime/online.py:47-50). Driving the magnetometer at 5 Hz -- one
# message every 0.2 s against a 0.1 s watchdog -- leaves the channel stale
# between EVERY message, so admissibility is closed throughout and no
# downstream consequence of the word can be observed at all. The first mag
# run in this package did exactly that and is the reason this table exists.
FAMILY_HZ = {"gnss": 5.0, "battery": 5.0, "mag": 20.0}


def hz_for(family):
    return FAMILY_HZ.get(family, HZ)

# the core channel whose NUMERIC payload is compared at VALUE level
CORE_KEY = {"gnss": "pos", "battery": "current",
            "mag": "field_ut"}


# ----------------------------------------------------------------- streams
def stream(word, family, hz=None, warmup_s=WARMUP_S):
    """Warm-up of valid messages, then one message per symbol.

    `t = t0 + k * period` rather than an accumulator: a previous package lost
    a commanded window to floating-point drift at t=12.0.
    """
    hz = hz or hz_for(family)
    period = 1.0 / hz
    base = {"gnss": GPS_BASE, "battery": BAT_BASE, "mag": MAG_BASE}[family]
    msgs, k = [], 0
    n_warm = int(round(warmup_s * hz))
    for k in range(n_warm):
        m = dict(base)
        _stamp(m, k * period, family)
        msgs.append(m)
    for j, sym in enumerate(word):
        t = (n_warm + j) * period
        if sym == "N":
            continue
        m = dict(base)
        if sym == "I":
            m.update(GPS_INVALID)
        elif sym == "X":
            m.update(BAT_SENTINEL)
        elif sym == "Z":
            m.update(MAG_ABSENT)
        _stamp(m, t, family)
        msgs.append(m)
    t_end = (n_warm + len(word)) * period + TAIL_S
    return msgs, t_end


def _stamp(m, t, family):
    m["_t_recv"] = round(t, 6)
    if family == "gnss":
        m["time_usec"] = int(round(t * 1e6))
    else:
        m["time_boot_ms"] = int(round(t * 1e3))


def _sym_at(word, tau, family, hz=None, warmup_s=WARMUP_S):
    """The commanded symbol whose slot most recently opened at or before tau.

    Returns (symbol, slot_time). Warm-up slots are reported as 'V'.
    """
    hz = hz or hz_for(family)
    period = 1.0 / hz
    k = int(np.floor(tau / period + 1e-9))
    n_warm = int(round(warmup_s * hz))
    if k < n_warm:
        return "V", k * period
    j = k - n_warm
    if j >= len(word):
        return "END", k * period
    return word[j], k * period


# ------------------------------------------------------- T1: the wire
def t1_protocol(word, tau, family, hz=None, warmup_s=WARMUP_S):
    """What the wire says at tau, using a receiver-side absence timeout.

    Absence is NOT encoded in any message -- ARINC 429 has no SSM value for
    "no word arrived" either, and detects it with a refresh-rate timeout at
    ~1.5x the nominal period. The same convention is used here so that T1 is
    a statement about the wire and not about any CSIA implementation.
    """
    hz = hz or hz_for(family)
    period = 1.0 / hz
    limit = ABSENCE_TIMEOUT_FACTOR * period
    n_warm = int(round(warmup_s * hz))
    # scan back over slots for the most recent one that actually carried a
    # message
    k = int(np.floor(tau / period + 1e-9))
    while k >= 0:
        t_k = k * period
        if k < n_warm:
            sym = "V"
        else:
            j = k - n_warm
            sym = word[j] if j < len(word) else "END"
        if sym in ("V", "I", "X", "Z"):
            return (sym if tau - t_k <= limit else "N"), t_k
        k -= 1
    return "N", None


def _numeric(family, chans):
    """The numeric payload crossing into the core, rounded for comparison."""
    v = chans.get(CORE_KEY[family])
    if v is None:
        return None
    try:
        return tuple(round(float(x), 4) for x in np.atleast_1d(v))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------- path A: v1.1 adapter
def _mk_adapter(clock):
    from csia.aircraft.adapters.ardupilot import ArduPilotAdapter
    return ArduPilotAdapter(clock=clock)


def _t3_ingest(adapter, channel):
    """Adapter retained state, read directly out of the instance."""
    entry = adapter._latest.get(channel)
    sent = adapter._sentinel_at.get(channel)
    if entry is None:
        if sent is None:
            return "N"
        return {"NO_3D_FIX": "I", "SENTINEL": "X"}.get(sent[1].value, "X")
    if sent is not None and sent[0] >= entry[1]:
        # a value is held AND the producer has since disowned it: the state
        # the implementation has no token for
        return "R"
    return "V"


def _t4_channel(adapter, channel, now):
    from csia.aircraft.sample import MissingReason
    cv = adapter._channel_value(channel, now)
    if cv.usable:
        sent = adapter._sentinel_at.get(channel)
        entry = adapter._latest.get(channel)
        if sent is not None and entry is not None and sent[0] >= entry[1]:
            return "R", cv.value
        return "V", cv.value
    return {MissingReason.NOT_RECEIVED: "N", MissingReason.STALE: "S",
            MissingReason.NO_3D_FIX: "I", MissingReason.SENTINEL: "X",
            MissingReason.FIELD_ABSENT: "N",
            MissingReason.NOT_QUALIFIED: "?",
            MissingReason.STUB: "?"}[cv.missing], None


class _Recorder:
    """Runs the frozen core + failsafe and reads T6..T9 back out."""

    def __init__(self, sensor, tick_hz=TICK_HZ):
        from csia.runtime.failsafe import FailsafePolicy
        from csia.runtime.online import OnlineTrustLayer
        self.sensor = sensor
        self.layer = OnlineTrustLayer(tick_hz=tick_hz, field_mode=True)
        self.policy = FailsafePolicy()
        self.rows = {}          # tau -> dict of T6..T9 tokens

    def absorb(self, states):
        for st in states or []:
            actions = self.policy.update(st)
            slot = self.layer.slots[self.sensor]
            self.rows[round(st.t, 6)] = {
                "T6_slot": ("V" if slot.valid else "I") if slot.seen else "N",
                "T6_last_t": round(slot.last_t, 6) if slot.seen else None,
                "T7_admissible": "A" if st.fresh.get(self.sensor) else "0",
                "T8_evidence": round(float(st.evidence[self.sensor]), 4),
                "T8_trust": round(float(st.trust[self.sensor]), 4),
                "T9_assurance": self.policy.level.name,
                "T9_actions": tuple(sorted(a.name for a in actions)),
            }


def probe_a(word, family):
    """v1.1 ArduPilot adapter -> to_core_samples -> frozen core."""
    alphabet, sensor, channel, _ = FAMILIES[family]
    msgs, t_end = stream(word, family)
    now = {"t": 0.0}
    adapter = _mk_adapter(lambda: now["t"])
    rec = _Recorder(sensor)
    dt = 1.0 / TICK_HZ
    per_tick, k_tick = {}, [0]
    emitted = {}

    def drain(until):
        while k_tick[0] * dt <= until + 1e-12:
            tau = k_tick[0] * dt
            now["t"] = tau
            smp = adapter.sample(t_mono=tau)
            samples = adapter.to_core_samples(smp)
            mine = [s for s in samples if s[0] == sensor]
            emitted[round(tau, 6)] = (
                "V" if mine and mine[0][2].get("valid") else
                ("I" if mine else NONE_TOK))
            t4_tok, t4_val = _t4_channel(adapter, channel, tau)
            per_tick[round(tau, 6)] = {
                "T3_ingest": _t3_ingest(adapter, channel),
                "T4_channel": t4_tok,
                "T5_core_bridge": emitted[round(tau, 6)],
                "T5_value": (_numeric(family, mine[0][2]) if mine else None),
                "T4_value": (None if t4_val is None else
                             tuple(round(float(x), 4)
                                   for x in np.atleast_1d(t4_val))),
            }
            for s in samples:
                rec.absorb(rec.layer.ingest(*s))
            k_tick[0] += 1

    for m in msgs:
        t = float(m["_t_recv"])
        drain(t - 1e-9)
        now["t"] = t
        adapter.ingest(m)
    drain(t_end)
    rec.absorb(rec.layer.flush(t_end))
    return _merge(word, family, per_tick, rec, has_t34=True)


# ------------------------------------------------- path B: plugins.py
def probe_b(word, family):
    """csia/runtime/plugins.py:map_mavlink -> frozen core (no adapter)."""
    from csia.runtime.plugins import map_mavlink
    alphabet, sensor, _channel, _ = FAMILIES[family]
    msgs, t_end = stream(word, family)
    rec = _Recorder(sensor)
    dt = 1.0 / TICK_HZ
    per_tick = {}
    ctx = {}
    k_tick = [0]

    def drain(until):
        """Open every tick slot up to `until`. `setdefault`, never assign: an
        emission recorded against a slot must not be erased when the grid
        later walks over it."""
        while k_tick[0] * dt <= until + 1e-12:
            per_tick.setdefault(round(k_tick[0] * dt, 6), {
                "T3_ingest": NA, "T4_channel": NA,
                "T5_core_bridge": NONE_TOK})
            k_tick[0] += 1

    for m in msgs:
        t = float(m["_t_recv"])
        drain(t - 1e-9)
        obj = types.SimpleNamespace(**m)
        obj.get_type = lambda k=m["mavpackettype"]: k
        for s_name, _t, chans in map_mavlink(obj, ctx):
            if s_name != sensor:
                # still fed to the core: withholding a sensor the message
                # really produced would change the core's state and make the
                # comparison meaningless
                rec.absorb(rec.layer.ingest(s_name, t, chans))
                continue
            tok = _plugin_token(family, chans)
            val = _numeric(family, chans)
            # the core is fed at the MESSAGE time; the emission is recorded
            # against the next tick boundary so the two paths line up on the
            # same grid
            slot_tau = round(np.ceil(t / dt - 1e-9) * dt, 6)
            per_tick.setdefault(slot_tau, {"T3_ingest": NA, "T4_channel": NA,
                                           "T5_core_bridge": NONE_TOK})
            per_tick[slot_tau]["T5_core_bridge"] = tok
            per_tick[slot_tau]["T5_value"] = val
            rec.absorb(rec.layer.ingest(s_name, t, chans))
    drain(t_end)
    rec.absorb(rec.layer.flush(t_end))
    return _merge(word, family, per_tick, rec, has_t34=False)


def _plugin_token(family, chans):
    """What plugins.py actually handed the core, value provenance included."""
    if not chans.get("valid", True):
        return "I"
    if family == "battery":
        # `max(msg.current_battery, 0) / 100.0` turns the documented
        # not-measured sentinel into a real-looking 0.00 A reading
        if float(chans.get("current", -1.0)) == 0.0:
            return "M"
    return "V"


# ------------------------------------------------ path C: ulog_source.py
def probe_c_events(word, family, hz=None, warmup_s=WARMUP_S):
    """Drive the committed `UlogSource._build_events` over the same alphabet.

    `__init__` needs a real .ulg, so the instance is built without it and
    `_topic` is replaced by synthetic uORB arrays. The BODY of
    `_build_events` -- the part that decides what `valid` means -- is the
    committed one, unmodified. This is the same treatment paths A and B get:
    real code, synthetic input.
    """
    from csia.runtime.ulog_source import UlogSource

    hz = hz or hz_for(family)
    period = 1.0 / hz
    n_warm = int(round(warmup_s * hz))
    t_slots, fixes, currents, mags = [], [], [], []
    for k in range(n_warm):
        t_slots.append(k * period)
        fixes.append(6)
        currents.append(5.0)
        mags.append((0.20, 0.05, 0.40))
    for j, sym in enumerate(word):
        if sym == "N":
            continue
        t_slots.append((n_warm + j) * period)
        fixes.append(1 if sym == "I" else 6)
        # -1.0 A is not invented: the committed 9.6 MB PX4 log carries
        # current_a == -1.0 on ALL 216 battery_status samples (see
        # px4_probe.py / PX4_FEASIBILITY.json). ulog_source.py:196-199 has no
        # branch that could read it as a sentinel and emits valid=True
        # unconditionally, so the frozen core is fed -1.0 A as a usable
        # battery current on real flight data.
        currents.append(-1.0 if sym == "X" else 5.0)
        mags.append((0.0, 0.0, 0.0) if sym == "Z" else (0.20, 0.05, 0.40))

    # sensor_combined at 50 Hz supplies t0 and satisfies the rate screen
    t_end = (n_warm + len(word)) * period + TAIL_S
    n_sc = int(round(t_end * 50.0)) + 1
    sc_t = (np.arange(n_sc) / 50.0 * 1e6).astype(np.int64)
    sc = {"timestamp": sc_t}
    for i, v in enumerate((0.0, 0.0, -9.80665)):
        sc[f"accelerometer_m_s2[{i}]"] = np.full(n_sc, v)
    for i in range(3):
        sc[f"gyro_rad[{i}]"] = np.zeros(n_sc)

    us = np.asarray([int(round(t * 1e6)) for t in t_slots], dtype=np.int64)
    gps = {"timestamp": us,
           "latitude_deg": np.full(len(us), 47.3977418),
           "longitude_deg": np.full(len(us), 8.5455938),
           "altitude_msl_m": np.full(len(us), 550.0),
           "fix_type": np.asarray(fixes, dtype=int),
           "vel_n_m_s": np.zeros(len(us)), "vel_e_m_s": np.zeros(len(us)),
           "vel_d_m_s": np.zeros(len(us))}
    bat = {"timestamp": us, "voltage_v": np.full(len(us), 12.0),
           "current_a": np.asarray(currents, dtype=float)}
    mg = {"timestamp": us}
    for i in range(3):
        mg[f"magnetometer_ga[{i}]"] = np.asarray([m[i] for m in mags],
                                                 dtype=float)

    # Only the family under test gets its topic. Feeding all three would let
    # one family's word drive another family's channel.
    topics = {"sensor_combined": sc}
    topics.update({"gnss": {"vehicle_gps_position": gps},
                   "battery": {"battery_status": bat},
                   "mag": {"vehicle_magnetometer": mg}}[family])

    src = object.__new__(UlogSource)
    src.path = "<synthetic uORB arrays>"
    src.include_esc = False
    src.duration = 0.0
    # `_build_events` binds `u = self.ulog` and then never uses it (every
    # topic goes through `self._topic`), so None is sufficient and nothing
    # about the decode is bypassed.
    src.ulog = None
    src._topic = lambda name, instance=0: (
        types.SimpleNamespace(data=topics[name])
        if name in topics and instance == 0 else None)
    return src._build_events()


def probe_c(word, family):
    _alphabet, sensor, _channel, _ = FAMILIES[family]
    _msgs, t_end = stream(word, family)
    ev = list(probe_c_events(word, family))
    rec = _Recorder(sensor)
    dt = 1.0 / TICK_HZ
    per_tick, k_tick = {}, [0]

    def drain(until):
        while k_tick[0] * dt <= until + 1e-12:
            per_tick.setdefault(round(k_tick[0] * dt, 6), {
                "T3_ingest": NA, "T4_channel": NA,
                "T5_core_bridge": NONE_TOK})
            k_tick[0] += 1

    for t, name, chans in ev:
        drain(t - 1e-9)
        if name != sensor:
            rec.absorb(rec.layer.ingest(name, t, chans))
            continue
        tok = "V" if chans.get("valid", True) else "I"
        slot_tau = round(np.ceil(t / dt - 1e-9) * dt, 6)
        per_tick.setdefault(slot_tau, {"T3_ingest": NA, "T4_channel": NA,
                                       "T5_core_bridge": NONE_TOK})
        per_tick[slot_tau]["T5_core_bridge"] = tok
        per_tick[slot_tau]["T5_value"] = _numeric(family, chans)
        rec.absorb(rec.layer.ingest(name, t, chans))
    drain(t_end)
    rec.absorb(rec.layer.flush(t_end))
    return _merge(word, family, per_tick, rec, has_t34=False)


# ------------------------------------------------------------------ merge
def _merge(word, family, per_tick, rec, has_t34):
    """One row per tick, every stage token side by side."""
    taus = sorted(set(per_tick) | set(rec.rows))
    rows = []
    for tau in taus:
        if tau < WARMUP_S:            # only the word's own consequences
            continue
        p = per_tick.get(tau, {})
        r = rec.rows.get(tau, {})
        t1, _slot_t = t1_protocol(word, tau, family)
        rows.append({
            "t": round(tau, 6),
            "T1_protocol": t1,
            "T2_decode": _t2_decode(word, tau, family),
            "T3_ingest": p.get("T3_ingest", NONE_TOK if has_t34 else NA),
            "T4_channel": p.get("T4_channel", NONE_TOK if has_t34 else NA),
            "T4_value": p.get("T4_value"),
            "T5_core_bridge": p.get("T5_core_bridge", NONE_TOK),
            "T5_value": p.get("T5_value"),
            "T6_slot": r.get("T6_slot", NONE_TOK),
            "T7_admissible": r.get("T7_admissible", NONE_TOK),
            "T8_evidence": r.get("T8_evidence"),
            "T8_trust": r.get("T8_trust"),
            "T9_assurance": r.get("T9_assurance", NONE_TOK),
            "T9_actions": r.get("T9_actions", ()),
        })
    return rows


def _t2_decode(word, tau, family):
    """The decoder is memoryless per message: its output for the last
    message inside the absence window is the message's own content."""
    return t1_protocol(word, tau, family)[0]


PATHS = {"v1_1_adapter": probe_a, "plugins_py": probe_b,
         "ulog_source_py": probe_c}


def stage_trace(rows, stage):
    """Project a run onto one stage. Evidence/trust are rounded scalars."""
    return tuple(r[stage] for r in rows)


def words(alphabet, max_len):
    import itertools
    for n in range(1, max_len + 1):
        for w in itertools.product(alphabet, repeat=n):
            yield "".join(w)


if __name__ == "__main__":
    for fam in ("gnss", "battery"):
        alpha = FAMILIES[fam][0]
        bad = alpha[1]
        print(f"\n=== {fam}  (alphabet {alpha}) ===")
        for path, fn in PATHS.items():
            rows = fn(bad, fam)
            head = rows[:3]
            print(f"  {path:<16} n={len(rows):4d}  "
                  f"first rows: " + " | ".join(
                      "".join(str(r[s])[:1] for s in
                              ("T1_protocol", "T2_decode", "T3_ingest",
                               "T4_channel", "T5_core_bridge", "T6_slot",
                               "T7_admissible")) for r in head))
