"""Shadow-mode runner: observe, log, advise. No authority, ever.

Pipeline, one direction only:

    vehicle telemetry
      -> ReadOnlyMavlinkConnection      (transmit surface denied)
      -> PlatformAdapter                (canonical units + qualification)
      -> AircraftSample                 (explicit validity metadata)
      -> OnlineTrustLayer               (FROZEN v1 -- unmodified)
      -> FailsafePolicy                 (evaluated for RECOMMENDATIONS only)
      -> FlightLog                      (deterministic S9 record)

There is no arrow back. `FailsafePolicy.update()` returns `Action` objects and
this module writes them to a log and, optionally, hands them to an external
consumer callback. It never converts one into a MAVLink message. The guard
makes that structurally impossible rather than merely true today.

Failure posture, in one line each:

  telemetry lost      -> channels go STALE, the layer abstains, ticks continue
  CSIA process dies   -> nothing happens to the aircraft; nothing is connected
  log write fails     -> counted, dropped, flight continues
  autopilot reboots   -> source time jumps; the monotonic clock does not
"""

from __future__ import annotations

import enum
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..aircraft.adapters import get_adapter
from ..runtime.failsafe import FailsafePolicy
from ..runtime.online import OnlineTrustLayer
from ..v1_1.staleness import build_runtime_stale_timeouts
from .flight_log import FlightLog, make_header
from .guard import (CommandAuthorityError, ReadOnlyMavlinkConnection,
                    assert_no_command_capability)

log = logging.getLogger(__name__)


class Mode(enum.Enum):
    """Deployment modes, ordered by authority. Only two exist so far.

    ADVISORY differs from SHADOW only in that recommendations are surfaced to
    an operator. Neither can command. There is deliberately no `ACTIVE` member:
    adding one is a separate safety work package, and an enum value is exactly
    the kind of thing that gets used before its safety case exists.
    """

    SHADOW = "SHADOW"
    ADVISORY = "ADVISORY"

    @property
    def may_command(self) -> bool:
        return False


@dataclass
class ShadowConfig:
    platform: str = "ardupilot"
    connection: str = "udp:127.0.0.1:14550"
    mode: Mode = Mode.SHADOW
    tick_hz: float = 25.0
    log_dir: str = "logs/shadow"
    profile: str = "FIELD_DERIVED_NOISE"
    field_mode: bool = True
    max_runtime_s: Optional[float] = None
    watchdog_timeout_s: float = 5.0
    autopilot_version: str = "unknown"
    vehicle_config: dict = field(default_factory=dict)
    log_max_bytes: int = 64 * 1024 * 1024
    heartbeat_timeout_s: float = 10.0
    # ONE ROW PER ENGINE STEP, not per shadow tick. Optional, off by default.
    #
    # The flight log records `states[-1]` -- the LAST engine state of each
    # shadow tick (see `_tick`). That is the right thing for "what did CSIA
    # conclude at this instant", and it is NOT sufficient to reconstruct a
    # recursion: whenever tick jitter fires two engine steps inside one shadow
    # tick, the first step's evidence and rho are gone, and a reconstruction
    # from the log alone would silently skip an update. Whenever it fires
    # none, the log records an empty trust dict.
    #
    # So a Mechanism B run writes its own trace. It is not a second flight
    # log: it carries only the recursion's own quantities, and it is written
    # AFTER the per-tick latency measurement stops, so tracing cannot inflate
    # the number R13 is judged on.
    trust_trace_path: Optional[str] = None
    # LOSS-OF-DATA SUPERVISION (SR-001 / SR-003). OFF BY DEFAULT, ON PURPOSE.
    #
    # The frozen failsafe alarms when a sensor's TRUST falls and says nothing
    # when the sensor stops delivering -- for seven of the eight nodes. The
    # overlay in `csia_supervision` supplies the missing rule and can only
    # RAISE the level, never lower it (effective = max(frozen, supervisor)).
    #
    # It defaults to False because shadow mode PRODUCES EVIDENCE. Turning it
    # on silently would mean logs recorded before and after this change
    # describe different systems while claiming the same mode, and nothing in
    # the log would say which. So it is an explicit choice, and the flight
    # log header records which policy was in force (`failsafe_policy`).
    data_loss_supervision: bool = False


