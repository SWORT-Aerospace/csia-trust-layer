# MAER EXPERIMENT — CHATGPT REVIEW REPORT

> **Self-contained.** The reviewer is assumed to have no repository access.
> Every number below is reproduced inline. The experiment was **stopped at the
> Item 4 feasibility hard stop**; sections describing scored results are marked
> `NOT_RUN` with the reason, rather than omitted.

## 1. Executive Verdict

**`INCONCLUSIVE`** — specifically, **`MAER_NOT_FEASIBLE`** at the pre-registration
gate. No implementation, no preregistration, no scored trial.

The experiment's causal core is ARM 2 versus ARM 2C: one discriminating
residual, present in both arms, differing *only* in whether it sits inside or
outside the closing `gvalid` mask. That design requires a residual that
discriminates `nominal` from `gps_fault` and remains computable during GNSS fix
loss. The audit establishes that no such residual exists in this architecture,
for a principled reason:

- `gps_fault`'s entire evidence set is one feature, `phys_gps`.
- `phys_gps = norm(finite-differenced reported position − Doppler velocity)`.
  Both inputs come from the GNSS receiver.
- Measured over the committed fix-loss windows (450 ticks ArduPilot, 448 PX4),
  **every** GNSS channel has usable share `0.000`, and the logged `phys_gps`
  residual is `None` on every tick.
- Relations that *do* survive (`redundant_imu`, `attitude_gravity_mag`,
  `temp_bias_drift`, all at 1.000 on ArduPilot) consume no GNSS input, so
  nothing makes them respond to a GNSS fault.
- The one GNSS-sensitive quantity that survives — the autopilot's EKF
  `pos_horiz_variance` — is contractually barred (`csia_may_use: false`,
  "CSIA must not consume the estimator it is meant to be independent of") and
  empirically arrived on 0 of 751 ticks anyway.

So under fix-loss self-occlusion the only discriminating observable is the
**missingness event itself** (`gnss.position.missing == NO_3D_FIX`). That is
categorical, not a residual, so it cannot be placed inside/outside a gate to
form the matched pair. The structural-rescue arm and the gate-event arm
collapse onto the same observable.

Two mechanisms remain independently controllable — persistence (frozen CUSUM,
PASS) and transport starvation (PASS, three reproductions). A narrower study is
possible but could not test H1 or H3, which are the mechanism-specificity
hypotheses the design exists to test.

**The specific question for the reviewer: is the "no discriminating residual
survives fix loss" argument correct, or is there a candidate class the audit
missed?** If it is correct, MAER's central claim may be untestable on this
architecture for a structural reason, which is itself a result.

## 2. Repository / Environment

```
repository commit      : 1bc3659 (branch claude/code-reviewer-repo-export-zicovg)
frozen CSIA tag        : csia-v1.0-research-final
ArduPilot upstream SHA : 01a504b472259602e13df4cf07df7c0cdbb35993 (ArduCopter V4.8.0-dev)
PX4 upstream SHA       : 547e2caa9883bc1609325f02b4914b4e2482fe62 (SIH, sihsim_quadx, PX4_SYS_AUTOSTART=10040)
OS / runtime           : Linux 6.18.44 x86_64, CPython 3.12.3
experiment start commit: 1bc3659
experiment final commit: see §22
```

Frozen core is untouched and bit-identical. Nothing under
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py` was
modified; enforced by `tests/test_v1_frozen.py`.

## 3. Feasibility Audit

### Structural rescue candidate: **FAIL**

```
candidate selected            : NONE — no candidate satisfies the criteria
target hypothesis             : gps_fault
target evidence set           : ["phys_gps"]        (csia/diagnosis/bayes.py CAUSES)
phys_gps residual             : norm(_gps_fd_vel - vel)      (online.py:562-566)
                                = finite-differenced REPORTED POSITION
                                  minus DOPPLER VELOCITY — both GNSS-derived
gate on P["gps"]              : gvalid * (1.0 if tau > 3.0 else 0.0)  (online.py:572)
                                and multiplied again by fresh["gps"]  (online.py:613)
