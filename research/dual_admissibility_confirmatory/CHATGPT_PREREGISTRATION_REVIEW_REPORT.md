# DUAL-CHANNEL ADMISSIBILITY — PREREGISTRATION REVIEW REPORT

Base exploratory commit `b21b539`. **No confirmatory trial has been run and no
confirmatory trace has been captured.** Item 32's hard stop is in force, and a
test asserts it (`tests/test_dual_admissibility_confirmatory.py::test_the_campaign_has_not_been_run`).

## 1. Exploratory result being frozen

Two mechanisms can produce the same operational inadmissibility `A = 0` while
requiring different diagnostic interpretations; under `D = A` that distinction
can be lost at the decision point. Candidate principle, not to be called
novel: *operational inadmissibility is not equivalent to diagnostic
noninformativeness.*

Source basis, unchanged and re-verified: `fresh[]` is computed once
(`online.py:603`) and feeds both every relation and physics gate plus the Beta
update (D) and `FailsafePolicy._conditions` (A). `D_gps == A_gps` by
construction.

## 2. Exploratory claims rejected

| Claim | Status now |
|---|---|
| gps_fault posterior improvement is the headline | **Retired.** Detector-dominant on the one real recording: +0.138 coupled, +0.002 from the split. Demoted to secondary. |
| "C0 aliases the two mechanisms" (strong H1) | **FALSE.** Measured during design. C0 aliases at the *leading decision* (0/857) but differs in `trust_gps` on 857/857. H1 frozen in weak form. |
| T1–T5 are `PROVED — NOVELTY NOT ESTABLISHED` | **Downgraded to `KNOWN/SUBSUMED`** by the prior-art search. |
| The partition/necessity condition is a result | **`KNOWN/SUBSUMED`.** It is the Fisher–Neyman factorisation criterion. |
| The architectural separation is a contribution | **`KNOWN/SUBSUMED`.** ARINC 429 SSM, SEVA, NAMUR NE 107. |
| "residual information survives the coupled gate, so the experiment is non-trivial" | **Overstated, corrected.** The residue is mostly an onset artefact — see §12. |

## 3. Exact primary candidate contribution

Not an architecture and not a theorem. **A measured instance of a consumer
destroying a distinction its own input protocol supplies**, with the source
chain traced to specific lines and the loss quantified under matched `A`. At
most a well-documented defect and its repair, in one system.

## 4. C0 — coupled

Operational invalidity propagates (`valid=False` reaches the frozen core, which
closes `gvalid` and `fresh` itself). `D = A`. Diagnostic evidence: the
categorical observation state, gated by `A`.

## 5. C1 — split

Same `A`. Diagnostic admissibility independent: categorical observation state
**plus** `h_acc` under its own frozen validity predicate.

## 6. C2 — status-only split

Same `A`. **Categorical observation state only** — `OBSERVED_VALID`,
`OBSERVED_INVALID`, `NOT_OBSERVED`. No `h_acc` in any form, no numeric
receiver-health field, no new detector. **Required, not optional.**

`C2` is scored against `C0`, which carries the identical categorical evidence
and differs in one boolean.

## 7. Exact operational A

```
A_gps(t) = fresh["gps"](t) = slot.valid ∧ slot.seen ∧ (t − slot.last_t ≤ 0.5 s)
```

`csia/runtime/online.py:603`, consumed by `FailsafePolicy._conditions`
(`failsafe.py:100, 145`) to raise `nav_degraded` → `SWITCH_NAV_INERTIAL`,
`INHIBIT_GPS_MODES`. Unmodified by any arm.

## 8. Exact diagnostic D

```
D_value(t)  = A_gps(t)                                   never readmitted
D_status(t) = 1[t − t_last_MESSAGE ≤ 0.5 s]              C1, C2
D_hacc(t)   = 1[hacc_valid(last usable)] · 1[t − that message ≤ 0.5 s]   C1 only
```

`D_status` gates on **message arrival**, not sample acceptance. That is the
only thing separating "the receiver said no fix" from "no message arrived";
gate it on anything derived from `last_t` and it fires on transport starvation.

## 9. Mechanism pair

