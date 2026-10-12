# Top five next implementations

**2026-09-30. Part 53 of the shadow-validation brief.** The ranking is derived
from this phase's results. FORGE is not on it: the evidence foundation is not
ready (`PROMOTION_REVIEW.md`).

**Scores are 1 (low) to 5 (high).** For implementation cost and runtime cost,
5 means cheap.

| rank | item | safety value | engineering value | customer value | generality | implementation cost | runtime cost | testability | reuse of existing methods | the result that motivates it |
|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **Adopt predicate-fault policy B in 2.1** (a governed semantic revision: withhold SUPPORTED over a failed refuter; tick invalid only on a structural fault) | 5 | 4 | 3 | 5 | 5 (a bitmask check; the reference implementation exists) | 5 | 5 (dataset D and the pinned test) | 4 (dependency-sensitive fault handling) | 168 fault-created wrong SUPPORTED under 2.1 today → 0, for 42 correct SUPPORTED lost (`PREDICATE_FAULT_POLICY.md`) |
| **2** | **Configuration-epoch invalidation**: the smallest admissibility piece. Records derived from a configuration carry its epoch; producers declare invalidating events and a maximum content age | 5 | 5 | 4 | 5 | 3 | 5 | 5 (E1, and design B once authorized) | 5 (PX4 already publishes the epochs: `instance_changed_count`, reset counters) | E1: 9 ticks of SUPPORTED false symptom after a lane switch → 0, with 0 valid records discarded; a fixed window failed both ways (`CONFIGURATION_TRANSITION_STUDY.md`) |
| **3** | **Starvation scoped to pacing inputs**: refute COMMUNICATION/input_starvation from the subject's declared pacing inputs or direct input links, not its closure; then accept R5a in successor profile r2 | 4 | 4 | 3 | 4 | 4 | 5 | 5 (W7 counterfactual; the 81 PROCESS_STALL and MS_D2 ticks) | 3 | latent defect L17: any correct G-2 completion restores v2.0's wrong reason; unblocks G-2 and two of the five ARTIFICIAL abstentions (`G2_ESTIMATOR_INPUT_AUDIT.md`) |
| **4** | **Minimum producer contract, lineage and health**, with PX4 EKF2 status as the first producer through an adapter | 5 | 5 | 5 | 5 | 2 | 4 | 4 | 5 (EKF2 innovation checks, the existing CUSUM) | L1 and L12: false corroboration from one source, removed by lineage disjointness without losing independent evidence (`DEPENDENCY_METADATA_PREVIEW.md`); stale and faulted producers; the evidence the H743 path needs |
| **5** | **Profile identity and the validator as a load-time gate**, plus a design-time isolability check of the signature matrix | 3 | 5 | 4 | 5 | 5 (the validator exists; this wires it and the digest into engine load) | 5 (build time only) | 5 (a failing profile per rule) | 4 (structural isolability tooling) | 9 of 10 profile mutations caught; real warnings in all three shipped profiles; MS_B4 and MS_B5 not separable on the multirotor, knowable before any run (`PROFILE_VALIDATOR_SPEC.md`) |

## Why this order

- **Items 1 and 3 are small, local revisions of 2.1.** Each removes a
  measured or constructible confidently-wrong answer. They are what
  `PROMOTION_REVIEW.md` counts as "requires revision".
- **Item 2 is the largest safety gain against the least new machinery.**
  PX4 already reports the configuration facts it needs.
- **Item 4 is the most valuable and the most work.** It is ranked after 2
  only because 2 can be built on today's records, while 4 needs an adapter.
- **Item 5 is cheap and mostly done.** It is ranked last because its safety
  value is indirect: it prevents mistakes rather than correcting answers.

## Considered and not in the top five

| item | why not now |
|---|---|
| signature refuters for the ARTIFICIAL abstentions (current absent refutes a lying RPM sensor; the producer's deadline refutes processing delay; GPS freshness refutes a slow source) | usefulness, not safety. Each needs its own shadow counterfactual. Next after the top five |
| the C port | the evidence adapters come first (`C_RUNTIME_DELTA.md` §4) |
| state-conditioned validity from estimated signals | XSYS-001 shows it can be worse than a fixed rule (`XSYS_STATE_CONDITIONED_EXPLORATION.md`) |
| function-table successor (G-3) | an owner decision about the frozen table; the residual is 252 contradictions confined to two link-starvation scenarios |
| FORGE | not until 1-4 exist |
