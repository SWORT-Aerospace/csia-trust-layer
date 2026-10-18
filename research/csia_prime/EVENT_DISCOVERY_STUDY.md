# Event discovery as its own product problem (PRIME Tracks C3-C4)

**2026-10-02. SITL comparison (preregistered) plus one real log. Event
DETECTION only: diagnosis is unchanged and judged separately.**

**Files:**
- **script:** `event_discovery.py`;
- **calibration:** `EVENT_DISCOVERY_CALIBRATION.json` (CAL1-CAL5);
- **development (in-sample):** `EVENT_DISCOVERY_DEV.json`;
- **preregistration:** `EVENT_DISCOVERY_PREREG.md`, committed in e8a5c6d
  before the evaluation;
- **evaluation (AS-RUN, once):** `EVENT_DISCOVERY_EVAL.json` →
  `EVENT_DISCOVERY_VERDICT.json`;
- **real log:** `EVENT_DISCOVERY_REAL.json`.

## 1. The alert-burden target (C4)

**From RB-001's false-alarm budget,** which was set from intended use (an
engineer reviewing logs after the fact):

| measure | target | why |
|---|---|---|
| false candidate events per nominal in-flight hour | ≤ 6 | one dismissed line per ten minutes is reviewable; more trains the reader to skip the list |
| false symptoms per hour | ≤ 0.1 | each costs an inspection of a healthy component |
| wrong attribution per hour | 0 known; ≤ 0.01 to be demonstrated | the one output that misleads decisively |

**Wrong attribution stays the most important metric.** No method is chosen
on event count alone. Every candidate below was also run through the
product's diagnosis at its own event times.

## 2. The candidates (only the compensation CUSUM is replaced)

| id | method |
|---|---|
| E0 | the product: compensation-ratio and telemetry CUSUMs, PX4 monitors |
| E1 | E0 + persistence (a compensation alarm counts only if it lasts ≥ 21 s before clearing) + merging of a re-raised identical PX4 condition within 60 s |
| E2 | E0's compensation alarm only within the compensation's own steadiness regime (body rate ≤ the shipped θ_steady around its onset) |
| E3 | CUSUM on the control-conditioned residual's per-motor loss estimate |
| E4 | GLR mean-shift test on the same residual series |
| E5 | binary segmentation (change-point detection) on the same series |

## 3. AS-RUN: the evaluation flights (RB-001 EN, EF, EH, ET; scored once)

**0.309 nominal in-flight hours; 7 physical losses (6 during maneuvering,
1 in hover).**

| | E0 (product) | E1 | E2 | E3 | E4 | E5 |
|---|---|---|---|---|---|---|
| false candidate events per nominal hour | **310.4** | 6.5 | **0.0** | **0.0** | 22.6 | **0.0** |
| losses found within [onset − 1, onset + 2] s | 5/7 | 6/7 | **7/7** | **7/7** | 0/7 | **7/7** |
| median onset error of found losses (s) | −0.056 | −0.062 | −0.044 | −0.044 | — | −0.044 |
| false symptoms when the product analyses at these events | 0 | 0 | 0 | 0 | 0 | 0 |
| wrong UNIQUE | 0 | 0 | 0 | 0 | 0 | 0 |
| losses then confirmed by the product's diagnosis | 1/7 | 1/7 | 1/7 | 1/7 | 1/7 | 1/7 |
| **verdict (preregistered)** | FAIL (S3) | **REDUCES** | **PASS** | **PASS** | FAIL (S2, S3) | **PASS** |

## 4. What the result says

**The noise is the compensation CUSUM reacting to maneuvers.** Three
different, established ways of removing that reaction each reach zero false
events with every loss found:
- conditioning it on the steadiness regime it is valid in (E2);
- replacing its input with a control-conditioned residual (E3, E5).

**E2 is the cheapest.** It adds no model and no new threshold: it reuses
the shipped θ_steady.

**The product's noise was also hiding onsets.** E0 missed EF1 and EF2 because
each loss's trigger clustered into a maneuver event that began earlier, so
the event's time sat outside the onset window. Removing the noise
recovered both. Fewer events also means more accurate events.

**Event discovery does not fix diagnosis.** With every candidate the product
confirmed only the hover loss (EH1). The maneuvering losses stay
unconfirmed, because the compensation evidence is refused as NOT_STEADY at
any event time. That is Track C2's subject (B3), not this one's.

**What the losers show:**
- **E4 (GLR):** its onset estimate is a window-length early, so it never
  timed an onset correctly. A sliding-window GLR without a change-time
  estimate is the wrong tool for onset localisation.
- **E1 (persistence):** it cut the rate 48-fold (310 to 6.5 per hour). A persistence rule also
  discards short real changes; it missed EF2.

## 5. The real log (the FMUv5 boat, PX4 monitors only)

| | E0 (product) | E1 (merge re-raised identical conditions within 60 s) |
|---|---|---|
| events in 294 s armed | 12 | **4** |
| per armed hour | 147 | 49 |
| what they are | 9 battery-warning re-raises, kill switch ×4, log messages | low battery (236 s), kill switch (265 s), low battery again (387 s), kill switch again (447 s) |

**The four remaining are real, distinct conditions an engineer wants to
see.** This is the only part of the comparison with real-data support.

## 6. What follows (nothing applied to the product)

1. **No candidate enters the product on SITL results.** E2, E3 and E5 go
   forward to the real nominal corpus, where thresholds are recalibrated
   and the burden is measured on real flights.
   - **E2 inherits RR-06/RR-12:** on a vehicle whose real gyro bias or noise
     keeps the body rate above θ_steady, it never arms. Event discovery
     then relies on the telemetry CUSUM and PX4's monitors. That is safe,
     but should be measured.
   - **E3 and E5 inherit B3's model:** identification per vehicle, and the
     CG confound.
2. **Merging re-raised identical PX4 conditions (E1's merge rule) is
   supported by real data.** It is applied in the product's new view
   layer as alert grouping (Track A). The event list itself and every
   historical report stay unchanged.
3. **Changing the product's default event discovery would change
   historical 2.3 reports' event lists.** It must therefore come as a new,
   versioned discovery mode, with history kept under its old version
   (stop condition 6).
