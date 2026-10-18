"""Simulation qualification (phases S1, S3, S4).

`contract`  the six-stage trial-validity chain. No scenario is scored unless
            every stage is demonstrated, with the measured intermediate
            recorded, and every intervention has a null control.
`profiles`  IDEAL_SIM / REALISTIC_SIM / FIELD_DERIVED_NOISE. Every simulated
            result must name the profile that produced it.
"""

from .contract import (Stage, StageResult, TrialContract, TrialVerdict,
                       NullControl)
from .profiles import PROFILES, NoiseProfile, get_profile

__all__ = ["Stage", "StageResult", "TrialContract", "TrialVerdict",
           "NullControl", "PROFILES", "NoiseProfile", "get_profile"]
