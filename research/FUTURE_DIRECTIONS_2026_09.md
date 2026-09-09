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

## 1. Record the tick boundary, not just the tick

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

## 2. Contamination-aware trust, not just corroboration-gated trust

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
