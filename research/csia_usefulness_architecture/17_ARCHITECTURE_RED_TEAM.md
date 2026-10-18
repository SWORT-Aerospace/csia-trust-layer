# Phase 54: final architecture red team

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**The brief was cut off in the middle of this phase.** It ended at "Can this
run on H743-class hardware". The questions below are the ones received,
answered in full. After them come six further questions a hostile reviewer
would ask, added and marked as such.

## 1. The questions received

**Is this becoming a metadata framework instead of an assurance system?**

It would be if metadata were accumulated for its own sake. Four guards
prevent that.

- **Every field must cite a failure mode it prevents.** In
  `EVIDENCE_RECORD_V2_FIELDS.csv` each of the 22 fields cites one.
- **Only 10 fields are required**, and 4 are audit-only.
- **Vehicle facts are referenced, not copied.** They are held once, by epoch
  and contract id.
- **The architecture changes decisions in exactly four places:**
  1. admissibility;
  2. refutation independence;
  3. disagreement;
  4. verdict naming.

  Anything that changes no decision is kept off the runtime path.

**Are contracts too complex?**

Not as specified.

- The grammar has seven operators, one clause family per kind, no
  disjunction beyond `in`, no quantifiers and no temporal operators.
- Every clause has one evaluator and one test.
- Contracts compile to masks.

The real risk is **authoring burden**: someone has to write a correct
contract for each producer. For that reason:

- the minimum contract has 9 required keys;
- component dependencies are referenced from the Trust Contract v0.1 rather
  than repeated;
- later, FORGE-style import from AADL or EMV2 (S041) should generate them.

**Can a simpler solution solve 80 % of the problem?**

Probably, yes, and the plan starts there. The minimum viable version is:

- **Envelope plus four contract clauses:**
  - `requires`;
  - `invalidated_by`;
  - `max_age_s`;
  - `window`.
- **The verdict split (T2).**
- **Predicate-error reporting (T3).**

That alone would have prevented the 55 XSYS-001 negative-control errors, as a
general rule rather than a pipeline convention. It would also fix the
UNSUPPORTED and UNIQUE defects.

Tags, independence, disagreement and targeted invalidation are Horizon 2.
They enter only if the lane-switch experiment shows the global-flush
baseline is worse. If the first experiment shows a time window suffices even
when gains change, event-bounded windows (I-14) are dropped.

**Are we duplicating autopilot state?**

No. The context has 16 dimensions, each **read** from a published message or
produced by a declared producer (`04_CONFIGURATION_TRANSITIONS.md` §2). CSIA
estimates none of them. It keeps only what a contract names.

**Are we importing too many algorithms?**

No. The four reference adapters wrap existing implementations:

- the CUSUM bank;
- PX4 estimator status;
- the XSYS-001 witnesses;
- a v2 domain.

No new detector, estimator, planner or fusion rule is introduced. The
anti-roadmap (`11_TARGET_ROLE_AND_NON_GOALS.md` §3) is explicit.

**Does provenance actually change decisions?**

Only two provenance elements do:

- **dependency tags**, through invalidation, the independence rule and the
  COMMON_SOURCE explanation;
- **`derived_from`**, through derived invalidation and the ban on parent and
  child as two witnesses.

Everything else is audit-only (`05_PROVENANCE_AND_DEPENDENCE.md` §1). If the
lane-switch experiment shows targeted invalidation is no better than a
global flush, the tag index loses its main justification and should be cut
to the independence rule alone.

**Can evidence invalidation itself create dangerous blindness?**

Yes. The design contains the three ways it could.

1. **Lifting a restriction without new evidence (FM-33).** The monotone rule
   prevents it: invalidation can widen hypothesis sets and move a function
   to UNKNOWN, never to ELIGIBLE. UNKNOWN outranks INELIGIBLE (S008).
2. **An invalidation storm (FM-30).** Hysteresis plus `CONTEXT_UNSTABLE`
   makes the blindness **visible** as UNKNOWN, not silent.
3. **Over-broad contracts that invalidate valid evidence.** This is measured,
   not assumed: "valid evidence incorrectly rejected" is a first-experiment
   metric (`14_FIRST_EXPERIMENT.md` §4), and the global-flush comparison is
   the second experiment.

**Can producers lie about their assumptions?**

They can **declare** anything. It does not help them:

- CSIA checks the declared conditions against context it reads
  independently;
- validation status comes from gate records, not from the producer;
- a producer can lower its own output to UNAVAILABLE but cannot raise its
  standing.

**A buggy contract is the real risk.** An enable condition that is too
permissive would admit evidence outside its validity, and no runtime check
can detect that. The mitigation is process:

- contracts are reviewed artifacts with tests;
- a contract's validation status is tied to the experiment that validated it
  (for example, W_DYN's to XSYS-001 under PX4 SIH only).

**Is conflict operationally useful?**

Yes, as an explanation and as a brake, not as a number
(`07_CONFLICT_SEMANTICS.md` §8).

- The brake keeps a hypothesis open when independent admissible evidence
  both confirms and refutes it.
- The explanation tells an operator whether to suspect a shared sensor
  (COMMON_SOURCE), re-run under the current configuration
  (CONFIGURATION_MISMATCH), or do nothing (DIFFERENT_TIMESCALE).

If the shadow comparison shows disagreements essentially never occur on
realistic logs, I-07 is deferred.

**Can this run on H743-class hardware?**

**Unproven.** There is no STM32H743 build of any CSIA component, and no target
measurement (S020).

What can be said:

- The new layer is bitmask and table-driven, with no allocation.
- Its target ranges (`08_PERFORMANCE_SAFETY_BOUNDARY.md` §3) are **plausible**
  for a 480 MHz Cortex-M7: tens of kilobytes of RAM, and microseconds per
  envelope. They remain **targets to be benchmarked**, and Gate E exists so
  that the answer is a measurement.
- v2 itself has no native port. Its host cost is dominated by the domains
  and the API document (about 0.75-3 ms in CPython, S012), not by
  localization (45.8 µs).

The recommended first product surface, the configuration-change evidence
analyzer, runs **off-board**. It does not depend on this answer.

## 2. Further questions a hostile reviewer would ask (added)

**Does any of this reduce wrong decisions, measured?**

Not yet.

- The only measured evidence is XSYS-001's negative control: 55/55 wrong
  without the check that admissibility generalises.
- The XSYS-001 replay (L4) is expected to reproduce "0 WRONG with the check".
  That is a reconstruction of the preregistered windows, not new evidence.
- The first new measurement is the first experiment.

Until then, the value claim is a design argument.

**Is the verdict split just renaming?**

Partly. The names are established (S061, S032). The value is that two
operationally different situations stop sharing a token:

- **INSUFFICIENT_EVIDENCE:** collect more.
- **NO_CONSISTENT_HYPOTHESIS:** the model is incomplete or a refuter is
  wrong.

This was independently criticised three times (S031, S032, and the novelty
boundary).

**Why not fix the attribution defect directly in `csia/v2`?**

Because v2 is frozen (S029, S045). The fix lives in the 2.1.0 overlay. The
2.0.0 compatibility view reproduces the frozen behaviour byte for byte,
defect included, until the freeze lifts. That is the honest compatibility
statement, not a preference.

**Does the architecture depend on the autopilot publishing context?**

For estimator and controller context, yes. Where a dimension is not
published (`TRANSITION_MATRIX.csv`, UNCLEAR rows), evidence that depends on
it is `UNKNOWN`, fail-closed. That makes the architecture **less** permissive
on autopilots that publish less. This is deliberate, and it is the
integration conversation the Trust Contract already anticipates (S023).

**Could the whole thing be replaced by an existing product?**

For the automotive domain, the DEM concepts (enable and storage conditions,
aging and healing) already cover most of admissibility and lifecycle
(S050). In aviation, ARINC 429 SSM covers per-word validity (S053).

No searched source applies them across heterogeneous autopilot evidence with:

- dependency-aware refutation;
- targeted invalidation on estimator and controller transitions.

**That is an engineering-integration gap, not a research claim.** The design
deliberately reuses those concepts rather than competing with them.

**What would make this review wrong?**

Any one of these:

1. The first experiment shows the event-bounded contract no better than a
   fixed window across gains.
2. The lane-switch experiment shows targeted invalidation no better than a
   global flush.
3. Integration engineers, interviewed in Horizon 2, do not find
   configuration-change evidence reports useful.

Each of those would cut a part of the architecture. The first two cut I-14
and I-02. The third moves the first product surface. The plan says so in
advance.
