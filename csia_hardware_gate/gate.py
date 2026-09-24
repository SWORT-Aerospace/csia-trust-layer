"""The gate between a requested acquisition mode and what actually runs.

THE FAILURE THIS PREVENTS
-------------------------
A live run is requested, some device constant turns out to be unverified, and
the run quietly proceeds against a fake or a default. The output then looks
like every other run. Nothing in the numbers records that the bytes came from
a model rather than a device, and a later reader has no way to tell -- which is
the same collapse `research/evidence_semantics/` records elsewhere: an absence
turning into a usable value.

So there is no fallback here. A live request that cannot be honoured raises
:class:`HardwareConfigurationBlocked` and the caller stops. Fake and replay are
reachable only by asking for them by name.

THE FIVE TERMINAL STATUSES, AND WHY THEY ARE FIVE
-------------------------------------------------
    VERIFIED_STATIC_CONFIGURATION   every governed constant is VERIFIED. This
                                    is a statement about the configuration on
                                    disk and NOT about any device: no hardware
                                    was touched to earn it.
    FAKE_DRIVER                     a synthetic controller ran, by explicit
                                    request. Says nothing about a device.
    REPLAY                          recorded frames were re-read, by explicit
                                    request. Says nothing about a device now.
    LIVE_HARDWARE_NOT_REACHABLE     the configuration was good enough to try,
                                    and the device did not answer.
    BLOCKED_CONFIGURATION           a live run was refused before any I/O,
                                    because a constant it would have used is
                                    UNVERIFIED or MISSING.

The last two are the pair that matters. Collapsing them into one "live failed"
state would let a configuration defect be read as a missing cable, and the
remedy for those is not the same: one needs a datasheet checked, the other
needs a device plugged in. Neither is ever reported as a success, and none of
the five is ever ``VALIDATED`` -- see :data:`FORBIDDEN_RESULT_STATUSES`.
"""
from __future__ import annotations

import dataclasses
from typing import Optional, Sequence

from .registry import (MISSING, UNVERIFIED, VERIFIED, HardwareConstant,
                       RegistryMalformed, blocking, load_registry)

# -- modes, requested explicitly and never inferred -------------------------

LIVE = "LIVE"
FAKE = "FAKE"
REPLAY_MODE = "REPLAY"

MODES = (LIVE, FAKE, REPLAY_MODE)

# -- terminal statuses ------------------------------------------------------

VERIFIED_STATIC_CONFIGURATION = "VERIFIED_STATIC_CONFIGURATION"
FAKE_DRIVER = "FAKE_DRIVER"
REPLAY = "REPLAY"
LIVE_HARDWARE_NOT_REACHABLE = "LIVE_HARDWARE_NOT_REACHABLE"
BLOCKED_CONFIGURATION = "BLOCKED_CONFIGURATION"

TERMINAL_STATUSES = (VERIFIED_STATIC_CONFIGURATION, FAKE_DRIVER, REPLAY,
                     LIVE_HARDWARE_NOT_REACHABLE, BLOCKED_CONFIGURATION)

#: Statuses that assert a device was exercised and behaved. None of the five
#: is one, and no code path here may emit one. Named so the prohibition is
#: testable rather than a convention somebody remembers.
FORBIDDEN_RESULT_STATUSES = ("VALIDATED", "HARDWARE_VALIDATED", "PASS",
                             "QUALIFIED", "CERTIFIED")

#: No status produced by this package is evidence about a physical device.
HARDWARE_VALIDATED = False


class HardwareConfigurationBlocked(RuntimeError):
    """A live hardware action was refused on configuration grounds.

    Typed, and carrying the offending constants, so a caller can report which
    values need a document rather than printing a sentence. It is deliberately
    NOT a subclass of the simulator's ``BusError`` or of
    ``DatasheetNotVerified``: catching bus faults must not accidentally catch
    a refusal to configure, because a refusal is not a fault to be retried.
    """

    def __init__(self, action: str,
                 constants: Sequence[HardwareConstant] = (),
                 detail: str = "") -> None:
        self.action = action
        self.constants = tuple(constants)
        self.detail = detail
        self.status = BLOCKED_CONFIGURATION
        names = ", ".join(f"{c.name}[{c.status}]" for c in self.constants)
        message = (
            f"refusing to {action}: {len(self.constants)} governed hardware "
            f"constant(s) are not VERIFIED against a hashed primary document"
            + (f" -- {names}" if names else "")
            + ". Nothing was substituted and no fallback was taken. Supply the "
              "document, record its sha256 and the page each value came from "
              "in hardware/constants/E2M_HARDWARE_CONSTANTS.yaml, then re-run. "
              "Fake-driver and replay modes remain available and must be "
              "requested by name.")
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"status": self.status, "action": self.action,
                "detail": self.detail,
                "blocking_constants": [c.as_dict() for c in self.constants]}