availability during fix loss  : gnss.position   usable share 0.000
                                gnss.velocity   usable share 0.000
                                gnss.velocity_z usable share 0.000
                                (ArduPilot 450 NO_3D_FIX ticks; PX4 448)
logged phys_gps residual      : None on every tick of the window
gvalid dependence             : total — three independent routes to zero
relations surviving fix loss  : ArduPilot redundant_imu 1.000,
                                attitude_gravity_mag 1.000, temp_bias_drift 1.000
                                PX4       attitude_gravity_mag 0.989
                                none consumes GNSS ⇒ non-discriminating
```

Rejected candidate worth naming explicitly, because it is the one that nearly
works:

```
estimator.variances (ArduPilot EKF_STATUS_REPORT.pos_horiz_variance)
  GNSS-fault sensitive?   YES — estimator position variance grows under denial
  survives fix loss?      YES — independent of gvalid
  usable?                 NO, twice over:
    contract  csia_may_use: false — "deliberately excluded from diagnosis.
              CSIA must not consume the estimator it is meant to be independent
              of. Logged for the autopilot-vs-CSIA comparison required by S9,
              and for nothing else."
    empirics  usable on 0 of 751 ticks in BOTH Mechanism A arms — the message is
              handled by the adapter but never arrived on the shadow link
              (itself an instance of Mechanism C)
  measured 50.15 Hz on the DRIVEN qualification link (2006 samples), so the
  message exists and flows; the bar is architectural, not a plumbing gap.
```

`phys_gps_inertial` was named in the brief as previously attractive. It does
not exist in the repository (zero source matches), and as a concept it compares
GNSS against inertial dead-reckoning — which has no GNSS side during fix loss.
It would apply to fix-*preserving* faults (Mechanism B) only.

Brief's PASS criteria, scored:

| criterion | result |
|---|---|
| computable during the fix-loss window | **NO** |
| independent of state destroyed by fix loss | **NO** |
| has a defined nominal reference | n/a (no candidate) |
| implementable without touching frozen core | yes |
| placeable both inside and outside `gvalid` | yes (for a residual, if one existed) |

Two hard criteria fail. Per the brief, no candidate was manufactured.

### Gate-event evidence: **INFEASIBLE FOR SCORED EMPIRICAL CLAIM**

```
Z                       : missingness reason on gnss.position (NO_3D_FIX vs present)
                          — a categorical event, not a residual
calibration dataset     : committed corpus
calibration N           : 2 flights contain ANY NO_3D_FIX tick
                            ap_FAULT   (ardupilot) 450/751 ticks lost
                            px4_FAULT  (px4)       448/751 ticks lost
                          28 further flights contain none
held-out evaluation     : IMPOSSIBLE — one fault flight per platform means any
                          fitted likelihood is fitted on the whole fault
                          population
model                   : none fitted
```

The brief's permitted fallback is taken. A synthetic gate-emission model would
be labelled `MODEL-BASED SENSITIVITY, NOT EMPIRICALLY CALIBRATED`; it is not
pursued, because it cannot support a scored empirical claim either.

### CUSUM: **PASS**

```
existing implementation : research/phase2/p1_offline_baselines.py  (arm "B4")
statistic               : one-sided CUSUM on the standardised PRE-TRANSFORM
                          residual (OnlineTrustLayer._lam, read-only)
                          S = max(0, S + z - k),  z = (lam - mu0)/sigma0
drift k                 : 0.5   (textbook: half the one-sigma shift to detect)
decision interval h     : 500.0
h selection rule        : smallest h from a fixed grid for which the CLEAN
                          NOMINAL ARM produces zero alarms — evaluated on the
                          clean arm only, never on a fault outcome
in-control statistics   : clean nominal arm only
clean-budget evidence   : R10_nominal_alarms = 0, satisfies_R10 = true
cost                    : 0.618 us/tick
committed negative result retained: h = 5.0 (textbook) produced 3 clean alarms,
                          failing R10, and is kept rather than deleted
