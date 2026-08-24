"""Adapter base: freshness, staleness, qualification, canonical assembly.

An adapter is a state machine over a telemetry stream. It holds the latest
value per channel, ages them against wall time, and emits an `AircraftSample`
on demand. It never blocks and never buffers unboundedly: exactly one value
per channel is retained, which is also what keeps memory flat over a long
flight (an acceptance criterion: "no unbounded queues").

Freshness is not the same as validity and neither is the same as
informativeness. All three are tracked separately:

    received?      -> MissingReason.NOT_RECEIVED
    recent enough? -> MissingReason.STALE
    means anything?-> MissingReason.STUB / NOT_QUALIFIED

A channel can be fresh, valid and still refused. That is the entire point of
the S2 layer.
"""

from __future__ import annotations

import math
import time
from typing import Optional

from ..qualification import SemanticContract, default_contract
from ..sample import (AircraftSample, ChannelValue, MissingReason, Quality,
                      SensorFrame)

# Per-channel maximum age before the value is STALE. Derived from the declared
# producer rate in CHANNEL_SEMANTICS.yaml with a 5x margin: a channel that has
# missed five consecutive publications is not "slightly old", it is gone.
MaxAge = {
    "imu0.accel": 0.20, "imu0.gyro": 0.20,
    "imu1.accel": 0.20, "imu1.gyro": 0.20,
    "mag.field_ut": 0.20,
    "baro.altitude": 0.50, "baro.temp_c": 0.50,
    "gnss.position": 1.00, "gnss.velocity": 1.00,
    "battery.voltage": 0.50, "battery.current": 0.50,
    "esc.rpm": 0.50, "esc.current": 0.50,
    "vibration.rms": 0.50,
    "vehicle_status.armed": 5.00,
    "estimator.variances": 1.00,
    "estimator.flight_mode": 5.00,
}
DEFAULT_MAX_AGE = 1.0

# Which AircraftSample group each channel belongs in.
GROUP_OF = {
    "imu0.accel": "imu", "imu0.gyro": "imu",
    "imu1.accel": "imu", "imu1.gyro": "imu",
    "mag.field_ut": "magnetometer",
    "baro.altitude": "barometer", "baro.temp_c": "barometer",
    "gnss.position": "gnss", "gnss.velocity": "gnss",
    "gnss.velocity_z": "gnss",
    "battery.voltage": "battery", "battery.current": "battery",
    "esc.rpm": "esc", "esc.current": "esc",
    "vibration.rms": "imu",
    "vehicle_status.armed": "navigation_state",
    "estimator.variances": "estimator_health",
    "estimator.flight_mode": "estimator_health",
}


