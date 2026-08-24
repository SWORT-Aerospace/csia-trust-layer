"""Ask the autopilot's OWN log whether the estimator had a heading reference.

WHY THIS EXISTS.

PX4 SIH prints this at boot, on every run:

    WARN [health_and_arming_checks] Preflight Fail: no heading reference

The vehicle then arms under force-arm and flies, so it is tempting to treat
the line as noise. That would be a mistake with consequences: if the
simulation genuinely had no heading source, then **every magnetometer,
GNSS-course, attitude and cross-sensor result measured on that backend would
be contaminated**, and the qualification report would have no way to know.

`estimatorCheck.cpp:648-670` is the exact source of the line. The condition is:

    !context.isArmed()
    && (hrt_absolute_time() - estimator_status_flags.timestamp < 5_s)
    && !estimator_status_flags.cs_yaw_align
    && lpos.xy_global

So it says one thing only: **at that instant the EKF had not declared yaw
alignment**. It does not say a heading source is missing, broken or disabled.
Distinguishing "not yet" from "not at all" needs the time series, and the
time series is in the ulog the autopilot already writes.

WHAT THIS MODULE ESTABLISHES, all from logged data and none of it inferred:

  1. WHEN yaw alignment happened, and whether it ever regressed.
  2. WHICH source aligned it -- magnetometer, GNSS yaw, external vision or
     manual -- by which `cs_*` flag turns true at the same moment.
  3. Whether that source stayed healthy: `cs_mag_fault`,
     `cs_mag_field_disturbed`, and the fraction of `estimator_aid_src_mag`
     samples actually fused rather than rejected.
  4. Whether the resulting heading was CORRECT, not merely "aligned", by
     comparing `vehicle_attitude` against `vehicle_attitude_groundtruth` --
     which SIH publishes, and which is the only truly independent check
     available. An estimator can be confidently wrong; alignment is a claim
     the estimator makes about itself.

The parsing is deliberately thin and the decision is a pure function, so the
verdict logic can be tested without a 13 MB binary log.
"""

from __future__ import annotations

import math
import os

# Which `cs_*` flag turning true alongside `cs_yaw_align` names the source.
# Order matters only for reporting; a tie is reported as a list.
YAW_SOURCE_FLAGS = {
    "cs_mag": "MAGNETOMETER",
    "cs_mag_hdg": "MAGNETOMETER",
    "cs_mag_3d": "MAGNETOMETER",
    "cs_gnss_yaw": "GNSS_YAW",
    "cs_ev_yaw": "EXTERNAL_VISION",
    "cs_yaw_manual": "MANUAL",
}

# Channels whose meaning depends on a valid heading reference. If the
# estimator never aligned yaw, nothing in this list may be quoted from that
# run -- the rule the "do not normalise it away" instruction asks for.
HEADING_DEPENDENT_CHANNELS = (
    "mag.field_ut",
    "gnss.velocity",       # carries course over ground
    "estimator.variances",
)

VERDICTS = ("HEADING_REFERENCE_VALID",
            "HEADING_REFERENCE_LATE",
            "HEADING_REFERENCE_LOST",
            "NO_HEADING_REFERENCE",
            "UNVERIFIABLE")


def _first_true(times, values):
    for i, v in enumerate(values):
        if v:
            return float(times[i])
    return None


def _regressed_after(times, values, t_align):
    """True if the flag went back to false after aligning.

    A transient at boot and a heading that drops out mid-flight are opposite
    findings, and only the time series separates them.
    """
    seen = False
    for t, v in zip(times, values):
        if t < t_align:
            continue
        if v:
            seen = True
        elif seen:
            return True
    return False


