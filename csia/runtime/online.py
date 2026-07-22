"""Online (real-time) trust layer: sample-in, trust-out.

Incremental mirror of the batch pipeline. Every filter here is the same
recursion the batch path applies vectorized (EW smoothing, Holt, the
complementary attitude filter, backward differences, the Beta trust update)
with the same constants imported from the same modules — and
``tests/test_runtime.py`` pins online-vs-batch trust trajectories together.

Usage:
    layer = OnlineTrustLayer()
    for sensor, t, channels in source.samples():
        for state in layer.ingest(sensor, t, channels):
            ...  # one TrustState per 25 Hz tick

Sample channel contract (numpy-compatible scalars/arrays):
    imu0/imu1: accel(3), gyro(3), valid
    baro:      altitude, temp_c, valid
    mag:       field_ut(3), valid
    gps:       pos(3), vel(3), valid
    motor_esc: rpm(4), current(4), valid
    battery:   voltage, current, valid
    vibration: rms, valid            (10 Hz RMS envelope channel)
"""

import time
from dataclasses import dataclass, field

import numpy as np

from ..diagnosis.bayes import TEMP_FEATURES, DiagnosisCore
from ..prediction.attitude import mag_heading_from_field, wrap_angle
from ..prediction.comparator import GATE_SPEED_HI, GATE_SPEED_LO
from ..prediction.predictors import HIST_CHANNELS
from ..sensors.truth import (AVIONICS_CURRENT, G, HOVER_CURRENT_PER_MOTOR,
                             HOVER_RPM, MASS, PACK_R_INTERNAL)
from ..trust_engine.engine import EngineConfig, TrustCore
from ..trust_graph.graph import EDGES

HOVER_THRUST_PER_MOTOR = MASS * G / 4.0
SENSORS = ("imu0", "imu1", "baro", "mag", "gps",
           "motor_esc", "battery", "vibration")

# Watchdog: a sensor that stops PRODUCING samples is as failed as one that
# produces bad ones — without this, the last value would be held forever and
# every consistency check would keep passing on stale data. Timeout is ~5x
# the sensor's nominal period.
STALE_TIMEOUT_S = {
    "imu0": 0.05, "imu1": 0.05, "baro": 0.1, "mag": 0.1, "gps": 0.5,
    "motor_esc": 0.1, "battery": 0.5, "vibration": 0.5,
}


# --- incremental primitives (same recursions as csia.prediction) -------------

class _EW:
    """Exponentially weighted smoother; matches predictors.ew_smooth."""

    def __init__(self, alpha):
        self.a = alpha
        self.y = None

    def update(self, x):
        x = np.asarray(x, dtype=float)
        if self.y is None:
            self.y = x.copy()
        self.y = (1.0 - self.a) * self.y + self.a * x
        return self.y


class _Holt:
    """One-step-ahead Holt forecast; matches predictors.holt_prediction."""

    def __init__(self, alpha=0.3, beta=0.05):
        self.a, self.b = alpha, beta
        self.level = None
        self.trend = 0.0

    def innovation(self, x):
        if self.level is None:
            self.level = float(x)
        pred = self.level + self.trend
        err = float(x) - pred
        self.level = pred + self.a * err
        self.trend = self.trend + self.a * self.b * err
        return err


class _AttFilter:
    """Complementary attitude filter; matches attitude.complementary_attitude."""

    K_TILT = 0.01

    def __init__(self):
        self.rp = np.zeros(2)
        self.yaw = 0.0
        self.prev_t = None

    def update(self, t, accel, gyro):
        dt = 0.0 if self.prev_t is None else t - self.prev_t
        self.prev_t = t
        self.rp = self.rp + gyro[:2] * dt
        self.yaw = self.yaw + gyro[2] * dt
        fmag = float(np.linalg.norm(accel))
        if abs(fmag - G) < 0.4 and np.linalg.norm(gyro) < 0.05:
            roll_acc = np.arctan2(accel[1], accel[2])
            pitch_acc = -np.arcsin(np.clip(accel[0] / fmag, -1.0, 1.0))
            self.rp = ((1.0 - self.K_TILT) * self.rp
                       + self.K_TILT * np.array([roll_acc, pitch_acc]))
        return np.array([self.rp[0], self.rp[1], self.yaw])


