# WP-C2 — Criticality-Weighted Exposure, the Free Repair, and the GPS Problem

**Date:** 2026-08-22 · **Branch:** `research/wp-e1` · **Not merged to main**
**Suite:** 448 before → **463** after (15 added by `tests/test_wp_c2_repair_flag.py`); 463 both with and without
`PYTHONPATH=.`, verified to confirm the file collects on a clean runner
**Production behaviour:** unchanged. The repair ships behind a research flag,
default off, asserted by test.

---

## 1. Verdict

Your severity hypothesis is **refuted, and your substantive conclusion is
correct anyway.** Criticality-weighted exposure does not invert the κ ordering
— it *widens* it in the same direction. But a different statistic, which
neither of us had named, does exactly what you expected CWE to do:
**remediability**. Twenty-five of 27 decision-relevant exposures vanish the
moment the aircraft carries all eight channels; the two that survive are both
gate-caused, and one of them is `gps_fault` ≡ `nominal` — nominal absorption
by an endogenous gate, on a safety-critical pair, with no repair inside the
current feature set. Your reading of the architecture was right; the metric
proposed to demonstrate it argues the other way. The free repair was then
executed and **works cleanly**: κ_max at full instrumentation halves, no new
collision appears anywhere in 1232 configurations, and no scenario regresses.
The GPS design study identifies the mechanism precisely via a control, and
recommends one candidate. Novelty remains unclaimed and full-text access
remains blocked.

---

## 2. Part 1 — CWE does not invert. Remediability does.

`D_critical` = 27 of 28 pairs. The single response-equivalent pair is
`nominal` ≡ `unexpected_maneuver`: both command the empty action set.

| Admissibility | CWE(gate alone) | CWE(channel alone) | CWE(joint) |
|---|---|---|---|
| Full instrumentation (all 8 channels) | **0.0741** | 0.0000 | 0.0741 |
| Corpus-observed (the 6 real configurations) | 0.0741 | **1.0000** | 1.0000 |
| Any channel subset | 0.0741 | **1.0000** | 1.0000 |

**Compare against κ:** gate ceiling 0.286 vs channel 1.000. Under CWE the gap
becomes 0.074 vs 1.000 — the *same* direction, wider. Weighting by commanded
response makes exogenous unavailability look worse, not better, because
channel absence eventually merges every decision-relevant pair while gate
closure merges two.

**So the panels do not invert, and I am reporting that as instructed.** The
severity revision would have been an error.

### What does invert: irreducible critical exposure

Define **IRE** = the fraction of `D_critical` merged under some configuration
reachable at **full instrumentation** — exposures no amount of sensor
purchasing removes.

| Metric | Gate closure (endogenous) | Channel absence (exogenous) |
|---|---|---|
| κ_max | 0.286 | 1.000 |
| CWE | 0.074 | 1.000 |
| **IRE** | **0.074** | **0.000** |

Channel absence contributes **zero** by construction: if every channel is
present, no channel is absent. So *every* irreducible critical exposure in
this architecture is gate-caused, and there are exactly two:

| Pair | Mechanism | Survives full instrumentation |
|---|---|---|
| `gps_fault` + `nominal` | either mechanism suffices | **yes** |
| `imu0_bias_drift` + `imu1_bias_drift` | either mechanism suffices | **yes** |
| the other 25 critical pairs | channel absence only | no |

Your underlying claim — *"the single worst exposure in the architecture, and
the one with no available repair, is nominal absorption caused by an
endogenous gate"* — is **correct**. It is established by irreducibility, not
by CWE magnitude.

**No critical pair requires both mechanisms jointly**, consistent with WP-C1's
sub-additivity result.

### One thing I could not verify

The endogeneity ratio quoted for `gvalid` (P(Z=0 | GNSS_DEG) ≈ 0.90 against
P(Z=0 | nominal) ≈ 0.02, ≈45:1) **does not exist anywhere in this
repository.** There is no emission table, closure-probability model, or
equivalent in source. I take it on your word, and it is labelled as external
to the codebase wherever it appears in these artifacts. It is also the number
that would convert IRE from a structural statement into a risk statement, so
it matters that it is currently unbacked here.

---

