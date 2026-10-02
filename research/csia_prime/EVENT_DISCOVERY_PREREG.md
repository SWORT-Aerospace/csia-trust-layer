# Event discovery comparison: preregistration (PRIME Track C3-C4)

**2026-10-02. Committed after calibration and the development run, BEFORE
the evaluation run.** Nothing below changes after this commit. Any later
analysis is labelled POST-HOC.

## 1. What is frozen

| item | frozen as |
|---|---|
| candidates, scoring, downstream analysis | `event_discovery.py`, SHA-256 `cd02b3c571f9e6cead90b4482a77f11fa82b4be16f99dd02d618557370495231` |
| calibration (CAL1-CAL5, nominal, by the 2 × null-maximum rule) | `EVENT_DISCOVERY_CALIBRATION.json`, SHA-256 `b43d4b1a2ca7e828a0dc1290abc80fcb7bd3f046b5d82fb090d177e4fdb105c5` |
| the residual model and B3's statistic | RB-001 `maneuver.py` `9c585800…` and `MANEUVER_CALIBRATION.json` (unchanged) |
| evaluation flights | RB-001 EN1-EN4, EF1-EF6, EH1, ET1, ET2: scored once by `--stage eval` |
| development flights | 2.3 V1-V13: in-sample, already seen (`EVENT_DISCOVERY_DEV.json`) |

**Disclosure.** The evaluation flights were scored before, by RB-001, for a
different question. Their product event count (339 per nominal hour) is
known and is E0's baseline here. No event-discovery choice was made on
them: every threshold comes from CAL1-CAL5, and the formulation constants
(windows, merge time) were fixed in the script before any run.

## 2. Calibrated values (from CAL1-CAL5 only)

| candidate | threshold |
|---|---|
| E1 | persistence D = 21.0 s (2 × the longest nominal compensation alarm, 10.5 s); PX4 merge window 60 s (fixed a priori) |
| E2 | θ_steady = 0.0989 rad/s (the shipped value; no new threshold) |
| E3 | k = 0.00917 (half of B3's θ_δ); h = 0.325 (2 × nominal peak 0.162) |
| E4 | per-motor σ from CAL; h = 338.2 (2 × nominal peak 169.1) |
| E5 | λ = 0.0120 (2 × the largest nominal split gain, 0.0060) |

## 3. Development reference (in-sample; not evidence)

| | E0 | E1 | E2 | E3 | E4 | E5 |
|---|---|---|---|---|---|---|
| false events per nominal in-flight hour | 183.9 | 4.7 | 0.0 | 0.0 | 28.3 | 0.0 |
| faults found within [onset − 1, onset + 2] s | 6/6 | 6/6 | 6/6 | 6/6 | **0/6** (its onset estimate sits a window-length early) | 6/6 |
| false symptoms downstream | 0 | 0 | 0 | 0 | 0 | 0 |

## 4. Success and failure criteria (per candidate, applied once to the evaluation run)

**Each criterion, and how it is applied:**
- **S1, safety:** zero false symptoms and zero wrong UNIQUE when the
  product analyses at the candidate's events (`known_onsets`).
- **S2, detection:** every evaluation fault flight that E0 finds within
  [onset − 1, onset + 2] s is also found by the candidate.
- **S3, burden:** false candidate events per nominal in-flight hour ≤ 6.
  That is the Part 15 budget (RB-001 `FALSE_ALARM_BUDGET.md`), set from
  intended use.

**What PASS and FAIL mean:**
- **PASS:** S1, S2 and S3 all hold.
- **REDUCES:** S1 and S2 hold, and the rate is at most half of E0's, but
  above 6 per hour.
- **FAIL:** anything else.

**What passing gives and does not give:**
- **No candidate enters the product on SITL results.**
- A passing candidate goes forward to the real nominal corpus. There its
  thresholds are recalibrated before any use, and its burden is
  measured on real flights.
- E1's PX4-warning merging is the one part with real-data support (the
  boat log). It is reported on that log separately (`--stage real`).