def assess(flag_times, flags, aid_fused=None, aid_rejected=None,
           aid_times=None, yaw_error_deg=None, log_end_s=None) -> dict:
    """Decide, from already-extracted series, whether heading was valid.

    Pure: no file access, no pyulog. `flag_times` are seconds relative to the
    first sample; `flags` maps flag name -> sequence aligned with it.
    """
    out = {"verdict": "UNVERIFIABLE", "aligned_at_s": None,
           "source": None, "notes": []}
    align = flags.get("cs_yaw_align")
    if align is None or not len(flag_times):
        out["notes"].append("estimator_status_flags absent from the log")
        return out

    t_align = _first_true(flag_times, align)
    out["aligned_at_s"] = t_align
    out["final_aligned"] = bool(align[-1])

    if t_align is None:
        out["verdict"] = "NO_HEADING_REFERENCE"
        out["notes"].append(
            "cs_yaw_align never became true: the EKF never had a heading "
            "reference, and no magnetometer, GNSS-course, attitude or "
            "cross-sensor result from this run may be quoted")
        return out

    # WHICH source. A flag that turns true at the same instant as yaw
    # alignment is the one that supplied it; anything later is a subsequent
    # mode change (mag heading -> 3D mag fusion is the usual one).
    sources = []
    for flag, name in YAW_SOURCE_FLAGS.items():
        series = flags.get(flag)
        if series is None:
            continue
        t_src = _first_true(flag_times, series)
        if t_src is not None and abs(t_src - t_align) < 1e-6:
            if name not in sources:
                sources.append(name)
    out["source"] = sources[0] if len(sources) == 1 else (sources or None)
    out["source_candidates"] = sources

    lost = _regressed_after(flag_times, align, t_align)
    # `is not None`, never truthiness: pyulog hands back numpy arrays, and
    # `array and ...` raises "truth value of an array is ambiguous".
    def _any(name):
        series = flags.get(name)
        return bool(any(bool(v) for v in series)) if series is not None else False

    fault = _any("cs_mag_fault")
    disturbed = _any("cs_mag_field_disturbed")
    out["mag_fault_seen"] = fault
    out["mag_field_disturbed_seen"] = disturbed

    # Fusion actually happening, measured after alignment rather than over the
    # whole log: the pre-alignment samples are exactly the ones expected to be
    # rejected, and averaging them in would hide a real rejection rate.
    if aid_fused is not None and aid_times is not None and len(aid_fused):
        after = [i for i, t in enumerate(aid_times) if t >= t_align]
        if after:
            out["fused_pct_after_align"] = round(
                100.0 * sum(float(aid_fused[i]) for i in after) / len(after), 2)
            if aid_rejected is not None:
                out["rejected_pct_after_align"] = round(
                    100.0 * sum(float(aid_rejected[i]) for i in after)
                    / len(after), 2)

    # GROUND TRUTH. The only check here that does not take the estimator's
    # word for anything.
    if yaw_error_deg is not None and len(yaw_error_deg):
        finite = [abs(e) for e in yaw_error_deg if math.isfinite(e)]
        if finite:
            out["yaw_error_vs_truth_deg"] = {
                "n": len(finite),
                "mean_abs": round(sum(finite) / len(finite), 4),
                "max_abs": round(max(finite), 4),
            }

    if lost:
        out["verdict"] = "HEADING_REFERENCE_LOST"
        out["notes"].append(
            "cs_yaw_align regressed to false after aligning: the heading "
            "reference dropped out during the run, which is a fault and not "
            "a boot transient")
        return out

    out["verdict"] = "HEADING_REFERENCE_VALID"
    out["notes"].append(
        f"cs_yaw_align false for the first {t_align:.3f} s and true for the "
        f"remainder"
        + (f" of {log_end_s:.1f} s" if log_end_s else "")
        + ". The boot-time 'Preflight Fail: no heading reference' is that "
          "window: estimatorCheck.cpp reports the flag, not the absence of a "
          "source.")
    if fault or disturbed:
        out["notes"].append(
            "a magnetometer fault or field disturbance was flagged at some "
            "point; heading-dependent channels need a closer look")
    return out


