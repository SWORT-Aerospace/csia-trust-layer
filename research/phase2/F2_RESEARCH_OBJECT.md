# F2 — the assurance-accumulator delay question

**Status: FORMALISED, NOT ANSWERED. No claim of novelty is made.**
F2 is active independently of F3 and of the invention gate.

---

## 1. The question

> For assurance accumulators with banked healthy confidence, bounded local
> evidence, regime-dependent forgetting and thresholded escalation, can a
> detector guarantee an upper bound on fault response delay while maintaining
> a fixed nominal false-alert requirement?

The brief's instruction is followed in order: **formalise the class, search
for counterexamples, and only then attempt anything.** Nothing below is a
proof attempt.

---

## 2. The class, stated

An **assurance accumulator** is a tuple `A = (T_0, e, rho, M, T*, D)`:

| symbol | meaning | CSIA v1's instance |
|---|---|---|
| `T_0 ∈ (0,1]` | banked confidence at fault onset | up to 1.0 |
| `e_f ∈ [0,1]` | **bounded** local evidence available under the fault | 0.70 when only `phys` is destroyed |
| `rho: regime → [rho_min, rho_max]` | regime-dependent forgetting | 0.95 … 0.998 |
| `M = 1/(1 − rho)` | asymptotic belief mass at a given `rho` | 20 … 500 |
| `T* ∈ (0,1)` | escalation threshold | `nav_caution = 0.75` |
| `D ≥ 0` | dwell before escalation commits | 1.0 s = 25 ticks |

Update, verified exact against the shipping code in WP-C8:

```
S_{k+1} = rho·S_k + 1
T_N     = ( x·S_0·T_0 + (1−x)·M·e_f ) / ( x·S_0 + (1−x)·M ),   x = rho^N
```

Escalation occurs at the first `N` with `T_N < T*`, committed after `D`.

**Response delay** `N*(A) = min{ N : T_N < T* }`, and the escalation boundary
is `N* + D`. For CSIA v1 with calm-flight banking, WP-C8 measured
`N* = 93.31` ticks and a boundary of `118.31`.

**Nominal false-alert requirement.** `R(A) = 0` transitions on clean flight
(R10). Written as a constraint, not a weighted term.

**The question, formally.** Does there exist `A` with

```
sup over faults in a stated class of  N*(A)  <  infinity      (bounded delay)
        subject to                    R(A) = 0                (fixed budget)
```

and, if so, what is the achievable bound as a function of `(T_0, e_f, T*)`?

---

## 3. Three counterexamples, found before any proof attempt

These are searched for first, per the brief. Each is a case where **no bound
exists**, so any positive answer must exclude it by assumption.

**CX-1 — insufficient evidence margin.** If `e_f ≥ T*`, then `T_N → e_f ≥ T*`
and the threshold is **never crossed**: `N* = ∞` for any `rho`, `M`, `T_0`.
CSIA v1 sits at `e_f = 0.70` against `T* = 0.75`, a margin of **0.05**. WP-C3's
signature repair moved `e_f`; a repair that moved it 0.05 further would make
the delay unbounded, not merely long. **Any bounded-delay claim must assume
`e_f < T*` and its bound must diverge as `e_f → T*`.**

**CX-2 — unbounded banking.** `N*` grows with `S_0·(T_0 − T*)`, and `S_0` is
capped only by `1/(1 − rho_max)`. As `rho_max → 1`, `S_0 → ∞` and `N* → ∞`.
A bound therefore cannot be stated without a **cap on accumulated mass**,
which is precisely what candidate B3 proposes and what R10 is expected to
resist.

**CX-3 — the false-alert constraint is not free.** The zero-false-alert budget
is what motivates large `M`, since smoothing is what suppresses clean-flight
excursions. So `R(A) = 0` and `sup N* < ∞` pull on the same parameter in
opposite directions. **The interesting question is not whether a bound exists
— CX-2 shows it does once mass is capped — but whether any cap satisfies both
constraints simultaneously.** That is an empirical question about the
clean-flight residual distribution, not a theorem.

**CX-4 — the fault need not be persistent.** The whole formulation assumes the
fault holds long enough for `N` ticks to elapse. WP-C8's duration experiment
was degenerate for exactly this reason: held glitches capped below the 118-tick
boundary never crossed it. A "bounded delay" guarantee is vacuous against
faults shorter than the bound.

---

## 4. What this reframes

The three counterexamples say the honest form of F2 is **not** "can a bound be
proved". It is:

> Given a measured clean-flight residual distribution, does there exist a mass
> cap `S_max` such that `R = 0` holds and `N*(S_max)` is acceptable — and is
> the resulting `N*` better than what a classical sequential test achieves on
> the same data at the same false-alert rate?

That is a **measurement**, and it is exactly what candidates B3 (mass cap) and
B4 (CUSUM) are for. F2 does not need new mathematics before those are run; it
needs those run.

**Consequence for sequencing:** F2's computational generalisation is deferred
until B3 and B4 are measured, because CX-3 makes the answer depend on data
those experiments produce. This is not a deprioritisation of F2. It is F2's
own formalisation saying which experiment answers it.

---

## 5. What is NOT claimed

- No novelty. Sequential change detection with a false-alarm constraint is a
  classical problem; Page (1954) and the standard model-based FDI treatments
  cover the comparator. The specific accumulator above is CSIA's, and being
  specific is not being new.
- No theorem. Rule 9 forbids a theorem claim generated from simulation, and
  §3 is a set of counterexamples, which requires no simulation and proves
  nothing positive.
- No bound. None is stated, because CX-3 says any bound is conditional on a
  measurement not yet made.

---

## 6. Open, with owner

| item | owner | blocks |
|---|---|---|
| measure the clean-flight residual distribution on the modern rig | this session, alongside B2/B4 | the CX-3 question, hence all of F2 |
| B3: does any `S_max` satisfy `R = 0`? | this session | F2's positive direction |
| B4: what delay does a properly parameterised CUSUM achieve at the same false-alert rate? | this session | whether F2 has any headroom left to claim |
| the `e_f < T*` margin as a design constraint | not started | a design rule, if one survives |
