"""ULog replay source — plug REAL PX4 flight logs into the trust layer.

This is the real-data validation path: any .ulg file (your own QGC download,
the public PX4 Flight Review database, autotest artifacts) replays through
the exact same OnlineTrustLayer the vehicle runs. Sensors the log doesn't
contain simply never go fresh, so their edges gate out and contribute no
evidence — no per-log configuration needed.

Topic map (PX4 uORB -> CSIA node), with frame conversion FRD/NED -> the
z-up convention used throughout this package (proper 180-deg rotation about
the x axis: body (x,-y,-z), world (n,-e,-d)):

  sensor_combined                 -> imu0   (accel m/s^2, gyro rad/s)
  vehicle_imu (instance 1)        -> imu1   (delta_velocity/dt integrals)
  vehicle_air_data                -> baro   (baro_alt_meter, baro_temp_celcius)
  vehicle_magnetometer|sensor_mag -> mag    (gauss -> uT)
  vehicle_gps_position            -> gps    (lat/lon/alt -> local m; NED vel;
                                             valid = fix_type >= 3)
  battery_status                  -> battery (voltage_v, current_a)
  esc_status (if logged)          -> motor_esc (rpm, current)

Airframe-specific edges (accel<->motor thrust law, vibration envelope) are
calibrated for the SOW001 quad; on an arbitrary log they would be model
mismatch, so analyze-log runs with ESC/vibration absent unless you know the
airframe matches. Use OnlineTrustLayer(mag_ref_ut=None) so the local field
magnitude self-calibrates (Earth's field: 25-65 uT by location).
"""

import logging
from typing import Iterator

import numpy as np

from .plugins import Sample, SourcePlugin

log = logging.getLogger(__name__)

M_PER_DEG_LAT = 111_320.0


def _frd_to_zup(v):
    """Body FRD -> z-up body: 180-deg rotation about x."""
    return np.array([v[0], -v[1], -v[2]], dtype=float)


