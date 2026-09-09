# Research directions, September 2026

**Status of every idea below: PROPOSED. None is evidenced, none is claimed
novel.** The prior-art search still has not run — every scholarly source
returns 403 here — so "I have not seen this done" is a statement about my
reading, not about the literature. Each entry therefore carries what would
have to be true for it to be worth doing, and what would kill it.

These are ordered by how directly this session's measurements motivate them.
The first three are not speculative at all: each closes a gap something
measured today walked into.

---

## 1. Record the tick boundary, not just the tick — DONE, AND IT FALSIFIED THE STATED KILL CONDITION

**Status: RESOLVED 2026-09-09. Ledger HF-017.** The proposal below is left
exactly as written, because it names a kill condition and the kill condition
is what makes the result worth anything.

The test ran. The residual did **not** persist: on one log, one
reconstruction and one comparator, the wall-clock join gave 119 divergences
and the tick-index join gave **0 divergent, 2250 of 2250 bit-identical**.
ArduPilot is unchanged at 0 under both, so agreement was not bought by
loosening the comparison — the tick join is an exact integer equality and is
the stricter of the two.

The phase offset was real and its cause was **not** the one guessed below.
It was not that the replay ticks only at hand-off times. It was that the
recorded rows were shifted by the first row's `t_mono`, which on that log sat
at 0.023607 s — 0.59 of a tick. The mechanism was in the comparison, not in
the replay.

Two further defects surfaced on the way and are recorded in HF-017: the
long-standing "144 divergent" figure came from a log with no staleness
configuration and was never a measurement, and the default log paths pointed
into a gitignored directory.

**What followed.** HF-004 was closed on this evidence by an explicit decision
of the program owner (HF-018), over my stated objection that two runs are not
a general property. The objection is preserved in the ledger rather than
removed.

**What is still open.** The values are reproduced on neither platform.
ArduPilot puts **zero** of 2248 decisions within the declared 1e-12
tolerance, worst relative difference 1.80e-05; PX4 manages 980 of 2242, worst
6.74e-10, appearing at tick 52 as 1.7e-14 and accumulating through the α/β
recursion. The tolerance has not been changed. The hand-offs HF-004 asked to
have logged at run time are still reconstructed.

---

**What today's measurement forces.** PX4 replay has 119 residual divergences
with a perfectly symmetric signature — 59 ticks where the replay has
`altitude_baro` live and the recording does not, 59 the other way. That is a
**phase offset of about one tick** at baro's staleness boundary, not a
semantic disagreement.

The mechanism is structural: the live run ticks on a 25 Hz wall clock, the
replay ticks only when a reconstructed hand-off arrives, so the two grids
drift relative to each other by a fraction of a tick. Around each of ~89 baro
arrival cycles, that fraction flips freshness for exactly one tick in each
direction.

**Proposal.** Log the layer's own tick boundary — the `tau` at which each
tick's staleness evaluation occurred — alongside `t_mono`. A replay can then
reproduce the tick grid instead of inferring it.

**What would kill it.** If the residual persists with the tick grid aligned,
the phase-offset hypothesis is wrong and the cause is elsewhere. That is a
clean falsification and it is cheap: one field, one SITL run.

**Why it matters beyond replay.** Decision replay is the only mechanism that
turns "the log says X" into "X is reproducible by an independent path". Until
it works on both platforms, every result in this repository is one-shot.

---

## 2. Contamination-aware trust — BUILT, MEASURED, AND REJECTED ON ITS OWN KILL CONDITION

**Status: RESOLVED 2026-09-09. Ledger SR-011.** The proposal below is left as
written. It named what would kill it, and something adjacent to that killed
it.

It was built. `csia_supervision/contamination.py` recovers the per-edge terms
exactly — 12000 comparisons against the core's own `c_nbr`, zero
disagreements, worst 3.3e-16 — and re-runs the Beta recursion on a restricted
partner set, reproducing `state.trust` at **max drift 0.0** when nothing is
restricted. **It needed no frozen-core change**, which corrects the claim in
the SR-010 withdrawal note.

**It does not rescue the rule.** All 95 enumerated combinations, motor_esc
unfaulted, threshold 0.82 chosen by the procedure declared beforehand:

| trust used | false alarms of 95 |
|---|---|
| core | 27 |
| restricted to partners in good standing | 14 |

Fourteen is not zero, so kill condition K2 fires and the rule stays
withdrawn.

**Why, which is the part worth keeping.** Partner-level standing and
edge-level agreement are different facts, and the restriction only filters on
the first. At the minimum, motor_esc sits at 0.65000 with all three incident
edges at consistency 0.0000 and its only *admitted* partner is imu0 at 0.8528
against imu0's own standing of 0.82. imu0's bias drift breaks the
accel/motor-current relation while imu0's own trust, held up by its other
edges, stays above threshold. The contamination arrives through an admitted
edge. Measured across the search: 78 of 95 runs.

**And the restriction has a worse failure of its own.** With no admissible
partner the neighbour term drops out and the sensor is scored on physics
checks alone, which read healthy. Maximum restricted trust at zero coverage:
**0.9987**. A sensor nothing can vouch for reports near-perfect trust. Five
of the 13 runs the restriction silenced were silenced this way, so 27 → 14 is
not a halving and must not be quoted as one.

**What is kept.** The decomposition, for the second reason the proposal gave:
`evidence_support` traces an evidence id to the edges holding it up. On a
clean hover, `baro.altitude.supported` rests 83% on the baro–gps edge and 17%
on the baro–battery thermal edge. Descriptive only — it promotes nothing and
UNKNOWN is still never resolved.

---

