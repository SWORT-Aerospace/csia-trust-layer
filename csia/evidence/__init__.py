"""CSIA-ACEG anytime-valid evidence (research layer, not flight software)."""

from .eprocess import (DEFAULT_KAPPA, E_MAX, P_MIN, BlockwiseEProcess,
                       LikelihoodRatioEProcess, NaivePerTickEProcess,
                       ar1_block_mean_p, calibrate)

__all__ = ["calibrate", "NaivePerTickEProcess", "BlockwiseEProcess",
           "LikelihoodRatioEProcess", "ar1_block_mean_p",
           "DEFAULT_KAPPA", "P_MIN", "E_MAX"]