class UlogSource(SourcePlugin):
    """Replay a PX4 .ulg file as a time-ordered CSIA sample stream."""

    def __init__(self, path: str, include_esc: bool = False):
        from pyulog import ULog  # lazy: optional dependency
        self.path = path
        self.scenario = f"ulog:{path}"
        self.include_esc = include_esc
        self.ulog = ULog(path)
        self.duration = 0.0
        self._events = self._build_events()

    def _topic(self, name, instance=0):
        try:
            return self.ulog.get_dataset(name, instance)
        except (KeyError, IndexError, ValueError):
            return None

    def _build_events(self):
        ev = []
        u = self.ulog
        t0_us = None

        def ts(data):
            return np.asarray(data["timestamp"], dtype=np.int64)

        # --- imu0: sensor_combined ------------------------------------------
        sc = self._topic("sensor_combined")
        if sc is not None:
            d = sc.data
            t_us = ts(d)
            t0_us = int(t_us[0])
            acc = np.column_stack([d["accelerometer_m_s2[0]"],
                                   d["accelerometer_m_s2[1]"],
                                   d["accelerometer_m_s2[2]"]])
            gyr = np.column_stack([d["gyro_rad[0]"], d["gyro_rad[1]"],
                                   d["gyro_rad[2]"]])
            # PX4 accel is specific force in FRD (rest ~ (0,0,-g)); the
            # z-up convention wants rest ~ (0,0,+g).
            # Downsample to ~50 Hz by BLOCK AVERAGING, never by decimation:
            # raw IMU samples carry many m/s^2 of prop vibration; picking
            # every k-th sample aliases that into the cross-IMU comparison,
            # while averaging (what a real driver's output filter does)
            # leaves the actual specific-force signal.
            n = len(t_us)
            block = max(1, int(round(n / (((t_us[-1] - t0_us) / 1e6) * 50.0))))
            m = (n // block) * block
            t_blk = t_us[:m].reshape(-1, block).mean(axis=1)
            acc_blk = acc[:m].reshape(-1, block, 3).mean(axis=1)
            gyr_blk = gyr[:m].reshape(-1, block, 3).mean(axis=1)
            for i in range(len(t_blk)):
                ev.append(((t_blk[i] - t0_us) / 1e6, "imu0", {
                    "accel": _frd_to_zup(acc_blk[i]),
                    "gyro": _frd_to_zup(gyr_blk[i]), "valid": True}))

        if t0_us is None:
            raise ValueError(f"{self.path}: no sensor_combined topic — "
                             "not a usable PX4 flight log")
        rel = lambda t_us: (np.asarray(t_us, np.int64) - t0_us) / 1e6

        # --- imu1: vehicle_imu instance 1 (delta integrals -> mean rates) ----
        vi = self._topic("vehicle_imu", 1)
        if vi is not None:
            d = vi.data
            t_s = rel(ts(d))
            dv = np.column_stack([d["delta_velocity[0]"],
                                  d["delta_velocity[1]"],
                                  d["delta_velocity[2]"]])
            da = np.column_stack([d["delta_angle[0]"], d["delta_angle[1]"],
                                  d["delta_angle[2]"]])
            dt_v = np.asarray(d["delta_velocity_dt"], float) * 1e-6
            dt_a = np.asarray(d["delta_angle_dt"], float) * 1e-6
            ok = (dt_v > 1e-5) & (dt_a > 1e-5)
            idx = np.nonzero(ok)[0]
            acc1 = dv[idx] / dt_v[idx, None]
            gyr1 = da[idx] / dt_a[idx, None]
            t1 = t_s[idx]
            # anti-alias block averaging to ~50 Hz (same reason as imu0)
            span = max(float(t1[-1] - t1[0]), 1e-3)
            block = max(1, int(round(len(t1) / (span * 50.0))))
            m = (len(t1) // block) * block
            if m >= block:
                tb = t1[:m].reshape(-1, block).mean(axis=1)
                ab = acc1[:m].reshape(-1, block, 3).mean(axis=1)
                gb = gyr1[:m].reshape(-1, block, 3).mean(axis=1)
                for i in range(len(tb)):
                    ev.append((float(tb[i]), "imu1", {
                        "accel": _frd_to_zup(ab[i]),
                        "gyro": _frd_to_zup(gb[i]), "valid": True}))

        # --- baro -------------------------------------------------------------
        ad = self._topic("vehicle_air_data")
        if ad is not None:
            d = ad.data
            t_s = rel(ts(d))
            temp = d.get("baro_temp_celcius",
                         np.full(len(t_s), 25.0))
            for i in range(len(t_s)):
                ev.append((float(t_s[i]), "baro", {
                    "altitude": float(d["baro_alt_meter"][i]),
                    "temp_c": float(temp[i]), "valid": True}))

        # --- mag --------------------------------------------------------------
        mg = self._topic("vehicle_magnetometer") or self._topic("sensor_mag")
        if mg is not None:
            d = mg.data
            t_s = rel(ts(d))
            key = "magnetometer_ga" if "magnetometer_ga[0]" in d else \
                ("x" if "x" in d else None)
            for i in range(len(t_s)):
                if key == "magnetometer_ga":
                    f = np.array([d["magnetometer_ga[0]"][i],
                                  d["magnetometer_ga[1]"][i],
                                  d["magnetometer_ga[2]"][i]]) * 100.0  # G->uT
                else:
                    f = np.array([d["x"][i], d["y"][i], d["z"][i]]) * 100.0
                ev.append((float(t_s[i]), "mag",
                           {"field_ut": _frd_to_zup(f), "valid": True}))

        # --- gps --------------------------------------------------------------
        gp = self._topic("vehicle_gps_position")
        if gp is not None:
            d = gp.data
            t_s = rel(ts(d))
            lat_key = "latitude_deg" if "latitude_deg" in d else "lat"
            scale = 1.0 if lat_key == "latitude_deg" else 1e-7
            lat = np.asarray(d[lat_key], float) * scale
            lon = np.asarray(d["longitude_deg" if lat_key == "latitude_deg"
                               else "lon"], float) * scale
            alt = np.asarray(d["altitude_msl_m" if lat_key == "latitude_deg"
                               else "alt"], float) \
                * (1.0 if lat_key == "latitude_deg" else 1e-3)
            fix = np.asarray(d["fix_type"], int)
            first = int(np.argmax(fix >= 3)) if (fix >= 3).any() else 0
            lat0, lon0, alt0 = lat[first], lon[first], alt[first]
            coslat = np.cos(np.deg2rad(lat0))
            for i in range(len(t_s)):
                pos = np.array([(lat[i] - lat0) * M_PER_DEG_LAT,
                                -(lon[i] - lon0) * M_PER_DEG_LAT * coslat,
                                alt[i] - alt0])
                vel = np.array([d["vel_n_m_s"][i], -d["vel_e_m_s"][i],
                                -d["vel_d_m_s"][i]], dtype=float)
                ev.append((float(t_s[i]), "gps", {
                    "pos": pos, "vel": vel, "valid": bool(fix[i] >= 3)}))

        # --- battery ----------------------------------------------------------
        bt = self._topic("battery_status")
        if bt is not None:
            d = bt.data
            t_s = rel(ts(d))
            for i in range(len(t_s)):
                ev.append((float(t_s[i]), "battery", {
                    "voltage": float(d["voltage_v"][i]),
                    "current": float(d["current_a"][i]), "valid": True}))

        # --- esc (airframe-specific edges; off unless explicitly enabled) -----
        if self.include_esc:
            es = self._topic("esc_status")
            if es is not None:
                d = es.data
                t_s = rel(ts(d))
                for i in range(len(t_s)):
                    rpm = np.array([d.get(f"esc[{m}].esc_rpm",
                                          np.zeros(len(t_s)))[i]
                                    for m in range(4)], float)
                    cur = np.array([d.get(f"esc[{m}].esc_current",
                                          np.zeros(len(t_s)))[i]
                                    for m in range(4)], float)
                    ev.append((float(t_s[i]), "motor_esc", {
                        "rpm": rpm, "current": cur, "valid": True}))

        ev = [e for e in ev if e[0] >= 0.0]
        # Minimum-rate screen: an IMU logged at 2 Hz is aliased vibration
        # snapshots, not a monitorable inertial stream (live rate is 100+ Hz;
        # the LOG lacks the data). Refusing to monitor it is the correct
        # product behavior — report it, don't guess from garbage.
        MIN_RATE_HZ = {"imu0": 10.0, "imu1": 10.0, "baro": 2.0, "mag": 2.0,
                       "gps": 0.5, "battery": 0.2, "motor_esc": 2.0}
        counts, spans = {}, {}
        for t, name, _ in ev:
            counts[name] = counts.get(name, 0) + 1
            spans[name] = max(spans.get(name, 0.0), t)
        self.excluded = {}
        for name, cnt in counts.items():
            rate = cnt / max(spans[name], 1.0)
            if rate < MIN_RATE_HZ.get(name, 0.0):
                self.excluded[name] = round(rate, 2)
        if self.excluded:
            log.info("%s: excluded (logged below monitoring minimum): %s",
                     self.path, self.excluded)
            ev = [e for e in ev if e[1] not in self.excluded]
        ev.sort(key=lambda e: e[0])
        self.duration = ev[-1][0] if ev else 0.0
        present = sorted({name for _, name, _ in ev})
        log.info("%s: %.0f s, %d samples, sensors: %s",
                 self.path, self.duration, len(ev), ", ".join(present))
        return ev

    @property
    def sensors_present(self):
        return sorted({name for _, name, _ in self._events})

    def stale_timeouts(self, factor: float = 5.0) -> dict:
        """Watchdog timeouts derived from the log's own topic rates —
        logged rates are often far below live sensor rates."""
        times = {}
        for t, name, _ in self._events:
            times.setdefault(name, []).append(t)
        out = {}
        for name, ts in times.items():
            if len(ts) > 3:
                gaps = np.diff(np.asarray(ts))
                med = float(np.median(gaps))
                p99 = float(np.percentile(gaps, 99))
                # logging is bursty: a gap the log itself contains during a
                # healthy flight must not trip the watchdog on replay
                out[name] = max(factor * med, 2.0 * p99, 0.2)
        return out

    def samples(self) -> Iterator[Sample]:
        for t, name, ch in self._events:
            yield name, t, ch