```

No frozen-core change needed (read-only on `_lam`). Porting to current-stack
traces requires `mu0`/`sigma0` re-derived on **clean** current-stack data; 28
such flights exist, so calibration/test separation is genuinely available here.

### Transport starvation: **PASS**

```
same platform/build     : PX4-Autopilot@547e2ca, sihsim_quadx, PX4_SYS_AUTOSTART=10040
same message source     : SCALED_PRESSURE
controlled condition    : presence/absence of SET_MESSAGE_INTERVAL on the
                          CONSUMER'S OWN link, both arms inside the same boot
measured delivery       : passive   1.000 Hz
                          requested 9.775 Hz
downstream freshness    : baro node fresh 0.0967 (passive) vs 0.9992 (driven)
reproductions           : 3 independent boots; requesting figure 9.800 / 9.825 /
                          9.775 Hz across them
```

Strongest arm in the audit; the only mechanism fully controllable on demand.

### Operating-regime validation: **DEFERRED**

`heading_course` needs sustained horizontal speed above `GATE_SPEED_LO = 2.0
m/s`. Committed corpus maximum is **0.170 m/s** over 26 flights (ArduPilot
0.170, PX4 0.130), so the relation has **zero** empirical activation anywhere in
the record. ArduPilot can fly the profile, but it needs a new
commanded-trajectory path in the rig plus a new campaign: feasible, not cheap.
The brief forbids letting it delay the main experiment.

## 4. Preregistration

```
preregistration path            : NOT WRITTEN
preregistration commit          : n/a
was it committed before scored trials? : n/a — no scored trials were run
```

The brief gates preregistration behind a feasibility PASS (Item 6, "If
feasibility passes"). Feasibility did not pass, and Item 5 directs: *"If
MAER_NOT_FEASIBLE: STOP. Return the full report. Do not implement anything."*

Hypotheses as stated in the brief, with the audit's bearing on each:

```
H1 structural rescue specificity  : UNTESTABLE AS SPECIFIED — requires a
                                    discriminating residual that survives fix
                                    loss; none exists (§3)
H2 temporal detector specificity  : TESTABLE — CUSUM feasible, Mechanism B
                                    condition already realizable on ArduPilot
H3 non-substitutability           : UNTESTABLE AS SPECIFIED — it is a claim
                                    about H1's mechanism; with no ARM 2 there
                                    is nothing for CUSUM to fail to substitute
                                    for
H4 evidence-cause discrimination  : PARTLY TESTABLE — GATE_CLOSED vs
                                    TRANSPORT_STARVED are both realizable and
                                    already distinguishable in existing
                                    instrumentation (see §11)
H5 combined system                : UNTESTABLE AS SPECIFIED — a combined arm
                                    missing its structural component is not
                                    the preregistered ARM 4
H6 operating regime (optional)    : DEFERRED
```

## 5. Algorithms / Experimental Arms

`NOT_RUN` — no arm was implemented. Definitions the audit did fix, for review:

```
ARM 0  BASELINE   exact frozen CSIA core, csia-v1.0-research-final, unmodified
ARM 1  GATE_EVIDENCE
       score_h += beta * log P(Z=z | H=h, C), beta = 1, inserted BEFORE the
       existing EWMA smoothing and tempering.
       BLOCKED: P(Z|H,C) cannot be calibrated (N=1 fault flight per platform).
ARM 2  STRUCTURAL_RESCUE
       one discriminating residual placed OUTSIDE the closing gvalid mask.
       BLOCKED: no such residual exists (§3).
ARM 2C GATED_STRUCTURAL_CONTROL
       identical residual multiplied by gvalid.
       BLOCKED: presupposes ARM 2.
ARM 3  CUSUM      S = max(0, S + z - 0.5), z = (lam - mu0)/sigma0, alarm at
                  S > 500.0, mu0/sigma0 from clean arm only. FEASIBLE.
ARM 4  MAER_COMBINED   union of components that passed. BLOCKED: would contain
                  only ARM 3 plus evidence-cause labelling, which is not the
                  preregistered combined arm.
