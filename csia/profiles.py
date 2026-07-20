"""Vehicle/platform profiles — the plug-in configuration layer.

A ``VehicleProfile`` bundles everything platform-specific about a CSIA
deployment: the sensor set, engine tick rate and tuning, failsafe
thresholds/timing, and watchdog timeouts. The trust mathematics
(TrustCore, DiagnosisCore) is platform-agnostic; what changes between
platforms is which sensors exist, which physical relationships tie them
together, and what the emergency plan is.

Extension contract for a NEW platform (rover, boat, fixed-wing, industrial
sensor network):
  1. Define its sensor nodes and edge set (an edge module implementing the
     platform's physical relationships — see csia/runtime/online.py for the
     SOW001 quad edge library as the reference implementation).
  2. Define a VehicleProfile with its failsafe rules and timeouts.
  3. Register it in PROFILES.
The edge physics is engineering work per platform, deliberately NOT a config
file: a physical constraint that nobody derived and validated is exactly the
kind of false confidence CSIA exists to eliminate.
"""

from dataclasses import dataclass, field

from .runtime.failsafe import FailsafeConfig
from .trust_engine.engine import EngineConfig

QUAD_SENSORS = ("imu0", "imu1", "baro", "mag", "gps",
                "motor_esc", "battery", "vibration")


@dataclass(frozen=True)
class VehicleProfile:
    name: str
    description: str
    sensors: tuple
    tick_hz: float = 25.0
    engine: EngineConfig = field(default_factory=EngineConfig)
    failsafe: FailsafeConfig = field(default_factory=FailsafeConfig)
    hardware: str = ""

    def __post_init__(self):
        if not self.sensors:
            raise ValueError("profile needs at least one sensor")
        if self.tick_hz <= 0:
            raise ValueError("tick_hz must be positive")


SOW001_QUAD = VehicleProfile(
    name="sow001_quad",
    description="SOW001 quadrotor: STM32H743VIT6 FC, dual ICM-42688-P, "
                "MS5611, RM3100, GPS, 4x ESC telemetry, pack monitor, "
                "vibration channel; Pi 5 companion over MAVLink.",
    sensors=QUAD_SENSORS,
    hardware="docs/HARDWARE.md#tier-1--sow001-baseline",
)

# Same airframe, tighter mission rules: escalates faster, recovers slower.
# Demonstrates that failsafe posture is a profile decision, not a code fork.
SOW001_QUAD_STRICT = VehicleProfile(
    name="sow001_quad_strict",
    description="SOW001 quad with mission-critical failsafe posture "
                "(faster escalation, conservative recovery).",
    sensors=QUAD_SENSORS,
    failsafe=FailsafeConfig(dwell_up=0.5, dwell_down=10.0,
                            nav_caution=0.85, power_critical=0.80,
                            att_caution=0.88, att_emergency=0.75),
    hardware="docs/HARDWARE.md#tier-1--sow001-baseline",
)

# interceptor_seeker: a synthetic first-pass seeker profile (IR + RF + INS).
# Its edge library and runtime live in csia/seeker/ (it does NOT use the quad
# OnlineTrustLayer). 100 Hz seeker-representative tick rate; 25 Hz runnable.
# SYNTHETIC — not validated against seeker hardware. See csia/seeker/.
INTERCEPTOR_SEEKER = VehicleProfile(
    name="interceptor_seeker",
    description="Missile-seeker engagement (SYNTHETIC first pass): IR seeker "
                "(bearing+intensity), RF seeker (range/range-rate/azimuth), "
                "INS. Closing intercept vs subsonic target. Runs the "
                "unmodified CSIA cores via csia/seeker/.",
    sensors=("ir_seeker", "rf_seeker", "ins"),
    tick_hz=100.0,
    hardware="SYNTHETIC — no hardware; see csia/seeker/ and deliverables/",
)

PROFILES = {p.name: p for p in (SOW001_QUAD, SOW001_QUAD_STRICT,
                                INTERCEPTOR_SEEKER)}


def get_profile(name: str) -> VehicleProfile:
    if name not in PROFILES:
        raise KeyError(f"unknown profile {name!r}; "
                       f"available: {sorted(PROFILES)}")
    return PROFILES[name]