`C_SENSOR`: messages continue at nominal rate, all `fix_type < 3`.
`C_TRANSPORT`: no message delivered, receiver healthy. Same platform, adapter,
consumer path and carrier.

## 10. Proof that A trajectories can be matched

Measured (`results/DESIGN_FEASIBILITY.json`):

| Arm | `A` mismatches, whole condition | in the scored interval | `A == 0` throughout |
|---|---|---|---|
| S0 reference (drop) | 0 | **0 / 857** | yes |
| C0 / C1 / C2 (propagate) | 8, all in `[12.00, 12.28]` | **0 / 857** | yes |

Propagation closes `A` immediately at onset; transport loss must wait out the
0.5 s timeout. The mismatch is exactly that transient and is bounded by `τ`.

**Scored interval:** `[onset + 0.5 + 0.2, end − 0.5 − 0.2]`.
**Admissibility gate, zero tolerance:** equal `A_trace_sha256` between the
paired mechanisms; a pair that fails is excluded and reported. More than 2 of
10 exclusions stops the campaign.

## 11. Primary mechanism-discrimination endpoint

Confusion matrix over `{SENSOR_INVALID, TRANSPORT_UNAVAILABLE, UNRESOLVED}`,
per arm, over matched-`A` ticks. The classifier is a **frozen decision rule
over runtime-observable state** — not a learned model, not a likelihood term —
which keeps detector magnitude out of the primary result. `UNRESOLVED` is a
first-class output. Counts and proportions only; no interval, no p-value.

Forbidden inputs: test condition, simulator parameter, filename, injected
label, trial index, onset time.

## 12. Information-retention endpoint

Exact `I(M; E)` at three points per arm — raw observation category, the arm's
downstream state, the arm's decision — computed from the exact empirical joint
over the scored population, no estimator. `I` is non-increasing along the
pipeline by data processing; **the inequality is textbook and is not claimed.**
What is measured is how much each architecture gives away.

## 13. Clean criterion

**Zero** mechanism classifications across all 10 clean trials, every arm. Not a
rate. An arm that fires is disqualified regardless of its discrimination score.

## 14. Held-out scenario count

30 trials: 10 `SENSOR_INVALID`, 10 `TRANSPORT_UNAVAILABLE` (paired by onset and
duration), 10 `CLEAN`. Every trial a fresh ArduPilot SITL boot, captured end to
end. Deterministic scenarios over a frozen nuisance schedule — **not iid
samples**, and labelled as such.

## 15. Contaminated / development traces

`results/DEVELOPMENT_TRACE_MANIFEST.json`: 20 files enumerated from the code,
**16 recordings** and 4 analysis outputs, each hashed. Primary contaminant:
`NON_SCORED_TEST_FIXTURE_M1.json.gz`.

**Derived contamination matters more than the file list.** Every synthetic
exploratory fixture was programmed over the *non-GNSS carrier* of that
recording, so a new schedule over the old carrier would still be contaminated.
That is why every confirmatory trial must be a fresh boot rather than a new
schedule.

## 16. Formal T1–T5 audit

`FORMAL_AUDIT.md` restates each with definitions, assumptions, proof,
implementation correspondence, and **what fails when each assumption is
removed** — the part the exploratory version omitted.

| | Proof | Prior art | Implementation |
|---|---|---|---|
| T1 evidence deletion | valid | `KNOWN/SUBSUMED` | verified |
| T2 self-masking faults | valid, necessity qualified | `KNOWN/SUBSUMED` | verified |
| T3 what the split can restore | valid | `KNOWN/SUBSUMED` | corollary measured |
| T4 steady-state posterior | valid | `KNOWN/SUBSUMED` | measured to 1.8 × 10⁻⁵ |
| T5 time to rank reversal | valid | `KNOWN/SUBSUMED` | **never measured** |

Two assumption-removal findings worth surfacing: T1 depends on the gate being
*multiplicative and linear*; and **T2 depends on `gps_fault` having a singleton
feature set** — a hypothesis with redundant support is not self-masking
regardless of coupling. The vulnerability is not the coupling alone.

## 17. Partition / sufficiency result