```

For reference, the diagnosis path ARM 1 would modify: per-tick gate-weighted
log-likelihoods, EWMA-smoothed (`SMOOTH_ALPHA = 0.06`, ~15-tick window),
tempered (`EVIDENCE_MULT = 1.5`), softmaxed. `score = log_prior + 1.5 ×
EWMA(ll)`; `PRIOR_NOMINAL = 0.86`. This output is a normalized hypothesis
weight, **not** a Bayesian posterior.

## 6. Experiment Matrix

`NOT_RUN`. Planned matrix was 4 conditions (CLEAN, FIX_LOSS,
FIX_PRESERVING_RAMP, TRANSPORT_STARVATION) × 5 or 6 arms × 5 repetitions = 100
or 120 trials. Zero were run. No cell has a valid N.

## 7. Fix-Loss Results

No MAER arms were run. The **baseline** behaviour is already committed from the
existing Mechanism A campaign, and is what motivated MAER. Reproduced here
because it is the evidence the feasibility argument rests on:

```
ArduPilot FAULT arm (fix lost), 450 NO_3D_FIX ticks observed downstream:
  snapshot      gvalid-gated GPS relation weight sum   diagnosis_top   gps_fault_p  rank  level
  pre  t=10.00                3.0                       nominal          0.0001      2    NORMAL
  at   t=12.00                3.0                       nominal          0.0001      2    NORMAL
  post t=14.01                0.0                       nominal          0.0131      2    CAUTION
  late t=22.01                0.0                       nominal          0.0227      2    CAUTION

PX4 FAULT arm (fix lost), 448 NO_3D_FIX ticks observed downstream:
  pre  t=10.00                1.0                       nominal          0.0001      4    NORMAL
  at   t=12.01                1.0                       nominal          0.0001      4    NORMAL
  post t=14.00                0.0                       nominal          0.0128      3    CAUTION
  late t=22.00                0.0                       nominal          0.0213      4    CRITICAL

Per-relation gate weights, control arm (fix preserved), ArduPilot:
  altitude_baro 1.00   heading_course 0.00   doppler_0 1.00   doppler_1 1.00
Per-relation gate weights, control arm, PX4:
  altitude_baro 0.00   heading_course 0.00   doppler_0 1.00   doppler_1 0.00
```

`gps_fault` never becomes the top hypothesis in either platform; the layer
reports `nominal` throughout while the fault it was built to catch is active.
Assurance still escalates (CAUTION/CRITICAL) through an independent
data-freshness disjunct that does not consult the diagnosis, so the vehicle is
not blind — but the cause is never named.

Note the PX4 control pool is 1.0 versus ArduPilot's 3.0. Three relations were
already dark for three *different* reasons, and they must not be blurred:
`altitude_baro` transport-starved, `velocity_gps_doppler_1` structurally absent
(SIH publishes no second IMU), `heading_course` closed by operating regime.

## 8. Gate-Placement Causal Test

```
Were STRUCTURAL_RESCUE and GATED_STRUCTURAL_CONTROL identical except for gate
placement?   NOT_RUN — neither arm exists.
quantitative difference : n/a
effect direction        : n/a
H1 verdict              : UNTESTABLE AS SPECIFIED (not refuted, not supported)
```

This is the heart of the stop. Without a residual that survives fix loss there
is no matched pair, and therefore no causal test of gate placement. Reviewer 1's
objection would stand unanswered by construction.

## 9. Persistence / Ramp Results

`NOT_RUN` for MAER arms. Baseline Mechanism B is committed and is the arm CUSUM
would have been compared against:

```
preregistered threshold T*      : 0.75
ArduPilot verdict               : REPLICATED
trials total / valid            : 20 / 20
conditions                      : CLEAN 0/5, STEP_SMALL 0/5, STEP_LARGE 0/5,
                                  RAMP_20S 5/5 crossing (as preregistered)
max reconstruction error        : 1.9984e-15  (tolerance 1e-6)
crossing error                  : 0 ticks     (tolerance 2)
PX4 verdict                     : INAPPLICABLE — no fix-preserving GNSS position
                                  offset exists on PX4 SIH; four candidate
                                  routes read out of source at 547e2ca, all
                                  fail. No substitute was flown.
