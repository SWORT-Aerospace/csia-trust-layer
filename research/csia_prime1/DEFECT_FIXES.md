# D-PRIME-1 and D-PRIME-2: the versioned fixes (PRIME-1 Phases 2-7)

**2026-10-03. Owner-approved versioned fixes. History unchanged.**

- **Both defects reproduced before any change:** `BASELINE_PRIME1.json`,
  committed in 29156b8.
- **Both are fixed in release `prime1` only.** Release `2.3` keeps them, as
  recorded.
- **Results:** `DEFECT_FIX_RESULTS.json`. **Regressions:**
  `tests/test_csia_prime1.py`.

## 1. Versioning (Phase 2)

| release | what | where |
|---|---|---|
| `2.3` | the stock bridge exactly as validated in 2.3 and used by PRIME | `analyze`; `assure --release prime`; default of every function that takes a release |
| `prime1` | CSIA Flight Assurance PRIME-1 | `assure` and `csia-assure` by default |

`csia_evidence_assurance/releases.py` holds the registry. A `prime1` report
names its release, timebase and discovery statistics. Its telemetry producer
carries its own version (`csia-prime1-stock-tel-r1`, contract
`stock-tel-2`). **A `2.3` report gains no field at all**, so its bytes are
unchanged.

**One recorded exception.** `manifest.json` records a digest of the whole
product package (`report.code_digests`). It changes whenever any package
file changes, including successor-only files the historical path never runs.
Every other byte of every historical output regenerates identically
(`HISTORICAL_GATE.json`).

## 2. D-PRIME-1: time representation changed an admissibility decision

**The defect.**
- The stock adapter rounded content times to the microsecond; the event
  anchor was not rounded.
- The 2.2 gate compared them as floats with a 1 ns tolerance.
- A sub-microsecond shift of every timestamp (0.5, 0.5001, 0.7 or 2.7 us)
  lost a hover loss's symptom, with 13 pieces of valid evidence rejected.

**The policy chosen (Phase 3): a canonical integer timebase at the declared
clock resolution.** It is not a larger tolerance.

| representation | before | prime1 |
|---|---|---|
| PX4 ULog timestamps | integer us, converted to float seconds | unchanged (already on the grid) |
| stock-topic times in the analysis | float, possibly off-grid (synthetic, resampled, perturbed input) | snapped to the 1 us grid on ingestion (`StockLog.canonical`, round half to even); two inputs that differ by less than half a tick become the same input |
| event anchors | the earliest trigger time, any float | on the grid (they come from canonical samples; discovery also snaps them) |
| content and produced times | rounded to 6 decimals by the adapter | unchanged |
| the gate's comparisons (window, future content, produced-before-content, staleness) | floats, 1 ns tolerance | integer ticks of `AnalysisContext.time_resolution_s` (1 us) |
| a producer with a coarser clock (a future bench instrument) | not representable | `producer_time_resolution_s` declares it; its times are compared at its coarser resolution |

**The principle.** Equivalent physical times at the supported precision get
the same decision. Evidence one tick outside its window is outside.

**Phase 4 tests** (`tests/test_csia_prime1.py`, all passing):
- exact lower and upper boundary;
- just inside and just outside (one tick);
- 0.4999 us (same tick) and 0.5001 us (next tick) at the boundary;
- anchor and content moved together by 0.3-2.7 us;
- a nanosecond producer;
- a producer declaring a 1 ms clock;
- a negative-offset window;
- two named anchors;
- out-of-order produced time (within one tick it is not impossible; two
  ticks are);
- a stale record (stale from the next tick);
- the historical float comparison, unchanged.

**End to end, on the synthetic hover loss:**

| shift (us) | 0 | 0.3 | 0.4999 | 0.5 | 0.5001 | 0.7 | 1.0 | 2.7 |
|---|---|---|---|---|---|---|---|---|
| `2.3` | symptom | symptom | symptom | **lost (13 rejected)** | **lost** | **lost** | symptom | **lost** |
| `prime1` | symptom | symptom | symptom | symptom | symptom | symptom | symptom | symptom |

## 3. D-PRIME-2: an RPM excess never opened an event

**The defect, in two halves:**
1. The telemetry CUSUM accumulated only a deficit. An RPM report above
   command opened no event: 2.3's V10 relied on PX4's simulation-only
   injection message.
2. When some later trigger opened an event, the event-relative statistic
   compared a corrupted BEFORE window with a corrupted AFTER window. It read
   NOMINAL, so the corruption disappeared from the report.

