# Mechanism matching specification

Items 6, 7, 10. The causal question is: *given the same operational
conclusion `A = 0`, can the architecture still say why?* Any difference in the
`A` trajectory between the two mechanisms is therefore a confound, not a
result.

## The two mechanisms

**`C_SENSOR` — receiver reports no fix.** GNSS messages continue to arrive at
the nominal rate; every one carries `fix_type < 3`. The receiver is talking and
saying it has no solution.

**`C_TRANSPORT` — healthy receiver, no delivery.** No GNSS message reaches the
consumer after onset. The receiver's health is unknown because nothing is
being said.

Both run on the same platform, the same adapter, the same consumer path, and
the same non-GNSS carrier. The *only* difference is whether the messages that
would have carried the no-fix report are delivered.

## Why the trajectories do not match naturally

Measured on development traces (`results/DESIGN_FEASIBILITY.json`):

| Arm | `A` mismatches over the whole condition | mismatch window |
|---|---|---|
| S0 reference (drop) | **0** | — |
| every propagating arm | **8 ticks** | `[12.00, 12.28]` |

Under propagating semantics an invalid sample is emitted, so `slot.valid`
becomes `False` and `A` closes **immediately** at onset. Under transport loss
nothing is emitted, so `A` closes only after `STALE_TIMEOUT_S["gps"] = 0.5 s`
has elapsed since the last accepted sample. The mismatch is exactly the onset
transient, and it is bounded by `τ`.

*(Under the drop reference the two are already bit-identical — which is the
invalidity-masking result restated.)*

## The scored interval

```
scored interval = [ onset + tau + margin ,  end_of_condition - tau - margin ]

tau    = STALE_TIMEOUT_S["gps"] = 0.5 s
margin = 0.2 s
```

The leading exclusion removes the onset transient. The trailing exclusion
removes the symmetric recovery transient, which the development conditions
never exercised because they ran to the end of the recording but which finite
confirmatory conditions will.

**Verified on development traces:** with `margin = 0.2 s`, `A` mismatches in
the scored interval = **0 of 857 ticks** on every arm, and `A == 0` throughout
for both mechanisms.

## Matching tolerance, preregistered

Exact matching is achievable and is therefore required, not approximated:

> **A trial pair is admissible only if `A_SENSOR(t) == A_TRANSPORT(t)` at
> every tick of the scored interval, and `A == 0` at every such tick.**
>
> Tolerance: **zero mismatched ticks.** A pair that fails is excluded from
> scoring and the exclusion is reported with its cause. If more than 2 of 10
> pairs are excluded, the campaign stops and the matching design is
> reconsidered rather than the tolerance loosened.

## Evidence that matching held

Per trial pair, recorded before any endpoint is computed:

* `A_trace_sha256` for each mechanism — the SHA-256 of the tuple
  `((t, A) for t in scored_interval)`. **The two hashes must be equal.**
* the scored interval bounds and tick count;
* the number of mismatched ticks over the whole condition, for the record.

Equal hashes are the admissibility gate. They are cheap, exact, and leave
nothing to judgement.

## Onset alignment

Both mechanisms in a pair use the **same onset time**, drawn from the
preregistered nuisance schedule. They are not independently randomised: the
pair is the unit, and pairing is what makes the comparison causal.

## What is deliberately not matched

The **raw observation stream** differs — that is the manipulation. `C_SENSOR`
delivers messages carrying `fix_type < 3`; `C_TRANSPORT` delivers none. Any
architecture that could not tell these apart from the raw stream would be
failing at a lower level than this experiment probes.
