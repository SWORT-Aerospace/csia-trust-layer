# Prior art — INCOMPLETE, ACCESS DENIED

## Verdict

**The required prior-art search could not be run from this host.**
Per the governing work order's own rule — *if full texts are inaccessible,
mark the novelty search INCOMPLETE and prohibit novelty claims* — and per
`docs/CURRENT_PROGRAM_STATE.md` §9.3, *no citation is invented to make a
guard pass*:

> **NO NOVELTY, PRIORITY OR ORIGINALITY CLAIM MAY BE MADE FOR ANY PART OF
> `csia_active_evidence/`.** Not in code, not in a docstring, not in a commit
> message, not in a paper. Promotion Gate G is **BLOCKED**.

## The refusals, verbatim, retried

Every scholarly endpoint returns HTTP 000 at the client. The agent proxy
reports `connect_rejected` — *gateway answered 403 to CONNECT (policy denial
or upstream failure)*. Retried on 2026-09-12 after the first denial:

```
arxiv.org:443                 000
api.semanticscholar.org:443   000
api.crossref.org:443          000
api.openalex.org:443          000
doi.org:443                   000
```

These are the same hosts already recorded as publication blockers 1, 3 and 4
in `docs/CURRENT_PROGRAM_STATE.md`. It is not a research problem; it needs a
human with publisher access.

## How to read the table below

The work order supplied nine sources with titles, authors, years and DOIs,
and a one-line characterisation of each. **Those characterisations are
reproduced here as the work order's claims about the sources, not as this
repository's findings.** Nothing below was read. Every cell that would
require reading the paper says `NOT READ`.

A row in this state cannot support a novelty claim in either direction: it
cannot establish that the work is new, and it cannot establish that it is
not.

| # | source | status | work order says it covers | fields requiring the full text |
|---|---|---|---|---|
| 1 | Ni, Ornik, Chou, Coogan, *Safe, Real-Time Active Model Discrimination and Fault Diagnosis for Nonlinear Systems via Differentiable Reachability*, arXiv:2606.19590 (2026) | **NOT READ — ACCESS DENIED** | robust safety constraints, interval output-reachable-set over-approximation, differentiable overlap objective, real-time nonlinear robotic experiments | system class, dimension, fault class, uncertainty model, safety proof basis, abstention behaviour, runtime, licence, overlap with this work |
| 2 | Kong, McMahon, Lahijanian, *Bayesian Diagnosability and Active Fault Identification*, arXiv:2509.04708 (2025) | **NOT READ — ACCESS DENIED** | quantitative diagnosability, active inputs, unmodelled faults under stated assumptions | all of the above |
| 3 | Daniels et al., *Active Fault Identification and Robust Control for Unknown Bounded Faults via Volume-Based Costs*, arXiv:2508.12010 / SysTol 2025 | **NOT READ — ACCESS DENIED** | set-membership identification, informative excitation, tube MPC for bounded faults | all of the above |
| 4 | Lovas, *In-Hover Quadrotor Rotor Degradation Monitoring Using Null-Space Excitation and Lock-In Detection*, Drones 10(5) 395, DOI 10.3390/drones10050395 (2026) | **NOT READ — ACCESS DENIED** | direct UAV propulsion probing; null-space excitation; lock-in detection | actuation rank, excitation construction, baselines, simulation limits |
| 5 | Sun et al., *Optimization of Mode Discerning Control for Nonlinear Hybrid Systems…*, DOI 10.1016/j.isatra.2026.06.044 (2026) | **NOT READ — ACCESS DENIED** | nonlinear bi-level formulation, differentiable optimisation for mode-discerning auxiliary control | all of the above |
| 6 | Harirchi/Luo/Ozay model invalidation; Singh/Ding/Ozay/Yong input design via affine abstraction | **NOT READ — ACCESS DENIED** | earlier guaranteed/set-based active diagnosis | all of the above |
| 7 | Pillai, Desai, Pattipati, Balasingam, *An Improved Approach to Estimate the Internal Resistance of a Battery During the HPPC Test*, arXiv:2505.06410 (2025) | **NOT READ — ACCESS DENIED** | **why the naive ΔV/ΔI estimate is biased when OCV changes** | the bias form, and whether it is the same drift-aliasing term derived in `DERIVATIONS.md` §3 |
| 8 | Hultberg, Zachariah, Ribeiro, *Anytime-Valid Conformal Risk Control*, arXiv:2602.04364 (2026) | **NOT READ — ACCESS DENIED** | what is guaranteed under growing calibration data and distribution shift | the exact assumptions |
| 9 | Vovk et al., *Conformal e-testing*, DOI 10.1016/j.patcog.2025.111841 (2025) | **NOT READ — ACCESS DENIED** | limits of conformal/e-process validity | which constructions fail to inherit strong validity |
| 10 | *Optimal Runtime Assurance via Reinforcement Learning*, ICCPS 2024 | **NOT READ — ACCESS DENIED** | separating a diagnostic proposal from safety authority | — (its RL policy is explicitly NOT to be imported) |
| 11 | Matei et al., ACM TCPS 8(1) 2024, DOI 10.1145/3631612 | **NOT READ — ACCESS DENIED** | `forge/PRIOR_ART_REQUIRED.md` already records it as covering *"interventions to disambiguate uncertain diagnosis"* | **the closest named prior art in this repository to this package's entire purpose** |

## Row 7 deserves a separate sentence

`DERIVATIONS.md` §3 derives that a probe whose current correlates with time
aliases open-circuit-voltage drift into the resistance estimate with lever
arm `d·cov(t,I)/var(I)`. The work order describes source 7 as showing *why
the naive ΔV/ΔI estimate is biased when OCV changes*. **On the work order's
own description, that is the same phenomenon.** The derivation here should
be assumed to be a re-derivation of a known result until someone reads the
paper, and `CLAIM_LEDGER.md` records it that way.

## The honest expectation, recorded before any reading

So it can be checked later: the errors-in-variables attenuation result is
certainly known; optimal input design is certainly known; the battery
drift-bias result is, on the work order's description, known; and the
five-part integration is **most likely also known**, in the active-fault-diagnosis
literature that `forge/PRIOR_ART_REQUIRED.md` already lists as required
reading.

Recording an expectation is not a substitute for a search. The search is
`INCOMPLETE`.

## Search strings that would be run

Preserved so the work is repeatable by someone with access, per the work
order's minimum query list: active fault diagnosis; active fault
identification; active model discrimination; safe excitation; diagnostic
manoeuvre; auxiliary signal; null-space excitation; set membership;
reachable output sets; interval reachability; zonotopes; runtime assurance;
Simplex; safety filter; diagnosability; identifiability; observational
equivalence; unmodelled faults; open set; reject option; abstention; UAV;
quadrotor; propulsion; battery impedance; ESC; motor degradation; evidence
graph; trust graph; causal ambiguity; eligibility; conformal martingale;
e-process; anytime-valid stopping. Date boundary 2014–2026, with forward and
backward citation tracing concentrated on 2023–2026.

**Access date attempted:** 2026-09-12. **Results retrieved:** none.

## Status

`INCOMPLETE — ACCESS DENIED`. Gate G BLOCKED. Clears when a human with
publisher access works this table plus `forge/PRIOR_ART_REQUIRED.md` §§3–4.
