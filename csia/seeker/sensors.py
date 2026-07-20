"""Seeker sensor models + fault/countermeasure injection.

Three nodes, mirroring the quad sensor-model pattern (truth + documented
Gaussian noise budget + injectable faults). All noise sigmas are
first-pass, representative-but-synthetic values chosen from the noise-budget
methodology the quad profile uses; they are NOT drawn from real seeker
datasheets and must be re-characterized against hardware before any claim.

  ir_seeker  — LOS azimuth/elevation (rad) + signal intensity (a.u.).
  rf_seeker  — range (m), closing velocity (m/s), azimuth (rad), lock flag.
  ins        — own-ship position/velocity (world) with slow drift.

Noise budget (documented):
  IR angular sigma      2.0 mrad  (fine-resolution imaging seeker, synthetic)
  RF angular sigma      6.0 mrad  (coarser than IR — antenna beamwidth)
  RF range sigma        8.0 m
  RF range-rate sigma   1.5 m/s   (Doppler)
  INS velocity sigma    0.4 m/s   + slow random-walk bias
  INS position sigma    1.5 m     + slow random-walk bias
  IR intensity model    I = IR_K / range^2  (+ 3% multiplicative noise)
"""

import numpy as np

IR_AZ_SIGMA = 2.0e-3       # rad
IR_EL_SIGMA = 2.0e-3
RF_AZ_SIGMA = 6.0e-3       # rad
RF_RANGE_SIGMA = 8.0       # m
RF_RRATE_SIGMA = 1.5       # m/s
INS_VEL_SIGMA = 0.4        # m/s
INS_POS_SIGMA = 1.5        # m
INS_VEL_RW = 0.03          # m/s per sqrt(sample) random-walk bias
IR_K = 3.0e8               # intensity scale (a.u.*m^2); ~1.0 at 17.3 km
IR_INTENSITY_NOISE = 0.03  # fractional


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def sample_ir(eng, faults, seed):
    rng = np.random.default_rng(seed)
    n = eng.n
    az = eng.az + rng.normal(0, IR_AZ_SIGMA, n)
    el = eng.el + rng.normal(0, IR_EL_SIGMA, n)
    intensity = IR_K / np.maximum(eng.rng, 1.0) ** 2
    intensity *= 1.0 + rng.normal(0, IR_INTENSITY_NOISE, n)
    for f in faults:
        if f["kind"] == "ir_decoy":
            # decoy pulls the reported bearing off the true target along a
            # plausible ramp to `offset_deg` over `ramp_s`, from onset.
            # Optional `end`: fault clears (recovery demo for the video tool).
            on = (eng.t >= f["start"]) & (eng.t < f.get("end", np.inf))
            elapsed = np.clip(eng.t - f["start"], 0, f.get("ramp_s", 1.5))
            frac = elapsed / f.get("ramp_s", 1.5)
            off = np.deg2rad(f["offset_deg"]) * frac * on
            az = az + off
    return {"t": eng.t, "az": az, "el": el, "intensity": intensity,
            "valid": np.ones(n, bool)}


def sample_rf(eng, faults, seed):
    rng = np.random.default_rng(seed)
    n = eng.n
    rrange = eng.rng + rng.normal(0, RF_RANGE_SIGMA, n)
    closing = eng.closing + rng.normal(0, RF_RRATE_SIGMA, n)
    az = eng.az + rng.normal(0, RF_AZ_SIGMA, n)
    lock = np.ones(n, bool)
    for f in faults:
        if f["kind"] == "rf_jam":
            on = (eng.t >= f["start"]) & (eng.t < f.get("end", np.inf))
            elapsed = np.clip(eng.t - f["start"], 0, f.get("ramp_s", 2.0))
            frac = elapsed / f.get("ramp_s", 2.0)
            # slow bias ramp on azimuth + range-rate, plus inflated variance
            az = az + np.deg2rad(f.get("az_bias_deg", 4.0)) * frac * on
            closing = closing + f.get("rrate_bias", 40.0) * frac * on
            extra = f.get("var_mult", 4.0)
            az = az + on * rng.normal(0, RF_AZ_SIGMA * extra, n)
            closing = closing + on * rng.normal(0, RF_RRATE_SIGMA * extra, n)
        elif f["kind"] == "multipath_glitch":
            # 1-3 tick outlier spike on range + azimuth
            k0 = int(round(f["start"] * eng.tick_hz))
            width = f.get("ticks", 2)
            sl = slice(k0, k0 + width)
            rrange[sl] += f.get("range_spike", 300.0)
            az[sl] += np.deg2rad(f.get("az_spike_deg", 8.0))
    return {"t": eng.t, "range": rrange, "closing": closing, "az": az,
            "lock": lock, "valid": np.ones(n, bool)}


def sample_ins(eng, faults, seed):
    rng = np.random.default_rng(seed)
    n = eng.n
    vbias = np.cumsum(rng.normal(0, INS_VEL_RW, (n, 3)), axis=0)
    v = eng.v_i + vbias + rng.normal(0, INS_VEL_SIGMA, (n, 3))
    p = eng.p_i + np.cumsum(vbias, axis=0) * eng.dt \
        + rng.normal(0, INS_POS_SIGMA, (n, 3))
    return {"t": eng.t, "pos": p, "vel": v, "valid": np.ones(n, bool)}
