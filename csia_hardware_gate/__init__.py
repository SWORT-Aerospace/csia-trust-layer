"""Refuse live hardware while any governed constant is unverified.

The policy in one line: a constant may reach silicon only when a human has
checked it against a cited page of a document that is in this repository and
hashes to a recorded digest. Everything else blocks, loudly and typed.

Nothing here validates hardware. :data:`HARDWARE_VALIDATED` is False and there
is no code path that sets it True.
"""
from __future__ import annotations

from .gate import (BLOCKED_CONFIGURATION, FAKE, FAKE_DRIVER,
                   FORBIDDEN_RESULT_STATUSES, HARDWARE_VALIDATED,
                   LIVE, LIVE_HARDWARE_NOT_REACHABLE, MODES, REPLAY,
                   REPLAY_MODE, TERMINAL_STATUSES,
                   VERIFIED_STATIC_CONFIGURATION, GateDecision,
                   HardwareConfigurationBlocked, require_live_hardware_permitted,
                   resolve, static_configuration_status)
from .registry import (BLOCKING_STATUSES, DECLARED_STATUSES, MISSING,
                       UNVERIFIED, VERIFIED, HardwareConstant,
                       RegistryMalformed, blocking, load_registry, summarise)

__all__ = [
    "BLOCKED_CONFIGURATION", "FAKE", "FAKE_DRIVER",
    "FORBIDDEN_RESULT_STATUSES", "HARDWARE_VALIDATED", "LIVE",
    "LIVE_HARDWARE_NOT_REACHABLE", "MODES", "REPLAY", "REPLAY_MODE",
    "TERMINAL_STATUSES", "VERIFIED_STATIC_CONFIGURATION", "GateDecision",
    "HardwareConfigurationBlocked", "require_live_hardware_permitted",
    "resolve", "static_configuration_status",
    "BLOCKING_STATUSES", "DECLARED_STATUSES", "MISSING", "UNVERIFIED",
    "VERIFIED", "HardwareConstant", "RegistryMalformed", "blocking",
    "load_registry", "summarise",
]
