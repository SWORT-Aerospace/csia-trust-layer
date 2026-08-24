"""MAVLink telemetry tee: a driven link, forwarded to passive listeners.

**This module TRANSMITS. It is deliberately not part of the shadow path.**

It exists because of a measured constraint: on ArduCopter 4.8 stream rates are
per-link runtime state, established only by a transmit on that link, and they
do not persist (`GCS.h:537`, `persist_streamrates() == false`; the `SRx_`
parameters do not exist). A strictly-passive monitor on its own link therefore
receives only HEARTBEAT, SYS_STATUS, HOME_POSITION and TIMESYNC -- never
sensor data. See `docs/deployment/AIRCRAFT_INTEGRATION.md` 2.0.

So something with transmit authority has to drive a link, and CSIA cannot be
it. The tee plays that role: it is the **GCS / telemetry infrastructure** that
already exists on a real aircraft, modelled explicitly instead of assumed.

    SITL SERIAL0  --(tee connects, REQUESTS streams)-->  tee
                                                          |
                                                 forwards bytes, unmodified
                                                          v
                                              udp:127.0.0.1:PORT
                                                          |
                                             CSIA binds and LISTENS ONLY

CSIA never transmits and never asks for anything. It reads a feed someone else
established, which is exactly what a telemetry tee is on a real vehicle: a
MAVProxy `--out`, a hardware UART tee, or a shared bus the GCS is polling.

Why this lives in `csia.simulation` and not `csia.deploy`: the deployment tree
is asserted to contain **zero** MAVLink transmit calls
(`tests/test_shadow_mode.py::test_no_send_calls_in_deployment_source`). Putting
a transmitter there would break that guarantee, and the guarantee is the point.
"""

from __future__ import annotations

import logging
import socket
import threading
import time

log = logging.getLogger(__name__)

# Streams a CSIA channel actually needs, from CHANNEL_SEMANTICS.yaml.
# RAW_SENSORS is not optional: ArduPilot publishes inertial instance 0 as
# RAW_IMU there, and a run without it loses imu0 and the magnetometer.
ARDUPILOT_STREAMS = (
    ("MAV_DATA_STREAM_RAW_SENSORS", 25),
    ("MAV_DATA_STREAM_EXTENDED_STATUS", 10),
    ("MAV_DATA_STREAM_POSITION", 10),
    ("MAV_DATA_STREAM_EXTRA1", 25),
    ("MAV_DATA_STREAM_EXTRA2", 10),
    ("MAV_DATA_STREAM_EXTRA3", 5),
)


class MavlinkTee:
    """Drive one MAVLink link and forward every message to UDP listeners.

    Bytes are forwarded **unmodified**: whatever the autopilot emitted is what
    a listener parses. The tee adds no messages of its own to the forwarded
    feed, so a listener cannot tell a teed stream from a direct one -- which is
    the property that makes an R13 measurement through it meaningful.
    """

    def __init__(self, source: str, outputs, platform: str = "ardupilot",
                 stream_rate_hz: int = 25):
        self.source = source
        self.outputs = [self._addr(o) for o in outputs]
        self.platform = platform
        self.stream_rate_hz = stream_rate_hz
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._conn = None
        self._thread = None
        self._running = False
        self.stats = {"forwarded": 0, "bytes": 0, "errors": 0,
                      "by_type": {}}

    @staticmethod
    def _addr(o):
        if isinstance(o, tuple):
            return o
        host, _, port = o.rpartition(":")
        return (host.replace("udp:", "").replace("udpout:", "") or "127.0.0.1",
                int(port))

    # ------------------------------------------------------------------
    def start(self, timeout: float = 60.0):
        """Connect, request streams, and begin forwarding in the background."""
        from pymavlink import mavutil

        self._conn = mavutil.mavlink_connection(self.source)
        self._conn.wait_heartbeat(timeout=timeout)
        log.info("tee: connected to %s (sys %d)", self.source,
                 self._conn.target_system)

        # THE TRANSMIT. This is the whole reason the tee exists, and it happens
        # here rather than anywhere in csia.deploy.
        if self.platform == "ardupilot":
            for name, hz in ARDUPILOT_STREAMS:
                self._conn.mav.request_data_stream_send(
                    self._conn.target_system, self._conn.target_component,
                    getattr(mavutil.mavlink, name), hz, 1)
        log.info("tee: requested %d streams", len(ARDUPILOT_STREAMS))

        self._running = True
        self._thread = threading.Thread(target=self._pump, daemon=True,
                                        name="mavlink-tee")
        self._thread.start()
        return self

    def _pump(self):
        while self._running:
            try:
                msg = self._conn.recv_match(blocking=True, timeout=1.0)
            except Exception as exc:                    # pragma: no cover
                self.stats["errors"] += 1
                log.warning("tee: receive error: %s", exc)
                continue
            if msg is None:
                continue
            buf = msg.get_msgbuf()
            if not buf:
                continue
            for addr in self.outputs:
                try:
                    self._sock.sendto(buf, addr)
                except OSError:
                    self.stats["errors"] += 1
            self.stats["forwarded"] += 1
            self.stats["bytes"] += len(buf)
            t = msg.get_type()
            self.stats["by_type"][t] = self.stats["by_type"].get(t, 0) + 1

    def wait_for_traffic(self, min_types: int = 5,
                         timeout: float = 20.0) -> bool:
        """Block until the feed is genuinely carrying sensor data.

        A positive control on the tee itself. Forwarding HEARTBEAT alone is
        indistinguishable from the broken passive-link case this exists to
        fix, so the harness must not proceed on "the tee started".
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            if len(self.stats["by_type"]) >= min_types:
                return True
            time.sleep(0.5)
        return False

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        try:
            self._sock.close()
        except Exception:
            pass

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()
        return False
