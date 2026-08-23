# Campaign harness: release package, prepared and NOT published

**Status: PREPARED, AWAITING APPROVAL.** Nothing here has been published,
uploaded, tagged or licensed. Two decisions are yours and neither has been made
on your behalf: **the licence** and **the scope**.

The brief asks for this as the analogue of the fault injector released by the
exemplar paper. It is the most reusable thing this programme has produced, and
it is what would make the paper citable for a tool rather than only for a
result.

---

## 1. What it is

A GNSS fault-injection and observation harness that drives a real ArduPilot
autopilot in software-in-the-loop, injects a parameterised fault, and records
every layer between the receiver and the final verdict on the same timebase.

It is not a simulator. It drives one, and its value is that the autopilot,
its EKF, its GPS driver and its MAVLink dialect are all real.

## 2. What it records, per tick

| Layer | Quantity |
|---|---|
| injected | commanded offset, applied schedule, slew rate, hold duration |
| receiver | `fix_type`, `satellites_visible`, raw position |
| estimator | EKF `pos_horiz_variance` (normalised innovation test ratio), status flags |
| estimator | fused position, and fused-minus-truth against `SIMSTATE` |
| diagnostic | per-component residuals `nbr`, `phys`, `temp`, `stat`, pre-smoothing |
| diagnostic | fused evidence, forgetting factor, trust pre- and post-recursion |
| gating | per-feature gate state, applicability `A_h` per hypothesis |
| verdict | failsafe level, transitions with reasons, posterior over causes |

Ground truth is the injection schedule, which is what makes `F_h` and therefore
`T_FH` and `T_SOFH` measurable at all.

## 3. Fault classes it can inject

| Class | Mechanism | Applicability effect |
|---|---|---|
| fix-loss denial | `SIM_GPS_DISABLE` | `A_h` drops to 0 |
| receiver link loss | `SIM_GPS_BYTELOSS` | `A_h` drops to 0 |
| retained-fix step | `SIM_GPS_GLITCH_X/Y` applied at once | `A_h` stays 1 |
| retained-fix ramp | same, applied in increments | `A_h` stays 1 |
| constellation reduction | `SIM_GPS_NUMSATS` | none in this build; see the ladder |

Axes: amplitude, slew rate, duration, onset time, mission phase, home site.

## 4. Files that would ship

```
research/wp_c6/q_gvalid_campaign.py      arms, pre-registration, estimator
research/wp_c7/campaign_expanded.py      ladder, onset, duration
research/wp_c7/glitch_mechanism.py       magnitude and slew sweeps
research/wp_c7/false_healthy.py          applicability and exposure scoring
research/wp_c7/variance_investigation.py did the parameters reach the sim
research/wp_c8/response_surface.py       two-detector coverage map
research/wp_c8/four_quantity_metrics.py  T_NA / T_UH / T_FH / T_SOFH
research/wp_c8/escalation_algebra.py     derivation and its test
```

Plus a standalone `README` with the acquisition steps for the SITL binary and
the pre-registration template.

## 5. Decisions that are yours

### 5.1 Licence

The harness itself is ours. Two things it touches are not:

- **The ArduPilot SITL binary is GPLv3.** It is deliberately **not vendored**
  in this repository; scripts fetch it and refuse to run without it. That
  keeps the harness free of GPL obligations, but anyone redistributing a
  bundle that includes the binary inherits them. If the release ships only
  source and fetch instructions, this stays clean.
- **`pymavlink` is LGPLv3.** Import-only use is fine; bundling is not.

Recommendation, for your decision: permissive (Apache-2.0 or BSD-3-Clause)
on our source, with the binary fetched at runtime and never redistributed.
**Not applied. Awaiting your approval.**

### 5.2 Scope

Three options, narrowest first.

| Option | Contents | Cost |
|---|---|---|
| **A. Scripts as-is** | the eight files above, unchanged | none; they import `csia` |
| **B. Decoupled harness** | same, with the layer behind an interface so others can plug in their own diagnostic | a day of work; makes it genuinely reusable |
| **C. Full package** | B plus packaging, CI, docs, worked example | a week |

Option A is honest but only useful to someone who already has our layer.
Option B is what makes it the analogue of a released fault injector.
**Not chosen. Awaiting your decision.**

### 5.3 What must be checked before any publication

- The eight files contain no credentials, hostnames or internal identifiers.
  **This has not been audited yet** and must be before release.
- The home coordinates are public airfields and city centres, which is fine,
  but confirm none is an operating site of interest.
- Whether the SWORT Aerospace name appears in a way you want published.

## 6. What is NOT claimed for it

It drives one autopilot build, ArduCopter 3.3 from 2015, because that is the
only binary this environment can reach. It has never been run against a current
ArduPilot or against PX4. Releasing it as a general GNSS fault-injection
harness would overclaim; releasing it as "the harness used for these
measurements, which others can extend" would not.
