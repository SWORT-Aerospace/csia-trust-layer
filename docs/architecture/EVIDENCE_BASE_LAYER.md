# The evidence-base layer

`csia_evidence/` answers three questions about THE EVIDENCE rather than about
the vehicle. CSIA could not previously ask any of them, and each gap showed
up the moment it met data it did not design.

**Status: research, outside the frozen core, promotes nothing.** No module
here imports a frozen path, and a test asserts it.

## Why these three together

They share one rule, stated in the package docstring and asserted by a test:

> **Nothing in this package promotes anything.**

Each module returns a record. A human or an explicit policy decides. That is
the same discipline `csia_supervision/capability_bridge.py` follows one layer
down, where an overlay may only withdraw support and UNKNOWN never becomes a
firm negative.

## 1. `ingestion` — recognise channels, and say how you know

CSIA's answer to an undeclared channel was `NOT_EVALUABLE`. Safe, and against
real data useless: a layer that refuses everything it was not handed a
specification for cannot be pointed at anything new.

Recognition now reports itself. Seven evidence kinds, ordered:

| kind | meaning |
|---|---|
| `DECLARED` | an interface document says so; no inference |
| `NAME_EXACT` | the normalised field name equals the canonical name or an alias |
| `UNIT_MATCH` | the source's declared unit matches |
| `NAME_FUZZY` | every token of a canonical name appears in the field name |
| `RELATIONAL` | the series satisfies a declared relation with a placed channel |
| `DIMENSIONAL` | the values sit inside the channel's declared plausible range |
| `UNRECOGNISED` | nothing matched |

**No number is attached to any of these**, because there is no calibrated
population from which one could be computed. Inventing 0.85 for `NAME_FUZZY`
is exactly the kind of number this repository exists to refuse. The order is
ordinal and it is the whole of what is claimed.

Three properties do the real work:

- **Only `DECLARED` and `NAME_EXACT` are usable without review.** Everything
  else is offered, not used.
- **Conflicts are first class.** When the name says one thing and the unit
  says another, that disagreement is the finding. A conflicted mapping is
  never usable whatever its best grade, because the conflict is evidence
  that the strong grade is wrong.
- **Dimensional agreement cannot identify a field.** It corroborates and it
  conflicts; it never places. Plausibility is a weak negative test: it can
  tell you a field named like a current holds values no current takes, and
  it cannot tell you an unnamed field is a current.

## 2. `intent` — what it was told, what it did, what deviating cost

CSIA reasons about whether a component is healthy. It had no representation
of tasking at all, so it could not tell a fault from a deliberate change of
plan. Those look identical in telemetry and mean opposite things.

The pattern already existed one layer down: `csia/prediction/comparator.py`
scores observed sensor behaviour against physics, history and neighbours.
This is the same comparison applied to intent.

**The part that is not obvious is the reason to build it.** A deviation is
not only a fact about the mission. It changes which evidence is admissible.
Half of CSIA's relations are gated on an operating condition: an effort
check needs a stationary setpoint, an impedance check needs a varying load, a
heading-versus-course check needs the vehicle to be translating. When the
system stops doing what it was told, those gates move.

A debrief that says "it deviated at t=340" and stops has discarded the more
useful half: *and for the next 90 seconds these relations could not run, so
the diagnosis over that window rests on two channels rather than six.*
`CommitmentOutcome.relations_suspended` is that half.

Four outcomes, and `NOT_EVALUABLE` is deliberately distinct from `HELD`. A
commitment whose channel is absent from the record is not a commitment that
was met.

**It does not judge.** A system that abandons a commitment to avoid a hazard
has done the right thing, and a layer that scored that as a failure would be
actively harmful. A test asserts the outcome record carries no field named
`correct`, `failure`, `score`, `penalty` or `blame`.

## 3. `corpus` — twenty runs on one airframe is one airframe

CSIA analyses a run. Anything accumulating across runs has to answer a
question it had no machinery for: **how much independent evidence is there,
actually?**

This is the lineage rule lifted one level. `csia_active_evidence/signatures.py`
refuses to let three residuals reading the same raw current count as three
pieces of evidence. The same argument applies to runs: two runs sharing an
airframe are two views of one airframe.

A run declares its factors. The effective sample size for a factor is the
number of **distinct values**, never the number of runs. When a claim depends
on several factors, the honest figure is the smallest of those counts,
because that is the one that runs out first:

```
n_effective = min over relevant factors of |distinct values|
```

`accumulate` **will not report a rate at an effective n of one.** The naive
rate is still returned, so nothing is hidden, but it is labelled as an
observation about a single article. A zero-failures-in-500-runs result on one
airframe is a claim about one airframe, and presenting it as a fleet figure
is how a number becomes a lie without anyone writing a false statement.

## What none of this establishes

- **`ingestion`** does not establish that any field is the channel it
  resembles, only what evidence was found and what was not.
- **`intent`** does not establish that a deviation was wrong.
- **`corpus`** gives an **upper bound** on the independence available. Runs
  sharing no declared factor value may still share something nobody declared.

## Where it came from

The three gaps were identified by reading a demanding external requirements
document as a specification for an evidence layer. The requirements named, in
operational language, several properties CSIA already had and three it
lacked. Nothing domain-specific from that document is implemented here, and
nothing in `csia_evidence/` knows what an aircraft is.
