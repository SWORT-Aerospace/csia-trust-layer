"""Seeker scenario catalog (fixed-seed, reproducible), mirroring the quad
csia.scenarios pattern. Faults are plain dicts consumed by sensors.py.

  clean_engagement — no faults; false-alarm baseline.
  ir_decoy         — IR bearing ramps to `offset_deg` from onset (decoy pull);
                     RF and INS truthful.
  rf_jam           — RF azimuth + range-rate slow-bias ramp + inflated
                     variance from onset; IR and INS truthful.
  multipath_glitch — 1-3 tick RF range/azimuth outlier spike (gate/dwell
                     suppression demo).
"""

SEEKER_SCENARIOS = {
    "clean_engagement": ("Full closing engagement, no faults", []),
    "ir_decoy": ("IR decoy: bearing pulled 6 deg from t=8 s",
                 [{"kind": "ir_decoy", "start": 8.0, "offset_deg": 6.0,
                   "ramp_s": 1.5}]),
    "rf_jam": ("RF jam: 4 deg az bias + 40 m/s range-rate bias from t=8 s",
               [{"kind": "rf_jam", "start": 8.0, "az_bias_deg": 4.0,
                 "rrate_bias": 40.0, "var_mult": 4.0, "ramp_s": 2.0}]),
    "multipath_glitch": ("RF multipath: 2-tick range/az spike at t=10 s",
                         [{"kind": "multipath_glitch", "start": 10.0,
                           "ticks": 2, "range_spike": 300.0,
                           "az_spike_deg": 8.0}]),
}


def scenario_faults(name):
    if name not in SEEKER_SCENARIOS:
        raise KeyError(f"unknown seeker scenario {name!r}; "
                       f"available: {list(SEEKER_SCENARIOS)}")
    return SEEKER_SCENARIOS[name][1]