**The fix (Phase 6), as explicit event semantics, not `abs(change)`.**

| element | prime1 |
|---|---|
| RPM_DEFICIT_EVENT (`propulsion.rpm_deficit`) | one-sided CUSUM on reference - q (the 2.3 arm, renamed) |
| RPM_EXCESS_EVENT (`propulsion.rpm_excess`) | a second one-sided CUSUM on q - reference: a separate arm, separate trigger kind, separate semantics in the trigger record |
| thresholds | the same frozen k_tel, h_tel. The 2.3 calibration rule set k from the largest **absolute** null deviation, so both directions were calibrated together |
| a channel that is already inconsistent | a telemetry alarm counts only while the channel's own trailing reference is within the declared band (q in [1/2, 2]); further excursions of a reported corruption open no new event |
| the late-event half | the telemetry statistic is withheld (UNAVAILABLE, `TELEMETRY_BASELINE_INCONSISTENT`) when its BEFORE window disagrees grossly with the other rotors, and the compensation then has no valid deficit to test |
| a flight-long inconsistency | a coverage notice names a rotor whose telemetry disagrees with its peers for most of the flight |
| ESC offline | `px4.esc_offline` (ESC_OFFLINE_EVENT): PX4's own offline bit, not a deficit |

**The event layer still attributes nothing.** It says only that a
telemetry channel changed enough to warrant analysis. A telemetry change is
never a motor fault on its own (finding SB-1, unchanged).

**Results:**

| case | `2.3` | `prime1` |
|---|---|---|
| synthetic RPM x0.1, x0.5, x0.775, x0.9 | deficit event, DEGRADED | RPM_DEFICIT_EVENT, DEGRADED (deficit) |
| synthetic RPM x1.1, x1.29, x2, x10 | **no event; never reported** | RPM_EXCESS_EVENT, DEGRADED (excess) |
| 2.3 V10 blinded (RPM x10, no injection message) | events at 56.5 s and 78.7 s (late); telemetry NOMINAL; "nothing adverse was observed" | RPM_EXCESS_EVENT at 49.6 s (the true onset); DEGRADED excess, L = -98.7; no motor fault |
| synthetic x10 analysed at a late anchor (80 s) | NOMINAL | UNAVAILABLE, TELEMETRY_BASELINE_INCONSISTENT |
| telemetry matrix, development bases (15 kinds x hover and maneuvering) | 20 of 30 by behaviour: all 10 excess and step-up cases missed. The matrix scores trigger names, which gives 2.3 8 of 30, because its deficit trigger is called `telemetry_change` | **30 of 30 as expected** |

**Not every perturbation becomes an anomaly** (`telemetry_matrix.py`; the
expected outcome per kind was written down before any run):
- a static offset from boot, a drift of 0.5 per cent per second, and a stuck
  value in hover open no event. They are **stated blind spots** of a change
  detector;
- a stuck value during maneuvering is found;
- a 10 s dropout is a log gap: refused, never a measurement.

## 4. Phase 7: no simulation-leak dependence

**The product reads none of the following:**
- PX4's failure-injection message: never a trigger; counted only in the
  labelled debug field `inputs.event_discovery.test_harness_messages_ignored`;
- SIH parameters (changed parameters are not read; initial parameters are
  read from a fixed list);
- truth labels, research sidecars, or a known onset (except through the
  benchmark hook, which is never the product path).

**Permanent test.** The same synthetic flight (telemetry x10, motor loss,
nominal), with and without an injection message and an SIH parameter, gives:
- identical events;
- identical symptoms;
- identical attribution;
- every evidence value identical.

Only the debug counter differs. The held-out evaluation repeats this on raw
against blinded copies of every flight (criterion S6).

## 5. Phase 5: the historical gate (`historical_gate.py`, `HISTORICAL_GATE.json`)

| history | result |
|---|---|
| XSYS-001 | 3,872 slots, 0 decision differences, 55/55, LB 0.7616 |
| Phase C, governance | unchanged |
| 2.2 replay corpus, XSYS replay, receipts, E1 | equal to the committed results |
| 2.2, pilot, 2.3, RB-001, PRIME tests | 51, 22, 33, 10 and 19 (+2 expected-fails pinning the historical defects) passed |
| 2.3 reports V1, V9, V13 | byte-identical (`analyze`) |
| PRIME's 11 sample outputs | identical (`assure --release prime`); manifests differ only in the recorded code digest |
| PRIME-A's 39 logs (historical path) | no crash; deterministic |

**No historical decision changed.**
