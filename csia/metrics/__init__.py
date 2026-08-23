"""Metric definitions shared by every CSIA measurement path.

One module owns each metric so the same quantity cannot be computed three
different ways in three different tools (audit finding F-01). See
docs/validation/METRIC_DEFINITIONS.md for the normative definitions.
"""

from .events import (DEFAULT_MERGE_S, AlertEpisode, alert_episodes,
                     alert_events, alert_summary, poisson_ci)
from .latency import (APPLIED_MITIGATION_UNAVAILABLE, ARBITRATION_ACTIONS,
                      CAUSE_TO_SOURCE, LEGACY_ANALYSIS_THRESHOLD, FaultWindow,
                      LatencyResult, OnsetBasis, associate_episode, measure,
                      production_threshold, time_to_arbitration,
                      time_to_classification, time_to_correct_isolation,
                      time_to_recovery, time_to_trust_threshold,
                      time_to_trusted_reentry, unassociated_episodes)

__all__ = [
    "AlertEpisode", "alert_episodes", "alert_events", "alert_summary",
    "poisson_ci", "DEFAULT_MERGE_S",
    "FaultWindow", "OnsetBasis", "LatencyResult", "measure",
    "associate_episode", "unassociated_episodes", "production_threshold",
    "time_to_trust_threshold", "time_to_classification",
    "time_to_correct_isolation", "time_to_arbitration", "time_to_recovery",
    "time_to_trusted_reentry",
    "LEGACY_ANALYSIS_THRESHOLD", "CAUSE_TO_SOURCE", "ARBITRATION_ACTIONS",
    "APPLIED_MITIGATION_UNAVAILABLE",
]