# -- log extraction --------------------------------------------------------


def _yaw_from_quat(q0, q1, q2, q3):
    return math.atan2(2.0 * (q0 * q3 + q1 * q2),
                      1.0 - 2.0 * (q2 * q2 + q3 * q3))


def _wrap_deg(a):
    return math.degrees(math.atan2(math.sin(a), math.cos(a)))


def newest_ulog(workdir: str):
    """The log the run just wrote. The rig wipes the workdir at launch, so
    the newest file under it belongs to this run and no other."""
    best, best_m = None, -1.0
    for dirpath, _dirnames, filenames in os.walk(workdir):
        for fn in filenames:
            if fn.endswith(".ulg"):
                p = os.path.join(dirpath, fn)
                m = os.path.getmtime(p)
                if m > best_m:
                    best, best_m = p, m
    return best


def heading_provenance(ulog_path: str) -> dict:
    """Extract the series from a ulog and assess them.

    Returns a verdict dict either way. A missing pyulog or an unreadable log
    is `UNVERIFIABLE` with the reason recorded -- never a silent pass, because
    "we could not check" and "it was fine" are the two things this whole
    module exists to keep apart.
    """
    result = {"log": ulog_path, "verdict": "UNVERIFIABLE", "notes": []}
    try:
        from pyulog import ULog
    except ImportError as exc:
        result["notes"].append(f"pyulog not installed: {exc}")
        return result
    if not ulog_path or not os.path.exists(ulog_path):
        result["notes"].append("no .ulg found for this run")
        return result

    try:
        u = ULog(ulog_path, ["estimator_status_flags", "estimator_aid_src_mag",
                             "vehicle_attitude", "vehicle_attitude_groundtruth"])
    except Exception as exc:                            # pragma: no cover
        result["notes"].append(f"could not read the log: {exc}")
        return result

    data = {d.name: d.data for d in u.data_list}
    sf = data.get("estimator_status_flags")
    if sf is None:
        result["notes"].append("estimator_status_flags not logged")
        return result

    t_flags = [x / 1e6 for x in sf["timestamp"]]
    t0 = t_flags[0]
    t_flags = [t - t0 for t in t_flags]
    flags = {k: sf[k] for k in sf if k.startswith("cs_")}

    aid = data.get("estimator_aid_src_mag")
    aid_t = aid_f = aid_r = None
    if aid is not None:
        aid_t = [x / 1e6 - t0 for x in aid["timestamp"]]
        aid_f = aid.get("fused")
        aid_r = aid.get("innovation_rejected")

    # Estimated yaw against the simulator's ground truth. Only SIH publishes
    # vehicle_attitude_groundtruth; on real hardware this block is skipped and
    # the verdict simply carries no ground-truth field.
    yaw_err = None
    est, gt = data.get("vehicle_attitude"), data.get("vehicle_attitude_groundtruth")
    if est is not None and gt is not None:
        te = [x / 1e6 - t0 for x in est["timestamp"]]
        tg = [x / 1e6 - t0 for x in gt["timestamp"]]
        ye = [_yaw_from_quat(est["q[0]"][i], est["q[1]"][i],
                             est["q[2]"][i], est["q[3]"][i])
              for i in range(len(te))]
        yg = [_yaw_from_quat(gt["q[0]"][i], gt["q[1]"][i],
                             gt["q[2]"][i], gt["q[3]"][i])
              for i in range(len(tg))]
        yaw_err = []
        j = 0
        for i, t in enumerate(te):
            while j + 1 < len(tg) and tg[j + 1] <= t:
                j += 1
            yaw_err.append(_wrap_deg(ye[i] - yg[j]))

    out = assess(t_flags, flags, aid_fused=aid_f, aid_rejected=aid_r,
                 aid_times=aid_t, yaw_error_deg=yaw_err,
                 log_end_s=t_flags[-1] if t_flags else None)
    out["log"] = ulog_path
    return out
