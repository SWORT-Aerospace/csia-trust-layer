# Closest-Paper Claim-Element Matrix

**Novelty status: `NOVELTY_UNRESOLVED`.**
**Primary text: NOT READ.** Seven retrieval endpoints were tried once each and
all were refused; the record is `results/EXTERNAL_ACCESS_CHECK.json`. No
content hash of the primary text is recorded, because no primary text was
retrieved.

## 1. The source, and what this matrix can and cannot be

> X. Ni, M. Ornik, G. Chou, and S. Coogan, *Safe, Real-Time Active Model
> Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable
> Reachability*, arXiv:2606.19590v1, 17 June 2026,
> DOI `10.48550/arXiv.2606.19590`.

Version, date, DOI and URL are as given in the task brief and in the supplied
`RCEC_RELATED_WORK_AND_NOVELTY_BOUNDARY.md`. They are **not** confirmed against
a retrieved document.

Every entry in the **Ni et al.** column is therefore marked
`FROM_BRIEF_NOT_PRIMARY_TEXT`. The claims in that column are what two
user-supplied secondary sources say about the paper. They are not what I read,
and no sentence in this repository may say the paper shows, states or
establishes anything on the strength of this matrix.

Every entry in the **RCEC** column is backed by a committed artifact or a named
test in this repository, and those are verifiable here.

A claim-element comparison against an unread primary text cannot settle
novelty. This matrix narrows the question and records what would close it.

## 2. The matrix

| # | Claim element | Ni et al. (secondary) | RCEC current evidence (verified here) | Consequence |
|---|---|---|---|---|
| 1 | Nonlinear finite-model active discrimination | `YES` — `FROM_BRIEF_NOT_PRIMARY_TEXT`, brief §13.1 | `PARTIAL`. Finite hypothesis bank of seven magnitudes over a battery family only; `discrimination.py`, `openset.py` | **RCEC cannot claim a general active-diagnosis method.** Nothing here touches nonlinear state models. |
| 2 | Robust pre-execution state/input safety over retained models | `YES`, conditional on the model/envelope and the reachability construction — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `NO`. The pre-gate is an interval over-approximation over an enumerated envelope, and its safety half is **vacuous over this action space** (34 A worst case against a 56 A limit; `COUNTEREXAMPLE_LOG.md` IV-19) | **The largest missing RCEC layer.** There is no reachable-set proof here and the phase says so in those words. |
| 3 | Output-feedback probe/control optimisation | `YES` — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `PARTIAL`. Selection over a frozen 72-action library plus S0–S3; no closed-loop policy optimisation. `strategies.py` | Compare against; do not rename ordinary selection-rule design as novelty. |
| 4 | Post-execution realized-action validity as a separate certificate | `NOT_EVALUATED` — `FROM_BRIEF_NOT_PRIMARY_TEXT`, brief §13.4 item 1 | `YES` in architecture and measured: clipping → `CLIPPED_CERTIFICATE_INVALID`, abort → `ABORTED_INCOMPLETE`, and Proposition C shows a full-window certificate bounds a prefix in neither direction | **RCEC's clearest differentiator**, and it is conditional on the closest paper genuinely not covering it, which I could not check. |
| 5 | Realized excitation under lag, saturation and sampling | `NOT_EVALUATED` as a separate sufficiency object — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `YES` for the declared battery model. Proposition A: a palindromic command with zero drift lever yields a realized lever of −0.0276 s through an ordinary causal bounded lag | Keep the scope narrow: realized current, not general nonlinear observability. |
| 6 | Errors-in-variables and drift bias | `NOT_EVALUATED` — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `YES`, analytically and empirically. The paired change error is exactly `\|λ̂−1\|·Δ` with λ̂ = 1.0009463544, matching measurement to seven digits (IV-9) | Domain-specific contribution. Not a replacement for reachable sets. |
| 7 | Unknown / unmodelled-fault experiment | `NOT_EVALUATED`; the formulation assumes the true model is in the finite candidate set — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `PARTIAL`. One ringing family, detectability boundary at 3.363 σ, routing rate 0.901 above and 0.000 below | **Neither work supports universal open-set diagnosis**, and this phase's boundary is one mechanism, not coverage. |
| 8 | Proposed / authorized / realized action lineage | `NOT_EVALUATED` — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `YES` by design and exercised end to end: the runner carries proposed and authorized digests per row and the clipped path is separately tested (`COUNTEREXAMPLE_LOG.md` IV-17) | Tested, not asserted from a schema — which it briefly was, until IV-17. |
| 9 | Hardware airborne validation | `NO`; the aircraft case is simulated — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `NO`. Simulator only, synthetic pack, no chemistry | **No flight or airworthiness claim from either result.** |
| 10 | Embedded low-power runtime | `NO`; reported optimisation uses an RTX 4070-class GPU — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `NOT_EVALUATED` on target. Component timings measured on this container's CPU and labelled as host timings; no CM5 or Pixhawk exists here | Benchmark the selector and the certificate separately on target hardware. Host-side search time and certificate finalisation time are never summed. |
| 11 | Independent outcome evaluator and locked protocol | `NOT_REPORTED` as an evaluation design feature — `FROM_BRIEF_NOT_PRIMARY_TEXT` | `INTERNAL` reimplementation with static import-graph isolation and positive controls; **no external replication** | **Never call this externally independently validated.** One author, one session. |

## 3. What the matrix does not settle

Rows 4, 5, 6, 8 and 11 are where a differentiating claim could live. Every one
of them turns on a `NOT_EVALUATED` in the Ni column, and every one of those
`NOT_EVALUATED`s comes from a secondary source rather than from reading the
paper. An absence reported by a summary is not an absence in the work.

So the matrix establishes what RCEC **may not** claim — rows 1, 2, 3, 9, 10 and
11 all foreclose something — and it does not establish what RCEC **may** claim.

## 4. What would resolve it

In order, and none of it possible from this container:

1. retrieve and read the primary text, specifically §§III, V-A–V-E, VI-B, VI-D
   and VII, and record its content hash;
2. redo this matrix against the text rather than against a summary;
3. implement the overlap objective on the paper's own models, or justify the
   reduction equation by equation against the text;
4. backward and forward citation chaining for the exact claim-element
   combination in rows 4, 5, 6, 8;
5. external replication by a different person or group with no access to locked
   outcomes during development.

Until all five, the status stays `NOVELTY_UNRESOLVED`.

## 5. Permitted and prohibited language

**Prohibited outright**, for active fault diagnosis, optimal excitation,
Fisher-information design, set-membership diagnosis, output-feedback model
discrimination, reachable-set safety, runtime assurance, and battery-resistance
estimation, individually: any claim of novelty. Each is long-established and at
least one is reproduced from a textbook identity inside this phase — P7a's
objective **is** the classical A-optimal design for resistance
(`BASELINE_MAPPING.md` §3).

**Prohibited until resolution:** any sentence asserting that the composition
across proposal, authorization, physical realization and evidence acceptance is
novel.

**Permitted now**, and only this: a description of what was built and measured,
with the scope attached. For example — *"Within a declared simulator envelope,
this phase binds a diagnostic inference to the authorized and realized
excitation, its measured information moments, its bounded estimator error, and
explicit invalidation conditions. Whether that combination is novel is
unresolved; the closest named source could not be retrieved."*
