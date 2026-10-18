# STAGE-0 EXPERIMENTAL DESIGN — CANDIDATE B

Item 34. Complete design. **Not executed.** Item 36 forbids implementation in
this stage and nothing here has been run: no detector was written, no CSIA file
was touched, no threshold changed, no scored data generated.

---

## 0. GATE — BEFORE ANY OF THIS RUNS

Stage 0 does not begin with an experiment. It begins with the reading that this
environment could not do. See `SELECTED_CANDIDATE_STAGE0_PROMPT.md` §1. If the
gate fails, the correct output of Stage 0 is a recorded kill and nothing else.

---

## 1. EXACT HYPOTHESIS

**H1.** On a real autopilot stack (ArduPilot and PX4, consumed by the frozen
CSIA v1 pipeline), there exists at least one monitored verdict *v* and at least
one tick *t* such that the effective independence κ_t(v) — the minimum upstream
vertex cut of *v*'s source-derived evidence-provenance graph — is strictly less
than the nominal independence κ̂(v) that the design credits, **and** no
mechanism in the stack signals that this has happened.

Formal definitions: `SELECTED_CANDIDATE_FORMAL_TARGET.md` §1.

---

## 2. EXACT NULLS

Three. Any one of them, if it wins, closes the direction. They are ordered by
estimated probability, most likely first — deliberately, so the design is not
built around the outcome the experimenter would prefer.

**H0c — Consequence null (most likely).** Independence deficits Δ_t(v) > 0
occur and are not design-declared, but **no assurance decision differs**
between a κ-aware and a κ-blind reading of the same trace. The phenomenon is
real and inert. *This is what the three preceding CSIA work packages each found
for their own phenomenon; there is no reason to expect otherwise here.*

**H0b — Baseline null.** Every (v, t) with Δ_t(v) > 0 lies inside a dependency
that a competent design-time common-cause analysis of this stack would already
have listed. The phenomenon is real and already handled by existing practice.

**H0a — Structural null.** Δ_t(v) = 0 for every monitored verdict at every
tick. There is no runtime collapse at all.

---

## 3. MANIPULATION

Two arms. The first has no manipulation at all; that is the point.

**Arm 1 — OBSERVATIONAL (no manipulation).** Compute κ_t(v) for every
monitored verdict across:

- the real 9.6 MB PX4 ULog already in the repository
  (`research/v1_1/results/.px4_link_probe/passive/log/2026-08-25/22_13_43.ulg`);
- the existing real MAVLink captures;
- a nominal SITL run per platform.

No fault is injected. Arm 1 alone decides H0a and H1.

**Arm 2 — SINGLE-UPSTREAM-FAULT INJECTION (paired).** Choose the vertex *c*
identified by Arm 1 as the smallest cut for some verdict with Δ_t(v) > 0.
Inject exactly one fault **at or above *c*** — that is, upstream of the point
where the nominally independent channels separate — and record:

- whether ≥2 channels in S(v) move together;
- whether any cross-check over S(v) fires;
- whether any CSIA verdict, diagnosis or failsafe action differs from the
  paired nominal run.

The manipulation is *upstream*. Existing CSIA fault injection acts at the
channel level and is therefore **not** sufficient; building the upstream
injection is the only new code Stage 0 requires, and it lives entirely in
`research/`, never in `csia/`.

---

## 4. CONTROLS

**C1 — Null control (nominal word).** Every cross-arm comparison is repeated
on an all-nominal trace, exactly as in
`research/evidence_semantics/contract_checker.py`. Any quantity that differs
between arms *on the nominal control* is `CONFOUNDED_BY_CONTROL` and counts for
nothing. This discipline has already disqualified results in two prior
packages and is not optional.

**C2 — Positive control on the instrument.** A channel pair that is
independent by construction (two transducers with no common upstream vertex,
identified before the audit runs) **must** yield κ = 2. If it yields 1, the
provenance graph is over-connected, the instrument is broken, and the entire
run is void.

**C3 — Negative control on the instrument.** A channel pair known to share an
upstream vertex by inspection (e.g. two fields decoded from the same MAVLink
message) **must** yield κ = 1. If it yields 2, the graph is under-connected —
the dangerous direction, since missing edges inflate κ — and the run is void.

**C4 — Frozen-core control.** `tests/test_v1_frozen.py` must pass before and
after. If the frozen core changed, every result is void.

---

## 5. PRIMARY ENDPOINT

> The set of triples **(verdict *v*, tick range, cut vertex *c*)** for which
> κ_t(v) < κ̂(v), computed from a provenance graph in which **every edge is
> pinned to a verified `file:line`** in ArduPilot, PX4 or CSIA source, together
> with the count of those triples for which no mechanism in the stack signalled
> the deficit.

Deterministic. No threshold, no fitted parameter, no label, no statistic.

**Reporting rule, binding:** κ must be reported for **every** monitored
verdict, including every verdict where κ = κ̂. Reporting only the deficits is
selective reporting and voids the result.

---

## 6. SECONDARY ENDPOINTS

**S1 — Time-variation of the graph.** Whether E_t actually varies with *t*.
Discharges proof obligation PO-3. If E_t is constant, the "runtime" framing is
dropped and the finding is downgraded to a design-time observation.

**S2 — Co-movement under upstream fault (Arm 2).** Whether ≥2 nominally
independent channels move together, with the sign and magnitude of each.

**S3 — Cross-check silence (Arm 2).** Whether any consistency test over S(v)
fires during the co-movement.

**S4 — Action-level consequence.** Whether the failsafe action set differs
between the paired runs. **This is the endpoint that decides H0c**, and the
prior probability that it shows no difference is high.