**What today's measurement forces.** The motor_esc low-trust rule was
withdrawn (SR-010) after the falsification search found a healthy sensor
raising CAUTION. Two guards were tried and both failed for the same reason:

> The guard gates **whether to judge**. It does not clean **the value being
> judged**. A sensor can be judged on a trust value that was dragged down by
> exactly the partners the guard has just ruled unfit to judge it.

**Proposal.** Carry, alongside `T_i`, a decomposition of *where that trust
came from* — the per-edge contribution to `E_i` over the recent window. Then
a judgement can be made on the trust attributable to partners in good
standing, rather than on the aggregate. Concretely: `E_i` already fuses four
sub-scores under known weights, and `C_nbr` is already a trust-weighted mean
over edges, so the per-edge terms exist at computation time and are simply
not retained.

**What would kill it.** If the renormalised trust is too noisy to threshold
on a sparsely-corroborated sensor, the rule shape is unsalvageable for
well-connected sensors and the honest answer is the one already recorded:
supervise absence, publish the detection floor for degradation, and leave it.

**Why it is not just a fix.** The same structure answers a question the
system currently cannot: *which* evidence is holding a capability up. That is
the difference between "altitude_hold is SUPPORTED" and "altitude_hold is
SUPPORTED, on the baro–gps edge alone, and gps is the weak leg."

---

## 3. Per-platform integration contracts, measured rather than documented

**What today's measurement forces.** Two platforms, two integration
constraints, neither discoverable from the code:

- **ArduPilot** streams nothing to a link until it has seen a GCS heartbeat
  on it. CSIA is read-only by construction and can never send one — so a
  forwarder is mandatory. Measured: 21 of 25 messages were heartbeats
  without one; 13,556 messages in the same 20 s with one.
- **PX4** streams unconditionally, but its GCS instance carries no
  `HIGHRES_IMU`, no `SCALED_PRESSURE`, no `SYS_STATUS`. CSIA on that link
  produced **zero** trust values. On the Onboard instance it produced trust
  on 2250 of 2251 ticks.

Both were found by running the thing and reading the output. Both would have
been found by a human in a field tent, at much greater cost.

**Proposal.** A `PlatformIntegrationContract` per adapter, executable rather
than prose: the messages required, the minimum rate for each, the link
topology that delivers them, and a probe that reports which requirements the
live link actually meets — before a trial rather than after. `preflight.py`
already has the shape; it currently proves the *build* is sound and says
nothing about whether the *link* will carry what the build needs.

**What would kill it.** Nothing measurable — this is engineering, not a
hypothesis. The risk is scope: it is only worth building if more platforms
follow, and a third platform is not currently planned.

---

## 4. Trust as a certificate rather than a scalar

`T_i` is a number with no provenance attached. Everything downstream —
capability evaluation, the supervision overlay, the mission layer — consumes
it on faith.

**Proposal.** Emit a signed evidence certificate: the value, the witness set
that produced it, an expiry, and the graph path it came from.
`csia_assurance/witness.py` is the seed. A consumer could then verify support
without trusting the producer, which is what would make CSIA composable
across a trust boundary rather than only inside one process.

**What would kill it.** If nothing downstream ever needs to verify rather
than trust, this is ceremony. The honest test is whether a second consumer
exists that is not part of this repository.

---

## 5. Fleet-level trust with the same demote-only discipline

The graph is intra-vehicle. Two aircraft observing the same environment have
a genuine cross-check available — a shared magnetic field, a shared
gravitational vector, a common GNSS constellation — and those are physical
relationships of exactly the kind the existing edges encode.

**Proposal.** Extend the edge model across vehicles, keeping the two rules
that make the current composition safe: the overlay may only raise, the
evidence bridge may only demote.

**What would kill it, and it is serious.** The hard part is not the
mathematics but the trust model *between* platforms. A compromised or merely
faulty peer becomes an evidence source, and the current design has no notion
of an adversarial neighbour — `C_nbr` weights by the neighbour's own trust,
which is a defence against a *broken* peer and not against a *lying* one.
Until that distinction is modelled, fleet extension would weaken the property
the whole system rests on.

---

## 6. Online identification of edge models

Edge residual thresholds are fixed constants in a frozen file. A specific
airframe has specific noise, and a threshold set for the fleet is
conservative for every individual.

**Proposal.** Learn per-airframe edge parameters with the frozen model as
prior, and treat the learned values as a *separate, versioned artifact* that
never modifies the frozen core.

**Why this is the hardest one to do honestly.** The entire freeze discipline
exists because a number that moves cannot be attributed. A learned threshold
is a number that moves. It would need a provenance story at least as strong
as the current one — what data trained it, over what window, and what a
replay does when it meets a log recorded under a different learned value. Do
not start this before §1 works, because without reproducible replay there is
no way to check a learned system at all.

---

## 7. Formal capability semantics

`bounded_verify.py` proves bounded properties today. The capability lattice
has one invariant that is asserted by tests and could be a theorem:

> **UNKNOWN is never promoted to SUPPORTED, under any input sequence.**

**Proposal.** Formalise the lattice and the evaluation function, and prove
monotonicity and non-promotion over arbitrary input sequences rather than
over generated ones. The property-based tests currently sample that space;
a proof would close it.

**What would kill it.** If the evaluation function is not actually monotone —
which the `requires_one_of` degraded path makes non-obvious — the proof
attempt fails and *that* is the finding, more valuable than the proof would
have been.

---

## What none of this changes

CSIA remains advisory in every mode, with no command path. None of these
directions adds authority, and none of them promotes a stage on its own. The
standing rule holds: **a negative result is acceptable, a known theorem is
acceptable, an unresolved mechanism is acceptable if labelled — an
unsupported novelty claim is not.**