`OPERATIONAL_DIAGNOSTIC_PARTITION_MODEL.md`. `φ_A` induces `~_A`; the
diagnostic task induces `~_D`. Diagnosing from the operational state alone
loses nothing **iff** `~_A` refines `~_D` — which is exactly the Fisher–Neyman
criterion, so item 24's condition is the negation of sufficiency.
**`PROVED — KNOWN/SUBSUMED`.**

The one thing the mathematics licenses is a design criterion, not a result:
*an architecture that gates diagnosis on its operational admissibility variable
is asserting that variable is a sufficient statistic for diagnosis; here that
assertion is false.*

Three overstatements are explicitly refuted in that document, including
"coupling always loses information" (false when `~_A` already refines `~_D`).

## 18. Shortest counterexample

From the frozen generator, over `{V, I, N}`:

| Arm | shortest pair of distinct raw words with identical downstream state |
|---|---|
| `S0` drop | `('I', 'N')` — **length 1** |
| `S1` coupled | `('VV', 'IV')` — length 2 |
| `S2c2` split | `('III', 'INI')` — length 3 |

`S0`'s is the cheapest possible witness: one message reporting no fix is
downstream-identical to no message at all.

## 19. Counterexample-generator freeze

`results/COUNTEREXAMPLE_GENERATOR_FREEZE.json` — five files hashed. **It may
not be modified in response to a confirmatory failure**; if it is found wrong,
the run is void and restarts from a new preregistration.

**Regression guard passes.** `results/TOOL_SELF_AUDIT.json`: the one-message
phase misalignment was re-injected into a non-scored fixture, the checker
reported the `IV`/`VV` collapse, and the correct implementation was restored
and re-verified. *(It took two attempts: the first patched a different module
instance than the checker uses, so the audit passed for the wrong reason. An
assertion now pins the identity.)*

## 20. Closest prior art

A search was run. `PRIOR_ART_MATRIX.md`.

* **ARINC 429 Sign/Status Matrix** — Normal / Functional Test / **Failure
  Warning** / **No Computed Data**. FW vs NCD *is* `SENSOR_INVALID` vs
  `TRANSPORT_UNAVAILABLE`, standardised since the 1970s.
* **SEVA self-validating sensors** (Henry & Clarke, Oxford, 1993) — Validated
  Measurement Value, Validated Uncertainty, **Measurement Value Status**.
* **NAMUR NE 107** — four status signals, with operators shown the summary and
  technicians the detailed diagnostics: an explicit two-audience split.
* **OPC UA StatusCode** — value plus quality, sub-bits carrying diagnostic
  detail; clients forbidden from altering it.
* **DES diagnosability under observation masks** — "diagnosis requirements are
  specified by a partition on the state set"; a coarser mask loses observation
  information.
* **Fisher–Neyman sufficiency**; **missing-indicator / MNAR** literature.

## 21. What prior art kills

1. Any claim that separating operational from diagnostic validity is new.
2. Any claim that distinguishing sensor-invalid from no-data is new — it is two
   bits in an ARINC 429 word.
3. Any claim that the partition / sufficiency result is new.
4. Any claim that "absence is informative" is new.

**That is the entire architectural and formal content of the exploratory
package.** A modern consumer that aliases FW and NCD is a regression against
1970s avionics practice, not a discovery.

## 22. What potentially survives

* A measured instance of a *consumer* destroying a protocol-supplied
  distinction — MAVLink `fix_type` carries it, the adapter records
  `NO_3D_FIX`, and the admissibility gate then aliases it.
* The failure mode named precisely: an assurance layer treating its operational
  admissibility variable as a sufficient statistic for diagnosis.
* The cross-ingest-path inconsistency: three committed decoders, three meanings
  for one raw condition, into one frozen core.

None are novelty claims.

## 23. Battery generalisation feasibility

`BATTERY_SOURCE_AUDIT.md`. Battery is 3/4 and the missing criterion changes the
question rather than merely weakening it:

* explicit invalid state: **partial** — `current_battery == -1` is rejected,
  but `battery.voltage` has no invalid path at all, and the rejection carries
  the default `SENTINEL` reason rather than a specific one;
