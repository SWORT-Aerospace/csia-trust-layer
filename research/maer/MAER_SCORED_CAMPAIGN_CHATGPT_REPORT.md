# MAER SCORED CAMPAIGN — CHATGPT REVIEW REPORT

## 1. Executive Verdict

**`INVALID`** — specifically, the campaign was **not run**. 0 of 100 scored
trials were executed.

Harness verification on a non-scored fixture established that the preregistered
**M1 condition cannot exercise the gate-placement manipulation**. Under
`SIM_GPS1_JAM = 1`, `gvalid` never falls: 0 of 999 post-onset ticks. With
`gvalid == 1` everywhere, A1 and A1G are identical *by construction* —
`contribution(1.0)` returns the same value for both arms, which
`tests/test_maer_arms.py` asserts as a property. MC1 therefore cannot fire, and
the preregistration states that MC1 failure invalidates the experiment.

The underlying problem is a genuine tension, and it is the scientifically
interesting result of this stage:

| ArduPilot GNSS fault | `gvalid → 0`? | `h_acc` live during invalid fix? |
|---|---|---|
| `SIM_GPS1_ENABLE = 0` | **yes**, 450 sustained ticks | **no** — frozen (Stage 0.5) |
| `SIM_GPS1_JAM = 1` | **no** — 0 post-onset ticks | **yes** — 278 distinct values |

**A live receiver-health residual and a closed validity gate do not co-occur
under either available ArduPilot GNSS fault model.** The experiment needs both
simultaneously and neither injection supplies both.

Per Stage-2 items 5 and 7 the campaign was stopped rather than repaired. M1 was
not switched back to `ENABLE=0`, the gate definition was not changed, MC1 was
not redefined, and nothing was tuned.

## 2. Freeze / Provenance

```
preregistration commit : d34c629
preregistration SHA256 : 39780e9f09b44545ca0426909ee1849c2e0307308420e3290f9fc95f07196623
                         (identical at the commit and in the working tree)
scored-start commit    : d34c629 (HEAD at verification)
frozen-core tag        : csia-v1.0-research-final
frozen-core test       : tests/test_v1_frozen.py PASS
ArduPilot SHA          : 01a504b472259602e13df4cf07df7c0cdbb35993 (V4.8.0-dev)
scored artifacts predating the preregistration : 0
```

## 3. Planned vs Executed Campaign

```
planned trials : 100  (20 scenarios x 5 arms)
executed       : 0
valid          : 0
rejected       : 0
replaced       : 0
```

No condition × arm cell was run. One **non-scored** capture was taken for
harness verification, at onset 7 s — a value in neither the preregistered onset
set (8, 11, 14, 17, 20, 23, 26, 29, 32, 35) nor the extension list (38, 41, 44,
47, 50), and tagged `NON_SCORED_TEST_FIXTURE_M1`.

## 4. Scenario Pairing

Verified on the fixture, and the mechanism works:

```
determinism    : two replays of one recording are byte-identical
pairing        : A1 and A1G share input_sha256 = e0197fa54432...
tick counts    : 1175 / 1175
```

Pairing is structural rather than asserted: the simulator runs **once** per
scenario, every MAVLink message is recorded with its receive time, and each arm
replays that recording through an adapter whose clock is the recorded time.
`AircraftAdapter.__init__` accepts a `clock`, so staleness replays exactly.

No pairing violations. The design is sound; the condition is not.

## 5. Manipulation Check MC1

**CANNOT FIRE on M1 — this is the blocking finding.**

Measured on the fixture (`SIM_GPS1_JAM = 1`, onset 7.0 s):

```
GPS_RAW_INT post-onset            : 2004 messages
  fix_type = 6 (valid)            : 1422
  fix_type = 1 (invalid)          :  582
  distinct h_acc on invalid fixes :  278      <- evidence is live
post-onset ticks                  :  999
post-onset ticks with gvalid == 0 :    0      <- gate never closes
total ticks with gvalid == 0      :    1      (pre-onset)
```

On the single `gvalid == 0` tick the manipulation behaved exactly as designed:
A1 contributed, A1G did not, with identical consistency. The mechanism is
correct. There is simply nothing for it to act on.

**Why.** `online.py:482`:

```c
gvalid = 1.0 if s["gps"].valid and s["gps"].seen else 0.0
```

