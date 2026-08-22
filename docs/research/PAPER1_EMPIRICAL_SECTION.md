# Paper 1 — Empirical section (draft)

**Status:** draft for the theory paper. Authorized 2026-08-22.
**Framing constraint (binding):** this section reports **coarsening from
channel unavailability**, a property of the corpus. It is **not** a
measurement of gate-conditioning, and must not be presented as one. See §4.

---

## N. Empirical evaluation

### N.1 What is measured, and what is not

The identifiability results developed above concern the coarsening of the
diagnostic partition when evidence becomes unavailable. Two distinct
mechanisms produce that coarsening, and this section measures exactly one of
them.

**Endogenous coarsening** occurs when a validity gate closes as a function of
the vehicle state — potentially including the state produced by the fault
under diagnosis. This is the mechanism the endogeneity results address, and it
is the mechanism whose *statistical* consequences motivate the exogeneity
condition.

**Exogenous coarsening** occurs when a sensing channel is absent from the
record entirely: the airframe did not carry the sensor, the topic was not
logged, or the stream never produced usable data. The evidence is missing for
reasons unrelated to the fault.

Both mechanisms remove features from the observable set, and the coarsening
index κ introduced in §M is agnostic to *why* a feature is unobservable. That
agnosticism is what permits a single index to describe both. Results that turn
on the *cause* of unavailability — in particular the tilt identity and the
exogeneity condition — apply only to the first mechanism.

**This section measures the second.** We report κ over the channel
configurations present in a corpus of real flight logs. We do **not** claim to
have measured gate-induced coarsening, and §N.5 states what would be required
to do so.

### N.2 Corpus

Twenty-six public PX4 Flight Review logs, 2385.9 s of recorded duration
(0.663 h raw; 0.518 h monitored after excluding the arming window in which no
alert can be raised). The logs are **unannotated**: none carries a ground-truth
health label, so no detection-performance claim is made from them, and no
hour is verified healthy. All 26 informed the system's field-mode tolerances,
so held-out exposure is zero. The corpus is used here **solely as a source of
realistic channel-availability configurations**, a purpose for which its lack
of annotation is irrelevant.

Channel availability ranges from 2 to 5 of the 8 trust-graph channels, mean
3.88:

| Channels present | Logs | Fraction |
|---|---|---|
| 5 | 12 | 46% |
| 4 | 5 | 19% |
| 3 | 3 | 12% |
| 2 | 6 | 23% |

### N.3 Method

For a channel set X, a diagnostic feature is observable iff every channel it
spans is present. Each hypothesis's signature is restricted to the observable
features. Because an unavailable feature is *skipped* rather than
down-weighted, hypotheses whose restricted signatures coincide receive
identical likelihood on every surviving feature and their posterior ratio
remains pinned at the prior ratio indefinitely. Such hypotheses form one
observable class.

We report κ = (H − P)/(H − 1) for H = 8 hypotheses and P observable classes:
κ = 0 when all hypotheses are mutually distinguishable, κ = 1 when all
collapse into a single class.

The computation requires no telemetry — only the channel inventory and the
signature matrix. It is deterministic and exactly reproducible.

### N.4 Results

| Channels | Logs | Observable classes | κ | Hypotheses absorbed into *nominal* |
|---|---|---|---|---|
| 5 | 12 | 5 | 0.429 | 3 |
| 4 | 5 | 3–4 | 0.571–0.714 | 4–5 |
| 3 | 3 | 2–4 | 0.571–0.857 | 4–6 |
| 2 | 6 | **1** | **1.000** | **7 (all)** |

Three findings:

**In every log in the corpus, at least one fault hypothesis is structurally
indistinguishable from healthy flight.** The incidence is 26 of 26.

**In the six two-channel logs — 23% of the corpus — κ = 1.000.** All eight
hypotheses occupy a single observable class. In those flights the diagnostic
layer is incapable of distinguishing anything from anything: the posterior is
the prior, permanently, regardless of what the vehicle does. This is a
stronger statement than the corpus average and should not be smoothed into it.

**Even the best-instrumented configuration coarsens substantially.** At five
channels — the maximum the corpus reaches, and only 46% of it — κ = 0.429,
with `imu0_bias_drift`, `imu1_bias_drift` and `vibration_anomaly` all absorbed
into *nominal*.

### N.5 These values are a lower bound

κ here is computed from the channel inventory alone, with every validity gate
treated as open. In flight, gates close **on top of** absent channels. The
observable feature set is therefore a subset of the one assumed here, the
partition is at least as coarse, and **actual in-flight κ is at least these
values and plausibly higher.**

### N.6 Two metrics, and why they disagree

κ counts how many distinctions are lost. It does not weight them by whether
losing them changes what the system should *do*. Reporting only κ makes
exogenous unavailability look like the dominant problem. Reporting only
severity-weighted measures would understate how much of the diagnostic
partition the corpus destroys. Both are needed, and their disagreement is
itself the finding.

Let `D_critical` be the hypothesis pairs requiring different commanded
responses — derived from the failsafe automaton's action table including
action parameters. For this system 27 of 28 pairs are decision-relevant; the
single exception is `nominal` versus `unexpected_maneuver`, which command the
same (empty) response and therefore need never be distinguished. Define

- **CWE(M)** — the fraction of `D_critical` merged under some configuration
  reachable by mechanism M alone;
