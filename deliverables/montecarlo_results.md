# interceptor_seeker — Monte Carlo results (SYNTHETIC first pass)

All numbers produced by `tools/interceptor_montecarlo.py` (fixed seeds, 100 Hz). **Synthetic; not validated against seeker hardware.**

Config: warmup 2.5 s (excluded from metrics), fault onset 8.0 s, actionable trust threshold 0.85.

## Detection & attribution (50 runs each)

| scenario | detection rate | latency mean / median / p95 (s) | attribution acc | mean min-trust (faulted) |
|---|---|---|---|---|
| ir_decoy | 1.00 (50/50) | 0.436 / 0.44 / 0.49 | 1.00 | 0.26 |
| rf_jam | 1.00 (50/50) | 0.242 / 0.24 / 0.351 | 1.00 | 0.04 |

**clean_engagement:** 1/50 runs raised any alarm (false-alarm rate 0.02).

## Exonerated-channel trust (unfaulted channels, 50 runs each)

Minimum trust of each *unfaulted* channel over the armed window (t > 2.5 s warmup), across all 50 runs. `min across runs` = the single lowest value any run reached; `mean of per-run min` = average of each run's minimum.

| faulted scenario | unfaulted channel | min across runs | mean of per-run min |
|---|---|---|---|
| ir_decoy | rf_seeker | 0.494 | 0.687 |
| ir_decoy | ins | 0.752 | 0.935 |
| rf_jam | ir_seeker | 0.214 | 0.260 |
| rf_jam | ins | 0.272 | 0.386 |

Reading: a channel is cleanly *trust*-exonerated only when it shares no graph edge with the faulted channel. INS shares no edge with the IR channel, so under ir_decoy it stays high (min 0.752). INS shares Edge B (rangerate_ins) with the RF channel, so under rf_jam it sags (min 0.272) — there it is exonerated by the diagnosis posterior (no INS hypothesis fires), not by trust value. Likewise the shared-bearing partner sags in both cases. This is the documented shared-edge coupling (see limitations).

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