# interceptor_seeker — Monte Carlo results (SYNTHETIC first pass)

All numbers produced by `tools/interceptor_montecarlo.py` (fixed seeds, 100 Hz). **Synthetic; not validated against seeker hardware.**

Config: warmup 2.5 s (excluded from metrics), fault onset 8.0 s, actionable trust threshold 0.85.

## Detection & attribution (50 runs each)

| scenario | detection rate | latency mean / median / p95 (s) | attribution acc | mean min-trust (faulted) |
|---|---|---|---|---|
| ir_decoy | 1.00 (50/50) | 0.436 / 0.44 / 0.49 | 1.00 | 0.26 |
| rf_jam | 1.00 (50/50) | 0.242 / 0.24 / 0.351 | 1.00 | 0.04 |

**clean_engagement:** 1/50 runs raised any alarm (false-alarm rate 0.02).

## ir_decoy magnitude sweep (20 runs/magnitude) — detection floor

| decoy offset | detection rate | mean latency (s) |
|---|---|---|
| 0.1deg | 0.00 (0/20) | — |
| 0.2deg | 0.50 (10/20) | 5.072 |
| 0.35deg | 1.00 (20/20) | 2.616 |
| 0.6deg | 1.00 (20/20) | 1.419 |
| 1.5deg | 1.00 (20/20) | 0.789 |
| 4.0deg | 1.00 (20/20) | 0.499 |

The detection floor is the smallest offset with a detection rate below 1.0; below it the decoy is within the combined bearing noise budget and is (correctly) not separable from noise.