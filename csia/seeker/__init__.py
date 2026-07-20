"""CSIA interceptor_seeker profile — a first-pass seeker-domain extension.

SYNTHETIC / FIRST-PASS. This package models a simplified missile-seeker
engagement and runs it through the UNMODIFIED CSIA cores (TrustCore,
DiagnosisCore) via new sensor models, comparator edges, and scenarios — the
same extension pattern the SOW001 quad profile uses. Nothing here is flight
software and nothing has been validated against real seeker hardware. The
engagement is a kinematic 2D closing intercept, not a 6-DOF simulation.

Prepared for U.S. Army xTech|Apex Intercept, Topic 4 (Fire Control and
Flight Guidance). Results are synthetic and labeled as such throughout.
"""

from .engagement import Engagement, generate_engagement
from .runtime import SeekerRuntime, run_seeker
from .scenarios import SEEKER_SCENARIOS

__all__ = ["Engagement", "generate_engagement", "SeekerRuntime",
           "run_seeker", "SEEKER_SCENARIOS"]