Those are the core's *slot* state. The adapter **withholds** the gps sensor on
an invalid fix (`to_core_samples` emits a sensor only when all its channels are
usable) rather than marking it invalid, so the slot is never invalidated — and
under jamming, valid fixes keep arriving between the invalid ones (1422 vs 582)
and continually refresh it.

`pass/fail`: **FAIL — experiment invalid.** Interpretation of H1 and H2 for the
structural arm is stopped, as the preregistration requires.

## 6. M0 Clean Results

Not run.

## 7. M1 JAM Results

Not run as scored trials. The fixture measurements in §5 are harness
verification, not results, and no arm comparison is drawn from them.

## 8. H1 — Diagnostic Rescue

**INCONCLUSIVE — not evaluated.** H1 requires MC1 to hold. It does not.

## 9. M2 Persistence-Ramp Results

Not run.

## 10. H2 — Mechanism-Specific Crossover

**INCONCLUSIVE — not evaluated.** The crossover requires `D(A1, M1)`, which
requires a functioning structural arm on M1.

No scenario-level values exist. None are reported, and none are estimated.

## 11. M3 Transport Results

Not run. Same-platform feasibility was established at Stage 1.1 (5 Hz → 5.05 Hz;
0.5 Hz → 0.50 Hz; 10.1× starvation ratio) but no scored trial was executed.

## 12. H3 — Evidence Cause

**INCONCLUSIVE — not evaluated.**

## 13. A3 Combined Result

Not run.

## 14. Exposure Metrics

Not computed. No scored ground truth exists, so `T_NA`, `T_UH`, `T_FH` and
`T_SOFH` are not reported for this campaign.

## 15. Compute Cost

Not benchmarked. Benchmarking arms that were never scored would attach
experiment-shaped numbers to an experiment that did not run.

## 16. Invalid / Rejected Trials

None — no trial was run, so none was rejected. This section is empty by fact,
not by omission.

## 17. Unexpected Results

**The blocking finding is itself the unexpected result, and it is the most
scientifically interesting thing this stage produced.**

Stage 0.5 established that `SIM_GPS1_ENABLE = 0` freezes `h_acc`, and chose
`SIM_GPS1_JAM = 1` for M1 precisely because it keeps receiver-health evidence
live. What was never checked — by me, or by any prior stage — is whether
jamming also closes the validity gate. It does not.

So the two properties the experiment requires are mutually exclusive across the
available fault models:

- `ENABLE = 0`: gate closes, evidence frozen → nothing live to rescue
- `JAM = 1`: evidence live, gate stays open → nothing to rescue it *from*

This was discovered on a non-scored fixture, before any scored trial. That is
the intended function of the non-scored verification step and it worked.

A second, smaller surprise: under jamming the layer's `h_acc` consistency sits
at median 0.0 across all 999 post-onset ticks, so the relation is saturated for
essentially the whole window — consistent with the `DETECTOR_DOMINANT_BUT_DECLARED`
finding preregistered at Stage 1.1.

## 18. Negative Results

- **MC1 cannot fire on M1.** The preregistered manipulation check fails for a
  structural reason, not a marginal one.
- **The M1 condition choice was wrong**, and it was wrong for a reason no prior
  stage tested: every stage checked evidence liveness, none checked gate
  closure under the same injection.

## 19. Post-Hoc Analyses

**NONE.** No scored data exists to analyse.

## 20. Red Team A–J

Most objections are moot because no result is claimed. The two that still bite:

**J — "The experiment was tuned after results."**
No result exists. Preregistration `d34c629`, SHA256 `39780e9f…`, verified
identical in the working tree; 0 scored artifacts predate it; nothing was
retuned when the fixture came back unusable. The stop is recorded rather than
worked around.

**A — "A1 wins trivially because the added relation alone flips the diagnosis."**
Still conceded, and now doubly so: `DETECTOR_DOMINANT_BUT_DECLARED` was
preregistered, and the fixture shows the relation saturated across the whole
window. Had the campaign run, H1 would have been a weak test — which is why H2
carried the result and why H2's unavailability is the real loss.

**B, C, D, E, F, G, H, I** — not applicable; no scored comparison, crossover,
scenario population, transport result or ablation was produced.

## 21. Claim Ledger

