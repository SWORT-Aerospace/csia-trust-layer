# Semantic portability contract

**What must be identical across supported hosts, what may vary, and by how
much.** The four levels are defined separately and **may not be conflated**:
an implementation that meets DECISION EQUIVALENCE while failing NUMERICAL
EQUIVALENCE is behaving correctly, and reporting that as a failure would push
the next author toward pinning floating-point bits that the platform does not
guarantee.

---

## Level 1 — DECISION EQUIVALENCE  *(EXACT, no tolerance)*

For the same canonical input record, on every supported host:

* the **assurance firewall verdict** — one of `SUPPORTED_UNIQUE`,
  `AMBIGUOUS`, `NON_IDENTIFIABLE`, `NOT_EVALUABLE`, `UNKNOWN` — must be
  **identical**;
* the **reason string** must be identical;
* the **set of competitors without a witness** must be identical;
* the **set of active discriminators per competitor** must be identical.

**No tolerance applies at this level, ever.** These are set-valued and
categorical; a "close" verdict is a different verdict. This is the level the
whole exercise is for: *equivalent justified evidence must produce equivalent
qualified assurance*.

## Level 2 — STRUCTURAL SUPPORT EQUIVALENCE  *(EXACT)*

`D(a,b)` for every pair, the equivalence classes, and each hypothesis's
classification must be identical. This is set arithmetic over booleans; it has
no floating-point content and therefore no licence to vary.

**If Level 2 differs between hosts, Level 1 will too, and the cause is a
defect, not a platform difference.**

## Level 3 — NUMERICAL EQUIVALENCE  *(DECLARED TOLERANCE)*

Continuous quantities the frozen core computes — trust coefficients, evidence
sums, hypothesis weights.

| comparison | requirement |
|---|---|
| same host, same input, repeated | **bit-identical**. A difference here is non-determinism and is a defect |
| different host, same architecture, same interpreter | **bit-identical expected**; any difference is reported, not tolerated silently |
| different architecture (x86_64 vs ARM64) | **relative difference ≤ 1e-12** on each reported scalar |

**1e-12 is not a threshold on the science.** It is a statement about IEEE-754
double arithmetic under different compilers and libm implementations, and it is
declared here **before** any cross-architecture measurement exists, so it
cannot be widened to fit a result. **If a measured deviation exceeds it, that is
a finding and the contract is what makes it one.**

## Level 4 — TIMING EQUIVALENCE  *(PLATFORM-SPECIFIC BOUNDS, NOT EQUIVALENCE)*

**There is no timing equivalence requirement and there must not be one.**
Latency depends on CPU, scheduler, contention and thermal state. What is
required instead:

* every host declares its own **normal / degraded / unsupported** envelope
  (`A15`);
* an envelope is measured on that host, never inherited from another;
* **a timing figure is never compared across hosts** as evidence of anything
  about CSIA.

---

## The failure mode this contract exists to prevent

> **A host outside the declared contract must produce `NOT_EVALUABLE` — never
> a confident verdict computed under conditions the contract does not cover.**

Silent divergence is worse than loud degradation. A host that quietly returns
`SUPPORTED_UNIQUE` with different numbers underneath has produced an
unsupported assurance, which is the exact defect the whole programme is about.

## Supported hosts

Declared in `docs/OPTIPLEX_VALIDATION_NODE.md` and measured by
`tools/assurance/portability_probe.py`. **A host with no recorded measurement
is not "probably fine": it is UNDECLARED, and the contract says nothing about
it.**
