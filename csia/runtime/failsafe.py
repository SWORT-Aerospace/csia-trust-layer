"""Failsafe policy: trust states -> mission-protection actions.

CSIA role: the "critical mission emergency plan". The trust layer's job is
not just to score sensors — it must keep the vehicle safe when they fail.
This is a deterministic, auditable state machine (no ML in the safety path):

  NORMAL     all sensor classes healthy
  CAUTION    a non-critical capability is degraded; reconfigure around it
             (e.g. GPS untrusted -> switch to inertial/baro position hold,
              inhibit GPS-guided modes; one IMU isolated -> select the other)
  CRITICAL   flight should end soon on our terms (power fault, structural
             vibration, single-attitude-source): reduce demand, land soon
  EMERGENCY  attitude reference integrity lost or compounding failures:
             STABILIZE + CONTROLLED DESCENT — level the vehicle on the best
             remaining attitude source and descend at a fixed rate. This is
             the "drone stabilizes and brings itself down" behavior.

Escalation requires the triggering condition to persist for ``dwell_up``
seconds (no single-tick flapping); de-escalation requires ``dwell_down``
seconds of health (hysteresis). Every transition carries machine-readable
actions plus a human-readable reason including the diagnosis callout.

ADVISORY BY DEFAULT: actions are recommendations for the autopilot/operator.
Wiring them to a real vehicle (see service.MavlinkActuator) is opt-in and,
for a real aircraft, subject to a qualification process this prototype does
not claim.
"""

import logging
from dataclasses import dataclass, field
from enum import IntEnum

log = logging.getLogger(__name__)


class FailsafeLevel(IntEnum):
    NORMAL = 0
    CAUTION = 1
    CRITICAL = 2
    EMERGENCY = 3


@dataclass(frozen=True)
class Action:
    name: str
    reason: str
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FailsafeConfig:
    """Trust thresholds per sensor class + state-machine timing.

    Thresholds sit between healthy-flight floors (>=0.88 clean, measured)
    and faulted minima (see README scenario table), with margin on both
    sides. att_* applies to max(imu0, imu1): losing ONE IMU is CAUTION
    (redundancy working), losing confidence in BOTH is the emergency."""
    nav_caution: float = 0.75        # gps
    heading_caution: float = 0.60    # mag
    struct_critical: float = 0.60    # vibration
    power_critical: float = 0.70     # battery
    att_caution: float = 0.82        # max(imu0, imu1); single-IMU-fault
                                     # worst case measures 0.86 — margin 0.04
    att_emergency: float = 0.70      # max(imu0, imu1)
    imu_isolation_gap: float = 0.12  # |T_imu0 - T_imu1| to prefer one unit
    dwell_up: float = 1.0            # s a condition must persist to escalate
    dwell_down: float = 5.0          # s of health required to de-escalate
    arm_time: float = 10.0           # s before failsafe arms: ground checks,
                                     # sensor calibration, trust-prior
                                     # convergence — standard pre-arm practice
    descent_rate: float = 1.5        # m/s commanded in EMERGENCY descent


@dataclass
class Transition:
    t: float
    level: FailsafeLevel
    previous: FailsafeLevel
    reasons: list
    actions: list