class ShadowRunner:
    """Owns the loop. Holds no send-capable object at any point."""

    def __init__(self, cfg: ShadowConfig,
                 consumer: Optional[Callable] = None,
                 connection_factory: Optional[Callable] = None):
        if cfg.mode.may_command:                       # pragma: no cover
            raise CommandAuthorityError(
                "ShadowRunner refuses any mode claiming command authority")
        self.cfg = cfg
        self.consumer = consumer
        self._connection_factory = connection_factory
        self.adapter = get_adapter(cfg.platform)
        # Phase 4.5 Gate B. The frozen core's STALE_TIMEOUT_S table has a
        # producer rate baked into a constant; the adapter derives MaxAge per
        # platform from the channel contract. Six of eight nodes disagree, and
        # the live path used to take the frozen defaults while the ULog CLI
        # already passed an override. A `baro` stream at its declared 10 Hz
        # against a 0.10 s watchdog false-staled on 2.8-3.7% of ticks under
        # +/-30% jitter, measured -- see validation/v1_1/deployment/.
        #
        # The override makes the runtime watchdog agree with the ingestion
        # layer that feeds it. It introduces no constant: the rule is
        # `max over required channels of the adapter's own MaxAge`.
        # The FROZEN core is not modified; it already accepts this argument.
        self.stale_timeouts = build_runtime_stale_timeouts(cfg.platform)
        self.layer = OnlineTrustLayer(tick_hz=cfg.tick_hz,
                                      field_mode=cfg.field_mode,
                                      stale_timeout_s=self.stale_timeouts)
        # The FROZEN policy either way. With supervision on it is WRAPPED,
        # never replaced: `SupervisedFailsafe` owns a `FailsafePolicy`,
        # forwards its conditions and dwell timers untouched, and reports
        # max(frozen, overlay) as the level. The frozen decision is always
        # still visible via `.frozen_level`.
        if cfg.data_loss_supervision:
            from csia_supervision import SupervisedFailsafe
            self.policy = SupervisedFailsafe(policy=FailsafePolicy())
        else:
            self.policy = FailsafePolicy()
        self.conn = None
        self.flight_log: Optional[FlightLog] = None
        self.authority_evidence: dict = {}
        self.stats = {"ticks": 0, "messages": 0, "stale_ticks": 0,
                      "max_latency_us": 0.0, "watchdog_trips": 0,
                      "reconnects": 0}
        # Per-tick latency, for a DISTRIBUTION rather than a mean. A mean
        # hides the tail and the tail is what misses a deadline. Bounded by a
        # ring buffer: "no unbounded queues" is an acceptance criterion, and a
        # 12-hour flight at 25 Hz would otherwise retain a million floats.
        # `max_latency_us` is kept separately and covers the whole flight, so
        # nothing is lost when the ring wraps.
        self.tick_latencies = deque(maxlen=100_000)
        # Where the tick time goes, split three ways. Same bound and
        # the same reason as tick_latencies.
        self.phase_us = {k: deque(maxlen=100_000)
                         for k in ("sample", "convert", "core")}
        self._running = False
        self._last_msg_mono = None
        self._trace_fh = None
        self._trace_rows = 0
        self._trace_errors = 0

    # ------------------------------------------------------------------
    def _trace_open(self):
        if not self.cfg.trust_trace_path:
            return
        path = self.cfg.trust_trace_path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._trace_fh = open(path, "w", encoding="utf-8")
        # The reconstruction has to know the constants it is NOT allowed to
        # fit, and it has to read them from the engine that produced the run
        # rather than from a copy in the analysis tool.
        cfg = self.layer.core.cfg
        self._trace_write({
            "record": "trace_header",
            "engine_config": {
                "w_nbr": cfg.w_nbr, "w_phys": cfg.w_phys,
                "w_temp": cfg.w_temp, "w_stat": cfg.w_stat,
                "rho_max": cfg.rho_max, "rho_min": cfg.rho_min,
                "alpha0": cfg.alpha0, "beta0": cfg.beta0,
            },
            "tick_hz": self.cfg.tick_hz,
            "field_mode": self.cfg.field_mode,
            "note": "one row per ENGINE STEP; the flight log keeps only the "
                    "last step of each shadow tick and cannot reconstruct a "
                    "recursion",
        })

    def _trace_write(self, row: dict):
        if self._trace_fh is None:
            return
        try:
            self._trace_fh.write(json.dumps(row, separators=(",", ":"),
                                            default=str) + "\n")
        except (OSError, TypeError, ValueError):
            self._trace_errors += 1

    # Edges incident on the `gps` node. Traced in full (consistency AND gate
    # weight) because the preregistered per-tick schema wants
    # `gate_applicable`, and the GPS gate IS `gvalid` -- the quantity whose
    # staying at 1 is the difference between a Mechanism B trial and a
    # Mechanism A trial. Restricted to these four so a 1500-tick trace stays
    # a few MB rather than tens.
    TRACE_EDGES = ("altitude_baro", "velocity_gps_doppler_0",
                   "velocity_gps_doppler_1", "heading_course")

    def _trace_states(self, fired: list, policy_row=None):
        """Record every engine step of this shadow tick.

        `fired` carries (state, S) pairs captured inside the ingest loop -- S
        has to be read there because alpha/beta advance on every step, so a
        single read afterwards would attribute the last step's S to all of
        them. The capture is a handful of float adds and only happens when
        tracing is on.

        NOTHING IS ROUNDED. The declared reconstruction tolerance is 1e-6, and
        storage rounding must not be allowed to eat any part of that budget:
        at 9 decimals the earlier probe's reconstruction floor was 6e-10,
        inside tolerance but for a reason that has nothing to do with the
        recursion. json.dumps writes shortest-round-trip repr, so the trace
        holds exactly the float the engine computed.

        `policy_row` belongs to the LAST state of the tick only -- that is the
        one the failsafe was actually updated with.
        """
        last = len(fired) - 1
        for i, (state, S) in enumerate(fired):
            row = {
                "record": "step",
                "t": state.t,
                "trust": {n: float(v) for n, v in state.trust.items()},
                "evidence": {n: float(v) for n, v in state.evidence.items()},
                "components": {n: {c: (None if v is None else float(v))
                                   for c, v in comp.items()}
                               for n, comp in state.components.items()},
                "fresh": {n: bool(v) for n, v in state.fresh.items()},
                "S": (None if S is None else
                      {n: float(v) for n, v in S.items()}),
                "armed": state.armed,
                "edges": {k: [float(state.edges[k][0]), float(state.edges[k][1])]
                          for k in self.TRACE_EDGES if k in state.edges},
            }
            if i == last and policy_row is not None:
                row["policy"] = policy_row
            self._trace_write(row)
            self._trace_rows += 1

    def _policy_row(self, state):
        """Failsafe conditions, dwell timers and level, for the trace.

        Read straight off the FROZEN FailsafePolicy after it has been updated
        with this tick's state -- never recomputed by a copy here, because a
        copy is a second implementation and would be the thing under test.
        """
        if state is None:
            return None
        try:
            conds = sorted(self.policy._conditions(state))
        except Exception:                                  # pragma: no cover
            conds = None
        since = getattr(self.policy, "_cond_since", None)
        row = {
            "conditions": conds,
            # dwell: how long each active condition has been held. The
            # failsafe DELETES the entry when a condition clears, so an
            # absent key is itself the measurement.
            "dwell_since": (None if not isinstance(since, dict)
                            else {k: float(v) for k, v in since.items()}),
            "level": (self.policy.level.name
                      if hasattr(self.policy, "level") else None),
        }
        # With supervision on, `level` above is the EFFECTIVE level. Record
        # the frozen policy's own level beside it, so a reader can always
        # separate what the frozen core decided from what the overlay added.
        if hasattr(self.policy, "frozen_level"):
            row["frozen_level"] = self.policy.frozen_level.name
            data_loss = self.policy.data_loss_row()
            if data_loss is not None:
                row["data_loss"] = data_loss
        return row

    # ------------------------------------------------------------------
    def connect(self):
        """Open the link and prove we cannot transmit before ticking."""
        if self._connection_factory is not None:
            raw = self._connection_factory()
        else:                                          # pragma: no cover
            from pymavlink import mavutil
            # input=True binds a listening socket rather than dialling out.
            raw = mavutil.mavlink_connection(self.cfg.connection, input=True)
        self.conn = ReadOnlyMavlinkConnection(raw, mode=self.cfg.mode.value)
        self.authority_evidence = assert_no_command_capability(
            self.conn, mode=self.cfg.mode.value)
        log.info("%s mode: %s (%d probes, write_half_closed=%s)",
                 self.cfg.mode.value, self.authority_evidence["result"],
                 self.authority_evidence["checked"],
                 self.authority_evidence.get("write_half_closed"))
        return self.conn

    def _open_log(self):
        header = make_header(
            adapter=self.adapter,
            mode=self.cfg.mode.value,
            autopilot_version=self.cfg.autopilot_version,
            command_authority=self.authority_evidence,
            sensor_availability=self.adapter.status()["channels"],
            profile=self.cfg.profile,
            vehicle_config=self.cfg.vehicle_config,
            failsafe_policy=("FROZEN_PLUS_DATA_LOSS_SUPERVISION"
                             if self.cfg.data_loss_supervision
                             else "FROZEN_ONLY"),
            # The timeouts THIS run used, not the ones a later replay would
            # derive. See HF-014.
            stale_timeout_s=self.stale_timeouts,
        )
        self.flight_log = FlightLog(self.cfg.log_dir, header,
                                    max_bytes=self.cfg.log_max_bytes)
        log.info("flight %s -> %s", header.flight_id, self.cfg.log_dir)
        return header

    # ------------------------------------------------------------------
    def run(self, message_iter=None, clock=time.monotonic):
        """Main loop.

        `message_iter` lets a test or a replay drive the loop without a
        socket; production passes None and messages are pulled from the
        read-only connection.
        """
        if self.conn is None:
            self.connect()
        header = self._open_log()
        self._trace_open()
        self._running = True
        t0 = clock()
        dt = 1.0 / self.cfg.tick_hz
        next_tick = t0

        try:
            src = message_iter if message_iter is not None \
                else self._recv_forever()
            for msg in src:
                if not self._running:
                    break
                if msg is not None:
                    self.adapter.ingest(msg)
                    self.stats["messages"] += 1
                    self._last_msg_mono = clock()
                now = clock()
                if now < next_tick:
                    continue
                next_tick = max(now, next_tick + dt)
                self._tick(now - t0, clock)
                if (self.cfg.max_runtime_s is not None
                        and now - t0 >= self.cfg.max_runtime_s):
                    break
        finally:
            self._running = False
            if self._trace_fh is not None:
                self._trace_write({"record": "trace_footer",
                                   "steps": self._trace_rows,
                                   "write_errors": self._trace_errors})
                try:
                    self._trace_fh.close()
                except OSError:
                    pass
                self._trace_fh = None
            if self.flight_log is not None:
                self.flight_log.close({"stats": self.stats})
            if self.conn is not None:
                try:
                    self.conn.close()
                except Exception:
                    pass
        return header

    def _recv_forever(self):                           # pragma: no cover
        while self._running:
            try:
                yield self.conn.recv_match(blocking=True, timeout=1.0)
            except CommandAuthorityError:
                raise
            except Exception as exc:
                log.warning("receive error: %s", exc)
                self.stats["reconnects"] += 1
                yield None

    # ------------------------------------------------------------------
    def _tick(self, t_rel: float, clock):
        # Phase timing, because "the tick is slow" is not an actionable fact.
        # A companion-profile run cut the message count 36% and moved the
        # median by 2%, which ruled out message volume; the next guess would
        # have been wrong too without splitting the tick up.
        t_wall0 = time.perf_counter()
        sample = self.adapter.sample(t_mono=t_rel)
        t_sample = time.perf_counter()

        core_samples = self.adapter.to_core_samples(sample)
        t_convert = time.perf_counter()

        # Feed the FROZEN core. Only admissible channels are in the sample,
        # so a stub cannot become evidence -- and no v1 code changed to make
        # that true.
        state = None
        fired = [] if self._trace_fh is not None else None
        core = self.layer.core
        for sensor, t, chans in core_samples:
            states = self.layer.ingest(sensor, t, chans)
            if states:
                state = states[-1]
                if fired is not None:
                    # alpha/beta advance on EVERY engine step, and `ingest`
                    # has already run all of this batch's steps by the time
                    # it returns. So the S read here belongs to the LAST
                    # state only; the earlier ones get None rather than a
                    # value that is not theirs. The reconstruction does not
                    # need runtime S -- this is a cross-check, and a
                    # cross-check that quietly mislabels its own data is
                    # worse than one with fewer points.
                    S = {n: core.alpha[n] + core.beta[n] for n in state.trust}
                    for s in states[:-1]:
                        fired.append((s, None))
                    fired.append((state, S))

        t_core = time.perf_counter()
        latency_us = (t_core - t_wall0) * 1e6
        self.phase_us["sample"].append((t_sample - t_wall0) * 1e6)
        self.phase_us["convert"].append((t_convert - t_sample) * 1e6)
        self.phase_us["core"].append((t_core - t_convert) * 1e6)
        self.stats["ticks"] += 1
        self.stats["max_latency_us"] = max(self.stats["max_latency_us"],
                                           latency_us)
        self.tick_latencies.append(latency_us)

        watchdog_tripped = False
        if self._last_msg_mono is not None:
            gap = clock() - self._last_msg_mono
            if gap > self.cfg.watchdog_timeout_s:
                watchdog_tripped = True
                self.stats["watchdog_trips"] += 1

        actions, level, reasons = [], "NORMAL", []
        if state is not None:
            actions = self.policy.update(state) or []
            level = self.policy.level.name if hasattr(
                self.policy, "level") else "NORMAL"
            reasons = [getattr(a, "reason", "") for a in actions]

        # AFTER the measured region closed at t_core, so tracing cannot
        # inflate the number R13 is judged on, and AFTER the policy update,
        # so the failsafe conditions, dwell timers and level recorded are the
        # ones this tick actually reached rather than the previous tick's.
        if fired:
            self._trace_states(fired, self._policy_row(state))

        if not sample.usable_channels():
            self.stats["stale_ticks"] += 1

        recommendation = {
            "level": level,
            "actions": [getattr(a, "name", str(a)) for a in actions],
            "params": [getattr(a, "params", {}) for a in actions],
            "reasons": reasons,
            "authority": "NONE",
            "mode": self.cfg.mode.value,
        }

        est = sample.estimator_health.get("estimator.variances")
        autopilot = {
            "flight_mode": sample.flight_mode,
            "estimator": (est.value if est is not None and est.value else None),
            "failsafe_active": bool(sample.flight_mode in
                                    ("LAND", "RTL", "AUTO.LAND", "AUTO.RTL")),
            "armed": self._armed(sample),
        }

        if self.flight_log is not None:
            self.flight_log.tick(
                t_mono=t_rel, sample=sample,
                trust_pre={}, trust_post=(state.trust if state else {}),
                residuals=(state.components if state else {}),
                gates=({k: list(v) for k, v in state.edges.items()}
                       if state else {}),
                evidence=(state.evidence if state else {}),
                diagnosis=self._diagnosis(state),
                ambiguity=self._ambiguity(state),
                recommendation=recommendation,
                autopilot=autopilot,
                latency_us=latency_us,
                extra={"watchdog_tripped": watchdog_tripped},
                # The layer's own freshness verdict. Not derivable from any
                # other field: the gate weights are PRODUCTS of freshness
                # terms and cannot be factored back apart (HF-014).
                fresh=(dict(state.fresh) if state is not None
                       and getattr(state, "fresh", None) else None),
            )

        if self.consumer is not None and self.cfg.mode is Mode.ADVISORY:
            # The consumer receives a plain dict. It is given no connection,
            # no adapter and no send-capable object of any kind.
            try:
                self.consumer(dict(recommendation), t_rel)
            except Exception as exc:
                log.warning("advisory consumer raised: %s", exc)

    @staticmethod
    def _armed(sample):
        cv = sample.navigation_state.get("vehicle_status.armed")
        return None if cv is None or not cv.usable else bool(cv.value)

    @staticmethod
    def _diagnosis(state):
        if state is None:
            return {"top": None, "posterior": {}}
        top = state.top_causes(3)
        return {"top": top[0][0] if top else None,
                "posterior": {k: round(float(v), 6)
                              for k, v in state.posterior.items()}}

    @staticmethod
    def _ambiguity(state):
        """Margin between the top two hypotheses.

        Reported because W-2 (misattribution) means a confident-looking top
        cause is not the same as a well-separated one, and a post-flight
        reader needs to see which it was.
        """
        if state is None:
            return None
        top = state.top_causes(2)
        if len(top) < 2:
            return None
        return round(float(top[0][1] - top[1][1]), 6)

    def stop(self):
        self._running = False


def env_mode() -> Mode:
    """CSIA_MODE from the environment, defaulting to the safest value.

    An unrecognised value is an error rather than a fallback: silently
    downgrading a typo to SHADOW would be safe, but silently *upgrading* one
    is the failure this refuses to make possible, so neither is allowed.
    """
    raw = os.environ.get("CSIA_MODE", "SHADOW").strip().upper()
    try:
        return Mode(raw)
    except ValueError:
        raise ValueError(
            f"CSIA_MODE={raw!r} is not a deployment mode. "
            f"Valid: {[m.value for m in Mode]}. There is no mode with "
            f"command authority.")