@dataclass
class TrustState:
    """One engine tick of the real-time trust layer."""
    t: float
    trust: dict            # sensor -> Trust Coefficient
    evidence: dict         # sensor -> fused evidence
    components: dict       # sensor -> {nbr, phys, temp, stat} (None if absent)
    posterior: dict        # cause -> probability
    fresh: dict            # sensor -> bool (valid AND recent data at this tick)
    armed: bool | None = None   # vehicle armed flag (None: source never said)
    edges: dict = field(default_factory=dict)  # edge key -> (consistency, gate)
    latency_us: float = 0.0

    def top_causes(self, n: int = 3):
        return sorted(self.posterior.items(), key=lambda kv: -kv[1])[:n]


@dataclass
class _SensorSlot:
    latest: dict = field(default_factory=dict)
    valid: bool = False
    seen: bool = False
    last_t: float = -1e9
    holt: dict = field(default_factory=dict)      # channel key -> _Holt
    lam_hist: _EW = field(default_factory=lambda: _EW(0.15))
    var_ratio: _EW = field(default_factory=lambda: _EW(0.05))
    hist_val: float = 0.0
    vr_val: float = 0.0
    base_buf: list = field(default_factory=list)
    scale: float = 1.0
    adapt_level: float = 0.0
    adapt_t: float = -1.0


