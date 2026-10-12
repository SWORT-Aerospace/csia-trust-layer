"""Fault injector: the host driver, and a simulated backend that says so.

PROTOCOL
    hardware/validation_rig/FAULT_INJECTOR_PROTOCOL.md (v0.1)

TWO BACKENDS, AND ONLY ONE OF THEM EXISTS
------------------------------------------
`SimulatedInjector` implements the wire protocol in process, with no device. It
is here so the orchestrator, the adjudication path and the trial-record shape
can be built and tested before hardware arrives.

`SerialInjector` is the real one, and it **refuses to construct**: no board has
been purchased (`USER_ACTION_REQUIRED.md` §D). A driver that opened a port and
returned plausible readings would produce E3 confirmations from nothing, and
they would be indistinguishable from measurements everywhere downstream.

THE ONE THING THIS FILE IS FOR
-------------------------------
`confirmed`. Everything else in the protocol is plumbing around a single
question: did the fault actually happen, measured downstream, or did a command
merely return success?

The simulated backend therefore carries `simulated: true` on every response and
`admissible_as_evidence: False` on every trial record it contributes to. Its
`confirmed: true` is a mock of a measurement. Reading it as evidence is exactly
the failure the protocol was written to prevent.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

PROTOCOL_VERSION = "0.1"

ERRORS = ("UNKNOWN_CHANNEL", "NOT_ARMED", "ALREADY_IN_STATE",
          "MEASURE_FAILED", "ACTUATION_FAILED", "PROTO_MISMATCH")


class InjectorError(RuntimeError):
    pass


@dataclass
class LineState:
    """What a measurement of a physical line returns."""

    continuity: bool = True
    line_mv: int = 3300
    activity_hz: float = 10.0

    def to_dict(self) -> dict:
        return {"continuity": self.continuity, "line_mv": self.line_mv,
                "activity_hz": self.activity_hz}


@dataclass
class SimulatedInjector:
    """The protocol, in process, honest about being a mock.

    `can_measure=False` models the injector this protocol most wants to catch:
    one that actuates and cannot confirm. It returns `confirmed: null`, NEVER
    `confirmed: true`, and a trial built on it must adjudicate
    INVALID_SCENARIO.
    """

    channels: tuple = ("gnss_uart", "imu1_spi_cs", "esc_telem")
    can_measure: bool = True
    armed: bool = False
    _token: Optional[str] = None
    _expires: float = 0.0
    _seq: int = 0
    _state: dict = field(default_factory=dict)
    _log: list = field(default_factory=list)

    def __post_init__(self):
        for channel in self.channels:
            self._state.setdefault(channel, LineState())

    # ------------------------------------------------------------- transport
    def send(self, command: dict) -> dict:
        """One line in, one line out -- the same shape as the serial link."""
        response = self._dispatch(command)
        response["seq"] = command.get("seq")
        response["simulated"] = True
        self._log.append((command, response))
        return response

    def send_line(self, line: str) -> str:
        return json.dumps(self.send(json.loads(line)))

    # -------------------------------------------------------------- commands
    def _dispatch(self, command: dict) -> dict:
        cmd = command.get("cmd")
        if cmd == "hello":
            return {"ok": True, "fw": "SIMULATED", "proto": PROTOCOL_VERSION,
                    "channels": list(self.channels),
                    "capabilities": ["cut", "restore"]
                                    + (["measure"] if self.can_measure else []),
                    "warning": ("SIMULATED INJECTOR -- no device. Every "
                                "confirmation below is a mock of a "
                                "measurement, not a measurement.")}
        if cmd == "arm":
            self.armed = True
            self._token = command.get("token")
            self._expires = time.monotonic() + float(command.get("ttl_s", 300))
            return {"ok": True, "armed": True, "token": self._token}
        if cmd == "status":
            return {"ok": True, "armed": self._is_armed(), "faults": [],
                    "channels": {c: {"state": ("PASS" if s.continuity
                                               else "CUT")}
                                 for c, s in self._state.items()}}
        if cmd == "measure":
            return self._measure(command.get("channel"))
        if cmd in ("cut", "restore"):
            return self._actuate(cmd, command.get("channel"))
        return {"ok": False, "error": "PROTO_MISMATCH",
                "detail": f"unknown command {cmd!r}"}

    def _is_armed(self) -> bool:
        return self.armed and time.monotonic() < self._expires

    def _measure(self, channel) -> dict:
        if channel not in self._state:
            return {"ok": False, "error": "UNKNOWN_CHANNEL",
                    "detail": f"no channel {channel!r}; have "
                              f"{sorted(self._state)}"}
        if not self.can_measure:
            return {"ok": False, "error": "MEASURE_FAILED",
                    "detail": "this injector has no measurement capability"}
        state = self._state[channel]
        return {"ok": True, "channel": channel, "t_us": int(time.time() * 1e6),
                **state.to_dict()}

    def _actuate(self, cmd, channel) -> dict:
        if channel not in self._state:
            # NAME WHAT EXISTS. An error that says only "no such channel"
            # sends the operator to guess at a bench, which is where a
            # mistyped channel becomes a cut line on the wrong bus.
            return {"ok": False, "error": "UNKNOWN_CHANNEL",
                    "detail": f"no channel {channel!r}; have "
                              f"{sorted(self._state)}"}
        if not self._is_armed():
            return {"ok": False, "error": "NOT_ARMED",
                    "detail": "arm with a trial token before actuating"}

        before = self._state[channel].to_dict() if self.can_measure else None
        want_cut = (cmd == "cut")
        if self._state[channel].continuity is not want_cut:
            return {"ok": False, "error": "ALREADY_IN_STATE",
                    "detail": f"{channel} is already "
                              f"{'cut' if want_cut else 'passing'}"}

        self._state[channel] = (LineState(False, 12, 0.0) if want_cut
                                else LineState(True, 3300, 10.0))
        after = self._state[channel].to_dict() if self.can_measure else None

        # CONFIRMED IS null, NOT false, WHEN THE LINE CANNOT BE MEASURED.
        # "we could not tell" and "it did not happen" are different facts, and
        # collapsing them is how an unconfirmed injection becomes a detector
        # miss in somebody's results table.
        confirmed = None
        if before is not None and after is not None:
            confirmed = (before["continuity"] != after["continuity"])

        now = int(time.time() * 1e6)
        return {"ok": True, "channel": channel, "commanded_at_us": now,
                "actuated_at_us": now + 41, "before": before, "after": after,
                "confirmed": confirmed}


class SerialInjector:
    """The real driver. Refuses to exist, because the device does not."""

    def __init__(self, *_args, **_kwargs):
        raise InjectorError(
            "the serial fault injector is not implemented, and a driver that "
            "opened a port and returned plausible readings would be worse "
            "than its absence.\n\n"
            "No fault-injection board has been purchased -- see "
            "USER_ACTION_REQUIRED.md section D and "
            "hardware/validation_rig/PURCHASE_JUSTIFICATION.csv. Its "
            "`confirmed: true` would be an E3 confirmation produced from "
            "nothing, indistinguishable from a measurement in every "
            "downstream file.\n\n"
            "The protocol it must implement is specified in "
            "hardware/validation_rig/FAULT_INJECTOR_PROTOCOL.md, and its "
            "acceptance test is written there.")


def injection_record(injector, channel: str, token: str) -> dict:
    """Drive one injection and return it in trial-record shape.

    The record is built so `tools/csia_experiment/validity.py` can adjudicate
    it without knowing which backend produced it -- and so a simulated one can
    never be mistaken for a measured one.
    """
    hello = injector.send({"seq": 1, "cmd": "hello"})
    if hello.get("proto") != PROTOCOL_VERSION:
        raise InjectorError(
            f"injector speaks protocol {hello.get('proto')!r}, host implements "
            f"{PROTOCOL_VERSION!r}. A rig whose responses cannot be "
            f"interpreted must not be armed.")

    baseline = injector.send({"seq": 2, "cmd": "measure", "channel": channel})
    injector.send({"seq": 3, "cmd": "arm", "token": token, "ttl_s": 300})
    cut = injector.send({"seq": 4, "cmd": "cut", "channel": channel})

    simulated = bool(cut.get("simulated"))
    confirmed = cut.get("confirmed")
    return {
        "backend": "simulated_injector" if simulated else "serial_injector",
        "evidence_tier": "E0" if simulated else "E3",
        "admissible_as_evidence": not simulated,
        "admissibility_note": (
            "SIMULATED INJECTOR. Its confirmation is a mock of a measurement "
            "and must never be counted as evidence that a physical fault "
            "occurred." if simulated else None),
        "injection": {"channel": channel, "baseline": baseline,
                      "actuation": cut, "confirmed": confirmed},
        # The evidence chain breaks at the first stage that was not evidenced
        # by a number. An unconfirmed injection is an unproven intervention.
        "first_break": (None if confirmed is True
                        else "SIMULATOR_STATE_CHANGED"),
        "protocol_version": PROTOCOL_VERSION,
    }