@dataclasses.dataclass(frozen=True)
class GateDecision:
    """What the gate permitted, and on what evidence."""

    mode: str
    status: str
    hardware_touched: bool
    blocking_constants: tuple = ()
    detail: str = ""

    def as_dict(self) -> dict:
        return {"mode": self.mode, "status": self.status,
                "hardware_touched": self.hardware_touched,
                "hardware_validated": False,
                "blocking_constants": [c.name for c in self.blocking_constants],
                "detail": self.detail}


def static_configuration_status(constants=None) -> GateDecision:
    """Classify the configuration on disk. Touches no hardware, ever."""
    try:
        constants = load_registry() if constants is None else constants
    except RegistryMalformed as error:
        return GateDecision(
            mode=LIVE, status=BLOCKED_CONFIGURATION, hardware_touched=False,
            detail=f"registry malformed: {error}")

    bad = blocking(constants)
    if bad:
        return GateDecision(mode=LIVE, status=BLOCKED_CONFIGURATION,
                            hardware_touched=False, blocking_constants=bad,
                            detail=f"{len(bad)} constant(s) not VERIFIED")
    return GateDecision(mode=LIVE, status=VERIFIED_STATIC_CONFIGURATION,
                        hardware_touched=False,
                        detail="every governed constant is VERIFIED against a "
                               "hashed document; this says nothing about "
                               "whether a device is present")


def require_live_hardware_permitted(action: str, constants=None) -> None:
    """Raise unless every governed constant is VERIFIED.

    Call this BEFORE opening a port, asserting a reset line, or writing a
    control register -- before any I/O at all, so that a blocked configuration
    cannot half-drive a device and leave it in an unknown state.
    """
    try:
        constants = load_registry() if constants is None else constants
    except RegistryMalformed as error:
        raise HardwareConfigurationBlocked(
            action, (), detail=f"registry malformed: {error}") from error

    bad = blocking(constants)
    if bad:
        raise HardwareConfigurationBlocked(action, bad)


def resolve(mode: str, *, action: str = "initialise live hardware",
            constants=None, probe=None) -> GateDecision:
    """Resolve an EXPLICIT mode request into a terminal decision.

    ``mode`` must be one of :data:`MODES`. There is no default: a caller that
    has not said which it wants has not said whether it is asking about a
    device, and guessing is the failure this module exists to prevent.

    ``probe`` is an optional zero-argument callable used only in LIVE mode,
    after the configuration gate has passed. It returns True when the device
    answered. It is never consulted for FAKE or REPLAY, and a blocked
    configuration never reaches it.
    """
    if mode not in MODES:
        raise ValueError(
            f"mode must be one of {MODES}; got {mode!r}. This is not "
            f"defaulted on purpose -- an unstated mode has previously meant "
            f"'fake', and a run that silently became fake is the exact "
            f"outcome this gate exists to prevent.")

    if mode == FAKE:
        return GateDecision(mode=FAKE, status=FAKE_DRIVER,
                            hardware_touched=False,
                            detail="synthetic controller, explicitly "
                                   "requested; not evidence about a device")
    if mode == REPLAY_MODE:
        return GateDecision(mode=REPLAY_MODE, status=REPLAY,
                            hardware_touched=False,
                            detail="recorded frames re-read, explicitly "
                                   "requested; not evidence about a device now")

    # LIVE. Configuration first, and no I/O until it passes.
    try:
        require_live_hardware_permitted(action, constants)
    except HardwareConfigurationBlocked as error:
        # Reported, never downgraded to FAKE_DRIVER. The caller decides what
        # to do; this function will not quietly choose a different run for it.
        return GateDecision(mode=LIVE, status=BLOCKED_CONFIGURATION,
                            hardware_touched=False,
                            blocking_constants=error.constants,
                            detail=error.detail or "configuration blocked")

    if probe is None:
        return GateDecision(
            mode=LIVE, status=LIVE_HARDWARE_NOT_REACHABLE,
            hardware_touched=False,
            detail="configuration is VERIFIED but no probe was supplied, so "
                   "no device was contacted")
    reachable = bool(probe())
    if not reachable:
        return GateDecision(mode=LIVE, status=LIVE_HARDWARE_NOT_REACHABLE,
                            hardware_touched=True,
                            detail="configuration is VERIFIED; the device did "
                                   "not answer")
    return GateDecision(mode=LIVE, status=VERIFIED_STATIC_CONFIGURATION,
                        hardware_touched=True,
                        detail="configuration is VERIFIED and the device "
                               "answered; this records reachability only and "
                               "is not a validation of the hardware")