class OnlineTrustLayer:
    """Real-time CSIA trust layer. Feed samples in timestamp order."""

    def __init__(self, tick_hz: float = 25.0,
                 config: EngineConfig | None = None,
                 t_calibrate: float = 2.0,
                 profile=None,
                 mag_ref_ut: float | None = float(np.hypot(22.0, 42.0)),
                 auto_baseline_s: float | None = None,
                 stale_timeout_s: dict | None = None,
                 mag_yaw_gain: float = 0.0,
                 field_mode: bool = False):
        # captured before profile mutates locals, so reset() can rebuild the
        # layer identically after a source time discontinuity (FC reboot)
        self._init_args = (tick_hz, config, t_calibrate, profile, mag_ref_ut,
                           auto_baseline_s, stale_timeout_s, mag_yaw_gain,
                           field_mode)
        # field_mode: the real-world tolerance package, ON for live vehicles
        # and log replay, OFF (default) for the simulator (where sigmas are
        # exact and bit-equivalence with the batch path is tested):
        #   * adaptive residual normalization (tau ~ 90 s running level,
        #     floored at 1) — each airframe/regime sets its own noise floor,
        #     the way adaptive innovation gating works in production EKFs;
        #     fast anomalies still spike through, slow ones are absorbed
        #     over ~tau (detection latency measured in seconds, unaffected)
        #   * time-skew tolerant dual-IMU comparison (short smoothers before
        #     differencing; log/live IMU timestamps are not synchronized)
        #   * mag-aided yaw (drift immunity) + self-calibrated |B| reference
        # auto_baseline_s: length of the self-calibration window. Real
        # installations have their own noise floors (vibration coupling,
        # IMU mounting, mag interference) — the commissioning procedure in
        # docs/HARDWARE.md, automated: raw residuals are collected for this
        # window, each check's sigma is scaled by max(1, median(lambda)),
        # and detection then means "beyond THIS airframe's own baseline".
        # None (default) = fixed simulation sigmas (bit-equivalent to batch).
        # stale_timeout_s: per-sensor watchdog overrides (log topics are
        # often recorded at 1-2 Hz even when the sensor runs at 100 Hz).
        # mag_yaw_gain: slow magnetometer yaw correction for the attitude
        # filter (drift-immunity on long flights; 0 keeps gyro-only yaw).
        # mag_ref_ut: expected local field magnitude. None -> self-calibrate
        # from the median of the first samples (real-world logs: Earth's
        # field is 25-65 uT depending on location; a fixed reference would
        # false-alarm everywhere except the simulator's mid-latitude site).
        if profile is not None:
            if tuple(profile.sensors) != SENSORS:
                raise ValueError(
                    f"profile {profile.name!r} sensor set does not match the "
                    "SOW001 quad edge library — new platforms need their own "
                    "edge module (see csia/profiles.py extension contract)")
            tick_hz = profile.tick_hz
            config = config or profile.engine
        self.dt_tick = 1.0 / tick_hz
        self.next_tick = 0.0
        self.t_cal = t_calibrate
        self.slots = {n: _SensorSlot() for n in SENSORS}
        self.core = TrustCore(SENSORS, config)
        self.diag = DiagnosisCore()
        self._edge_meta = {}
        for a, b, relation, _ in EDGES:
            self._edge_meta.setdefault(relation, (a, b))
        # dual doppler edges are keyed separately in the comparator
        self._edge_meta["velocity_gps_doppler_0"] = ("imu0", "gps")
        self._edge_meta["velocity_gps_doppler_1"] = ("imu1", "gps")
        self._edge_meta.pop("velocity_gps_doppler", None)

        # IMU ground calibration: buffer, then replay through the filter —
        # same pre-arm practice the batch path models retroactively.
        self._imu_buf = {"imu0": [], "imu1": []}
        self._imu_bias = {}   # name -> (accel_bias, gyro_bias)
        self._att = {"imu0": _AttFilter(), "imu1": _AttFilter()}
        self._att_val = {"imu0": np.zeros(3), "imu1": np.zeros(3)}

        # native-rate derivative memories
        self._gps_prev = None          # (t, pos, vel)
        self._gps_fd_vel = np.zeros(3)
        self._gps_fd_dvel = np.zeros(3)
        self._gps_step_peak = 0.0      # peak |fd - vel| since last decay
        self._mag_heading = 0.0

        # tick-rate smoother states (match comparator's tick-level EWs)
        self._lam = {}                          # edge/phys key -> _EW(0.15)
        self._fw_s = {n: _EW(0.1) for n in ("imu0", "imu1")}
        self._dvel_s = _EW(0.1)
        self._rgps_s = _EW(0.1)
        self._ocv = _EW(0.01)
        self._alt_s = _EW(0.1)
        self._temp_s = _EW(0.05)
        self._alt_s_prev = None
        self._temp_s_prev = None
        self._mag_ref = mag_ref_ut
        self._mag_cal_buf = []
        self._bad_samples = 0   # non-finite/malformed samples rejected
        self._stale = dict(STALE_TIMEOUT_S)
        if stale_timeout_s:
            self._stale.update(stale_timeout_s)
        self._baseline_s = auto_baseline_s
        self._base_buf = {}          # check key -> raw lambda list
        self._scale = {}             # check key -> sigma^2 scale (>=1)
        self._mag_yaw_gain = mag_yaw_gain
        self._field = field_mode
        if field_mode:
            self._mag_ref = None
            self._mag_yaw_gain = max(self._mag_yaw_gain, 0.005)
        self._adapt = {}             # check key -> slow-level _EW
        self._acc_s = {n: _EW(0.06) for n in ("imu0", "imu1")}  # ~0.7 s
        # Vehicle armed state (from HEARTBEAT / vehicle_status). None means
        # the source never reported it -> fall back to the simulator's
        # scripted t>5s arming proxy. False gates the motor edges OFF (idle
        # rotors explain no lift; on the ground these checks would read
        # gravity as a thrust mismatch) and holds the failsafe.
        self._armed: bool | None = None
        self._armed_since: float | None = None

    def reset(self):
        """Full state reset after a source time discontinuity (FC reboot,
        looped replay): filters, biases, calibration, and the tick counter
        all restart from zero. Trust re-converges from the prior."""
        OnlineTrustLayer.__init__(self, *self._init_args)

    # --- ingest ---------------------------------------------------------------

    def ingest(self, sensor: str, t: float, channels: dict) -> list:
        """Apply one sample; returns TrustStates for any ticks that fired.
        Ticks fire strictly before the first sample with a later timestamp,
        matching the batch sample-and-hold alignment exactly."""
        if sensor == "vehicle_status":
            # vehicle state channel (armed flag) — not a trust node; gates
            # the motor edges and the failsafe. Ticks fire first, exactly as
            # for a sensor sample, so tick timing is source-order invariant.
            states = []
            while self.next_tick < t - 1e-12:
                states.append(self._tick(self.next_tick))
                self.next_tick += self.dt_tick
            armed = bool(channels.get("armed", False))
            if armed and self._armed is not True:
                self._armed_since = t
            self._armed = armed
            return states
        if sensor not in self.slots:
            raise ValueError(f"unknown sensor {sensor!r}")
        for key, val in channels.items():
            if key != "valid" and not np.all(np.isfinite(
                    np.asarray(val, dtype=float))):
                # malformed telemetry must never enter the filters — count
                # it and drop the sample (absence, not poisoned evidence)
                self._bad_samples += 1
                return []
        states = []
        while self.next_tick < t - 1e-12:
            states.append(self._tick(self.next_tick))
            self.next_tick += self.dt_tick
        self._apply(sensor, t, channels)
        return states

    def flush(self, t_end: float) -> list:
        states = []
        while self.next_tick <= t_end + 1e-12:
            states.append(self._tick(self.next_tick))
            self.next_tick += self.dt_tick
        return states

    def _apply(self, sensor: str, t: float, ch: dict):
        slot = self.slots[sensor]
        slot.seen = True
        slot.last_t = t
        slot.valid = bool(ch.get("valid", True))

        if sensor in ("imu0", "imu1"):
            accel = np.asarray(ch["accel"], dtype=float)
            gyro = np.asarray(ch["gyro"], dtype=float)
            if sensor not in self._imu_bias:
                self._imu_buf[sensor].append((t, accel, gyro))
                if t >= self.t_cal:
                    # Bias can only be estimated from GROUND (pre-t_cal)
                    # samples. A topic that starts logging mid-flight has no
                    # ground window — calibrating from in-flight samples
                    # would subtract flight acceleration as "bias" and
                    # poison every downstream check. Zero bias instead.
                    buf = self._imu_buf[sensor]
                    ground = [(tb, ab, gb) for tb, ab, gb in buf
                              if tb < self.t_cal]
                    if ground:
                        acc_b = (np.mean([a for _, a, _ in ground], axis=0)
                                 - np.array([0.0, 0.0, G]))
                        gyr_b = np.mean([g for _, _, g in ground], axis=0)
                    else:
                        acc_b = np.zeros(3)
                        gyr_b = np.zeros(3)
                    self._imu_bias[sensor] = (acc_b, gyr_b)
                    for tb, ab, gb in buf:  # replay calibrated history
                        self._att_val[sensor] = self._att[sensor].update(
                            tb, ab - acc_b, gb - gyr_b)
                    self._imu_buf[sensor] = []
                # pre-calibration: hold raw values (warm-up window)
                slot.latest["accel"], slot.latest["gyro"] = accel, gyro
            if sensor in self._imu_bias:
                acc_b, gyr_b = self._imu_bias[sensor]
                accel, gyro = accel - acc_b, gyro - gyr_b
                slot.latest["accel"], slot.latest["gyro"] = accel, gyro
                self._att_val[sensor] = self._att[sensor].update(t, accel, gyro)
                if self._mag_yaw_gain > 0.0 and self.slots["mag"].seen:
                    f = self._att[sensor]
                    err = float(wrap_angle(np.array(
                        [self._mag_heading - f.yaw]))[0])
                    f.yaw += self._mag_yaw_gain * err
                    self._att_val[sensor][2] = f.yaw
        elif sensor == "gps":
            pos = np.asarray(ch["pos"], dtype=float)
            vel = np.asarray(ch["vel"], dtype=float)
            vz_ok = bool(ch.get("vz_valid", True))
            if self._gps_prev is not None:
                pt, ppos, pvel = self._gps_prev
                dt = max(t - pt, 1e-6)
                self._gps_fd_vel = (pos - ppos) / dt
                self._gps_fd_dvel = (vel - pvel) / dt
                # step detector: position must not jump beyond what the
                # reported velocity can explain (spoof/glitch step signature)
                dstep = self._gps_fd_vel - vel
                if not vz_ok:   # no real vz reported: judge horizontal only
                    dstep = np.array([dstep[0], dstep[1], 0.0])
                self._gps_step_peak = max(self._gps_step_peak,
                                          float(np.linalg.norm(dstep)))
            self._gps_prev = (t, pos, vel)
            slot.latest["pos"], slot.latest["vel"] = pos, vel
            slot.latest["vz_ok"] = vz_ok
        elif sensor == "mag":
            field_ut = np.asarray(ch["field_ut"], dtype=float)
            slot.latest["field_ut"] = field_ut
            if self._mag_ref is None:
                self._mag_cal_buf.append(float(np.linalg.norm(field_ut)))
                if t >= self.t_cal and len(self._mag_cal_buf) >= 10:
                    self._mag_ref = float(np.median(self._mag_cal_buf))
                    self._mag_cal_buf = []
            self._mag_heading = float(mag_heading_from_field(
                field_ut[None, :], self._att_val["imu0"][None, :])[0])
        else:
            for key, val in ch.items():
                if key != "valid":
                    slot.latest[key] = np.asarray(val, dtype=float) \
                        if np.ndim(val) else float(val)

        # historical predictor (native rate, raw channels — Holt tracks level,
        # so IMU turn-on bias does not matter here; matches the batch path)
        chans = HIST_CHANNELS.get(sensor, [])
        lams = []
        for key, col, sigma in chans:
            if key not in ch:
                continue
            x = ch[key] if col is None else np.asarray(ch[key])[col]
            h = slot.holt.setdefault((key, col), _Holt())
            lams.append((h.innovation(float(x)) / sigma) ** 2)
        if lams:
            lam = float(np.mean(lams))
            if self._field:
                # time-correct adaptive level: sensors log at wildly
                # different rates (vehicle_imu at 2 Hz in some logs) — a
                # per-sample alpha would make the 90 s time constant depend
                # on sample rate, so compute it from actual elapsed time
                if slot.adapt_t < 0:
                    slot.adapt_level = lam
                else:
                    a = 1.0 - np.exp(-(t - slot.adapt_t) / 90.0)
                    slot.adapt_level += a * (lam - slot.adapt_level)
                slot.adapt_t = t
                lam = lam / (max(1.0, slot.adapt_level) * 3.0)
            elif self._baseline_s is not None:
                if not self._base_done:
                    slot.base_buf.append(lam)
                else:
                    lam = lam / slot.scale
            slot.hist_val = float(slot.lam_hist.update(lam))
            slot.vr_val = float(slot.var_ratio.update(lam))

    # --- tick -----------------------------------------------------------------

    def _lam_upd(self, key, resid, sigma, df=1.0):
        raw = (float(resid) / sigma) ** 2 / df
        if self._field:
            # normalize by the running level, then tolerate chi-square tail
            # scatter: a chi^2_1 ratio has p95 ~ 3.8, so only >3x excursions
            # beyond this airframe's own floor count as inconsistency
            # (faults sit 10-100x above the level; detection unaffected)
            level = self._adapt.setdefault(key, _EW(4.4e-4))  # tau ~ 90 s
            raw = raw / (max(1.0, float(level.update(raw))) * 3.0)
        elif self._baseline_s is not None:
            if not self._base_done:
                self._base_buf.setdefault(key, []).append(raw)
            else:
                raw = raw / self._scale.get(key, 1.0)
        ew = self._lam.setdefault(key, _EW(0.15))
        return float(ew.update(raw))

    @property
    def _base_done(self):
        return self._baseline_s is None or bool(self._scale)

    def _finish_baseline(self):
        for key, buf in self._base_buf.items():
            self._scale[key] = max(1.0, float(np.median(buf)))
        for n, slot in self.slots.items():
            if slot.base_buf:
                slot.scale = max(1.0, float(np.median(slot.base_buf)))
                slot.base_buf = []
        self._base_buf = {}
        self._lam = {}               # restart smoothers on the scaled floor
        for slot in self.slots.values():
            slot.lam_hist = _EW(0.15)
            slot.var_ratio = _EW(0.05)

    def _tick(self, tau: float) -> TrustState:
        t0 = time.perf_counter()
        if (self._baseline_s is not None and not self._base_done
                and tau >= self._baseline_s):
            self._finish_baseline()
        s = self.slots
        L = lambda n, k, d=None: s[n].latest.get(k, d)

        acc0 = L("imu0", "accel", np.array([0.0, 0.0, G]))
        acc1 = L("imu1", "accel", np.array([0.0, 0.0, G]))
        att0, att1 = self._att_val["imu0"], self._att_val["imu1"]
        rpm = L("motor_esc", "rpm", np.full(4, 1200.0))
        esc_i = L("motor_esc", "current", np.zeros(4))
        vel = L("gps", "vel", np.zeros(3))
        pos = L("gps", "pos", np.zeros(3))
        alt = float(L("baro", "altitude", 0.0))
        temp = float(L("baro", "temp_c", 25.0))
        field_ut = L("mag", "field_ut", np.array([22.0, 0.0, -42.0]))
        batt_v = float(L("battery", "voltage", 16.8))
        batt_i = float(L("battery", "current", 0.0))
        vib_rms = float(L("vibration", "rms", 0.08))

        gvalid = 1.0 if s["gps"].valid and s["gps"].seen else 0.0
        vh = float(np.hypot(vel[0], vel[1]))
        course = float(np.arctan2(vel[1], vel[0]))
        speed_gate = float(np.clip(
            (vh - GATE_SPEED_LO) / (GATE_SPEED_HI - GATE_SPEED_LO), 0.0, 1.0))
        # Motor edges gate on ARMED state: real vehicle state when the
        # source provides it (HEARTBEAT / vehicle_status), the simulator's
        # scripted t>5s arming as the bench fallback. 1 s ramp after arming
        # (spin-up transient), hard zero when known-disarmed.
        if self._armed is None:
            armed_gate = float(np.clip((tau - 5.0) / 1.0, 0.0, 1.0))
        elif self._armed:
            armed_gate = float(np.clip(tau - (self._armed_since or 0.0),
                                       0.0, 1.0))
        else:
            armed_gate = 0.0

        E = {}
        if self._field:
            a0s = self._acc_s["imu0"].update(acc0)
            a1s = self._acc_s["imu1"].update(acc1)
            red_resid = np.linalg.norm(a0s - a1s)
        else:
            red_resid = np.linalg.norm(acc0 - acc1)
        E["redundant_imu"] = self._lam_upd(
            "redundant_imu", red_resid, 0.09, df=3), 1.0
        f_from_rpm = float(HOVER_THRUST_PER_MOTOR
                           * ((rpm / HOVER_RPM) ** 2).sum() / MASS)
        f_from_cur = float(HOVER_THRUST_PER_MOTOR * ((np.clip(
            esc_i, 0, None) / HOVER_CURRENT_PER_MOTOR) ** (2.0 / 3.0)).sum()
            / MASS)
        E["accel_motor_current"] = self._lam_upd(
            "accel_motor_current", acc0[2] - f_from_cur, 0.45), armed_gate
        E["accel_esc_rpm"] = self._lam_upd(
            "accel_esc_rpm", acc1[2] - f_from_rpm, 0.45), armed_gate
        E["altitude_baro"] = self._lam_upd(
            "altitude_baro", alt - pos[2], 2.2), gvalid

        # A dialect with no real vertical velocity (GPS_RAW_INT carries none;
        # the source marks vz_valid=False) must never have a z-residual
        # fabricated from the zero placeholder: compare horizontal only
        # (df drops 3 -> 2). Previously a steady climb read as a spoof-like
        # vertical error in the flagship phys_gps check.
        vz_ok = bool(L("gps", "vz_ok", True))
        dvel_s = self._dvel_s.update(self._gps_fd_dvel)
        for n, acc, att, key in (("imu0", acc0, att0, "velocity_gps_doppler_0"),
                                 ("imu1", acc1, att1, "velocity_gps_doppler_1")):
            f_w = _body_to_world_1(acc, att)
            f_w = f_w - np.array([0.0, 0.0, G])
            fw_s = self._fw_s[n].update(f_w)
            d = fw_s - dvel_s
            if not vz_ok:
                d = np.array([d[0], d[1], 0.0])
            E[key] = self._lam_upd(
                key, np.linalg.norm(d), 1.6, df=3 if vz_ok else 2), gvalid

        E["attitude_gravity_mag"] = self._lam_upd(
            "attitude_gravity_mag",
            wrap_angle(np.array([self._mag_heading - att0[2]]))[0],
            np.deg2rad(5.0)), 1.0
        E["heading_course"] = self._lam_upd(
            "heading_course",
            wrap_angle(np.array([self._mag_heading - course]))[0],
            np.deg2rad(10.0)), speed_gate * gvalid
        E["power_thrust"] = self._lam_upd(
            "power_thrust", batt_i - float(esc_i.sum()) - AVIONICS_CURRENT,
            0.5), 1.0
        rms_pred = float(np.sqrt((0.35 * rpm.mean() / HOVER_RPM
                                  / np.sqrt(2.0)) ** 2 + 0.08 ** 2))
        E["vibration_prop_freq"] = self._lam_upd(
            "vibration_prop_freq", vib_rms - rms_pred, 0.035), 1.0

        temp_s = float(self._temp_s.update(temp))
        dtemp = 0.0 if self._temp_s_prev is None \
            else (temp_s - self._temp_s_prev) / self.dt_tick
        self._temp_s_prev = temp_s
        E["temp_bias_drift"] = self._lam_upd(
            "temp_bias_drift", dtemp, 0.5), 0.2

        P = {}
        r_raw = self._gps_fd_vel - vel
        if not vz_ok:
            r_raw = np.array([r_raw[0], r_raw[1], 0.0])
        r_gps = self._rgps_s.update(r_raw)
        lam_gps = self._lam_upd("phys_gps", np.linalg.norm(r_gps),
                                0.45, df=3 if vz_ok else 2)
        # absolute step check, NOT adaptively normalized: no vehicle
        # teleports — sigma 20 m/s of unexplained instantaneous motion
        lam_step = (self._gps_step_peak / 20.0) ** 2
        self._gps_step_peak *= 0.85   # hold the alarm a few seconds
        P["gps"] = (max(lam_gps, lam_step),
                    gvalid * (1.0 if tau > 3.0 else 0.0))
        ocv = float(self._ocv.update(batt_v + batt_i * PACK_R_INTERNAL))
        P["battery"] = (self._lam_upd(
            "phys_battery", batt_v - (ocv - batt_i * PACK_R_INTERNAL),
            0.06), 1.0)
        i_pred = HOVER_CURRENT_PER_MOTOR * (rpm / HOVER_RPM) ** 3
        P["motor_esc"] = (self._lam_upd(
            "phys_motor_esc", float(np.abs(esc_i - i_pred).mean()), 0.2), 1.0)
        mag_ref_ready = self._mag_ref is not None
        P["mag"] = (self._lam_upd(
            "phys_mag", (float(np.linalg.norm(field_ut))
                         - (self._mag_ref if mag_ref_ready else 0.0)),
            0.6), 1.0 if mag_ref_ready else 0.0)
        alt_s = float(self._alt_s.update(alt))
        alt_rate = 0.0 if self._alt_s_prev is None \
            else (alt_s - self._alt_s_prev) / self.dt_tick
        self._alt_s_prev = alt_s
        P["baro"] = (self._lam_upd(
            "phys_baro", max(abs(alt_rate) - 8.0, 0.0), 3.0), 1.0)
        P["vibration"] = (self._lam_upd(
            "phys_vibration", vib_rms - rms_pred, 0.05), 1.0)

        # Self-awareness: if a channel's residuals sit chronically >5 sigma
        # (adaptive level > 25), its logged rate/noise makes the temporal
        # predictor uninformative — WITHDRAW that evidence (renormalize over
        # the physical checks) instead of scoring garbage.
        def _hist_ok(n):
            return not (self._field and s[n].adapt_level > 25.0)
        hist = {n: (s[n].hist_val if _hist_ok(n) else None) for n in SENSORS}
        vr = {n: (s[n].vr_val if _hist_ok(n) else None) for n in SENSORS}
        fresh = {n: s[n].valid and s[n].seen
                 and (tau - s[n].last_t) <= self._stale[n]
                 for n in SENSORS}
        # Every edge requires BOTH endpoint sensors alive; every physics
        # check requires its own sensor alive. A missing/stale/absent sensor
        # (e.g. a flight log without ESC telemetry) contributes NO evidence
        # anywhere — its trust simply holds at the prior.
        E = {key: (lam, gate * float(fresh[self._edge_meta[key][0]])
                   * float(fresh[self._edge_meta[key][1]]))
             for key, (lam, gate) in E.items()}
        P = {n: (lam, gate * float(fresh[n])) for n, (lam, gate) in P.items()}
        # the vibration envelope prediction is computed FROM motor rpm — no
        # live rpm, no check (otherwise real vib levels vs a default-rpm
        # envelope would false-alarm on any airframe without ESC telemetry)
        P["vibration"] = (P["vibration"][0],
                          P["vibration"][1] * float(fresh["motor_esc"]))

        edges_now = {key: (*self._edge_meta[key], lam, gate)
                     for key, (lam, gate) in E.items()}
        res = self.core.step(edges_now, P, hist, vr, fresh)

        feats = {key: (float(np.exp(-0.5 * max(0.0, lam - 1.0))), gate)
                 for key, (lam, gate) in E.items()}
        for n, (lam, gate) in P.items():
            feats[f"phys_{n}"] = (
                float(np.exp(-0.5 * max(0.0, lam - 1.0))), gate)
        for n in TEMP_FEATURES:
            feats[f"temp_{n}"] = (1.0, 0.0) if hist[n] is None else (
                float(np.exp(-0.5 * max(0.0, hist[n] - 1.0))), 1.0)
        posterior = self.diag.step(feats)

        return TrustState(
            t=tau,
            edges={key: (float(np.exp(-0.5 * max(0.0, lam - 1.0))), gate)
                   for key, (lam, gate) in E.items()},
            trust={n: res[n]["trust"] for n in SENSORS},
            evidence={n: res[n]["evidence"] for n in SENSORS},
            components={n: {c: res[n][c] for c in ("nbr", "phys", "temp",
                                                   "stat")} for n in SENSORS},
            posterior=posterior,
            fresh=fresh,
            armed=self._armed,
            latency_us=(time.perf_counter() - t0) * 1e6)


def _body_to_world_1(vec_b: np.ndarray, att: np.ndarray) -> np.ndarray:
    """Single-sample body->world rotation (transpose of world_to_body)."""
    r, p, y = att
    cr, sr, cp, sp = np.cos(r), np.sin(r), np.cos(p), np.sin(p)
    cy, sy = np.cos(y), np.sin(y)
    R = np.array([
        [cp * cy, cp * sy, -sp],
        [sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, sr * cp],
        [cr * sp * cy + sr * sy, cr * sp * sy - sr * cy, cr * cp],
    ])
    return R.T @ vec_b