H2 verdict                      : NOT TESTED (feasible, not run)
```

## 10. Mitigation Crossover

```
Did CUSUM repair Mechanism A?          NOT_RUN
Did structural rescue repair Mech B?   NOT_RUN (arm does not exist)
Did gate evidence repair Mechanism A?  NOT_RUN (uncalibratable)
Did MAER select different responses?   NOT_RUN
H3 verdict                             : UNTESTABLE AS SPECIFIED
```

Full crossover matrix: `MAER_CROSSOVER_MATRIX.csv` was **not** produced, because
producing an empty or predicted matrix would invite it being read as a result.

## 11. Transport-Starvation Results

The mechanism is fully characterised even though no MAER arm ran, because the
controlled experiment was already performed:

```
passive delivery rate   : 1.000 Hz   (consumer link, no SET_MESSAGE_INTERVAL)
requested delivery rate : 9.775 Hz   (same link, same boot, requested)
freshness — two gates in series, and the SECOND one binds:
    channel max_age = MAX_AGE_MARGIN / declared_rate = 5.0/10 = 0.50 s
    node    STALE_TIMEOUT_S['baro']                  = 0.10 s   <- binding,
            a fixed runtime constant that NO declaration feeds
    measured: channel usable 0.4943, node fresh 0.0967
relation availability   : altitude_baro live 0.0812 (PX4) vs 0.9984 (ArduPilot)
runtime evidence cause  : STARVED_BY_TRANSPORT
did the system distinguish transport starvation from gate closure?
    YES, in the existing instrumentation and WITHOUT access to injected-fault
    labels. The distinction is computed from source/delivery/freshness/gate
    state: an endpoint whose CHANNEL was never usable is structural; an endpoint
    delivered too slowly for the freshness budget is transport-starved; a
    relation whose endpoints were all usable and whose weight is still zero is
    gate-closed. Verdicts on the committed corpus:
        altitude_baro (PX4)          STARVED_BY_TRANSPORT
        velocity_gps_doppler_1 (PX4) DARK_STRUCTURAL
        heading_course (both)        DARK_BY_GATE
any false physical-fault attribution?  NONE OBSERVED — starved relations
    contribute no weight rather than a fault-shaped residual
H4 verdict              : SUPPORTED BY EXISTING INSTRUMENTATION, NOT BY A
                          PREREGISTERED MAER TRIAL
