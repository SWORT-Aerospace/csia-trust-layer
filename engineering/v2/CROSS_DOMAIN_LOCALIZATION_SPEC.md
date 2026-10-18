# CROSS-DOMAIN CAUSAL LOCALIZATION

Phase C §§2–6, 13, 26–27, 32, 39. Implementation: `csia/v2/localization.py`,
`csia/v2/signatures.py`. Generated results: `LOCALIZATION_RESULTS.csv`,
`CROSS_DOMAIN_SIGNATURE_MATRIX.csv`, `EVIDENCE_SUBSET_RESULTS.csv`.

---

## 1. What this layer is for, and what it must never do

Six domain monitors produce six independent opinions. A symptom that several
of them can produce — a stale output, an unresponsive actuator — gets six
partial answers and no decision. This layer turns the six opinions into a
statement of the form:

> these four domains could have produced this symptom; this evidence rules
> out three of them by name; the fourth is what is left.

The prohibition is §2, and it is the whole design constraint:

> Do not emit CAUSE = X merely because X changed first or X correlates.

Two things follow, and everything in `localize()` exists to enforce them.

**A hypothesis that survives elimination is not a cause.** Survival means
nobody refuted it. `unresolved` is a separate field from `supported` and no
consumer may read the first as the second. A localization with one survivor
and nothing confirming it is `UNSUPPORTED`, not `SUPPORTED` — the difference
between "the only one left" and "the one the evidence points at".

**A confident answer must be earned by a discriminating measurement.**
`SUPPORTED` requires exactly one hypothesis confirmed and zero survivors
beside it. Anything else is `AMBIGUOUS`, and §39 says so directly: *don't
force unique localization*.

## 2. The four verdicts

| verdict | meaning |
|---|---|
| `SUPPORTED` | one hypothesis is confirmed and every rival is refuted by name |
| `AMBIGUOUS` | more than one explanation survives, whether or not any is confirmed |
| `UNSUPPORTED` | nothing modelled survives, or exactly one survives and nothing confirms it |
| `NO_EVIDENCE` | the symptom is present and no predicate about it is measurable |

`UNSUPPORTED` covering "everything was ruled out" is deliberate. That is a
finding about the **model**, not about the vehicle: the symptom is real and
no declared hypothesis explains it. Reinstating a hypothesis to avoid an
empty answer would be inventing a cause.

## 3. Three-valued predicates

A predicate returns `True`, `False`, or `None`, and `None` means **not
measurable on this platform at this tick**. It is not "probably fine".

```
    True   the observation holds
    False  the observation affirmatively does not hold
    None   nothing reported, or the platform has no such channel
```

`None` eliminates nothing and confirms nothing. This is the single most
load-bearing rule in the file: a two-valued predicate would silently turn
"I cannot see" into "it is not so", and a diagnostic system that does that
produces confident wrong answers rather than honest ambiguous ones.

The Phase C run exposed exactly that defect in the shared-dependency
predicates. `SHARED_ADVERSE_COMPUTE_DEPENDENCY` returned `False` when the
adverse sources declared no compute node at all, which made
`NO_SHARED_ADVERSE_DEPENDENCY` come back `True` and reported
`SENSOR/independent_faults` as `SUPPORTED` — on a scenario whose injected
cause was a saturated CPU the dependency model could not see. §5's
`_covered()` now decides whether the model has anything to say about a domain
before any of those predicates may answer; where it does not, they return
`None` and `dependency_model_blind_to` names the gap in the results CSV.

## 4. The elimination loop

For one symptom on one subject:

1. Evaluate every predicate any hypothesis references. Once, cached, so two
   hypotheses reading the same predicate cannot disagree about its value.
2. For each hypothesis: if any `refuted_by` predicate is `True`, it is
   **rejected**, and the rejecting predicate is recorded with it. There is no
   anonymous elimination — `rejected` is a list of `(hypothesis, predicate)`
   pairs and the operator can see what killed each one.
3. Otherwise, if it is confirmed (`any` of `confirmed_by` is `True`, or `all`
   of them when `confirm_requires_all` is set), it is **supported**.
4. Otherwise it is **unresolved**.
5. The verdict follows from the counts, per §2 above.

No arithmetic, no priors, no thresholds. §5 permits Bayes later and does not
require it now; nothing here would need to change to add a scoring layer on
top, because the elimination result is already the set that scoring would
have to operate over.

## 5. The signature matrix

`CROSS_DOMAIN_SIGNATURE_MATRIX.csv` is generated from the same hypothesis
declarations the runtime uses, so it cannot drift from behaviour. 54 rows over
9 symptoms:

| cell | rows |
|---|---|
| `CAN_EXPLAIN` | 22 |
| `CANNOT_EXPLAIN` | 28 |
| `DEPENDS` | 4 |

§4's rule is enforced by construction: **every `CAN_EXPLAIN` cell names a
mechanism and the confirming evidence**, and a generated check asserts none is
blank. A domain that "might be involved" without a stated mechanism is not
allowed into the matrix, because that is how a candidate set becomes a list of
everything.

## 6. Directionality (§§26–27)

Two asymmetries are modelled explicitly because collapsing them turns one
event into two faults:

**CPU overload → processing delay, never the reverse.** A saturated CPU can
explain a late process. A late process does not imply a saturated CPU — it may
be blocked, descheduled, or waiting on I/O. `COMPUTE/processing_delay` is
confirmed by the process's own budget, not by the host's load.

**Transport latency is COMMUNICATION; an end-to-end deadline is TIMING.**
`TIMING/deadline_violation` means the deadline was missed *with every segment
inside its own budget* — a composition fault in its own right. It is therefore
refuted by `NO_TIMING_SEGMENT_OVER_BUDGET_FALSE`: when a segment IS over
budget, the miss belongs to that segment's domain and counting it again here
would report one overrun as two independent faults.

`MS_D4_COMPUTE_DEADLINE` is the literal test. The nav channel misses its
end-to-end deadline because the estimator segment blows its budget; the result
is `COMPUTE/estimator_stale` supported and `TIMING/deadline_violation`
rejected, with `NO_TIMING_SEGMENT_OVER_BUDGET_FALSE` named as the rejecter.

## 7. Common cause (§13)

Two sensors failing together is one finding when they share an adverse node
and two findings when they do not. `_shared_adverse_dependency()` walks the
profile's declared dependency graph — direct dependencies and one level up,
so a rail feeding a converter feeding two sources is still found — and
requires the shared node to be **itself adverse**. A healthy shared
dependency is not a common cause; it is a shared dependency.

Downstream symptoms are never counted as independent causes. Records derived
from other records carry `attributable=False` and cannot enter a candidate
set at all.

## 8. Minimum resolving evidence (§6)

`minimum_resolving_subsets()` answers "what would it have taken?" by
exhaustive enumeration over subsets of the **measurable** predicates, up to
size 6. Unmeasurable predicates are excluded from the enumeration: a subset
containing one would appear to resolve something that was actually resolved by
the predicates around it.

Measured, from `EVIDENCE_SUBSET_RESULTS.csv`:

| scenario | measurable | minimum subset | verdict |
|---|---|---|---|
| `MS_A1_SENSOR_DELAY` | 11 | 5 | SUPPORTED |
| `MS_A4_PROCESS_STALL` | 11 | 4 | SUPPORTED |
| `MS_B4_MECHANICAL` (aircraft) | 9 | 4 | AMBIGUOUS |
| `MS_TS_B5_RESPONSE_SENSOR` (bench) | 11 | 4 | SUPPORTED |
| `MS_C4_CPU_SATURATED_NOT_SHARED` | 2 | 1 | AMBIGUOUS |
| `MS_D1_NAV_SOURCE` | 9 | 4 | SUPPORTED |

The C rows are the interesting ones: only two predicates are measurable at
all, because the dependency model is blind to COMMUNICATION and COMPUTE
sharing for that source pair. The subset enumerator reports what the platform
can actually resolve, not what the hypothesis list would like it to.

## 9. Structured output (§32)

`Localization.to_dict()` is the canonical form; `render()` is one line of
prose and is explicitly not canonical. Every field is machine-readable:

```json
{
  "symptom": "OUTPUT_STALE",
  "subject": "nav_solution",
  "verdict": "SUPPORTED",
  "initial_domains": ["COMMUNICATION", "COMPUTE", "SENSOR", "TIMING"],
  "supported": ["COMMUNICATION/transport_delay"],
  "rejected": [
    ["COMPUTE/process_stall", "PRODUCER_PROCESS_HEALTHY"],
    ["COMPUTE/processing_delay", "PROCESSING_WITHIN_BUDGET"],
    ["SENSOR/source_slow", "SOURCE_INTERVAL_NOMINAL"],
    ["TIMING/clock_inconsistent", "CLOCK_CONSISTENT"]
  ],
  "unresolved": [],
  "unmeasurable": [],
  "evidence": ["CLOCK_CONSISTENT", "PROCESSING_WITHIN_BUDGET",
               "PRODUCER_PROCESS_HEALTHY", "SOURCE_INTERVAL_NOMINAL",
               "TRANSPORT_WITHIN_BUDGET_FALSE"]
}
```

## 10. Determinism

`localize()` takes `(spec, index, subject, predicates)` and nothing else — a
test asserts that signature by parsing the AST, so no future edit can pass the
scenario in. The evidence index is order-independent, predicates are pure
functions of the index, and no clock is read anywhere on the decision path.
Two runs of the same trace produce identical localizations, and the ledger
replays bit for bit.

## 11. Known limits

- **The dependency model is the ceiling on common-cause reasoning.** Where a
  component declares no dependency in a domain, §13 cannot reach a shared
  cause there and now says so rather than guessing. On the multirotor this
  means shared-link and shared-compute causes are unreachable for the
  `battery`/`motor_esc` pair. Fixing that is a profile change — declaring the
  real dependencies — not a framework change.
- **Hypothesis granularity is fixed by the declarations.** `COMPUTE/
  estimator_stale` covers both "stopped" and "over budget", which is why
  `MS_D2` and `MS_D4` land on the same answer. Splitting them would require
  evidence that separates them, which this platform does not produce.
- **No probability is attached to an ambiguous set.** Ranking the survivors
  would require priors nobody has measured. §5 does not require it and none is
  invented.