class FailsafePolicy:
    def __init__(self, config: FailsafeConfig | None = None):
        self.cfg = config or FailsafeConfig()
        self.level = FailsafeLevel.NORMAL
        self.transitions: list[Transition] = []
        self._cond_since: dict[str, float] = {}   # condition -> onset time
        self._issued: set[str] = set()            # conditions already acted on
        self._below_since: float | None = None    # de-escalation hysteresis
        self._selected_imu: str | None = None
        self._ever_fresh: set[str] = set()        # sensors seen delivering data

    # --- condition evaluation ---------------------------------------------------

    def _conditions(self, state) -> dict[str, tuple[FailsafeLevel, str, list]]:
        """Active (un-dwelled) conditions: name -> (level, reason, actions)."""
        cfg = self.cfg
        T = state.trust
        fresh = state.fresh
        # A sensor that is not delivering data has NO meaningful trust value
        # (it holds the Bayesian prior). Rules must only reason over sensors
        # actually being monitored — comparing against a frozen prior
        # produced phantom "IMU divergence" alarms on real flight logs.
        imus = [n for n in ("imu0", "imu1") if fresh.get(n)]
        att = max((T[n] for n in imus), default=1.0)
        best_imu = max(imus, key=lambda n: T[n]) if imus else "imu0"
        top = state.top_causes(1)[0]
        diag = f"diagnosis {top[0]} p={top[1]:.2f}"
        out = {}

        if att < cfg.att_emergency:
            out["attitude_lost"] = (FailsafeLevel.EMERGENCY,
                f"attitude reference integrity lost "
                f"(imu0={T['imu0']:.2f}, imu1={T['imu1']:.2f}; {diag})",
                [Action("STABILIZE", "level vehicle on best remaining "
                        "attitude source", {"source": best_imu}),
                 Action("CONTROLLED_DESCENT", "descend at fixed rate to "
                        "ground; do not attempt navigation",
                        {"rate_mps": cfg.descent_rate}),
                 Action("BROADCAST_MAYDAY", "notify GCS of autonomous "
                        "emergency descent", {})])
        elif att < cfg.att_caution:
            out["attitude_degraded"] = (FailsafeLevel.CRITICAL,
                f"attitude confidence degraded (best {att:.2f}; {diag})",
                [Action("PREPARE_LANDING", "end flight soon on our terms", {}),
                 Action("LIMIT_MANEUVERS", "reduce angular-rate demand", {})])

        gap = abs(T["imu0"] - T["imu1"]) if len(imus) == 2 else 0.0
        if gap > cfg.imu_isolation_gap and min(T["imu0"], T["imu1"]) < 0.85 \
                and self._selected_imu != best_imu:
            out["imu_isolated"] = (FailsafeLevel.CAUTION,
                f"IMU divergence isolated to {'imu1' if best_imu == 'imu0' else 'imu0'} "
                f"(imu0={T['imu0']:.2f}, imu1={T['imu1']:.2f}; {diag})",
                [Action("SELECT_IMU", "switch attitude/velocity source to the "
                        "trusted unit", {"use": best_imu})])

        # "was monitored" = the sensor delivered data at some point this
        # run (tracked in update()); a sensor absent from the whole flight
        # must not raise loss-of-data alarms. (Previously inferred from
        # trust != the Beta-prior mean 0.8 — a silent coupling that broke
        # if EngineConfig's prior changed.)
        gps_was_monitored = "gps" in self._ever_fresh
        if (T["gps"] < cfg.nav_caution and fresh.get("gps")) or \
                (not fresh.get("gps", True) and gps_was_monitored):
            why = "GPS data invalid" if not fresh.get("gps", True) \
                else f"GPS trust {T['gps']:.2f}"
            out["nav_degraded"] = (FailsafeLevel.CAUTION,
                f"{why} ({diag})",
                [Action("SWITCH_NAV_INERTIAL", "hold position on IMU+baro "
                        "dead-reckoning; expect drift", {}),
                 Action("INHIBIT_GPS_MODES", "block GPS-guided modes "
                        "(RTL/waypoint) until trust recovers", {})])

        if T["battery"] < cfg.power_critical and fresh.get("battery"):
            out["power_fault"] = (FailsafeLevel.CRITICAL,
                f"power integrity fault (battery {T['battery']:.2f}; {diag})",
                [Action("REDUCE_POWER", "lower speed/climb demand", {}),
                 Action("LAND_NOW", "land at nearest safe location", {})])

        if T["vibration"] < cfg.struct_critical and fresh.get("vibration"):
            out["structural"] = (FailsafeLevel.CRITICAL,
                f"structural vibration anomaly (trust "
                f"{T['vibration']:.2f}; {diag})",
                [Action("LIMIT_THROTTLE", "reduce rotor loading", {}),
                 Action("LAND_SOON", "land before damage propagates", {})])

        if T["mag"] < cfg.heading_caution and fresh.get("mag"):
            out["heading_degraded"] = (FailsafeLevel.CAUTION,
                f"magnetometer untrusted (mag {T['mag']:.2f}; {diag})",
                [Action("HEADING_HOLD_GYRO", "hold heading on gyro "
                        "integration; inhibit mag fusion", {})])
        return out

    # --- state machine ----------------------------------------------------------

    def update(self, state) -> list[Action]:
        """Feed one TrustState; returns actions issued this tick.

        A condition's actions are issued exactly once, when it has persisted
        for dwell_up (re-issued only if it clears and returns). The level is
        the max over dwelled-in conditions; escalation is immediate once
        dwelled, de-escalation requires dwell_down of the target holding."""
        cfg = self.cfg
        t = state.t
        # track data delivery even pre-arm, so a sensor that dies during
        # ground checks still counts as "was monitored" once armed
        for n, ok in state.fresh.items():
            if ok:
                self._ever_fresh.add(n)
        if t < cfg.arm_time:   # not armed: calibration + prior convergence
            return []
        conds = self._conditions(state)

        for name in list(self._cond_since):     # conditions that cleared
            if name not in conds:
                del self._cond_since[name]
                self._issued.discard(name)
        for name in conds:
            self._cond_since.setdefault(name, t)
        active = {name: c for name, c in conds.items()
                  if t - self._cond_since[name] >= cfg.dwell_up}

        issued: list[Action] = []
        for name, (_, reason, actions) in active.items():
            if name not in self._issued:
                self._issued.add(name)
                issued.extend(actions)

        target = max((c[0] for c in active.values()),
                     default=FailsafeLevel.NORMAL)
        if target > self.level:
            self._below_since = None
            self._transition(t, target,
                             [c[1] for c in active.values()], issued)
        elif target < self.level:
            if self._below_since is None:
                self._below_since = t
            if t - self._below_since >= cfg.dwell_down:
                self._below_since = None
                recover = [Action("RESUME_NORMAL", "restore nominal modes",
                                  {})] if target == FailsafeLevel.NORMAL else []
                issued.extend(recover)
                self._transition(
                    t, target,
                    [c[1] for c in active.values()]
                    or ["all monitored conditions recovered"], recover)
        else:
            self._below_since = None

        for a in issued:
            if a.name == "SELECT_IMU":
                self._selected_imu = a.params["use"]
        return issued

    def _transition(self, t, level, reasons, actions):
        prev = self.level
        self.level = level
        self.transitions.append(Transition(t, level, prev, reasons, actions))
        log.warning("failsafe %s -> %s @ t=%.1fs: %s",
                    prev.name, level.name, t, "; ".join(reasons) or "-")