**S5 — Cross-platform replication.** Whether the same verdict shows the same
deficit on ArduPilot and on PX4. A deficit present on one platform and absent
on the other is a much weaker result and must be reported as such.

**S6 — Design-declared coverage.** For each deficit, whether it corresponds to
a dependency that this project's own design documentation already declares.
Discharges H0b as far as this stack's own documents allow; the ARP4761 question
is settled by reading, not by this experiment.

---

## 7. CONFOUNDERS

| confounder | why it threatens the result | mitigation |
|---|---|---|
| **Missing provenance edges** | inflate κ, making the system look *more* independent; the reported deficit would be an underestimate but a spurious *absence* of deficit would be an overestimate of independence | κ declared as an **upper bound** (PO-2); C3 negative control; every edge cited and re-read |
| **Spurious edges** | deflate κ, manufacturing deficits that do not exist | C2 positive control; edges accepted only with a verified `file:line` |
| **Configuration-dependent wiring** | the graph on disk may not be the graph in the run | record the exact parameter set and build configuration with the run; report the configuration as part of the result, not as a footnote |
| **Confusing staleness with dependency** | an absent channel is not a dependent channel | absence and dependency are separate vertex states; a verdict with a missing channel is excluded from the κ computation and reported separately |
| **Frozen-core drift** | any downstream change would be misread as a κ effect | C4 |
| **Timing / tick-grid drift** | float accumulation misaligns arms (this bit a previous package) | integer tick indices, `tau = k * dt`, as already used in `probe.py` |
| **Warm-up and arm time** | the failsafe returns `[]` below `arm_time = 10.0 s`, so early ticks cannot show an action difference | warm-up ≥ 12.0 s before scoring the action endpoint, declared in advance |
| **Experimenter degrees of freedom in choosing *c*** | picking the cut vertex that gives the best story | *c* is chosen by the smallest-cut rule stated in §3 before Arm 2 runs, and the rule is frozen in the prompt |

---

## 8. INVALID-TRIAL RULES

A trial is **void**, not adjusted, if any of the following hold:

1. Any provenance edge cannot be resolved to a `file:line` that still contains
   the cited construct when re-read at check time.
2. C2 (positive control) yields κ ≠ 2, or C3 (negative control) yields κ ≠ 1.
3. The provenance audit is not byte-identical across two independent runs.
4. `tests/test_v1_frozen.py` fails, or any file under `csia/` is modified.
5. The paired arms differ in seed, scenario, tick grid, or build configuration.
6. The nominal control (C1) shows a difference between arms.

Void trials are recorded and published. They are not re-run with adjusted
parameters until they pass.

---

## 9. EXPECTED ARTIFACTS

Under `research/evidence_independence/` — a **new** directory; nothing under
`csia/` and nothing under an existing research package is modified.

| artifact | content |
|---|---|
| `PROVENANCE_GRAPH.json` | V, E_t, every edge with `file:line` and the cited text |
| `PROVENANCE_CITATIONS.csv` | one row per edge; re-verified at check time |
| `EFFECTIVE_INDEPENDENCE.csv` | κ_t and κ̂ for **every** verdict and tick, deficits and non-deficits alike |
| `INDEPENDENCE_DEFICITS.csv` | the primary endpoint: (verdict, tick range, cut vertex, signalled?) |
| `GRAPH_TIME_VARIATION.json` | S1 |
| `UPSTREAM_INJECTION_RESULTS.csv` | S2, S3, S4, paired, with the null control column |
| `CONTROLS.json` | C1–C4 outcomes; the run is void unless all pass |
| `CROSS_PLATFORM.csv` | S5 |
| `BASELINE_COMPARISON.md` | H0b: deficits vs. design-declared dependencies; and the written ARP4761 argument from the gate |
| `PRIOR_ART_GATE.md` | the §0 gate's findings, including any kill |
| `CLAIM_LEDGER.json` | statuses from item 42's vocabulary only |
| `CHATGPT_REVIEW_REPORT.md` | the stage report |
| `tests/test_evidence_independence.py` | guards: frozen core untouched, controls enforced, every edge cited, no selective reporting, no novelty wording |

---

## 10. EXPECTED RUNTIME

| phase | estimate |
|---|---|
| Prior-art gate (§0) — reading, on a machine with library access | 1–2 days |
| Provenance audit of ArduPilot + PX4 + 3 CSIA paths | 1–2 days of source reading |
| κ computation over real logs | minutes |
| Upstream injection cell in SITL, paired | minutes per cell |
| Controls, tests, write-up | 1 day |
| **Total** | **under one week**, dominated by reading, not compute |

Item 15's bar — the kill test should run in minutes to hours, not weeks — is
met for the *experiment*. The reading is the long pole and it is the part that
must not be skipped.

---

## 11. STOP CONDITIONS

**Stop and record a kill if:**

- the §0 gate finds any prior work that computes a runtime effective-
  independence count for a monitor's verdict;
- the §0 gate cannot distinguish runtime κ from ARP4761 common-mode analysis;
- Arm 1 yields Δ_t(v) = 0 everywhere (H0a wins);
- every deficit is design-declared (H0b wins);
- C2 or C3 fails and cannot be repaired without weakening the citation
  requirement.

**Stop and report a null result — not a kill — if:**

- deficits exist, are not design-declared, and no action differs (H0c wins).
  This is a legitimate, publishable negative finding about a real autopilot
  stack, and it must be reported as the result rather than converted into a
  reason to widen the search until something moves.

**Never:**

- adjust κ̂ after seeing κ;
- choose the cut vertex *c* after seeing which choice produces a difference;
- relax the `file:line` citation requirement to admit an edge that makes the
  result stronger;
- re-run a void trial with adjusted parameters and report the second run;
- report only the verdicts that showed a deficit.
