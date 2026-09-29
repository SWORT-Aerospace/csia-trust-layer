# Exception semantics audit (Part 9)

CSIA semantic correctness audit, 2026-09-29. Result ids refer to
`semantic_probe_results.json`. Literature ids are defined in `SOURCES.md`.

## 1. Answer

**Reproduced.** A predicate that raises becomes "not measurable":

- **Where.** `Predicate.__call__`, localization.py:136-140.
- **What it does.** `except Exception: return None`.
- **Consequence.** A software defect in a predicate is indistinguishable, in
  every output, from evidence that was not available.
- **And it changes conclusions.**
  - On the 44 shipped final ticks, making a predicate raise changed a
    decision for **19 of the 26** base predicates: 187 decision changes in
    total.
  - **9** of those changes *created* a SUPPORTED verdict (P5).
  - In no case did the failure appear anywhere in the output.

`csia/v2` imports no logging facility and emits no warning. **Nothing is
logged.**

**Two further silent paths exist:**

1. A predicate that returns something other than `True`, `False` or `None` is
   silently treated as not True. It is also **not** listed as unmeasurable
   (R10).
2. Malformed records are swallowed by predicates but crash attribution. The
   same fault therefore fails silently in one stage and loudly in the other
   (R11, R15).

## 2. The brief's cases

The spec for R9 and R10 has two hypotheses, both confirmed by P (True): h1 is
refuted by Q and h2 by R. The shipped-corpus figures come from P5, which
injects `RuntimeError` into one predicate at a time on all 44 final ticks.

| case | current result | logged? | observable downstream? | decision changes? | can a defect masquerade as unavailable evidence? |
|---|---|---|---|---|---|
| predicate returns **False** | measured false; neither refutes nor confirms through that id; its `_FALSE` twin is True | no need | yes: in `predicate_values` | only as evidence should | — |
| predicate returns **True** | measured true | — | yes: in `evidence` | as evidence should | — |
| predicate returns **None** | "not measurable"; listed in `unmeasurable` | — | yes: in `unmeasurable` | eliminates nothing, by design | — |
| predicate raises an **expected** exception, e.g. `KeyError` on a missing lookup key | None; listed in `unmeasurable` | **no** | **no**: identical to a None return | **yes**: R9B, P5 | **yes** |
| predicate raises an **unexpected** exception, e.g. `ZeroDivisionError` | None; listed in `unmeasurable` | **no** | **no** | **yes** | **yes** |
| **missing input**: the record the predicate needs is absent | None via `_nominal` for single records. **Not** None for aggregates or shared nodes (`MISSING_EVIDENCE_AUDIT.md`) | — | yes, where None | as intended for single records; wrong for aggregates | — |
| **malformed input**: `reason_codes=None` | the `in None` TypeError is caught, so None. **11 predicates** silently unmeasurable (R11A) | **no** | **no** | yes: every COMMAND_NO_RESPONSE hypothesis becomes unresolved | **yes** |
| **malformed input**: `dependencies=None` | `attribute()` **raises** → the tick fails (R11B). Predicates that read dependencies would reach the same TypeError, and the catch-all would turn it into None. This follows from localization.py:139; it is not a separately recorded probe case | the exception propagates | yes, as a crash | the tick is lost | no: loud in attribution, silent in predicates |
| predicate returns `numpy.True_`, `1`, `"yes"` or `nan` | `values.get(pid) is True` is False, so it is neither True nor unmeasurable (R10) | **no** | only in `detail.predicate_values` | **yes**: `numpy.True_` should have refuted h1. Result AMBIGUOUS instead of SUPPORTED h2 | **yes**: worse, it looks like a **measured** False |
| hypothesis names a **predicate id not in the table** | `KeyError` propagates; the tick fails (R15A) | exception | yes | tick lost | no |
| a **symptom detector** raises | propagates; the tick fails (R15B) | exception | yes | tick lost | no |

## 3. R9B: an exception can create a SUPPORTED cause

| Q (refutes h1) | R (refutes h2) | verdict |
|---|---|---|
| True | True | UNSUPPORTED: every declared explanation ruled out |
| **raises** | True | **SUPPORTED h1** |

A working refuter would have eliminated h1. When the refuter crashes, h1 is
named the cause, and the only trace is `Q` appearing in `unmeasurable`.

**On shipped data** (P5), all 9 exception-created SUPPORTED verdicts come from
one predicate, NO_TIMING_SEGMENT_OVER_BUDGET.

- **What that predicate does.** It is the §27 guard that refutes
  TIMING/deadline_violation when a timing segment is already over its own
  budget. It exists so that "one overrun is not counted as two independent
  faults" (signatures.py:683-689).
- **What happens when it raises.** The guard silently disappears, and the
  double-counted cause is reported as SUPPORTED.

**Per-predicate effect of an injected exception** (P5, decision changes over
the corpus):