```

H4 is the one hypothesis with genuine supporting evidence, and it must be
labelled honestly: it comes from a harness audit of committed artifacts, **not**
from a preregistered scored campaign.

## 12. Combined MAER Result

`NOT_RUN`. A combined arm containing only CUSUM plus evidence-cause labelling
is not ARM 4 as preregistered, and running it under that name would be a
substitution the brief forbids.

## 13. Optional Operating-Regime Result

`DEFERRED`.

```
speeds available in corpus : max 0.170 m/s (ArduPilot), 0.130 m/s (PX4), 26 flights
gate threshold             : GATE_SPEED_LO 2.0 m/s, GATE_SPEED_HI 3.0 m/s
heading_course availability: 0.0000 on every flight, both platforms
H6 verdict                 : DEFERRED
```

## 14. Exposure Metrics

`NOT_RUN` for MAER arms. `T_NA`, `T_UH`, `T_FH`, `T_SOFH` retain their existing
definitions and their existing Phase-I values; no new ground truth was
generated, so no new values are reported. Reporting recomputed exposure metrics
without a scored campaign would attach experiment-shaped numbers to an
experiment that did not run.

## 15. Compute Benchmark

`NOT_RUN` for MAER arms. The one benchmarked component is the existing frozen
detector: **B4 CUSUM, 0.618 µs/tick**, from
`research/phase2/results/baseline_comparison.json`. No median/p95/p99/max
distribution is reported for arms that were never executed.

## 16. Negative Results

Every preregistered prediction that failed, plus every audit expectation that
did not survive:

1. **The structural-rescue arm has no candidate.** The brief anticipated
   `phys_gps_inertial` as attractive. It does not exist in the repository, and
   the concept requires a GNSS side that fix loss removes.
2. **The most promising candidate is barred by the architecture's own
   independence contract.** `estimator.variances` would work physically and is
   forbidden by `csia_may_use: false`.
3. **That same candidate was also transport-starved to zero** on the shadow
   link — 0 of 751 ticks — so even without the contract bar it was unavailable.
4. **Gate-event calibration is impossible on the committed corpus.** 2 fault
   flights total.
5. **My own prior reporting of the starvation mechanism was wrong in
   emphasis.** I attributed it to `max_age`; the binding gate is the node
   `STALE_TIMEOUT_S` (0.10 s vs 0.50 s), which no declaration feeds. An account
   using only `max_age` predicts ~50 % availability where the measurement shows
   ~8 %.
6. **`heading_course` has zero empirical activation anywhere in the corpus**, so
   the only magnetometer cross-check against an independent reference has never
   been exercised.

## 17. Invalid / Rejected Trials

None — no trials were run, so nothing was rejected. No replacement policy was
exercised. This section exists so its emptiness is explicit rather than implied.

## 18. Post-Hoc Analyses

The feasibility audit is, by construction, not preregistered — it is the
pre-registration gate. It is exploratory and must not be read as a scored
result. Analyses performed:

- fix-loss channel/relation survival survey over committed logs
- GNSS-fault-sensitivity screen of every surviving relation
- calibration-N count for the gate-event term
- B4 parameter extraction from the committed Phase-2 artifact
- transport-starvation controllability confirmation

No hypothesis test was performed on any of them.

## 19. Red-Team Review

```
Reviewer 1  "The structural rescue worked only because you added more evidence,
             not because of gate placement."
  verdict   : NOT APPLICABLE — no structural rescue was run. Their objection is
              precisely why ARM 2C was required, and precisely why the absence
              of a viable ARM 2 is a stop rather than a workaround.

Reviewer 2  "CUSUM also fixes self-occlusion, so your mechanism distinction is
             false."
  verdict   : UNTESTED. Cannot be answered without running CUSUM on FIX_LOSS.
              The audit does NOT claim H3; it records H3 as untestable as
              specified. Note the mechanistic prediction that CUSUM cannot
              recover a quantity whose residual is None on every tick is
              plausible but UNMEASURED, and must not be reported as a result.

Reviewer 3  "Your MAER logic just memorizes fault labels."
  verdict   : NOT APPLICABLE — no MAER logic exists. For the evidence-cause
              classification that DOES exist, the state is computed from
              source/delivery/freshness/gate state only; injected-fault labels
              are not an input. Verifiable from the tool source.

Reviewer 4  "Transport starvation and gate closure are both missing-data
             problems; your taxonomy has no operational distinction."
  verdict   : ANSWERED. Three verdicts are produced from runtime state without
              fault labels: STARVED_BY_TRANSPORT (delivered too slowly for the
              freshness budget), DARK_STRUCTURAL (endpoint channel never
              usable), DARK_BY_GATE (all endpoints usable, weight still zero).
              On the committed corpus these separate altitude_baro,
              velocity_gps_doppler_1 and heading_course respectively.

Reviewer 5  "Your gate-event likelihood is trained on the test set."
  verdict   : CONCEDED IN ADVANCE. No calibration/test split is possible with 2
              fault flights, so no empirical gate-likelihood claim is made.

Reviewer 6  "Combined MAER wins only because it contains every detector."
  verdict   : NOT APPLICABLE — no combined arm was run, and one containing only
              the surviving component would not be ARM 4.

Reviewer 7  "The rescue relation is not physically valid after GNSS fix loss."
  verdict   : REVIEWER IS CORRECT, and this is the finding. Every GNSS channel
              has usable share 0.000 during the window and the phys_gps residual
              is None on every tick. This objection is why the arm is stopped.

Reviewer 8  "Safe ambiguity is just hiding failure."
  verdict   : NOT APPLICABLE — no abstention layer was implemented. Had it been,
              the brief's hierarchy already separates ambiguity from correct
              attribution and does not count it as correct.