* invalid becomes no-update: **no** — unlike GNSS, the reject does **not** pop
  `_latest`, so a disowned current is *retained* until it ages out;
* one gate both roles: **yes** — `fresh["battery"]`, raising `CRITICAL`;
* surviving health fields: **yes, richer than GNSS** — `charge_state`,
  `fault_bitmask`, `battery_remaining`.

So battery exhibits `RETAINED_AS_IF_CURRENT` where GNSS exhibits
`OBSERVED_INVALID → NOT_OBSERVED`. **Running it as though it were the same
experiment would confuse two defects.** Recommendation: do not implement;
file the retained-invalid-current behaviour as a defect in its own right.

## 24. Physical HIL design

`PHYSICAL_HIL_VALIDATION_PLAN.md`, retargeted from the sustained-closure sweep
to the matched-`A` mechanism pair. L1 deterministic UBX emulator → real flight
controller; L2 real receiver, **conducted and shielded only**; L3 clean real
flight, passive shadow. No radiated interference at any level.

**Criterion 0 gates everything and is currently unanswered:** does a real
flight controller forward `GPS_RAW_INT` while the receiver reports
`fixType = 0`? In SITL it does — the M1 recording contains 582 such messages —
but on hardware it is unknown. If it does not, `C_SENSOR` and `C_TRANSPORT` are
indistinguishable at the consumer on real hardware and the whole GNSS line is
moot for physical deployments.

## 25. Preregistration commit

`DUAL_ADMISSIBILITY_PREREGISTRATION.md`, committed with this report. Frozen on
commit; any change voids the campaign.

## 26. Scientific blockers

**B1 — the campaign's empirical content is smaller than it appears, and
smaller than my own first draft claimed.** Under matched `A`, `C0`'s failure is
close to analytically forced (T1), and `C2`'s success is close to tautological
given its inputs. The *leak* that would have made it non-trivial turns out to
be mostly an onset artefact: `trust_gps` **freezes** when `A` closes
(`engine.py:146`), so within the scored interval it is a constant inherited
from the excluded transient, and the fields that do move discriminate at chance
(0.5047, 0.5053). What genuinely remains: the clean control on fresh data, and
whether a **single cross-pair** threshold on raw trust generalises. On one
development pair such a threshold scores 1.0000 — purely on the artefact.

**B2 — HIL criterion 0 is unanswered and is cheaper and more decisive than the
software campaign.** If real hardware does not forward no-fix reports, 30 SITL
captures answer a question that does not arise in deployment.

**B3 — prior art has already demoted what a clean pass can license** (§21). The
preregistration says so, but it means the campaign's value is assurance of this
product, not research output.

Not blockers, and resolved: matched `A` (verified, zero tolerance achievable);
status-only ablation without a detector (specified); a null arm that can kill
the claim (`C0_STRONG`, corrected); contamination (manifested and hashed);
instrument integrity (self-audit passes); `SENSOR_DEGRADED_BUT_VALID` (deferred
with a stated reason rather than dropped).

## 27. Final recommendation

**`BLOCKER_REMAINS`.**

The preregistration is complete, internally consistent, and capable of
reporting that the split was unnecessary. I do not recommend spending 30 fresh
SITL captures on it in its current sequence, for the reasons in §26.

Recommended resequencing, cheapest decisive step first:

1. **Answer HIL criterion 0** — does a real flight controller forward
   `GPS_RAW_INT` with `fix_type < 3`? One bench setup, no campaign. If no, stop
   the GNSS line for hardware.
2. **Test `C0_STRONG` cross-pair generalisation on development data**, which is
   already burnt. Capture 3 pairs at different onsets, not 10, and check
   whether one frozen threshold survives. If it does, the claim collapses for
   the cost of 6 boots instead of 30.
3. **Then, only if 1 and 2 both favour proceeding, run the 30-trial campaign**
   as specified.
4. **Independently of all of it, fix the cross-ingest-path inconsistency** and
   the retained-invalid-current behaviour in the battery path. Both are defects
   on their own merits and neither depends on this research question.

**NOVELTY: NOT ESTABLISHED**, and after §20–21, not establishable in the terms
the exploratory package used.
