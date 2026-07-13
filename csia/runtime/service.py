"""TrustLayerRuntime: source plugin -> online trust layer -> failsafe -> actuators.

This is the deployable composition. On the SOW001 stack it runs on the Pi 5
companion: MavlinkSource in, per-tick TrustState out, failsafe actions to a
MAVLink actuator (opt-in) and/or the GCS. On the bench it runs the same code
against SimulatedFlightSource, optionally paced to wall-clock real time.
"""

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field

from .failsafe import Action, FailsafeLevel, FailsafePolicy
from .online import OnlineTrustLayer, TrustState
from .plugins import SourcePlugin

log = logging.getLogger(__name__)


class Actuator(ABC):
    """Executes (or records) failsafe actions."""

    @abstractmethod
    def execute(self, action: Action, state: TrustState):
        ...


class LoggingActuator(Actuator):
    """Default: advisory only. Records and logs every action."""

    def __init__(self):
        self.executed: list[tuple[float, Action]] = []

    def execute(self, action: Action, state: TrustState):
        self.executed.append((state.t, action))
        log.warning("ACTION t=%.1fs %s %s — %s",
                    state.t, action.name, action.params or "", action.reason)


class MavlinkActuator(Actuator):  # pragma: no cover - needs hardware
    """Sends failsafe actions to an autopilot over MAVLink. OPT-IN and
    EXPERIMENTAL: mode strings target ArduPilot; validate in SITL first.
    This prototype makes no airworthiness claims."""

    MODE_FOR_ACTION = {
        "CONTROLLED_DESCENT": "LAND",
        "LAND_NOW": "LAND",
        "LAND_SOON": "RTL",
        "SWITCH_NAV_INERTIAL": "ALT_HOLD",
    }

    def __init__(self, conn: str, enable_commands: bool = False):
        from pymavlink import mavutil
        self.m = mavutil.mavlink_connection(conn)
        self.m.wait_heartbeat(timeout=5.0)
        self.enable_commands = enable_commands

    def execute(self, action: Action, state: TrustState):
        mode = self.MODE_FOR_ACTION.get(action.name)
        self.m.mav.statustext_send(
            6, f"CSIA {action.name}: {action.reason[:40]}".encode())
        if mode and self.enable_commands:
            log.warning("MAVLink: commanding mode %s (%s)", mode, action.name)
            self.m.set_mode(mode)
        elif mode:
            log.warning("MAVLink: advisory only — would command %s", mode)


@dataclass
class RunSummary:
    scenario: str
    ticks: int
    final_level: str
    transitions: list
    min_trust: dict
    actions: list
    mean_latency_us: float
    states: list = field(default_factory=list, repr=False)


class TrustLayerRuntime:
    def __init__(self, source: SourcePlugin,
                 layer: OnlineTrustLayer | None = None,
                 policy: FailsafePolicy | None = None,
                 actuators: list | None = None,
                 realtime: bool = False, speed: float = 1.0,
                 log_path: str | None = None,
                 keep_states: bool = False,
                 profile=None):
        self.source = source
        self.profile = profile
        self.layer = layer or OnlineTrustLayer(profile=profile)
        self.policy = policy or FailsafePolicy(
            profile.failsafe if profile else None)
        self.actuators = actuators if actuators is not None \
            else [LoggingActuator()]
        self.realtime = realtime
        self.speed = speed
        self.log_path = log_path
        self.keep_states = keep_states
        self.listeners = []   # callables(state, actions)

    def run(self) -> RunSummary:
        states_kept = []
        min_trust = {}
        n_ticks = 0
        lat_sum = 0.0
        wall0 = time.monotonic()
        t_last = 0.0
        fh = open(self.log_path, "w") if self.log_path else None
        try:
            for sensor, t, channels in self.source.samples():
                if self.realtime:
                    lag = t / self.speed - (time.monotonic() - wall0)
                    if lag > 0:
                        time.sleep(lag)
                for state in self.layer.ingest(sensor, t, channels):
                    self._handle(state, min_trust, states_kept, fh)
                    n_ticks += 1
                    lat_sum += state.latency_us
                t_last = t
            for state in self.layer.flush(t_last):
                self._handle(state, min_trust, states_kept, fh)
                n_ticks += 1
                lat_sum += state.latency_us
        finally:
            if fh:
                fh.close()
            self.source.stop()

        return RunSummary(
            scenario=getattr(self.source, "scenario", "live"),
            ticks=n_ticks,
            final_level=self.policy.level.name,
            transitions=self.policy.transitions,
            min_trust={k: round(v, 3) for k, v in min_trust.items()},
            actions=[(round(t, 2), a.name) for act in self.actuators
                     if isinstance(act, LoggingActuator)
                     for t, a in act.executed],
            mean_latency_us=lat_sum / max(n_ticks, 1),
            states=states_kept)

    def _handle(self, state: TrustState, min_trust, states_kept, fh):
        actions = self.policy.update(state)
        for a in actions:
            for actuator in self.actuators:
                actuator.execute(a, state)
        for cb in self.listeners:
            cb(state, actions)
        for n, v in state.trust.items():
            if state.t > 10.0:   # after prior convergence
                min_trust[n] = min(min_trust.get(n, 1.0), v)
        if self.keep_states:
            states_kept.append(state)
        if fh:
            fh.write(json.dumps({
                "t": round(state.t, 3),
                "level": self.policy.level.name,
                "trust": {k: round(v, 4) for k, v in state.trust.items()},
                "diagnosis": {k: round(v, 4) for k, v in
                              state.posterior.items() if v > 0.01},
                "actions": [asdict(a) for a in actions],
            }) + "\n")