## 3. Part 2 — the repair works

`attitude_gravity_mag` added to `imu0_bias_drift`'s LOW set, behind
`CSIA_WP_C2_IMU_REPAIR`, **default off**.

### Certificate diff over all 1232 reachable configurations

| k (min channels) | Exposed before → after | Critical before → after | Fixed | Newly broken |
|---|---|---|---|---|
| **8** | 2 → **1** | 2 → **1** | `imu0_bias_drift+imu1_bias_drift` | **none** |
| 7 | 12 → 12 | 11 → 11 | — | none |
| 6 | 23 → 23 | 22 → 22 | — | none |
| 5 | 28 → 28 | 27 → 27 | — | none |

- **κ_max at full instrumentation: 0.2857 → 0.1429.** Halved.
- **CWE(gate): 0.0741 → 0.0370.** **IRE: 0.0741 → 0.0370**, leaving only
  `gps_fault` ≡ `nominal`.
- **No new collision anywhere.**

**A reporting trap worth naming.** The union of exposed pairs over the *whole*
lattice reads 28 → 28, which looks like the repair did nothing. That is an
artifact of including the degenerate zero-channel configuration, where every
pair merges regardless. The diff must be reported per admissibility level, and
the code now does.

**Honest limitation:** the repair helps **only at full instrumentation**. It
requires both `imu0` and `mag` present, and no corpus log configuration
benefits. It fixes the aircraft we build, not the logs we borrowed.

### Scenario effects — all five, before and after

| Scenario | Δ latency | Δ min trust | Δ peak posterior | Top cause still correct |
|---|---|---|---|---|
| `gps_spoof` | 0.0 | 0.000000 | 0.000000 | yes |
| `imu0_bias_drift` | 0.0 | 0.000000 | **−0.0658** | yes |
| `mag_emi` | 0.0 | 0.000000 | 0.000000 | yes |
| `power_sag` | 0.0 | 0.000000 | 0.000000 | yes |
| `vibration_anomaly` | 0.0 | 0.000000 | 0.000000 | yes |

Clean-scenario false positives: **0 of 999 settled ticks before, 0 after.**

The one non-zero effect is a real cost, reported as such: `imu0_bias_drift`'s
peak posterior falls from 0.9861 to 0.9203, because a larger LOW set demands
more features be simultaneously anomalous. It remains well above the harness's
0.85 assertion bound, and the top cause is still correct — but it is a
confidence reduction on the fault the repair targets, traded for structural
separability from its twin.

**Recommendation:** the evidence supports promoting this to default. It is one
line, it halves irreducible critical exposure, and nothing regresses. That
decision is yours; I implemented nothing in production.

---

## 4. Part 3 — the GPS problem, with the mechanism isolated

Full study in `research/wp_c2/GPS_INTEGRITY.md`. **Nothing implemented.**

Five candidate relations plus one control were each added to `gps_fault`'s
LOW set and the full lattice recomputed:

| Candidate | Gated by | Critical @k=8 | New collisions |
|---|---|---|---|
| `gps_cn0_stats`, `gps_sat_geometry`, `gps_clock_bias_rate` | — | 2 → **1** | none |
| `phys_gps_inertial` | — | 2 → **1** | none |
| `gps_baro_alt_ungated` | — | 2 → **1** | none |
| **CONTROL:** same relation, gated by `gvalid` | `gvalid` | 2 → **2** | none |

**The control is the result.** The identical relation, gated by `gvalid`,
repairs nothing. What fixes the pair is not the physics — it is *independence
from the gate the fault triggers*. This is the theory's prediction reproduced
as a controlled computational experiment.

Below full instrumentation the candidates separate: single-channel GPS-internal
relations reach 11 → 7 critical exposed at k=7, versus 11 → 9 for
`phys_gps_inertial`, which needs an IMU too.

**One candidate fails the physical test.** `gps_baro_alt_ungated` is the
existing `altitude_baro` edge with its gate removed — but the gate exists
*because* GPS altitude is meaningless without a valid fix. Ungating it would
manufacture a distinction from noise. Formally convenient, physically wrong,
**rejected**. This is the same failure mode as WP-C1's unconstrained repair
search, caught by applying the same constraint.

