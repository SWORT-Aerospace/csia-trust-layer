"""Exposure accounting and statistical exposure planning.

Slice 3A. Two defects in how CSIA reported flight exposure:

1. **Composition was hidden.** "0.66 flight hours" merged annotated and
   unannotated data into one number, and the surrounding prose called it
   "healthy". No log in the corpus carries any annotation, so no hour of it is
   verified healthy.

2. **The denominator was wrong.** The rate used raw log duration, but the
   failsafe cannot raise an alert during ``arm_time``. 21.8% of the committed
   corpus lies inside that window. Dividing alerts by time in which alerts are
   impossible understates the rate.

This module reports exposure BY CATEGORY and never emits a combined rate
without its composition.
"""

import math
from dataclasses import dataclass, field


# --- confidence intervals -----------------------------------------------------

def poisson_ci(k: int, hours: float, conf: float = 0.95) -> tuple:
    """Exact (Garwood) Poisson rate interval per hour."""
    if hours <= 0:
        raise ValueError("hours must be > 0")
    if k < 0:
        raise ValueError("k must be >= 0")
    from scipy.stats import chi2
    a = 1.0 - conf
    lo = chi2.ppf(a / 2, 2 * k) / 2 / hours if k else 0.0
    hi = chi2.ppf(1 - a / 2, 2 * k + 2) / 2 / hours
    return (float(lo), float(hi))


def zero_event_upper_bound(hours: float, conf: float = 0.95) -> float:
    """Upper confidence bound on the rate given ZERO observed events.

    The rule-of-three limit: -ln(1-conf)/hours (= 3/hours at 95%). Observing
    nothing never demonstrates a rate of zero — only a bound.
    """
    if hours <= 0:
        raise ValueError("hours must be > 0")
    return -math.log(1.0 - conf) / hours


def hours_for_upper_bound(target_rate: float, conf: float = 0.95) -> float:
    """Zero-event exposure needed to bound the rate below ``target_rate``."""
    if target_rate <= 0:
        raise ValueError("target_rate must be > 0")
    return -math.log(1.0 - conf) / target_rate


def projected_interval(k: int, hours: float, conf: float = 0.95) -> dict:
    """What the interval WOULD be for an assumed event count and exposure."""
    lo, hi = poisson_ci(k, hours, conf)
    return {"events": k, "hours": round(hours, 3),
            "rate_per_hour": round(k / hours, 3),
            "ci_low": round(lo, 3), "ci_high": round(hi, 3),
            "ci_width": round(hi - lo, 3),
            "fold_uncertainty": (round(hi / lo, 1) if lo > 0 else None)}