| predicate | decision changes | of which created SUPPORTED |
|---|---|---|
| V1_1_FUNCTION_ELIGIBLE | 16 | 0 |
| ESTIMATOR_PROCESS_HEALTHY | 16 | 0 |
| FUNCTION_LINKS_NOMINAL | 16 | 0 |
| ACTUATOR_POWER_NOMINAL | 12 | 0 |
| COMMAND_DELIVERED | 12 | 0 |
| CLOCK_CONSISTENT | 11 | 0 |
| STALL_SIGNATURE | 11 | 0 |
| CURRENT_PRESENT | 10 | 0 |
| PROCESSING_WITHIN_BUDGET | 10 | 0 |
| PROCESS_ALIVE_AND_PRODUCING | 10 | 0 |
| SOURCE_INTERVAL_NOMINAL | 10 | 0 |
| PRODUCER_PROCESS_HEALTHY | 9 | 0 |
| TRANSPORT_WITHIN_BUDGET | 9 | 0 |
| FUNCTION_TIMING_WITHIN_DEADLINE | 8 | 0 |
| NO_TIMING_SEGMENT_OVER_BUDGET | 8 | **9** |
| CPU_HEADROOM_NOMINAL | 7 | 0 |
| PHYSICAL_RESPONSE_NOMINAL | 5 | 0 |
| SHARED_ADVERSE_POWER_DEPENDENCY | 5 | 0 |
| CHANNEL_LINK_NOMINAL | 2 | 0 |

The SUPPORTED column can exceed the change column. That happens when one
changed tick gains several SUPPORTED localizations, one per navigation
function.

## 4. Why v2 chose this, and where the choice goes wrong

The design reason is stated in the code: "a predicate that cannot look is not
a predicate that saw 'no'" (localization.py:139-140). Mapping an exception to
None is **fail-safe for elimination**. An exception can never *refute*
anything. That half of the reasoning is sound.

**The defect is that "cannot look" and "is broken" share one value.** This is
the error-hiding pattern that empirical studies of exception handling single
out: catching an exception and doing nothing informative with it (L09). Two
consequences follow:

1. **An exception is never distinguishable from absent evidence.** A
   permanently broken predicate looks, forever, like a platform that does
   not instrument that stage. Nobody is prompted to fix it.
2. **Removing a refuter is not neutral.** Set elimination is monotone in
   information, as N1 shows. Losing a refutation can therefore raise
   certainty:
   - "all rejected" becomes SUPPORTED (R9B);
   - AMBIGUOUS becomes SUPPORTED, when the lost refuter belonged to a
     hypothesis whose confirmer is also true.

**Within the repository the right pattern already exists.** The assurance
firewall's exception barrier produces `NOT_EVALUABLE` with the exception
named, and it never produces a positive verdict (`csia_assurance/firewall.py`,
`FIREWALL_INTERNAL_EXCEPTION`).

## 5. Uniformity across stages

The same kind of fault gets opposite treatment by stage:

| stage | a fault becomes |
|---|---|
| domain plugin | a named, attributed UNAVAILABLE record plus a ledger event |
| predicate | a silent None |
| detector, attribution, predicate table lookup | an exception that fails the whole tick, so every output of that tick is lost |

`EvidenceRecord.__post_init__` (evidence.py:105-111) validates:

- the two enum fields;
- the three required strings.

It does **not** validate that `reason_codes`, `dependencies` and
`affected_functions` are tuples. A producer can therefore construct a record
that some stages swallow and others crash on.

## 6. What the correction must and must not do (`MINIMAL_CORRECTION_DESIGN.md`, C4)

- **Keep** the fail-safe elimination rule: a raising predicate eliminates
  nothing.
- **Add** a distinct reported state: `predicate_errors`, listing the
  predicate, the subject and the exception class. Non-bool returns are
  reported the same way, as `NON_BOOL:<type>`.
- **Do not** turn a predicate error into a verdict change on its own.
  - The shadow implements exactly this.
  - On the corpus it changes **no** decision (C4: 0 of 2,640 ticks). That is
    expected: shipped predicates never raise.
  - On P5's injected faults, it reports the fault in every evaluated tick.
    That is 259 predicate-tick evaluations over the 26 predicates
    (P5.per_predicate).

**Decision about SUPPORTED over an errored predicate: left to governance.**
The option is whether SUPPORTED should be withheld when an errored predicate
was one of the refuters of the supported hypothesis. It is **not** in the
minimal set, because it changes verdicts on inputs that frozen v2 never
recorded.

## 7. XSYS-001

Replay of all 3,872 sealed Stage-1 localization slots, calling each XSYS
predicate's raw test with no catch:

- **0** exceptions;
- **0** non-bool returns (X.predicate_raises, X.predicate_non_bool_returns).

The catch-all never fired in XSYS-001. Correcting the exception semantics
cannot change it.
