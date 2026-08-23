# CSIA Trust Layer — Technology Readiness Assessment

**Baseline:** commit `c13889f` (v0.8.0). **Assessor posture:** self-assessment
written to survive an Army transition team's scrutiny — every level is
justified by a named repository artifact, and gaps are stated, not smoothed.

TRL definitions per DoDI 5000.88 / NASA scale. CSIA has two distinct
technology lines with different maturity; they are assessed separately.

## Headline

| Technology line | TRL | One-line justification |
|---|---|---|
| **CSIA trust/diagnosis core (UAV profile)** | **TRL 4**, entering 5 | Component validated in the lab (sim + 26 real logs + live SITL); target-hardware/relevant-environment validation is the open step to 5. |
| **Interceptor-seeker extension** | **TRL 2–3** | Synthetic Monte Carlo proof-of-concept only; no seeker hardware or GFI data. Clearly labeled synthetic throughout. |

The UAV core is the transition asset. The seeker line is a credible concept
with first-pass synthetic evidence — do not conflate them.

## Maturity by axis (UAV core)

### Software maturity — HIGH (≈ 8/10 as software engineering)
Evidence: CI-gated test suite; online/batch equivalence pinned;
causality regression; C-vs-Python parity at 1e-12; determinism with
byte-identical campaign regeneration; crash containment, self-health,
bounds safety; requirements + traceability + evidence matrices; perf-
regression harness with a blessed baseline; changelog + semantic version.
*This is the repository's strongest axis — it is genuinely well-engineered
software.* Not DO-178C qualified (that is a separate program, not a TRL).

### Deployment maturity — MODERATE (≈ 6/10)
Evidence: advisory-by-default runtime; systemd package for desktop and Pi;
reconnect + reboot recovery; profiles as configuration; JSONL state logging.
Gaps: install verified only on desktop (not target); no packaged release
artifact (wheel/container) published; no field configuration-management
record yet. Deployable, not yet fielded.

### Validation maturity — MODERATE-HIGH (≈ 6.5/10)
Evidence: single-frozen-config Monte Carlo (150 runs) with Wilson/Poisson
CIs; 26 real PX4 logs (0.518 monitored h, unannotated, none held out); live SITL incl. fault injection; scenario
harness with attribution/isolation/recovery assertions. Gaps: (a) **slow
IMU-bias detection fails** (TPR 0.00) — a measured hole; (b) real-log
false-alarm rate is train/test contaminated with a wide CI; (c) SITL
numbers predate v0.8.0. Held-out protocol written (`VALIDATION_PROTOCOL.md`)
but not yet executed.

### Embedded maturity — LOW (≈ 3/10)
Evidence: native C core designed for STM32H7/Pi 5, zero-alloc, bounds-safe,
parity-tested on desktop; on-target tooling + templates staged. Gap: **no
target hardware has run the code.** All embedded timing is desktop
measurement or extrapolation. This is the axis holding the overall TRL down.

## What is preventing TRL 5

TRL 5 = "component validated in a **relevant environment**." Concretely,
CSIA needs all of:

1. **Target hardware in the loop** (REQ-050/051/052): the runtime on a Pi 5
   consuming live MAVLink, with measured p99 tick latency under the 40 ms
   budget and an overnight thermal/endurance soak. *Tooling ready; hardware
   absent.* — **primary blocker.**
2. **Relevant-environment run** (REQ-053): the stack on an actual airframe
   (SITL-then-flight), advisory, telemetry live, `state.jsonl` captured —
   not a desktop replay.
3. **Held-out validation** (REQ-005 + VALIDATION_PROTOCOL): either fix
   slow-IMU-bias detection or formally scope it out, and produce a
   false-alarm number on fresh logs with a tight CI.

None of the three requires touching the validated algorithm. #1 and #2 are
the ~$300–500 hardware spend + a few evenings; #3 is compute + discipline.
Closing #1 and #2 credibly moves the UAV core to **TRL 5**; adding a
documented operational-representative flight campaign starts the case for 6.

## Honest caveats for the reviewer
- "TRL 4 (flight-validated)" in older materials overstates: **it has not
  flown.** Correct phrasing: *validated in simulation, on real flight-log
  replay, and in live SITL.* (Fixed in v0.8.0 README; whitepaper edit pending.)
- The 674 ns/tick figure is desktop; the STM32 microsecond figures are
  projections until REQ-050 is measured.
- The seeker line's "100% detection" is synthetic and must always be labeled.
