"""CSIA real-time runtime — the deployable trust layer.

``OnlineTrustLayer`` ingests sensor samples one at a time (from a MAVLink
link, a log, or the simulator) and emits a ``TrustState`` per engine tick.
``FailsafePolicy`` turns trust states into a NORMAL/CAUTION/CRITICAL/
EMERGENCY state machine with concrete recovery actions. ``TrustLayerRuntime``
wires a source plugin, the online layer, the policy, and actuators together.

The batch pipeline (csia.prediction + csia.trust_engine) remains the
analysis/replay path; this runtime shares the same per-tick cores
(TrustCore, DiagnosisCore), and an equivalence test pins the two together.

NOT flight software: failsafe outputs are ADVISORY by default. Commanding a
real autopilot requires an explicit opt-in and, for a real aircraft, a
qualification process this prototype does not claim.
"""

from .failsafe import (Action, FailsafeConfig, FailsafeLevel, FailsafePolicy)
from .online import OnlineTrustLayer, TrustState
from .plugins import SimulatedFlightSource, SourcePlugin
from .service import LoggingActuator, TrustLayerRuntime

__all__ = [
    "OnlineTrustLayer", "TrustState",
    "FailsafePolicy", "FailsafeConfig", "FailsafeLevel", "Action",
    "SourcePlugin", "SimulatedFlightSource",
    "TrustLayerRuntime", "LoggingActuator",
]
