# interceptor_seeker extension — run summary

**SYNTHETIC first-pass. Nothing here is flight software or validated against
real seeker hardware.** The engagement is a kinematic 2D closing-intercept
model; sensor noise budgets are representative engineering defaults, not
datasheet values. Every number below was produced by an actual run in this
repo (fixed seeds, reproducible bit-for-bit). Prepared for U.S. Army
xTech|Apex Intercept, Topic 4.

## What was built

New code (extension only — the trust engine, diagnosis engine, and runtime
core were **not** modified; the seeker drives the unmodified `TrustCore` and
`DiagnosisCore`):

- `csia/seeker/engagement.py` — pure-pursuit closing-intercept truth model.
- `csia/seeker/sensors.py` — IR / RF / INS sensor models + fault injection.
- `csia/seeker/runtime.py` — 2 comparator edges + 3 physics self-models +
  `SeekerPolicy` escalation ladder; drives the unmodified cores.
- `csia/seeker/scenarios.py` — fixed-seed scenario catalog.
- `csia/profiles.py` — registered `interceptor_seeker` `VehicleProfile`.
- `tools/interceptor_montecarlo.py`, `tools/interceptor_plots.py`.
- `tests/scenarios/test_seeker_scenarios.py` — 7 new tests.

Deliverables in `deliverables/`: `trust_graph_catalog.md`,
`montecarlo_results.{md,json}`, `failsafe_transitions.md`, `license_audit.md`,
three PNG plots, this summary.

## Trust graph (3 nodes)

Nodes: `ir_seeker`, `rf_seeker`, `ins`. Edges: **A** bearing agreement
(IR az vs RF az; gated by RF lock ∧ IR SNR proxy), **B** RF range-rate vs
INS-projected closing (gated by closing phase). Physics self-models:
`phys_rf` (RF closing vs range-derived rate), `phys_ir` (1/R² irradiance vs
IR intensity), `phys_ins` (INS velocity vs windowed position rate).

## Headline numbers (100 Hz, 50 runs/scenario unless noted)

| scenario | detection rate | latency mean / p95 (s) | attribution acc | mean min-trust (faulted) |
|---|---|---|---|---|
| ir_decoy (6° bearing pull) | **50/50 (1.00)** | 0.44 / 0.49 | **1.00** | 0.26 |
| rf_jam (4° az + 40 m/s rr bias) | **50/50 (1.00)** | 0.24 / 0.35 | **1.00** | 0.044 |
| clean_engagement | **1/50 alarms (0.02)** | — | — | 1 brief CAUTION, endgame |

Per-tick trust+diagnosis latency: ~57 µs (reference Python, desktop).

## Detection floor (ir_decoy magnitude sweep, 20 runs/magnitude)

| decoy offset | 0.1° | 0.2° | 0.35° | 0.6° | 1.5° | 4.0° |
|---|---|---|---|---|---|---|
| detection rate | 0.00 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 |
| mean latency (s) | — | 5.07 | 2.62 | 1.42 | 0.79 | 0.50 |

**Detection floor ≈ 0.2–0.35°**, i.e. the combined IR+RF bearing noise
budget (σ ≈ 0.36°). Below it the decoy is statistically indistinguishable
from sensor noise and is correctly *not* detected — this is a physical floor,
not a tuning failure, and it is reported as a result.

## Failsafe / escalation

The `SeekerPolicy` ladder (NORMAL→CAUTION→CRITICAL, reusing the CSIA
`FailsafeLevel` enum) escalated correctly per scenario; full transition logs
in `failsafe_transitions.md`. CRITICAL on a targeting channel emits
`INHIBIT_TERMINAL_COMMIT` + `HANDOVER_TO_ALT_SEEKER` (advisory) — the
engagement-confidence signal the white paper maps to fire control.

## Test status

**48/48 pass** (`python -m pytest`): 41 pre-existing (all still green,
confirming the extension did not disturb the core) + 7 new seeker tests
(detection, attribution, INS exoneration, clean no-alarm, determinism,
unmodified-core check, detection-floor bracket).

## Anomalies, surprises, honest caveats

1. **IR is dragged down under RF jam** (min-trust ≈ 0.27) via the *shared*
   bearing edge, even though IR is truthful. Diagnosis still attributes
   `rf_jam` at 100% (the RF-specific edge B + phys_rf discriminate), but the
   IR *trust value* is coupled. A third independent bearing reference (or an
   RF-independent IR check) would decouple this. Documented, not hidden.
2. **`phys_ir` is necessary, not optional** (contrary to the task's "Edge C
   only if time"): without an RF-independent IR self-model, the IR node has
   only the shared bearing edge and is both falsely implicated under RF jam
   and at risk of empty evidence. It was implemented for correctness.
3. **First-pass calibration bug found and fixed honestly:** single-tick
   differencing of range/position at 100 Hz amplified sensor noise ~100×,
   collapsing `phys_rf`/`phys_ins` in *clean* flight. Fixed with windowed
   (0.5 s) rate estimation, not by inflating σ to mask it.
4. **Warmup (2.5 s) is excluded from metrics**, identical methodology to the
   quad profile's prior-convergence exclusion. During warmup the rate
   windows fill and the Beta prior settles; trust transiently dips then
   recovers. The escalation ladder arms only after warmup.
5. **multipath_glitch** (2-tick RF spike) produced one brief CAUTION rather
   than full suppression — the EW smoothing + Beta integrator spread the
   spike beyond the dwell window. A transient result, reported as-is.
6. **"INS-derived closing velocity" uses the known target velocity**, valid
   in this synthetic setup; on a real system that term comes from a track
   filter. This is the single biggest fidelity gap vs a real deployment.
7. **1/50 clean runs (seed 3038) raised a brief CAUTION** near intercept
   (t≈10–13 s), where the closing geometry becomes extreme; channels dipped
   to ~0.70 (never reaching the 0.55 CRITICAL threshold) and self-cleared.
   Reported as-is: false-alarm rate 0.02, all CAUTION-level, all in the
   terminal endgame. Not tuned away.
8. **Reproducibility bug found and fixed during the sanity re-run:** the
   Monte Carlo previously seeded from `hash(scenario_name)`, which Python
   randomizes per process — so numbers were not bit-reproducible across runs.
   Replaced with fixed per-scenario seed bases; two consecutive runs are now
   byte-identical. (The earlier "0/50 clean" figure was an artifact of the
   non-reproducible seeding; the reproducible figure is 1/50.)

## Reproduce every number

```sh
python -m pytest tests/scenarios/test_seeker_scenarios.py   # scenario tests
python tools/interceptor_montecarlo.py     # -> montecarlo_results.{md,json}
python tools/interceptor_plots.py          # -> the 3 PNG plots
python -m pytest                           # full suite
```

All runs are deterministic (fixed per-scenario seed bases: ir_decoy 1000+i,
rf_jam 2000+i, clean 3000+i; sweep 50000+…); re-running reproduces the
tables above bit-for-bit (verified: two consecutive runs byte-identical).
