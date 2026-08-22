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

A structural bound on the gate contribution can be computed separately. Over
all sixteen configurations of the four gates that actuate on a signature-
referenced feature, with all channels present, κ is at most **0.286**: gate
closure alone can destroy at most two of the eight distinctions, because five
hypotheses rest on features no gate controls. The corpus property measured
above therefore dominates the theorised mechanism's structural ceiling by a
wide margin — 1.000 against 0.286.

We emphasise what this comparison does and does not license. It shows that in
this system, under this corpus, exogenous unavailability is the larger source
of coarsening. It does **not** measure gate-induced coarsening, whose
structural ceiling is not its realised value, and it does not bear on the
statistical questions the exogeneity condition addresses.

### N.6 Scope: attribution, not detection

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

### N.7 Limitations

1. **One mechanism only.** Gate-induced coarsening is unmeasured. Establishing
   it requires per-tick gate traces, which the committed corpus artifacts do
   not contain.
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

### N.8 Reproduction

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
