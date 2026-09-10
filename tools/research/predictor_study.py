"""Would a better nominal predictor detect smaller faults? Measured, offline.

THE CLAIM UNDER TEST
--------------------
CSIA's temporal sub-score is a one-step Holt double-exponential innovation:
predict the next sample, square the normalised error, feed it to the frozen
trust math as `lam`. The standard argument for putting learning here is:

    a better nominal model produces whiter, smaller innovations on healthy
    data, so the same lam machinery separates a fault from nominal at a
    smaller fault magnitude.

This tool tests that claim on simulated flights and reports how much it would
help. IT CHANGES NOTHING. No frozen file is touched, no predictor is
substituted into CSIA, and nothing here runs at flight time. It reads the
same raw channel streams the layer reads and does the arithmetic beside it.

THE FAILURE MODE THAT DECIDES THE ANSWER
-----------------------------------------
A predictor good enough to whiten the innovations on healthy data may also be
good enough to TRACK THE FAULT. A slow bias drift is, to an autoregressive
model with enough memory, just a trend to be predicted -- so the innovation
stays small, the lam never rises, and the fault becomes INVISIBLE. The better
the nominal model, the better it hides exactly the fault class CSIA exists to
catch.

That is not a hypothetical. `bias_drift` is a linear ramp, and a linear ramp
is what a Holt trend term or an AR model with a unit-root-ish pole predicts
best of all.

So whiteness on clean data is NOT the metric. The metric is the separation
between clean and faulted innovations, and both halves are reported:

    clean_sigma       std of innovation on HELD-OUT clean flight
    fault_excursion   mean |innovation| during the fault window
    d_prime           (fault_excursion - clean_mean_abs) / clean_sigma

`d_prime` rises if the predictor sharpens the nominal model WITHOUT following
the fault, and falls if it follows the fault. Reporting only `clean_sigma`
would show every candidate as an improvement.

TRAIN AND TEST ARE DIFFERENT FLIGHTS
-------------------------------------
Every fitted predictor is fitted on one clean flight and evaluated on a
DIFFERENT one, over a different noise realisation. Fitting and scoring on the
same series measures memorisation and reports it as skill.

WHAT THIS STUDY CANNOT TELL YOU, AND IT IS THE BIGGEST LIMITATION
-------------------------------------------------------------------
Every fault here is a parametric injection from a set of six known kinds.
A predictor tuned against them is tuned against the injector, not against a
barometer. The repository already records fault classes the simulator cannot
produce at all -- RF jamming as RF, urban multipath -- and notes that the
nearest available proxy omits the degraded-but-present regime a real fault
produces first. Those are precisely the regimes a better predictor would be
claimed to help with, and there is no data for them here. A positive result
from this tool is a reason to collect real data, not a reason to ship a
model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia.prediction.predictors import HIST_CHANNELS               # noqa: E402
from csia.sensors import generate_flight                           # noqa: E402
from csia.sensors.faults import Fault                              # noqa: E402

INSTRUMENT = "tools.research.predictor_study"

DURATION = 60.0
FAULT_START, FAULT_LEN = 20.0, 30.0

#: The detection index a magnitude must reach to count as detected on a
#: channel. FIXED FOR EVERY PREDICTOR, so the comparison is of floors and
#: not of thresholds. d' = 1 is one clean-window standard deviation of
#: separation, the conventional weakest useful value; nothing here is tuned
#: to it and the raw curve is reported so a reader can pick another.
D_PRIME_DETECTED = 1.0

#: Magnitude grids, per fault kind, spanning well below and well above the
#: campaign ranges so a floor is BRACKETED rather than assumed. A grid whose
#: smallest value is already detected has not found a floor and says so.
#: EVERY PARAMETER NAME HERE WAS READ OUT OF THE SENSOR THAT CONSUMES IT.
#: The first version guessed three of them -- `depth` for the battery,
#: `amp` for the magnetometer, `rate` for the GPS -- and a sensor silently
#: ignores a parameter it does not know, applying its default instead. So the
#: grid swept nothing, the perturbation was identical at every magnitude, and
#: the study reported "no detection floor" for a sweep that never varied the
#: fault. That is the MX-021 shape and `_stimulus_varies` below now catches
#: it. Sources: battery.py:30 depth_v, motor.py:32 rpm_loss,
#: magnetometer.py:34 amplitude / :40 rate, gps.py:42 drift,
#: barometer.py:42 rate, imu.py:57 rate, vibration.py:38 gain.
MAGNITUDES = {
    ("baro", "bias_drift"): ("rate", (0.005, 0.01, 0.02, 0.05, 0.1, 0.2,
                                      0.5, 1.0, 2.0)),
    ("imu0", "bias_drift"): ("rate", (0.002, 0.005, 0.01, 0.02, 0.05, 0.1,
                                      0.2, 0.5, 1.0)),
    ("battery", "power_sag"): ("depth_v", (0.05, 0.1, 0.2, 0.4, 0.8, 1.3,
                                           2.0, 3.0)),
    ("vibration", "vibration_anomaly"): ("gain", (1.2, 1.5, 2.0, 3.0, 5.0,
                                                  8.0, 12.0)),
    ("mag", "emi_spike"): ("amplitude", (0.5, 1.0, 2.0, 5.0, 10.0, 20.0,
                                         50.0)),
    # gps.py:42 reads `drift` as a THREE-VECTOR of metres, defaulting to
    # (3, 0, 0) -- a latitude-only offset. Sweeping a scalar called `rate`
    # left every run on that default.
    ("gps", "gps_spoof"): ("drift", ((1.0, 0.0, 0.0), (3.0, 0.0, 0.0),
                                     (10.0, 0.0, 0.0), (30.0, 0.0, 0.0),
                                     (100.0, 0.0, 0.0))),
    ("motor_esc", "power_sag"): ("rpm_loss", (25.0, 100.0, 250.0, 500.0,
                                              1000.0, 2200.0)),
}

def _check_grid_parameters():
    """AT IMPORT. `PARAMETER_INERT` inside `run_floors` catches this too, but
    only after a full sweep has run; this catches it before one starts, and
    names the parameters the sensor does read."""
    from csia_stress.fault_params import assert_effective
    for (sensor, kind), (param, _values) in MAGNITUDES.items():
        assert_effective(sensor, kind, [param])


_check_grid_parameters()


#: The single-magnitude faults used by the whiteness-versus-detection half of
#: the study, DERIVED from the grids above rather than restated, so the two
#: halves cannot drift apart and be compared anyway. The representative
#: magnitude is the grid's upper-middle point: large enough that a real
#: detector sees it, small enough not to saturate every candidate.
FAULTS = {
    f"{sensor}_{kind}": Fault(kind, sensor, FAULT_START, FAULT_LEN,
                              {param: values[max(0, len(values) * 2 // 3)]})
    for (sensor, kind), (param, values) in MAGNITUDES.items()
}


# --- the predictors --------------------------------------------------------

class Holt:
    """EXACTLY CSIA's `_Holt`, copied so the baseline is the real baseline.

    Not imported, because importing it from the frozen module and then
    comparing against variants would make an accidental edit to the frozen
    file look like a predictor result. Pinned instead by a test that asserts
    this recursion matches `csia.runtime.online._Holt` sample for sample.
    """

    name = "holt (CSIA baseline)"
    fits = False

    def __init__(self, alpha=0.3, beta=0.05):
        self.a, self.b = alpha, beta
        self.level = None
        self.trend = 0.0

    def innovation(self, x):
        if self.level is None:
            self.level = float(x)
        pred = self.level + self.trend
        err = float(x) - pred
        self.level = pred + self.a * err
        self.trend = self.trend + self.a * self.b * err
        return err


class Persistence:
    """Predict the last value. The floor: anything worse is not a predictor."""

    name = "persistence"
    fits = False

    def __init__(self):
        self.prev = None

    def innovation(self, x):
        x = float(x)
        err = 0.0 if self.prev is None else x - self.prev
        self.prev = x
        return err


class AR:
    """Autoregressive of order p, coefficients fitted offline by least squares.

    THE LEARNED CANDIDATE. Fitting is ordinary linear regression on lagged
    values of a clean training flight -- no library beyond numpy, no network,
    deterministic, and cheap enough to evaluate at 25 Hz (p multiply-adds).
    """

    fits = True

    def __init__(self, order=8):
        self.order = order
        self.coef = None
        self.buf: list = []
        self.name = f"AR({order}) fitted offline"

    def fit(self, series):
        x = np.asarray(series, dtype=float)
        p = self.order
        if len(x) <= p + 10:
            self.coef = np.zeros(p)
            self.coef[0] = 1.0
            return self
        rows = np.stack([x[i:len(x) - p + i] for i in range(p)], axis=1)
        target = x[p:]
        # Lag 1 is the LAST column, so coef[-1] multiplies the most recent
        # sample. Ridge term is 1e-8, present only to keep a singular design
        # matrix from producing infinities on a constant channel.
        gram = rows.T @ rows + 1e-8 * np.eye(p)
        self.coef = np.linalg.solve(gram, rows.T @ target)
        return self

    def innovation(self, x):
        x = float(x)
        if len(self.buf) < self.order:
            self.buf.append(x)
            return 0.0
        pred = float(np.dot(self.coef, self.buf[-self.order:]))
        self.buf.append(x)
        if len(self.buf) > 4 * self.order:
            self.buf = self.buf[-2 * self.order:]
        return x - pred


class DiffAR:
    """AR fitted on FIRST DIFFERENCES, then integrated back.

    Included because it is the shape most likely to expose the failure mode
    this study exists to find: differencing removes a trend, so a model that
    predicts differences well will follow a ramp almost perfectly and hide a
    bias drift. If `d_prime` collapses for anything, it should collapse here.
    """

    fits = True

    def __init__(self, order=8):
        self.order = order
        self.coef = None
        self.buf: list = []
        self.prev = None
        self.name = f"AR({order}) on first differences"

    def fit(self, series):
        d = np.diff(np.asarray(series, dtype=float))
        inner = AR(self.order).fit(d)
        self.coef = inner.coef
        return self

    def innovation(self, x):
        x = float(x)
        if self.prev is None:
            self.prev = x
            return 0.0
        d = x - self.prev
        self.prev = x
        if len(self.buf) < self.order:
            self.buf.append(d)
            return 0.0
        pred_d = float(np.dot(self.coef, self.buf[-self.order:]))
        self.buf.append(d)
        if len(self.buf) > 4 * self.order:
            self.buf = self.buf[-2 * self.order:]
        return d - pred_d


def _candidates():
    return [Holt(), Persistence(), AR(4), AR(8), AR(16), DiffAR(8)]


# --- data ------------------------------------------------------------------

def _sensors(offset: int) -> dict:
    from csia.sensors.barometer import Barometer
    from csia.sensors.battery import Battery
    from csia.sensors.gps import GPS
    from csia.sensors.imu import IMU
    from csia.sensors.magnetometer import Magnetometer
    from csia.sensors.motor import MotorESC
    from csia.sensors.vibration import VibrationSensor
    return {
        "imu0": IMU("imu0", seed=1 + offset),
        "imu1": IMU("imu1", seed=2 + offset),
        "baro": Barometer(seed=3 + offset),
        "mag": Magnetometer(seed=4 + offset),
        "gps": GPS(seed=5 + offset),
        "motor_esc": MotorESC(seed=6 + offset),
        "battery": Battery(seed=7 + offset),
        "vibration": VibrationSensor(seed=8 + offset),
    }


def _streams(faults, profile, offset):
    truth = generate_flight(duration=DURATION, profile=profile)
    return {name: s.sample(truth, tuple(faults))
            for name, s in _sensors(offset).items()}


def _series(streams, sensor, key, col):
    """One channel column, at its native rate, plus ITS OWN timeline.

    A stream can carry more than one timeline. `vibration` holds the raw
    accelerometer at 59990 samples under `t` and the windowed `rms` at 599
    under `t_rms`; taking `t` for both silently pairs a fault window with the
    wrong series, and the first version of this function did exactly that.
    So the time vector is chosen per channel and its length is ASSERTED
    against the channel's, rather than assumed.
    """
    stream = streams[sensor]
    x = np.asarray(stream[key] if col is None
                   else np.asarray(stream[key])[:, col], dtype=float)
    t_key = f"t_{key}" if f"t_{key}" in stream else "t"
    t = np.asarray(stream[t_key], dtype=float)
    if t.shape[0] != x.shape[0]:
        raise ValueError(
            f"{sensor}.{key}[{col}]: timeline {t_key} has {t.shape[0]} "
            f"samples and the channel has {x.shape[0]}; pairing them would "
            f"put the fault window on the wrong samples")
    return t, x


# --- the measurement -------------------------------------------------------

def _innovations(predictor_factory, series, coef_source=None):
    """Run a fresh predictor over a series and return its innovations."""
    p = predictor_factory()
    if getattr(p, "fits", False):
        if coef_source is None:
            raise ValueError(f"{p.name} needs training data and got none")
        p.fit(coef_source)
    return np.array([p.innovation(v) for v in series], dtype=float)


def _autocorr(x, lags=(1, 2, 5)):
    x = np.asarray(x, dtype=float)
    x = x - x.mean()
    denom = float(np.dot(x, x))
    if denom <= 0:
        return {f"lag{k}": None for k in lags}
    return {f"lag{k}": float(np.dot(x[:-k], x[k:]) / denom) for k in lags}


def study_channel_floors(sensor, key, col, sigma) -> dict:
    """The detection floor of each predictor on one channel.

    THE QUESTION IS ABOUT MAGNITUDE, SO THE ANSWER MUST SWEEP MAGNITUDE.
    A single d' at one fault size cannot answer "would it detect SMALLER
    faults". For each predictor this walks the magnitude grid and reports the
    smallest value reaching `D_PRIME_DETECTED`.

    THE NO-STIMULUS GUARD. Before any predictor is scored, the faulted
    channel is differenced against the clean one. If they are identical the
    fault does not touch this channel at all, and the point is recorded as
    NO_STIMULUS and EXCLUDED from every statistic. Scoring it would report
    "the predictor did not detect it" when the truth is "there was nothing
    to detect" -- the MX-021 shape, and it is not hypothetical here: a GPS
    position spoof perturbs none of the four gps channels this predictor
    watches, because horizontal position is deliberately left to the physics
    check.
    """
    grid = MAGNITUDES.get((sensor, _kind_for(sensor)))
    if grid is None:
        return {"sensor": sensor, "channel": f"{key}[{col}]",
                "status": "NO_GRID_DECLARED"}
    param, values = grid
    kind = _kind_for(sensor)

    train = _streams((), "hover_circle", 0)
    clean = _streams((), "fast_cruise", 100)
    _, train_x = _series(train, sensor, key, col)
    t_clean, clean_x = _series(clean, sensor, key, col)
    warm = 32

    protos = _candidates()
    curves = {p.name: [] for p in protos}
    floors = {}
    stimulus = []

    for value in values:
        fault = Fault(kind, sensor, FAULT_START, FAULT_LEN, {param: value})
        fs = _streams((fault,), "fast_cruise", 100)
        t_f, fault_x = _series(fs, sensor, key, col)
        perturbation = float(np.max(np.abs(clean_x - fault_x)))
        stimulus.append({"magnitude": value, "max_abs_perturbation":
                         perturbation})
        if perturbation == 0.0:
            for p in protos:
                curves[p.name].append({"magnitude": value,
                                       "status": "NO_STIMULUS"})
            continue
        for proto in protos:
            factory = ((lambda p=proto: type(p)(p.order))
                       if getattr(proto, "fits", False)
                       else (lambda p=proto: type(p)()))
            c_inn = _innovations(factory, clean_x, train_x)[warm:]
            f_inn = _innovations(factory, fault_x, train_x)[warm:]
            win = (t_clean[warm:] >= FAULT_START + 2.0) & (
                t_clean[warm:] <= FAULT_START + FAULT_LEN)
            win_f = (t_f[warm:] >= FAULT_START + 2.0) & (
                t_f[warm:] <= FAULT_START + FAULT_LEN)
            if not win.any() or not win_f.any():
                continue
            base_abs = float(np.mean(np.abs(c_inn[win])))
            base_sd = float(np.std(c_inn[win]))
            exc = float(np.mean(np.abs(f_inn[win_f])))
            d = (exc - base_abs) / base_sd if base_sd > 0 else None
            curves[proto.name].append({"magnitude": value, "d_prime": d})
            if (d is not None and d >= D_PRIME_DETECTED
                    and proto.name not in floors):
                floors[proto.name] = value

    scored = [s for s in stimulus if s["max_abs_perturbation"] > 0.0]
    # THE SWEPT PARAMETER MUST ACTUALLY REACH THE SENSOR.
    #
    # A sensor silently ignores a parameter name it does not know and applies
    # its default, so a mis-named parameter produces a perfectly plausible
    # sweep in which every magnitude perturbs the channel by exactly the same
    # amount. Three grids in this file's first version did that, and the
    # study reported "no detection floor" for a sweep that never varied the
    # fault. Identical perturbation across a grid is that signature.
    levels = {round(s["max_abs_perturbation"], 12) for s in scored}
    inert = len(scored) > 1 and len(levels) == 1
    if not scored:
        status = "NO_STIMULUS_AT_ANY_MAGNITUDE"
    elif inert:
        status = "PARAMETER_INERT"
    else:
        status = "SCORED"
    return {
        "sensor": sensor, "channel": f"{key}[{col}]", "fault_kind": kind,
        "parameter": param, "declared_sigma": sigma,
        "status": status,
        "distinct_perturbation_levels": len(levels),
        "magnitudes_with_stimulus": len(scored),
        "magnitudes_tried": len(values),
        "stimulus_check": stimulus,
        "detection_floor": {p.name: floors.get(p.name) for p in protos},
        "curves": curves,
    }


def _fmt_ratio(c) -> str:
    """A missing ratio is not 1.0 and must not print as a number."""
    if c["floor_ratio"] is None:
        return "HOLT_NEVER_DETECTED"
    return f"{c['floor_ratio']:.2f}"


def _kind_for(sensor: str) -> str:
    for (s, kind) in MAGNITUDES:
        if s == sensor:
            return kind
    return "bias_drift"


def study_channel(sensor, key, col, sigma) -> dict:
    """One channel column, every predictor, every fault."""
    # TRAIN on one profile and seed; TEST on another of each.
    train = _streams((), "hover_circle", 0)
    test_clean = _streams((), "fast_cruise", 100)
    _, train_x = _series(train, sensor, key, col)
    t_test, test_x = _series(test_clean, sensor, key, col)

    rows = []
    for proto in _candidates():
        factory = (lambda p=proto: type(p)(p.order)) if getattr(
            proto, "fits", False) else (lambda p=proto: type(p)())
        clean_inn = _innovations(factory, test_x, train_x)
        # Discard the warm-up: a fitted model returns 0.0 until its buffer
        # fills, and counting those as perfect predictions would flatter it.
        warm = 32
        clean_inn = clean_inn[warm:]
        clean_sigma = float(np.std(clean_inn))
        clean_abs = float(np.mean(np.abs(clean_inn)))

        # THE BASELINE IS THE SAME TIME WINDOW ON THE CLEAN FLIGHT, not the
        # whole clean flight.
        #
        # The first version compared the fault window (22-50 s) against
        # whole-flight clean statistics, which confounds the fault with the
        # flight phase: `fast_cruise` manoeuvres inside that window, so a
        # channel whose innovations are naturally larger there scored as
        # detected and one whose innovations are naturally smaller scored
        # NEGATIVE. Six of nine channels came back negative, which is what
        # sent me looking. Same window, same profile, same seed, clean
        # against faulted, is a paired comparison and has no such term.
        clean_win = (t_test >= FAULT_START + 2.0) & (
            t_test <= FAULT_START + FAULT_LEN)
        clean_win = clean_win[warm:]
        win_abs = (float(np.mean(np.abs(clean_inn[clean_win])))
                   if clean_win.any() else None)
        win_sigma = (float(np.std(clean_inn[clean_win]))
                     if clean_win.any() else None)

        faults = {}
        for fname, fault in FAULTS.items():
            if fault.target != sensor:
                continue
            fs = _streams((fault,), "fast_cruise", 100)
            tf, fx = _series(fs, sensor, key, col)
            finn = _innovations(factory, fx, train_x)[warm:]
            tf = tf[warm:]
            window = (tf >= FAULT_START + 2.0) & (
                tf <= FAULT_START + FAULT_LEN)
            excursion = (float(np.mean(np.abs(finn[window])))
                         if window.any() else None)
            d_prime = (None if (excursion is None or win_abs is None
                                or not win_sigma)
                       else (excursion - win_abs) / win_sigma)
            faults[fname] = {"fault_excursion": excursion,
                             "clean_same_window_mean_abs": win_abs,
                             "clean_same_window_sigma": win_sigma,
                             "d_prime": d_prime}

        rows.append({
            "predictor": proto.name,
            "fitted": bool(getattr(proto, "fits", False)),
            "clean_sigma": clean_sigma,
            "clean_mean_abs": clean_abs,
            "clean_sigma_over_declared": (clean_sigma / sigma
                                          if sigma else None),
            "clean_autocorrelation": _autocorr(clean_inn),
            "per_fault": faults,
        })
    return {"sensor": sensor, "channel": f"{key}[{col}]",
            "declared_sigma": sigma, "predictors": rows}


def run_floors() -> dict:
    """THE ANSWER TO THE QUESTION ASKED: how much smaller a fault?"""
    channels = []
    for sensor, entries in sorted(HIST_CHANNELS.items()):
        for key, col, sigma in entries:
            channels.append(study_channel_floors(sensor, key, col, sigma))

    scored = [c for c in channels if c.get("status") == "SCORED"]
    blind = [c for c in channels
             if c.get("status") == "NO_STIMULUS_AT_ANY_MAGNITUDE"]
    inert = [c for c in channels if c.get("status") == "PARAMETER_INERT"]
    if inert:
        raise ValueError(
            "the swept parameter never reached the sensor on: "
            + ", ".join(f"{c['sensor']}.{c['channel']} ({c['parameter']})"
                        for c in inert)
            + " -- every magnitude perturbed the channel identically, so the "
              "grid measured nothing. Fix the parameter name against the "
              "sensor that consumes it; do not report a floor from this.")
    baseline = "holt (CSIA baseline)"
    comparisons = []
    for c in scored:
        floors = c["detection_floor"]
        base = floors.get(baseline)
        better = {k: v for k, v in floors.items()
                  if v is not None and (base is None or v < base)}
        best_name = (min(better, key=lambda k: better[k]) if better else None)
        comparisons.append({
            "channel": f"{c['sensor']}.{c['channel']}",
            "fault_kind": c["fault_kind"],
            "parameter": c["parameter"],
            "holt_floor": base,
            "best_floor": (better[best_name] if best_name else base),
            "best_predictor": best_name or baseline,
            # A ratio needs both floors. When Holt never reaches the
            # threshold at any magnitude on the grid and a candidate does,
            # there is no ratio to quote -- the improvement is unbounded
            # BELOW the grid's reach and saying "infinite" would overstate
            # a result whose true size the grid cannot see.
            "floor_ratio": (base / better[best_name]
                            if (best_name and better[best_name]
                                and base is not None) else
                            (None if base is None and best_name else 1.0)),
            "holt_never_detected": base is None,
            "all_floors": floors,
        })

    ratios = [c["floor_ratio"] for c in comparisons
              if c["floor_ratio"] is not None
              and c["holt_floor"] is not None]
    improved = [c for c in comparisons
                if (c["floor_ratio"] is not None and c["floor_ratio"] > 1.0)
                or c["holt_never_detected"]]
    return {
        "schema": "csia.research.predictor_floor_study/1",
        "question": ("By how much would a better nominal predictor lower the "
                     "magnitude at which a fault becomes visible to the "
                     "temporal sub-score?"),
        "d_prime_threshold": D_PRIME_DETECTED,
        "channels_total": len(channels),
        "channels_scored": len(scored),
        "channels_with_no_stimulus_at_any_magnitude": [
            f"{c['sensor']}.{c['channel']}" for c in blind],
        "structural_finding": (
            "A channel with NO STIMULUS at any magnitude is not a detection "
            "failure. It means the fault does not perturb that channel at "
            "all, so no predictor of any kind could see it and reporting a "
            "floor would be reporting an instrument artifact as a result."),
        "comparisons": comparisons,
        "channels_improved": len(improved),
        "median_floor_ratio": (float(np.median(ratios)) if ratios else None),
        "max_floor_ratio": (float(max(ratios)) if ratios else None),
        "detail": channels,
    }


def run() -> dict:
    channels = []
    for sensor, entries in sorted(HIST_CHANNELS.items()):
        for key, col, sigma in entries:
            channels.append(study_channel(sensor, key, col, sigma))

    # The comparison that answers the question, per channel that has a fault.
    verdict = []
    for ch in channels:
        base = next(r for r in ch["predictors"]
                    if r["predictor"].startswith("holt"))
        for fname in sorted({f for r in ch["predictors"]
                             for f in r["per_fault"]}):
            b = base["per_fault"].get(fname, {}).get("d_prime")
            if b is None:
                continue
            best, best_name = b, base["predictor"]
            whitest, whitest_name = base["clean_sigma"], base["predictor"]
            for r in ch["predictors"]:
                d = r["per_fault"].get(fname, {}).get("d_prime")
                if d is not None and d > best:
                    best, best_name = d, r["predictor"]
                if r["clean_sigma"] < whitest:
                    whitest, whitest_name = r["clean_sigma"], r["predictor"]
            verdict.append({
                "channel": f"{ch['sensor']}.{ch['channel']}",
                "fault": fname,
                "holt_d_prime": b,
                "best_d_prime": best,
                "best_predictor": best_name,
                "relative_gain": (best - b) / abs(b) if b else None,
                "whitest_on_clean": whitest_name,
                "whitest_clean_sigma": whitest,
                "holt_clean_sigma": base["clean_sigma"],
                # THE POINT OF THE STUDY. If these disagree, "whiter
                # innovations detect smaller faults" is false on this
                # channel, and the predictor that looks best on healthy data
                # is not the one that detects the fault.
                "whitest_is_also_best_detector": whitest_name == best_name,
            })

    disagreements = [v for v in verdict
                     if not v["whitest_is_also_best_detector"]]
    gains = [v["relative_gain"] for v in verdict
             if v["relative_gain"] is not None]
    return {
        "schema": "csia.research.predictor_study/1",
        "question": ("Would a better nominal predictor let the existing lam "
                     "machinery detect smaller faults?"),
        "design": {
            "train": "hover_circle, seed offset 0",
            "test": "fast_cruise, seed offset 100 -- a different profile AND "
                    "a different noise realisation",
            "metric": "d_prime = (mean|innovation| in the fault window on "
                      "the FAULTED flight - mean|innovation| in the SAME "
                      "window on the CLEAN flight) / std of that clean "
                      "window. Paired on window, profile and seed, so "
                      "flight phase cannot be read as a fault.",
            "warmup_discarded_samples": 32,
        },
        "channels_studied": len(channels),
        "comparisons": len(verdict),
        "cases_where_the_whitest_predictor_is_not_the_best_detector":
            len(disagreements),
        "median_relative_gain_over_holt": (
            float(np.median(gains)) if gains else None),
        "max_relative_gain_over_holt": (float(max(gains)) if gains else None),
        "verdict": verdict,
        "detail": channels,
        "what_this_is_not": (
            "Every fault here is a parametric injection from six known "
            "kinds, so a predictor scored against them is scored against the "
            "injector. The repository records fault classes the simulator "
            "cannot produce at all, and those are the regimes a better "
            "predictor would be claimed to help with. A positive result here "
            "is a reason to collect real data, not a reason to ship a "
            "model. Nothing in CSIA was changed to produce it."),
    }


def _controls():
    """The study is worthless if a predictor cannot fail to detect.

    POSITIVE: on a pure ramp, persistence sees a constant step and the AR on
    first differences predicts the ramp almost exactly. Their innovations
    must differ by orders of magnitude -- that is the fault-tracking effect
    the whole study exists to measure, on data whose answer is arithmetic.

    NEGATIVE: on white noise with no structure, a fitted AR must NOT beat
    persistence meaningfully. A study whose fitted models improved on noise
    would be fitting the training draw, and every gain it reported would be
    that.
    """
    from tools.assurance.instrument_controls import (NEGATIVE, POSITIVE,
                                                     Control, ControlPair,
                                                     register)

    def _ramp_case():
        ramp = np.arange(600, dtype=float) * 0.01
        pers = _innovations(lambda: Persistence(), ramp)
        dar = _innovations(lambda: DiffAR(8), ramp, coef_source=ramp)
        return {"persistence": float(np.mean(np.abs(pers[64:]))),
                "diff_ar": float(np.mean(np.abs(dar[64:])))}

    def _noise_case():
        rng = np.random.default_rng(7)
        train = rng.normal(0.0, 1.0, 4000)
        test = rng.normal(0.0, 1.0, 4000)
        pers = _innovations(lambda: Persistence(), test)
        ar = _innovations(lambda: AR(8), test, coef_source=train)
        return {"persistence_sigma": float(np.std(pers[64:])),
                "ar_sigma": float(np.std(ar[64:]))}

    return register(ControlPair(
        instrument=INSTRUMENT,
        positive=Control(
            name="a differencing model tracks a pure ramp and persistence "
                 "does not",
            kind=POSITIVE,
            run=_ramp_case,
            expect=lambda d: d["diff_ar"] < d["persistence"] / 100.0,
            basis=("the first difference of a linear ramp is a constant, so "
                   "a model fitted on differences predicts it exactly while "
                   "persistence carries the full step every sample; this is "
                   "arithmetic, not a property of this tool"),
        ),
        negative=Control(
            name="a fitted model does not beat persistence on white noise",
            kind=NEGATIVE,
            run=_noise_case,
            # Persistence on white noise has variance 2*sigma^2; an AR that
            # has learned nothing predicts ~0 and gets sigma^2. So the AR is
            # legitimately better by sqrt(2) and no more. Anything beyond
            # that is fitted noise.
            expect=lambda d: d["ar_sigma"] > d["persistence_sigma"] / 1.55,
            basis=("independent samples carry no predictable component; the "
                   "sqrt(2) allowed here is the known ratio between a "
                   "difference of two independent draws and one draw, not a "
                   "tolerance chosen for this study"),
        ),
    ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    from tools.assurance.instrument_controls import guard, stamp
    _controls()
    report = guard(INSTRUMENT)

    doc = {"whiteness_vs_detection": run(), "detection_floors": run_floors()}
    doc = stamp(doc, report)
    text = json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"wrote {args.out}")
        w, f = doc["whiteness_vs_detection"], doc["detection_floors"]
        print(f"\nA. whiteness is not detection: the whitest predictor on "
              f"clean data is NOT the best detector in "
              f"{w['cases_where_the_whitest_predictor_is_not_the_best_detector']}"
              f" of {w['comparisons']} cases")
        print(f"\nB. detection floors ({f['channels_scored']} channels "
              f"scored, {len(f['channels_with_no_stimulus_at_any_magnitude'])}"
              f" with no stimulus at any magnitude)")
        for c in f["comparisons"]:
            print(f"  {c[chr(39)+chr(39)] if False else c['channel']:22s} {c['fault_kind']:18s} "
                  f"holt floor={str(c['holt_floor']):>8s}  "
                  f"best={str(c['best_floor']):>8s}  "
                  f"ratio={_fmt_ratio(c)}  ({c['best_predictor']})")
        print(f"\n  channels improved: {f['channels_improved']} of "
              f"{len(f['comparisons'])}; median floor ratio "
              f"{f['median_floor_ratio']}")
        if f["channels_with_no_stimulus_at_any_magnitude"]:
            print("  no stimulus at any magnitude: "
                  + ", ".join(f["channels_with_no_stimulus_at_any_magnitude"]))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
