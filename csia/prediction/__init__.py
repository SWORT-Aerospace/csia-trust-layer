"""CSIA prediction comparator package.

For each sensor, produces three independent predictions of the incoming
measurement — physics-model, historical-trend, neighbor-sensor — and
quantifies their disagreement as normalized squared residuals that the
trust engine converts to consistency scores.
"""

from .attitude import calibrate_imu_stream, complementary_attitude
from .comparator import PredictionComparator, TickData

__all__ = ["calibrate_imu_stream", "complementary_attitude",
           "PredictionComparator", "TickData"]
