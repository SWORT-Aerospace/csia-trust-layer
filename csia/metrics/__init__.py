"""Metric definitions shared by every CSIA measurement path.

One module owns each metric so the same quantity cannot be computed three
different ways in three different tools (audit finding F-01). See
docs/validation/METRIC_DEFINITIONS.md for the normative definitions.
"""

from .events import (DEFAULT_MERGE_S, AlertEpisode, alert_episodes,
                     alert_events, alert_summary, poisson_ci)

__all__ = ["AlertEpisode", "alert_episodes", "alert_events", "alert_summary",
           "poisson_ci", "DEFAULT_MERGE_S"]
