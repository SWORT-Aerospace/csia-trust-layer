"""Alert event / episode semantics — the single definition of "false alarm".

Audit finding F-01: the repository counted operator alerts three different
ways, and the figure published for real flight logs used the loosest one.
``csia/cli.py`` counted ``len(summary.transitions)``, which includes
DE-ESCALATION edges: a ``CAUTION -> NORMAL`` recovery (issuing RESUME_NORMAL)
was being reported as a "failsafe activation". On the committed 26-flight
corpus that inflated the rate by 1.50x (3 counted vs 2 real alerts).

This module owns the vocabulary. Definitions, from narrowest to widest:

  TRANSITION      any FailsafePolicy state-machine edge, escalation or
                  recovery. NOT an operator alert. Retained only for
                  backward comparison with previously published numbers.

  ALERT EVENT     a transition that INCREASES severity (level > previous).
                  A CAUTION -> CRITICAL escalation is a second event within
                  the same incident, so events over-count operator burden.

  ALERT EPISODE   a contiguous period of non-NORMAL posture: opens on the
                  first escalation out of NORMAL, closes on return to NORMAL.
                  Escalations WITHIN the episode do not open a new one. Two
                  episodes separated by less than ``merge_s`` of recovered
                  posture are merged, so a flapping condition counts once.
                  THIS is the operator-facing unit and the one to publish.

An episode still open when the flight ends is reported with ``end=None`` and
counted — the operator saw it; the log merely stopped first.

Rates are reported with an exact Poisson interval, because the real-log
corpus is 0.663 flight-hours and a point estimate from 2 events carries far
less information than two significant figures imply (audit finding F-09).
"""

from dataclasses import dataclass

# Default recovered-posture gap below which two episodes are treated as one
# incident. 10 s > FailsafeConfig.dwell_down (5.0 s default) so a condition
# that clears hysteresis and immediately re-trips still reads as one episode.
DEFAULT_MERGE_S = 10.0

NORMAL = "NORMAL"


@dataclass(frozen=True)
class AlertEpisode:
    """One operator-facing alert incident."""
    start: float                 # s, first escalation out of NORMAL
    end: float | None            # s, return to NORMAL; None = open at log end
    peak_level: str              # worst posture reached
    escalations: int             # severity-increasing edges inside the episode
    reasons: tuple               # reason strings, first occurrence order

    @property
    def open_at_end(self) -> bool:
        return self.end is None

    @property
    def duration(self) -> float | None:
        return None if self.end is None else self.end - self.start


def _level_name(level) -> str:
    """Accept FailsafeLevel enums or plain strings (replayed JSON reports)."""
    return getattr(level, "name", None) or str(level)


def _rank(level) -> int:
    """Severity rank; FailsafeLevel is an IntEnum, JSON reports carry names."""
    if isinstance(level, int):
        return int(level)
    order = ("NORMAL", "CAUTION", "CRITICAL", "EMERGENCY")
    name = _level_name(level)
    if name not in order:
        raise ValueError(f"unknown failsafe level {name!r}")
    return order.index(name)


def alert_events(transitions) -> list:
    """Severity-INCREASING transitions. Excludes recoveries.

    This is the definition ``validation.bench`` and ``validation.monte_carlo``
    already used implicitly (``level != NORMAL``); stated explicitly here so
    every call site shares it.
    """
    out = []
    for tr in transitions:
        prev = getattr(tr, "previous", None)
        if prev is None:                       # replayed report without prev:
            if _rank(tr.level) > 0:            # treat any non-NORMAL as an event
                out.append(tr)
        elif _rank(tr.level) > _rank(prev):
            out.append(tr)
    return out


def alert_episodes(transitions, merge_s: float = DEFAULT_MERGE_S) -> list:
    """Group transitions into operator-facing incidents.

    ``transitions`` must be in non-decreasing time order (FailsafePolicy
    appends chronologically). Accepts both live ``Transition`` objects and
    dicts decoded from a committed JSON report.
    """
    if merge_s < 0:
        raise ValueError("merge_s must be >= 0")

    rows = []
    for tr in transitions:
        t = tr["t"] if isinstance(tr, dict) else tr.t
        level = tr["level"] if isinstance(tr, dict) else tr.level
        prev = (tr.get("previous") if isinstance(tr, dict)
                else getattr(tr, "previous", None))
        reasons = (tr.get("reasons", []) if isinstance(tr, dict)
                   else list(getattr(tr, "reasons", [])))
        rows.append((float(t), _level_name(level),
                     None if prev is None else _level_name(prev), reasons))
    if any(rows[i][0] > rows[i + 1][0] for i in range(len(rows) - 1)):
        raise ValueError("transitions must be in non-decreasing time order")

    episodes: list[AlertEpisode] = []
    start = None
    peak = NORMAL
    escalations = 0
    reasons: list = []

    for t, level, prev, why in rows:
        if level != NORMAL:
            if start is None:
                # Reopen the previous episode instead of starting a new one if
                # the recovered gap was shorter than the merge window.
                if episodes and episodes[-1].end is not None \
                        and t - episodes[-1].end < merge_s:
                    last = episodes.pop()
                    start, peak = last.start, last.peak_level
                    escalations, reasons = last.escalations, list(last.reasons)
                else:
                    start, peak, escalations, reasons = t, NORMAL, 0, []
            # count this edge as an escalation if it raised severity
            if prev is None or _rank(level) > _rank(prev):
                escalations += 1
            if _rank(level) > _rank(peak):
                peak = level
            for r in why:
                if r not in reasons:
                    reasons.append(r)
        else:
            if start is not None:
                episodes.append(AlertEpisode(start, t, peak, escalations,
                                             tuple(reasons)))
                start, peak, escalations, reasons = None, NORMAL, 0, []

    if start is not None:                       # never recovered before end
        episodes.append(AlertEpisode(start, None, peak, escalations,
                                     tuple(reasons)))
    return episodes


def poisson_ci(k: int, hours: float, conf: float = 0.95) -> tuple:
    """Exact (Garwood) Poisson rate interval per hour for k events."""
    if hours <= 0:
        raise ValueError("hours must be > 0")
    from scipy.stats import chi2
    a = 1.0 - conf
    lo = chi2.ppf(a / 2, 2 * k) / 2 / hours if k else 0.0
    hi = chi2.ppf(1 - a / 2, 2 * k + 2) / 2 / hours
    return (float(lo), float(hi))


def alert_summary(transitions, hours: float,
                  merge_s: float = DEFAULT_MERGE_S) -> dict:
    """Every alert count under all three definitions, plus rates + CI.

    Emitting all three keeps previously published figures comparable while the
    corrected ``episodes`` number becomes the one to quote.
    """
    eps = alert_episodes(transitions, merge_s)
    evs = alert_events(transitions)
    n_tr = len(list(transitions))
    lo, hi = poisson_ci(len(eps), hours)
    return {
        "hours": round(hours, 4),
        "merge_s": merge_s,
        "episodes": len(eps),
        "episodes_per_hour": round(len(eps) / hours, 3),
        "episodes_per_hour_ci95": [round(lo, 3), round(hi, 3)],
        "alert_events": len(evs),
        "transitions": n_tr,          # legacy definition, retained for compare
        "episodes_open_at_end": sum(1 for e in eps if e.open_at_end),
        "peak_levels": [e.peak_level for e in eps],
    }
