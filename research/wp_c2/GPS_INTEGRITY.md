# WP-C2 Part 3 — GPS integrity: design study

**Nothing is implemented.** This is a structural study of candidate relations
that would move `gps_fault` ≡ `nominal` into `Δ_guaranteed`.

## The problem, stated precisely

`gps_fault`'s LOW signature is the singleton `{phys_gps}`, and `phys_gps` is
gated by `gvalid` (`comparator.py:199`, `gvalid * (ticks > 3.0)`). When the
GPS fix goes invalid the feature is **skipped**, not down-weighted
(`bayes.py:99-100`), leaving `gps_fault` with the empty signature — which is
`nominal`'s. The posterior ratio is then pinned at the prior ratio 0.02 : 0.86
for the rest of the flight.

**A GPS fault cannot be diagnosed in the mode a GPS fault produces.** This is
the engineering shape the theory predicts: you need evidence about a channel
that survives the gate that channel's own fault triggers.

The one existing escape, `temp_gps`, is ungated but is `unexpected_maneuver`'s
*sole* LOW feature, so adding it merges `gps_fault` with
`unexpected_maneuver` — itself a critical pair. Not a fix.

## The mechanism, isolated by a control

Each candidate below was added to `gps_fault`'s LOW set and the full 1232-
configuration lattice recomputed. One control was run: the *same* feature,
gated by `gvalid`.

| Candidate | Channels | Gated by | Critical exposed @k=8 | Fixed | New collisions |
|---|---|---|---|---|---|
| `phys_gps_inertial` | gps, imu0 | — | 2 → **1** | `gps_fault+nominal` | none |
| `gps_cn0_stats` | gps | — | 2 → **1** | `gps_fault+nominal` | none |
| `gps_sat_geometry` | gps | — | 2 → **1** | `gps_fault+nominal` | none |
| `gps_clock_bias_rate` | gps | — | 2 → **1** | `gps_fault+nominal` | none |
| `gps_baro_alt_ungated` | gps, baro | — | 2 → **1** | `gps_fault+nominal` | none |
| **CONTROL:** `gps_cn0_gvalid_gated` | gps | `gvalid` | 2 → **2** | — | none |

**The control is the result.** The same relation, gated by `gvalid`, fixes
nothing. What repairs the pair is not the physics of the candidate — it is
*independence from the gate the fault triggers*. Every ungated GPS-spanning
relation works identically at full instrumentation; κ_max@8 falls 0.286 → 0.143
in every case.

They separate below full instrumentation. Critical pairs exposed at k ≥ 7:

| Candidate | k=7 | k=6 |
|---|---|---|
| single-channel (`gps` only) | 11 → **7** | 22 → 21 |
| `phys_gps_inertial` (gps + imu0) | 11 → 9 | 22 → 21 |
| `gps_baro_alt_ungated` (gps + baro) | 11 → 7 | 22 → 21 |

**Single-channel candidates dominate**: a relation needing only `gps` survives
more channel configurations than one needing `gps` *and* an IMU.

## Physical soundness — which candidates are real

WP-C1's first repair search produced formally valid, physically meaningless
options before it was constrained. The same test is applied here: does the
relation actually carry information about GPS integrity, and can it be
computed when the fix is invalid?

| Candidate | Physically sound? | Assessment |
|---|---|---|
| `gps_cn0_stats` — carrier-to-noise density | **Yes** | C/N₀ collapse or an implausibly *uniform* C/N₀ across satellites is the classic spoofing/jamming signature. Independent of fix validity: the receiver reports signal quality whether or not it has a fix. **Strongest candidate.** |
| `gps_sat_geometry` — satellite count and DOP dynamics | **Yes** | Sudden count changes, or a count that stays high while the fix degrades, is diagnostic. Available without a fix. |
| `gps_clock_bias_rate` — receiver clock-bias drift | **Yes, but weaker** | A meaconing/spoofing attack often perturbs the clock solution. Requires a solution to exist, so it degrades exactly when needed most — partially self-defeating. |
| `phys_gps_inertial` — GPS position derivative vs inertial velocity | **Yes, with a caveat** | Physically the strongest cross-check, but it needs an IMU channel and the inertial reference drifts without GPS, so its useful window is bounded. Costs a channel in the certificate. |
| `gps_baro_alt_ungated` — GPS altitude vs barometric | **FAILS the physical test** | This is `altitude_baro` with its gate removed. The gate exists *because* GPS altitude is meaningless without a valid fix. Ungating it would feed garbage into the diagnosis and manufacture a distinction from noise. **Formally convenient, physically wrong. Do not implement.** |

## Telemetry availability in the corpus — the blocker

`csia/runtime/ulog_source.py:165-188` reads `vehicle_gps_position` and uses
**only** lat/lon/alt, NED velocity, and `fix_type >= 3` as validity. It does
**not** plumb `satellites_used`, `noise_per_ms`, `jamming_indicator`, `hdop`,
`vdop`, or the clock fields, all of which exist in the PX4 message.

Consequently:

- **No candidate can be evaluated on the committed corpus today.** The
  ingestion path discards the fields every one of them needs.
- **Whether the 26 logs even contain those fields is UNKNOWN.**
  `data/real_logs_report.json` records channel *names* only — no topic or
  field inventory — and the raw `.ulg` files are not in version control.
  Determining this requires re-acquiring the corpus.

This is a plumbing gap, not a hardware gap: the fields are standard in
`vehicle_gps_position` and cost nothing to read.

## Ranking and recommendation

| Rank | Candidate | Certificate benefit | Telemetry | Cost |
|---|---|---|---|---|
| **1** | `gps_cn0_stats` | max (2→1 @k=8, 11→7 @k=7) | field exists in PX4, **not plumbed**; presence in corpus UNKNOWN | low: read one field, add one residual, one signature line |
| 2 | `gps_sat_geometry` | max | same | low |
| 3 | `phys_gps_inertial` | max @k=8, weaker @k=7 | needs no new fields | medium: windowed estimator |
| 4 | `gps_clock_bias_rate` | max | not plumbed | medium |
| — | `gps_baro_alt_ungated` | max | available | **rejected on physical grounds** |

**Recommendation: `gps_cn0_stats`.** It is independent of `gvalid` by
construction, needs one additional telemetry field, is the standard integrity
signal for exactly this threat, and delivers the maximum certificate benefit
available.

**Prerequisite before any implementation:** re-acquire the corpus and confirm
the field is populated in a usable fraction of logs. A relation nothing can
evaluate is worse than the collision it replaces.

## Scope limits

1. Every row above is **structural**. Adding a feature to a signature makes
   the hypotheses formally distinguishable; whether the residual carries
   enough signal-to-noise to separate them *statistically* is unmeasured and
   unmeasurable without data.
2. The fix holds **at full instrumentation only**. If the `gps` channel is
   absent entirely, every candidate dies with it and `gps_fault` collapses
   into `nominal` again. Nothing repairs the diagnosis of a channel that is
   not there.
3. The frequency of `gvalid` closure in flight is **unmeasured**, so how often
   this collision actually occurs is unknown. See WP-C2 Part 5.