def compare_rates_approx(k1: int, h1: float, k2: int, h2: float) -> dict:
    """APPROXIMATE two-rate comparison. Explicitly not a decision procedure.

    Normal approximation to the log rate ratio; unreliable at small counts,
    which is exactly the regime CSIA is in today. Provided for exposure
    PLANNING only — labelled approximate wherever it is reported.
    """
    if min(h1, h2) <= 0:
        raise ValueError("hours must be > 0")
    if k1 == 0 or k2 == 0:
        return {"method": "APPROXIMATE_NORMAL_LOG_RATIO",
                "usable": False,
                "reason": "a zero count makes the log rate ratio undefined; "
                          "use exact zero-event bounds instead"}
    r1, r2 = k1 / h1, k2 / h2
    se = math.sqrt(1.0 / k1 + 1.0 / k2)
    lo = math.exp(math.log(r1 / r2) - 1.96 * se)
    hi = math.exp(math.log(r1 / r2) + 1.96 * se)
    return {"method": "APPROXIMATE_NORMAL_LOG_RATIO", "usable": True,
            "rate_ratio": round(r1 / r2, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
            "significant_at_95": not (lo <= 1.0 <= hi),
            "caveat": "approximate; unreliable below ~10 events per arm"}


# --- exposure accounting ------------------------------------------------------

@dataclass
class ExposureAccount:
    """Flight-hours broken out by every dimension that changes their meaning."""
    total_raw_hours: float = 0.0
    total_monitored_hours: float = 0.0
    unmonitored_hours: float = 0.0
    by_health: dict = field(default_factory=dict)
    by_partition: dict = field(default_factory=dict)
    by_autopilot: dict = field(default_factory=dict)
    by_firmware: dict = field(default_factory=dict)
    by_airframe: dict = field(default_factory=dict)
    by_sensor_config: dict = field(default_factory=dict)
    excluded_duplicate_hours: float = 0.0
    excluded_missing_channel_hours: float = 0.0
    excluded_other_hours: float = 0.0
    counted_logs: int = 0
    excluded_logs: int = 0

    def to_dict(self) -> dict:
        d = {k: (round(v, 4) if isinstance(v, float) else v)
             for k, v in self.__dict__.items()}
        for key in ("by_health", "by_partition", "by_autopilot", "by_firmware",
                    "by_airframe", "by_sensor_config"):
            d[key] = {k: round(v, 4) for k, v in sorted(d[key].items())}
        return d


def account(manifests, arm_time_s: float = 20.0) -> ExposureAccount:
    """Aggregate exposure. Duplicates and excluded logs never count."""
    acc = ExposureAccount()
    for m in manifests:
        raw_h = m.flight_duration_s / 3600.0
        if not m.counts_toward_exposure:
            acc.excluded_logs += 1
            if m.duplicate_of is not None:
                acc.excluded_duplicate_hours += raw_h
            elif m.exclusion_reason and "channel" in m.exclusion_reason.lower():
                acc.excluded_missing_channel_hours += raw_h
            else:
                acc.excluded_other_hours += raw_h
            continue

        mon_s = (m.monitored_duration_s if m.monitored_duration_s
                 else max(0.0, m.flight_duration_s - arm_time_s))
        mon_h = mon_s / 3600.0
        acc.counted_logs += 1
        acc.total_raw_hours += raw_h
        acc.total_monitored_hours += mon_h
        acc.unmonitored_hours += raw_h - mon_h

        def bump(d, key):
            d[key] = d.get(key, 0.0) + mon_h

        bump(acc.by_health, m.health_classification)
        bump(acc.by_partition, m.dataset_partition)
        bump(acc.by_autopilot, m.autopilot)
        bump(acc.by_firmware, m.firmware_version or "UNKNOWN")
        bump(acc.by_airframe, m.airframe_type or "UNKNOWN")
        bump(acc.by_sensor_config, "+".join(sorted(m.sensor_inventory)) or "NONE")
    return acc


def rate_report(manifests, category: str, arm_time_s: float = 20.0,
                conf: float = 0.95, basis: str = "monitored") -> dict:
    """Alert-episode rate for ONE health category, with full composition.

    A rate is never emitted without: the count, the exposure, the interval,
    the health composition, and the exclusions behind it.
    """
    sel = [m for m in manifests
           if m.counts_toward_exposure and m.health_classification == category]
    if basis not in ("monitored", "raw"):
        raise ValueError("basis must be 'monitored' or 'raw'")

    hours = 0.0
    for m in sel:
        if basis == "raw":
            hours += m.flight_duration_s / 3600.0
        else:
            mon = (m.monitored_duration_s if m.monitored_duration_s
                   else max(0.0, m.flight_duration_s - arm_time_s))
            hours += mon / 3600.0
    episodes = sum(m.alert_episodes for m in sel)

    out = {
        "health_category": category,
        "exposure_basis": basis,
        "logs": len(sel),
        "exposure_hours": round(hours, 4),
        "alert_episodes": episodes,
        "flights_with_0_episodes": sum(1 for m in sel if m.alert_episodes == 0),
        "flights_with_1_episode": sum(1 for m in sel if m.alert_episodes == 1),
        "flights_with_multiple_episodes":
            sum(1 for m in sel if m.alert_episodes > 1),
    }
    if hours <= 0:
        out.update({"rate_per_hour": None,
                    "note": "no exposure in this category"})
        return out
    lo, hi = poisson_ci(episodes, hours, conf)
    out.update({
        "rate_per_hour": round(episodes / hours, 3),
        "ci95_per_hour": [round(lo, 3), round(hi, 3)],
        "interpretation": (
            f"no CSIA alert episode occurred during {hours:.3f} h of "
            f"{category} real-flight-log replay; this bounds the rate below "
            f"{zero_event_upper_bound(hours, conf):.2f}/h at "
            f"{int(conf * 100)}% confidence, and is NOT a demonstration of a "
            "zero rate"
            if episodes == 0 else
            f"{episodes} alert episode(s) in {hours:.3f} h of {category} "
            "replay; interval is wide at this count"),
    })
    return out