- **IRE** — the fraction of `D_critical` merged under some configuration
  reachable when **all** channels are present, i.e. exposures that no amount
  of instrumentation removes.

| Metric | Gate closure (endogenous) | Channel absence (exogenous) |
|---|---|---|
| κ_max | **0.143** | 1.000 |
| CWE | **0.037** | 1.000 |
| **IRE** | **0.037** | **0.000** |

**CWE does not invert the κ ordering; it widens it.** Weighting by commanded
response makes exogenous unavailability look *worse*, not better: channel
absence exposes every decision-relevant pair, gate closure exposes one of 27.

**The ordering that inverts is remediability.** Twenty-six of the 27
decision-relevant exposures vanish the moment the aircraft carries all eight
channels — they are properties of *this corpus*, not of the architecture. The
**one** that survives full instrumentation is gate-caused: `gps_fault` ≡
`nominal`, the fault hypothesis whose sole discriminating feature is suppressed
by the very gate that a GPS fault triggers. That is
nominal absorption produced by an endogenous gate, on the most safety-relevant
pair in the system, and it is the one exposure for which no repair exists
inside the current feature set.

The endogeneity results are therefore load-bearing **through irreducibility,
not through κ magnitude**. A reader given only κ would conclude the theorised
mechanism is a minor contributor. A reader given only IRE would miss that the
corpus destroys the partition wholesale. Neither reading alone is correct.

> **Version note.** These gate figures are POST-promotion (commit `081cca3`,
> which added `attitude_gravity_mag` to `imu0_bias_drift`, repairing the
> `imu0`/`imu1` collision). Pre-promotion they were κ_max 0.286, CWE 0.074 and
> IRE 0.074, with two surviving pairs rather than one. The argument is
> unchanged in either version: the gate ceiling sits far below the corpus's
> 1.000, and every irreducible exposure is gate-caused. See
> `docs/audit/VERSION_BOUNDARY.md`.

We emphasise what this does and does not license. Gate-induced coarsening
remains **unmeasured**: 0.143 and 0.037 are structural ceilings computed from
the signature matrix and gate map, not realised frequencies. In particular the
frequency of `gvalid` closure in flight is unknown, and a certificate says
what can happen, never how often.

### N.7 Scope: attribution, not detection

The coarsening reported here constrains **attribution**. The trust recursion
and the failsafe policy consume trust coefficients and data freshness, not the
diagnosis posterior, so detection and escalation behaviour are unaffected by
κ. No safety property is implicated by this measurement alone.

The consequence is nonetheless substantive for how such corpora are used as
evidence. A common practice is to report the absence of alerts across a body
of unannotated logs as support for a low false-alarm rate. Where κ is high,
that inference is doubly weak: the logs carry no ground truth, **and** the
attribution layer could not have named most faults had they occurred. Absence
of an alert in a κ = 1.000 configuration is close to uninformative about the
system's diagnostic capability.

### N.8 Limitations

1. **One mechanism measured, one bounded.** Gate-induced coarsening is
   unmeasured; §N.6 reports only its structural ceiling. Establishing the
   realised value requires per-tick gate traces, which the committed corpus
   artifacts do not contain. The single most important missing number is the
   in-flight frequency of `gvalid` closure.
2. **Structural, not statistical.** Hypotheses in one observable class may
   still separate if their conditional distributions differ in magnitude or
   variance. κ bounds structural indistinguishability only.
3. **Signature-level.** Distinct signatures do not guarantee practical
   separability at realistic evidence strengths.
4. **Binary features.** Partial gate closure down-weights rather than removes;
   the analysis describes the endpoints of a continuum.
5. **Memoryless.** The diagnosis carries an exponentially-weighted accumulator
   that persists across transitions, so brief unavailability does not
   instantaneously erase accumulated evidence. Transient dynamics are
   unmodelled.
6. **Single corpus, single airframe class.** No firmware, airframe or vehicle
   metadata exists for these logs, so corpus diversity is unmeasured and
   generalisation beyond small multirotor PX4 logs is not supported.
7. **Nominal reproducibility.** The logs are identified by UUID with no
   content hashes recorded, so re-acquisition cannot be proven byte-identical.

### N.9 Reproduction

The computation depends only on the committed channel inventory and signature
matrix; no flight data is required to re-derive it.

---

## Note to co-authors — do not remove before review

The temptation in this section is to write "we measured the phenomenon at 100%
incidence." **Do not.** The theorems concerning endogeneity describe gates
closing as a function of the fault; what is measured here is channels missing
from logs. A referee who reads carefully will find that the measured mechanism
is not the theorised one, and the empirical section will not survive it. The
framing above — exogenous coarsening, measured via an index that is agnostic
to the cause, with the endogenous mechanism explicitly unmeasured and its
structural ceiling reported for contrast — is both defensible and, in our
view, the stronger claim: it is the first measurement of κ on a real corpus,
and it happens to show the corpus property dominating the theorised one.

A second temptation, added after the severity analysis: do **not** drop κ in
favour of the criticality-weighted numbers. CWE does not rescue the endogenous
mechanism — it makes exogenous absence look worse still. What carries the
endogeneity argument is irreducibility (IRE), and it carries it on two pairs
out of 27, one of which now has a repair. State all three metrics. A referee
who sees only the one that flatters the theory will find the other two.