**Recommendation: `gps_cn0_stats`** — carrier-to-noise density statistics.
Independent of `gvalid` by construction, the standard integrity signal for
spoofing and jamming, maximum certificate benefit, one telemetry field.

**Blocker:** `ulog_source.py:165-188` reads only lat/lon/alt, NED velocity and
`fix_type` from `vehicle_gps_position`. It does **not** plumb
`satellites_used`, `noise_per_ms`, `jamming_indicator` or DOP. So **no
candidate can be evaluated on the committed corpus today**, and whether the 26
logs even contain those fields is **UNKNOWN** — the report records channel
names only, and the raw logs are not in version control. This is a plumbing
gap, not a hardware gap.

---

## 5. Part 4 — novelty attack still blocked

Retried this session. `www.sciencedirect.com` returned `EGRESS_BLOCKED`, as
did every academic domain in WP-C1. **Zero full texts have been read on this
subject.**

`research/wp_c2/NOVELTY_ATTACK_REQUEST.md` gives the exact reading list with
the specific question each source must answer and a decision rule per source.
The sharpest is for Carvalho et al.: *does anything there correspond to the
loss probability depending on the fault hypothesis?* If yes, the endogeneity
half is occupied and we stop. It also names the search term that snippet
search could not resolve and that would most cleanly pre-empt us:
**fault-induced unobservability / self-masking faults**.

Posture unchanged: **novelty claimed nowhere.**

---

## 6. Part 5 — what the certificate cannot say

1. **Frequency.** A certificate says what *can* happen, never how often. The
   in-flight closure frequency of `gvalid` is unmeasured and is **the single
   most important missing number in the programme** — it is what converts
   IRE = 0.037 from a structural fact into a risk.
2. **Reachability fidelity.** `C_reach` is derived from source, never observed
   in flight. A configuration deemed unreachable that occurs in practice
   invalidates the certificate for that case.
3. **Structural, not statistical.** Merged pairs may still separate on
   magnitude or variance. κ, CWE and IRE all bound structural
   indistinguishability only.
4. **Novelty.** Unresolved pending full-text access.
5. **The endogeneity ratio is external.** No emission table exists in this
   repository (§2).
6. **`D_critical` is implementation-dependent.** Change the failsafe action
   set — add an action, parameterise one differently — and every number here
   must be recomputed.

---

## 7. What I got wrong, and how I found out

**A test that would have failed on a clean CI runner.** My first version of
`tests/test_wp_c2_repair_flag.py` imported `research.wp_c2.repair_experiment`
at module scope. That works locally because I run with `PYTHONPATH=.`; in CI,
`pip install -e .` ships `csia` only, so collection would have failed.
`tests/test_ci_env.py::test_every_third_party_import_is_installed_by_ci`
caught it immediately — the same guard that exists because commit `75881b9`
failed this exact way. Fixed by moving the research import behind
`pytest.importorskip` and keeping the production-path assertions standalone,
then verified by running the file **without** `PYTHONPATH` to simulate a clean
runner. The guard did its job on its author.

**A metric that reads backwards.** The whole-lattice certificate diff shows
28 → 28 exposed pairs, which looks like the repair failed. It is the
zero-channel configuration dominating a union. Caught by checking the per-`k`
breakdown against the κ_max curve, which disagreed with the headline.

**Two of my own hypotheses did not survive**, both in the same direction as
WP-C1's: I expected CWE to invert the ordering because that is what the task
framing implied, and it does not. And I expected the GPS candidates to differ
on physical grounds; they differ almost entirely on *gate dependence*, which
the control made obvious.

---

## 8. Open, with owners

| Item | Owner | Blocking |
|---|---|---|
| Promote the IMU repair to default | You | Nothing — evidence is in |
| `gvalid` in-flight closure frequency | WP-E2 | Corpus re-acquisition |
| Plumb GPS integrity fields, then evaluate `gps_cn0_stats` | Engineering | Corpus re-acquisition to confirm field presence |
| Full-text novelty attack | You | Egress policy; reading list ready |
| Emission-table provenance for the 45:1 ratio | You | Not in repo |
| `SWORT_CSIA.pdf` + submission date | You | Four documents still blocked |