Reviewer 9  "You tuned after seeing results."
  verdict   : NOT APPLICABLE — no parameters were fitted and no scored trial
              was run. Nothing exists to tune. The one detector considered
              carries pre-existing parameters (k=0.5, h=500.0) selected on the
              clean arm only.

Reviewer 10 "This entire result is specific to one diagnostic architecture."
  verdict   : CONCEDED. The finding is a property of THIS layer: a
              single-feature evidence set for gps_fault, that feature gated on
              gvalid, and a contract barring the estimator. A layer with a
              redundant GNSS-integrity feature outside the validity mask would
              not have this problem. No claim extends beyond the evaluated
              architecture.
```

## 20. Claim Ledger

```
claim   : No residual in this architecture discriminates nominal from gps_fault
          during GNSS fix loss.
evidence: CAUSES["gps_fault"] == ["phys_gps"]; phys_gps inputs both GNSS-derived;
          all GNSS channels usable share 0.000 over 898 fix-loss ticks across two
          platforms; logged phys_gps residual None on every tick.
status  : PROVED / DETERMINISTIC IMPLEMENTATION PROPERTY (for this commit)
allowed : "In the evaluated configuration, no available residual discriminates
           the target hypothesis during fix loss."
forbidden: "Structural rescue is impossible in principle." / any claim about
           other diagnostic architectures.

claim   : estimator.variances is barred from diagnosis by contract.
evidence: CHANNEL_SEMANTICS.yaml csia_may_use: false with recorded reason.
status  : PROVED / DETERMINISTIC IMPLEMENTATION PROPERTY
allowed : "The one surviving fault-sensitive quantity is excluded by the
           layer's independence contract."
forbidden: "EKF variance cannot detect GNSS denial." (it can; it is barred)

claim   : Gate-event likelihood cannot be calibrated on the committed corpus.
evidence: 2 flights contain any NO_3D_FIX tick; 28 contain none.
status  : PROVED / DETERMINISTIC IMPLEMENTATION PROPERTY
allowed : "No calibration/test split is available."
forbidden: any empirical P(Z|H,C) figure.

claim   : Transport starvation is deterministically controllable and
          distinguishable from gate closure without fault labels.
evidence: passive 1.000 Hz vs requested 9.775 Hz, same boot, 3 reproductions;
          three-way verdict separation on the committed corpus.
status  : SUPPORTING / PROVISIONAL (harness audit, not a preregistered trial)
allowed : "Existing instrumentation distinguishes them on committed artifacts."
forbidden: "H4 is confirmed." (no scored campaign supports it)

claim   : The binding freshness gate is the node timeout, not channel max_age.
evidence: STALE_TIMEOUT_S['baro'] 0.10 s vs max_age 0.50 s; channel usable
          0.4943 vs node fresh 0.0967 on PX4.
status  : PROVED / DETERMINISTIC IMPLEMENTATION PROPERTY
allowed : "Availability is gated twice and the node budget binds."
forbidden: attributing the starvation to max_age alone.

claim   : MAER as specified is not feasible on this architecture.
evidence: this audit.
status  : INCONCLUSIVE for the research question; PROVED for the gating facts.
allowed : "The crossover experiment cannot be run as specified."
forbidden: "Mechanism-aware diagnosis does not work."
```

## 21. Novelty Status

**NO NOVELTY CLAIM HAS BEEN AUTHORIZED.**

Closest known conceptual categories, none of which is claimed as new here:
analytical redundancy; active FDI; sequential detection (CUSUM, Page 1954);
missing-observation diagnosis; Bayesian/gate evidence; abstention and
uncertainty sets; communication-aware diagnosis; operating-regime-dependent
diagnosability.

What was actually tested: whether a crossover design distinguishing structural
evidence restoration, gate-event evidence, sequential accumulation and
evidence-unavailability qualification could be executed inside one implemented
autonomous-aircraft diagnostic layer. It could not, because the structural arm
has no realizable candidate. No word from {first, novel, unprecedented, never
before} is used.

## 22. Reproducibility

```
artifact manifest : research/maer/MAER_FEASIBILITY_AUDIT.json
                    research/maer/MAER_FEASIBILITY_REPORT.md
                    research/maer/maer_feasibility_audit.py   (the generator)