| claim | status | strongest allowed wording | forbidden |
|---|---|---|---|
| A live receiver-health residual and a closed validity gate do not co-occur under either tested ArduPilot GNSS fault model | `IMPLEMENTATION_PROPERTY` (measured, one fixture + committed Mechanism A artifacts) | "In the evaluated configuration, neither available injection produced both simultaneously." | "GNSS jamming does not invalidate navigation validity." |
| `gvalid` does not fall under `SIM_GPS1_JAM = 1` | `IMPLEMENTATION_PROPERTY` | "Measured 0 of 999 post-onset ticks on one non-scored fixture." | any claim of generality across scenarios — only one fixture was measured |
| MAER's structural arm is untestable as frozen | `PREREGISTERED_REFUTED` (the design, not a hypothesis) | "The preregistered M1 condition cannot exercise MC1." | "Mechanism-aware diagnosis does not work." |
| H1, H2, H3 | `INCONCLUSIVE` | "Not evaluated." | any directional statement |

## 22. Scientific Interpretation

- **Did preserving live receiver-health evidence improve diagnosis?**
  Unknown. Not evaluated.
- **Was the effect gate-placement-specific?**
  Unknown — the gate never closed, so placement had no consequence.
- **Did CUSUM preferentially improve the persistence mechanism?**
  Unknown. Not evaluated.
- **Did the predicted crossover exist?**
  Unknown. Not evaluated.
- **Could evidence-loss be distinguished from transport starvation?**
  Unknown. Not evaluated.
- **Did the combined system earn its complexity?**
  Unknown. Not evaluated.

What *was* learned: the self-occlusion mechanism and the receiver-health rescue
occupy **different fault regimes** in this simulator. The fault that destroys
the evidence (fix loss) also freezes the receiver's self-report; the fault that
keeps the self-report alive (jamming) does not destroy the evidence. Whether
that is a property of ArduPilot's SITL models or of GNSS receivers generally is
not established here.

## 23. What This Does NOT Establish

- **physical GNSS jamming**: nothing. All observations are SITL.
- **cross-platform**: nothing. ArduPilot only; PX4 rejected at Stage 0.5.
- **population statistics**: nothing. One non-scored fixture.
- **field false-alarm rate**: nothing.
- **certification**: nothing.
- **general theorem**: nothing. The co-occurrence finding is about two specific
  simulator fault models.

## 24. Manuscript Impact

**`DO_NOT_INTEGRATE`** — as a MAER result. There is no MAER result.

The co-occurrence finding may be worth one sentence in the existing
self-occlusion limitations, if it survives independent review and is
re-measured across more than one fixture.

## 25. Novelty Status

**NO NOVELTY CLAIM AUTHORIZED.** Exact experimental result: a preregistered
mechanism-specific mitigation crossover was designed, frozen, and then not
executed, because its manipulation check could not fire under the frozen
condition.

## 26. Scientific Blockers

1. **No ArduPilot GNSS fault model supplies live receiver-health evidence AND a
   closed validity gate simultaneously.** This blocks MAER's structural arm
   entirely, not merely the current condition.
2. The finding rests on **one** non-scored fixture plus the committed Mechanism
   A artifacts. Before any redesign it should be re-measured across several
   onsets, and other ArduPilot GNSS parameters (`SIM_GPS1_NUMSATS`,
   `SIM_GPS1_LCKTIME`, `SIM_GPS1_FIXTYPE`) should be checked for a model that
   does supply both.

## 27. Publication Blockers

1. No current-stack manuscript source exists in the repository (unchanged).
2. Bibliography: 37 unresolved citation markers (unchanged).

## 28. Recommendation to ChatGPT

**`DO_NOT_INTEGRATE`**, and the specific question for review is a design one
rather than a statistical one:

> Is there an ArduPilot GNSS fault model that closes `gvalid` while keeping
> `h_acc` live? `SIM_GPS1_FIXTYPE` (forces the reported fix type directly) and
> `SIM_GPS1_NUMSATS` (drives satellite count, which gates lock) are the obvious
> candidates and were **not** examined. If one of them supplies both properties,
> MAER is revivable under a **new** preregistration — the current one cannot be
> amended, since amending a preregistration after discovering its condition is
> unusable is exactly the move that invalidates preregistration.

If no such model exists, the honest conclusion is stronger than a failed
experiment: in this architecture and simulator, the fault that occludes the
evidence also silences the receiver's account of itself, so there is nothing to
rescue at the moment rescue is needed.