class PlatformAdapter:
    """Common machinery. Subclasses implement `ingest`."""

    platform = "base"
    adapter_version = "1.1.0"

    def __init__(self, contract: Optional[SemanticContract] = None,
                 max_age: Optional[dict] = None,
                 clock=time.monotonic):
        self.contract = contract or default_contract()
        self.max_age = dict(MaxAge)
        if max_age:
            self.max_age.update(max_age)
        self._clock = clock
        # channel -> (raw_value, t_mono_received, t_source, frame, unit)
        self._latest: dict = {}
        self._t_source_last: Optional[float] = None
        self._flight_mode: Optional[str] = None
        self.counters = {"messages": 0, "mapped": 0, "unmapped": 0,
                         "rejected_sentinel": 0, "time_reanchors": 0}
        self._unmapped_types = {}

    # -- subclass interface ------------------------------------------------

    def ingest(self, msg) -> None:                      # pragma: no cover
        raise NotImplementedError

    # -- shared helpers ----------------------------------------------------

    def _put(self, channel: str, value, *, t_source=None,
             frame: SensorFrame = SensorFrame.NONE, unit: str = ""):
        """Record the latest raw value for a channel."""
        if value is None:
            return
        self._latest[channel] = (value, self._clock(), t_source, frame, unit)
        self.counters["mapped"] += 1
        if t_source is not None:
            self._t_source_last = t_source

    def _note_unmapped(self, type_name: str):
        self.counters["unmapped"] += 1
        self._unmapped_types[type_name] = \
            self._unmapped_types.get(type_name, 0) + 1

    def unmapped_types(self) -> dict:
        """Message types seen but not consumed.

        Reported rather than silently dropped: an integration where a channel
        the contract expects never arrives should be visible at the adapter,
        not diagnosed later as a mysterious abstention.
        """
        return dict(self._unmapped_types)

    # -- sampling ----------------------------------------------------------

    def _channel_value(self, channel: str, now: float) -> ChannelValue:
        entry = self._latest.get(channel)
        if entry is None:
            return self.contract.qualify(channel, None)
        value, t_recv, t_source, frame, unit = entry
        age = now - t_recv
        limit = self.max_age.get(channel, DEFAULT_MAX_AGE)
        if age > limit:
            q, may, reason, _ = self.contract.effective(channel)
            return ChannelValue.absent(
                channel, MissingReason.STALE,
                quality=(Quality.UNAVAILABLE if q.admissible else q),
                note=f"age {age:.2f}s exceeds {limit:.2f}s")
        return self.contract.qualify(channel, value, unit=unit, frame=frame,
                                     t_source=t_source, age_s=age)

    def sample(self, t_mono: Optional[float] = None) -> AircraftSample:
        """Assemble the canonical sample. Never blocks."""
        now = self._clock()
        t = t_mono if t_mono is not None else now
        s = AircraftSample(t_mono=t, t_source=self._t_source_last,
                           flight_mode=self._flight_mode)
        for channel in self.contract.channels:
            cv = self._channel_value(channel, now)
            group = GROUP_OF.get(channel)
            if group is None:
                continue
            getattr(s, group)[channel] = cv
        s.metadata = {
            "platform": self.platform,
            "adapter_version": self.adapter_version,
            "contract_version": self.contract.version,
            "frozen_core": self.contract.frozen_core,
            "counters": dict(self.counters),
        }
        return s

    # -- bridge to the FROZEN v1 core --------------------------------------
    #
    # The v1 online layer consumes (sensor, t, channels) tuples. This is the
    # only place that shape is produced, and it is produced ONLY from
    # admissible channels. A blocked channel is simply not emitted, so the
    # frozen layer sees the sensor as unavailable and abstains -- which is
    # behaviour it already had. No v1 code changes.

    CORE_MAP = {
        "imu0": {"accel": "imu0.accel", "gyro": "imu0.gyro"},
        "imu1": {"accel": "imu1.accel", "gyro": "imu1.gyro"},
        "mag": {"field_ut": "mag.field_ut"},
        "baro": {"altitude": "baro.altitude", "temp_c": "baro.temp_c"},
        "gps": {"pos": "gnss.position", "vel": "gnss.velocity"},
        "battery": {"voltage": "battery.voltage",
                    "current": "battery.current"},
        "motor_esc": {"rpm": "esc.rpm", "current": "esc.current"},
        "vibration": {"rms": "vibration.rms"},
        "vehicle_status": {"armed": "vehicle_status.armed"},
    }

    def to_core_samples(self, s: AircraftSample) -> list:
        """AircraftSample -> the frozen core's sample tuples.

        A sensor is emitted only when ALL of its required channels are usable.
        Partial sensors are withheld: half a GPS fix is not a degraded fix, it
        is a fabricated one.
        """
        out = []
        for sensor, mapping in self.CORE_MAP.items():
            chans = {}
            complete = True
            for core_key, channel in mapping.items():
                cv = s.get(channel)
                if cv is None or not cv.usable:
                    # baro.temp_c is optional to the core; everything else is
                    # required for its sensor to be emitted at all.
                    if channel == "baro.temp_c":
                        continue
                    complete = False
                    break
                chans[core_key] = cv.value
            if not complete or not chans:
                continue
            if sensor == "gps":
                # GPS_RAW_INT carries no vertical rate; the core already
                # knows to judge horizontal only when told.
                chans["vz_valid"] = False
            if sensor != "vehicle_status":
                chans["valid"] = True
            out.append((sensor, s.t_mono, chans))
        return out

    # -- reporting ---------------------------------------------------------

    def status(self) -> dict:
        now = self._clock()
        chans = {}
        for channel in self.contract.channels:
            cv = self._channel_value(channel, now)
            chans[channel] = {
                "usable": cv.usable,
                "quality": cv.quality.value,
                "missing": cv.missing.value if cv.missing else None,
                "age_s": (None if cv.age_s is None
                          else round(cv.age_s, 4)),
            }
        return {
            "platform": self.platform,
            "adapter_version": self.adapter_version,
            "counters": dict(self.counters),
            "unmapped_types": self.unmapped_types(),
            "channels": chans,
        }


def finite(x) -> bool:
    """Reject NaN/inf before they reach the core.

    A NaN propagates silently through a weighted mean and turns an entire
    trust vector into NaN several ticks later, far from the message that
    produced it.
    """
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False
