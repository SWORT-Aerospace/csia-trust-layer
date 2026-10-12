# COUNTEREXAMPLES TO THE MENGER CLAIM

Item 8. The frontier report (`research/frontier_selection/`, commit `65fa17e`)
proposed approximately:

> κ = 1 ⇒ the consistency residual has zero power against a fault at the cut
> vertex.

Item 8 says this is too broad until proved, and asks for the smallest
counterexample. **It is too broad. Two counterexamples follow, in opposite
directions, and together they refute the claim as stated.**

---

## 1. COUNTEREXAMPLE A — SHARED SOURCE, RESIDUAL STILL SENSITIVE

**Setup.** One shared upstream variable *c*. Two channels:

    y₁ = f₁(c)
    y₂ = f₂(c)

κ_prov = 1: every path from the sensing frontier to {y₁, y₂} passes through
*c*. A fault is a perturbation *δ* applied at *c*.

**Residual.** r = y₁ − y₂ = f₁(c) − f₂(c).

**Sensitivity.**

    ∂r/∂δ = f₁′(c) − f₂′(c)

which is **non-zero whenever f₁′ ≠ f₂′**.

**A shared source therefore does not imply a blind residual.** The claim as
written is false.

### 1.1 Concrete instance from the audited stack

From `RUNTIME_TOPOLOGY_SOURCE_AUDIT.md` §4, state N1: `vibration.rms` and
`imu1.accel` both derive from `accel1`. But they are different functions of it:

- `imu1.accel` is the low-passed accelerometer vector, published in engineering
  units by `send_scaled_imu`;
- `vibration.rms` is a high-passed magnitude statistic —
  `AP_InertialSensor::get_vibration_levels()`, an accumulated variance-like
  quantity, not the raw sample.

f₁ (low-pass, signed, vector) and f₂ (high-pass, magnitude, scalar) have
manifestly different derivatives. A **step bias** injected at `accel1` moves
`imu1.accel` and leaves `vibration.rms` nearly unchanged, because a constant
offset is exactly what the high-pass rejects. So the residual between them is
**sensitive** to a step bias at the shared vertex, not blind to it.

Conversely a **broadband noise** fault at `accel1` moves `vibration.rms`
strongly and `imu1.accel` weakly.

So even in the very example that motivates the candidate, κ_prov = 1 does not
imply diagnostic blindness. It implies blindness *only for the specific fault
signatures that both transforms treat identically* — and which those are is a
property of f₁ and f₂, not of the graph.

---

## 2. THE EXACT CONDITION UNDER WHICH BLINDNESS DOES FOLLOW

Blindness requires **residual invariance at the cut vertex**, not graph
separation:

> Let R be the residual map and *c* the cut vertex. The residual is blind to
> perturbations at *c* iff
>
>     ∂R/∂c = 0  (or, without differentiability, R(c+δ) = R(c) for the
>                 admissible perturbation set)

This is the condition the frontier report should have stated. Note what it
needs: **the functional forms f₁, f₂ and the residual algebra.** The graph does
not supply them.

The special case in which graph separation alone is sufficient is narrow:

> **Sufficient special case.** If κ_prov = 1 with cut vertex *c*, **and** the
> residual is of the form R = y₁ − g(y₂) **with** g ∘ f₂ = f₁ identically on
> the perturbation range, then R is invariant to any perturbation at *c*.

That is the "the residual re-derives one channel from the other" case — an
algebraic tautology rather than a physical cross-check. It is real (it is what
happens when a monitor compares a quantity against a recomputation of itself),
but it is a much smaller class than "κ = 1".

**The honest statement is therefore conditional, and the condition is about
functions, not topology.** As item 9 anticipated, the statement in its correct
form is close to tautological; the research question would have to be whether
graph structure can *certify* such invariance without already possessing the
complete functional model. Counterexample A shows it cannot in general.

---

## 3. COUNTEREXAMPLE B — DISTINCT SOURCES, RESIDUAL STILL BLIND

The converse failure, which is the more damaging one.

**Setup.** Two transducers with no shared software node: accel0 and accel1 on
one airframe, κ_prov = 2 by construction. A structural resonance, a thermal
transient, or a common mounting deflection perturbs both **identically**:

    y₁ = h(a) + ε
    y₂ = h(a) + ε        (same ε, from the shared physical environment)

**Residual.** r = y₁ − y₂ = 0 regardless of ε. The residual is **blind** to the
common-mode disturbance even though κ_prov = 2.

There is no software-provenance edge to draw here. The coupling is physical and
lies entirely outside the graph the audit's extraction rules (§1 of the audit)
are able to build.

The same argument applies to shared clocks, shared calibration procedures and
shared power rails — all three of which the audit explicitly excluded.

---

## 4. CONSEQUENCE FOR κ_prov — ITEM 11'S NULL IS CORRECT

Item 11 states the hostile null:

> **H_KILL_PROVENANCE:** A source-provenance graph alone cannot determine
> diagnostic information diversity, because two paths from the same source can
> encode distinct physical constraints, while two paths from different nominal
> sources can be perfectly dependent.

**Counterexample A proves the first clause. Counterexample B proves the
second. The null holds in both directions.**

Item 11's instruction follows directly:

> If this null is correct: κ_prov is **NOT sufficient** as the central
> quantity. Do not rescue it by redefining it after seeing the result.

**Accepted. κ_prov is not sufficient as the central quantity, and it is not
redefined here to make it sufficient.** It is at most a cheap *screening*
signal — a necessary-condition heuristic for one of the two failure modes, with
known false negatives (B) and known false positives (A).

This is recorded as claim `E4` in `CLAIM_LEDGER.json` with status `REFUTED`
against the frontier report's formulation.

---

## 5. WHAT THIS DOES NOT REFUTE

Precision matters here, so that nothing is over-claimed in either direction.

- It does **not** refute that diagnostic sensitivity can change at runtime. It
  refutes that **κ_prov measures it**.
- It does **not** refute the audited finding that ArduPilot's `VIBRATION`
  provenance changes in flight without announcement. That stands on its cited
  lines.
- It does **not** establish that anyone else has published the correct
  conditional statement in §2. That is a prior-art question, and the prior-art
  gate for this stage returned `INCONCLUSIVE_MISSING_FULLTEXT`
  (`REQUIRED_READING_MANIFEST.md`).
