"""Alert event/episode semantics (audit finding F-01).

The regression these tests exist to prevent: counting a failsafe RECOVERY
edge as an operator alert, which inflated the published real-log false-alarm
rate by 1.50x.
"""

import json
import os

import pytest

from csia.metrics import (alert_episodes, alert_events, alert_summary,
                          poisson_ci)
from csia.runtime.failsafe import FailsafeLevel, Transition

N, C, X, E = (FailsafeLevel.NORMAL, FailsafeLevel.CAUTION,
              FailsafeLevel.CRITICAL, FailsafeLevel.EMERGENCY)


def tr(t, level, previous, *reasons):
    return Transition(t=t, level=level, previous=previous,
                      reasons=list(reasons), actions=[])


# --- the exact defect F-01 describes -----------------------------------------

def test_recovery_edge_is_not_an_alert():
    """CAUTION then back to NORMAL is ONE alert, not two.

    This is the precise miscount that produced 4.5/h instead of 3.0/h on the
    real-log corpus.
    """
    trs = [tr(23.1, C, N, "GPS trust 0.71"), tr(42.0, N, C, "recovered")]
    assert len(trs) == 2                       # two transitions ...
    assert len(alert_events(trs)) == 1         # ... one escalation ...
    assert len(alert_episodes(trs)) == 1       # ... one operator episode
    assert alert_episodes(trs)[0].peak_level == "CAUTION"


def test_escalation_within_incident_is_one_episode():
    """NORMAL->CAUTION->CRITICAL->NORMAL is one incident, two escalations."""
    trs = [tr(10.0, C, N, "gps"), tr(12.0, X, C, "power"), tr(30.0, N, X)]
    (ep,) = alert_episodes(trs)
    assert (ep.start, ep.end, ep.peak_level) == (10.0, 30.0, "CRITICAL")
    assert ep.escalations == 2
    assert len(alert_events(trs)) == 2         # events over-count burden ...
    assert len(alert_episodes(trs)) == 1       # ... episodes do not


def test_deescalation_without_full_recovery_stays_one_episode():
    """CRITICAL -> CAUTION is still an ongoing alert, not a new one."""
    trs = [tr(10.0, X, N, "power"), tr(20.0, C, X), tr(40.0, N, C)]
    (ep,) = alert_episodes(trs)
    assert ep.peak_level == "CRITICAL" and ep.escalations == 1


# --- flapping / merge window --------------------------------------------------

def test_flapping_merges_into_one_episode():
    trs = [tr(10.0, C, N, "gps"), tr(15.0, N, C),
           tr(18.0, C, N, "gps"), tr(25.0, N, C)]      # 3 s recovered gap
    assert len(alert_episodes(trs, merge_s=10.0)) == 1
    assert len(alert_episodes(trs, merge_s=2.0)) == 2  # gap exceeds window


def test_merged_episode_keeps_earliest_start_and_worst_level():
    trs = [tr(10.0, C, N, "a"), tr(15.0, N, C),
           tr(18.0, X, N, "b"), tr(25.0, N, X)]
    (ep,) = alert_episodes(trs, merge_s=10.0)
    assert ep.start == 10.0 and ep.end == 25.0
    assert ep.peak_level == "CRITICAL"
    assert ep.escalations == 2
    assert ep.reasons == ("a", "b")


def test_separated_episodes_are_distinct():
    trs = [tr(10.0, C, N, "a"), tr(15.0, N, C),
           tr(120.0, C, N, "b"), tr(140.0, N, C)]
    assert len(alert_episodes(trs)) == 2


# --- edge cases ---------------------------------------------------------------

def test_no_transitions_is_no_alerts():
    assert alert_episodes([]) == [] and alert_events([]) == []


def test_episode_open_at_flight_end_is_counted():
    """A CAUTION that never clears before the log ends still reached the
    operator — the log stopping is not a recovery."""
    (ep,) = alert_episodes([tr(32.0, C, N, "gps")])
    assert ep.open_at_end and ep.end is None and ep.duration is None
    assert alert_summary([tr(32.0, C, N, "gps")], 1.0)["episodes"] == 1


def test_emergency_peak_is_reported():
    trs = [tr(5.0, C, N), tr(6.0, E, C), tr(9.0, N, E)]
    assert alert_episodes(trs)[0].peak_level == "EMERGENCY"


def test_out_of_order_transitions_rejected():
    with pytest.raises(ValueError, match="non-decreasing"):
        alert_episodes([tr(20.0, C, N), tr(10.0, N, C)])


def test_negative_merge_window_rejected():
    with pytest.raises(ValueError, match="merge_s"):
        alert_episodes([], merge_s=-1.0)


def test_accepts_json_report_dicts_without_previous():
    """Committed reports (data/real_logs_report.json) carry no 'previous'."""
    rows = [{"t": 23.1, "level": "CAUTION", "reasons": ["gps"]},
            {"t": 42.0, "level": "NORMAL", "reasons": []}]
    assert len(alert_episodes(rows)) == 1


# --- rates --------------------------------------------------------------------

def test_poisson_ci_brackets_point_estimate():
    lo, hi = poisson_ci(2, 0.663)
    assert lo < 2 / 0.663 < hi
    assert poisson_ci(0, 1.0)[0] == 0.0


def test_summary_reports_all_three_definitions():
    trs = [tr(23.1, C, N, "gps"), tr(42.0, N, C)]
    s = alert_summary(trs, hours=0.663)
    assert s["transitions"] == 2      # legacy (what was published)
    assert s["alert_events"] == 1
    assert s["episodes"] == 1
    assert s["episodes_per_hour"] == pytest.approx(1 / 0.663, rel=1e-3)


# --- the corpus-level regression ----------------------------------------------

REPORT = os.path.join(os.path.dirname(__file__), "..", "data",
                      "real_logs_report.json")


@pytest.mark.skipif(not os.path.exists(REPORT), reason="corpus report absent")
def test_real_log_corpus_recount():
    """Pins the corrected headline number against the committed artifact.

    26 flights / 0.663 h carry 3 transitions, but only 2 are alerts; the
    third is a recovery. Published rate was 4.52/h; the correct
    operator-facing rate is 3.02/h.
    """
    with open(REPORT) as fh:
        rep = json.load(fh)
    hours = rep["total_hours"]
    all_tr = [t for f in rep["flights"] for t in f["transitions"]]

    assert len(all_tr) == 3 == rep["total_transitions"]

    episodes = sum(len(alert_episodes(f["transitions"]))
                   for f in rep["flights"])
    assert episodes == 2
    assert len(all_tr) / hours == pytest.approx(4.52, abs=0.01)   # published
    assert episodes / hours == pytest.approx(3.02, abs=0.01)      # corrected