class LiveFeed:
    """Thread-safe rolling window of TrustStates, exported in the same JSON
    shape as a replay so the dashboard renders live data with zero special
    cases. window_s of history is kept (default: the whole 60 s pattern)."""

    def __init__(self, window_s: float = 60.0, tick_hz: float = 25.0,
                 title: str = "LIVE"):
        self._states = deque(maxlen=int(window_s * tick_hz) + 4)
        self._lock = threading.Lock()
        self._level = "NORMAL"
        self.title = title
        import networkx as nx
        from ..trust_graph import build_trust_graph
        g = build_trust_graph()
        self._sensors = list(g.nodes)
        self._layout = {n: [round(float(x), 4), round(float(y), 4)]
                        for n, (x, y) in
                        nx.spring_layout(g, seed=7, k=1.6).items()}
        self._edge_meta = None
        self._causes = None

    def push(self, state: TrustState, level_name: str):
        with self._lock:
            # a timestamp going backwards means the source restarted (looped
            # scenario / vehicle reboot): stale history would render as
            # overlapping passes — drop it.
            if self._states and state.t < self._states[-1].t:
                self._states.clear()
            self._states.append(state)
            self._level = level_name
            if self._causes is None:
                self._causes = list(state.posterior)

    def clear(self):
        with self._lock:
            self._states.clear()

    def doc(self) -> dict | None:
        with self._lock:
            states = list(self._states)
            level = self._level
        if len(states) < 3:
            return None
        r4 = lambda v: round(float(v), 4)
        sensors = self._sensors
        causes = self._causes
        from .online import OnlineTrustLayer as _O
        meta = self._edge_meta
        if meta is None:
            meta = self._edge_meta = _O()._edge_meta
        edge_keys = list(states[0].edges)
        return {
            "name": "live",
            "title": f"{self.title} — failsafe {level}",
            "t": [r4(s.t) for s in states],
            "sensors": sensors,
            "trust": {n: [r4(s.trust[n]) for s in states] for n in sensors},
            "components": {comp: {n: [(-1.0 if s.components[n][comp] is None
                                       else r4(s.components[n][comp]))
                                      for s in states] for n in sensors}
                           for comp in ("nbr", "phys", "temp", "stat")},
            "edges": [{"key": k, "a": meta[k][0], "b": meta[k][1],
                       "c": [r4(s.edges[k][0]) for s in states],
                       "gate": [r4(s.edges[k][1]) for s in states]}
                      for k in edge_keys],
            "diagnosis": {"causes": causes,
                          "posterior": [[r4(s.posterior[c]) for c in causes]
                                        for s in states]},
            "aux": {"speed_gate": [r4(s.edges["heading_course"][1])
                                   for s in states]},
            "faults": [],
            "layout": self._layout,
            "latency_us": {
                "mean": r4(sum(s.latency_us for s in states) / len(states)),
                "p95": r4(sorted(s.latency_us for s in states)[
                    int(0.95 * (len(states) - 1))])},
        }


def run_service(scenario: str = "clean", port: int = 8017,
                replay_dir: str | None = None, speed: float = 1.0,
                profile=None, loop: bool = True):
    """The single-command product: real-time runtime + dashboard + live feed.

    Runs the trust layer against the named scenario in wall-clock real time
    (looping so the live view always moves), while serving the dashboard —
    replays AND the /data/live.json feed — on the same port. On a vehicle,
    swap SimulatedFlightSource for MavlinkSource and drop --loop.
    """
    from ..dashboard.serve import serve
    from .plugins import SimulatedFlightSource

    feed = LiveFeed(title=f"LIVE runtime — scenario {scenario}, "
                          f"advisory failsafe")

    def _worker():
        while True:
            feed.clear()
            runtime = TrustLayerRuntime(
                SimulatedFlightSource(scenario), realtime=True, speed=speed,
                profile=profile)
            runtime.listeners.append(
                lambda st, _a: feed.push(st, runtime.policy.level.name))
            summary = runtime.run()
            log.info("live pass complete: final %s, %d ticks",
                     summary.final_level, summary.ticks)
            if not loop:
                return

    thread = threading.Thread(target=_worker, daemon=True,
                              name="csia-live-runtime")
    thread.start()
    serve(port=port, replay_dir=replay_dir, live=feed.doc)