seeds             : none — the audit is deterministic over committed artifacts
build commands    : none; no simulator was launched by this audit
raw data          : research/v1_1/results/mechanism_a/*.json
                    research/v1_1/results/shadow_flights/*.json
                    research/v1_1/results/mechanism_b_gps/*.json
                    research/v1_1/results/PX4_LINK_RATE_PROBE.json
                    research/phase2/results/baseline_comparison.json
analysis command  : python research/maer/maer_feasibility_audit.py
deterministic replay : re-running the generator reproduces
                    MAER_FEASIBILITY_AUDIT.json byte-for-byte
```

Nothing in the audit is transcribed: figures are parsed from frozen source and
the channel contract, or counted from committed logs, at run time.

## 23. Scientific Blockers

1. **No structural-rescue candidate exists** (§3). Blocks H1, H3, H5 and the
   ARM 2 / ARM 2C causal core.
2. **Gate-event likelihood is uncalibratable** on the committed corpus (2 fault
   flights). Blocks ARM 1 as a scored empirical claim.
3. **`heading_course` has never been exercised**, so the only magnetometer
   cross-check against an independent reference has zero empirical support
   anywhere in the record. This also bears on the existing `mag_emi` probe,
   whose surviving magnetic relation uses a magnetometer-coupled reference.

## 24. Publication Blockers

1. **No current-stack manuscript source exists in the repository.** Exhaustive
   search across all refs finds two `.tex` files ever: `papers/csia_systems/
   main.tex` (titled *"Measured Self-Occlusion in a Deployed Cross-Sensor
   Diagnostic Layer"*, Phase-I only, whose own Limitations section says every
   SITL number "should be repeated on a current ArduPilot and on PX4 before it
   is relied on") and an unrelated gate-conditioning scaffold.
   `CSIA_Systems_Paper_I_CURRENT_STACK_SUBMISSION_CANDIDATE.pdf` has zero blobs
   in the object database; it is reported to exist outside the repository and,
   being a rendering, cannot serve as an editable source.
2. **Bibliography: 37 unresolved citation markers**, requiring a human with
   publisher-record access. `make bib-guard` fails by design.

## 25. Proposed Systems-Paper Impact

**No manuscript was modified.**

- **Strong enough to integrate**: nothing from MAER — it did not run. The
  feasibility finding itself is publishable as a *limitation*: in this layer,
  fix-loss self-occlusion removes the only feature supporting the target
  hypothesis, and no surviving relation can substitute. That sharpens the
  existing self-occlusion result rather than adding a new one.
- **Should remain supplement**: the transport/gate/regime three-way evidence
  taxonomy and the two-gate freshness finding.
- **Should not be published**: any MAER result, any mechanism-specificity
  claim, any statement that CUSUM does or does not repair Mechanism A.
- **Title/abstract/contribution change?** No. Nothing here licenses a new
  contribution claim.

## 26. Final Recommendation to ChatGPT

**`PUBLISH_NEGATIVE_RESULT_ONLY`** — and specifically, publish it as a
limitation inside the existing self-occlusion narrative, not as a new
experiment.

The reason is that the negative result is *informative about the architecture*
rather than about MAER. "We tried a mechanism-aware repair and it underperformed"
would be a weak result. "The target hypothesis has one supporting feature, that
feature is gated on the flag the fault zeroes, every input to it disappears, no
surviving relation is sensitive to the fault, and the one quantity that is
sensitive is barred by the layer's own independence contract" is a strong,
checkable statement about why self-occlusion is hard to repair *here*.

The single most valuable thing a reviewer can do with this report: **attack §3.**
If a discriminating, fix-loss-surviving, contractually-permitted observable
exists and the audit missed it, the stop is wrong and MAER should proceed. If
not, the stop stands and the finding is the result.
