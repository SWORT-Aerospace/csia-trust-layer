# CSIA IP candidate map (stage 2, pre-result)

This file is part of the second-stage novelty verification (2026-09-27/28).
Source ids are listed in `research/csia_novelty_audit/BIBLIOGRAPHY.md`.

**No legal conclusion is drawn here.** This map sorts CSIA's elements by what
the technical prior-art screen shows. It does not say whether anything is:

- patentable;
- valid;
- infringing;
- free to operate.

Items marked **[ATTORNEY]** are worth putting in front of a registered patent
attorney, together with the prior art listed beside them. Every patent cited
was seen at V0 only; no claim was read
(`research/csia_novelty_audit/CSIA_PATENT_PRIOR_ART_SCREEN.md`).

**A question for the attorney, not answered here.** What is the effect of the
dates and visibility of this repository's commits that already describe these
items? That includes the XSYS-001 preregistration and the CSIA source code.

## A. Likely prior art: do not pursue broadly

| element | why | prior art |
|---|---|---|
| cross-sensor validation; analytical redundancy across subsystems | textbook | B04–B06, B58–B60 |
| a cross-domain evidence graph / signature matrix | standard | B08, B62, P07, P12 |
| physical consequence as witness | standard; in fielded code | B44, B92, B130 (V4) |
| actuator-versus-sensor discrimination | decades old | P01, B43, B44, B46, P03–P05 |
| controller compensation as evidence | in fielded code | B130 (V4) |
| temporal signatures; transient-then-steady reasoning | standard | B37, B38, B40, P14 |
| set elimination, candidate sets, AMBIGUOUS | standard | B28, B29, P06 |
| "survival is not support" | the consistency–abduction spectrum | B31, B137 |
| three-valued evidence | standard | B70, B89 |
| health- or integrity-gated action / runtime assurance | standard; patented | B87, B79–B81, P24, P08 |

## B. Potentially protectable implementation detail

These are specific, concrete rules. Each is an instance of a known concept,
and none has been assessed for protectability.

| element | the concrete detail | nearest prior art | note |
|---|---|---|---|
| B-1 detectability-gated "nominal" affirmation | a witness may return "nominal" (refuting physical loss) only if the RPM-implied loss predicts a response of at least 2× its threshold, for the dynamics witness (s_dyn · L_T1 ≥ 2 θ_dyn) and the compensation witness (1/(1 − L_T3) − 1 ≥ 2 θ_ctrl) | B30, B138 | a parameterized rule; small |
| B-2 loss-axis projection of body rate | e = normalize(p_y, −p_x) from the rotor position, with body-rate deviation projected on e over the first 0.2 s | B50, B54, B125 | standard geometry |
| B-3 allocator-ratio compensation witness against a T0 baseline | κ_m = c_m / mean of the other motors, over a post-compensation window, minus its pre-onset value | B130 (`thrust_balance`, V4) | **very close to fielded code** |
| B-4 window-scoped applicability | a witness returns None / NOT_APPLICABLE outside its window, never False, so it eliminates nothing there | B119, B142, B70 | small |
| B-5 the certificate's staleness fields | the certificate carries hashes of configuration, software and evidence, the hypothesis set, the evidence topology, the semantics version and `valid_until`, so a consumer can detect staleness | B62, B63 (AI-ESTATE records) | engineering provenance; low value |

## C. Potentially protectable architecture / composition

| element | description | nearest prior art | flag |
|---|---|---|---|
| C-1 (= MNC-1) | For a multirotor, physical rotor-effectiveness loss is separated from telemetry corruption that matches the local RPM symptom. Two witnesses are used, each with a window: a transient dynamics witness and a post-compensation allocator witness. Each is inapplicable outside its window and detectability-gated. They are combined by elimination that answers AMBIGUOUS unless one cause is refuted and the other confirmed | **EPOS family (P03–P05, P25)**, P15, P01, B117, B118, B130 | **[ATTORNEY]**, with the whole EPOS family, P15, P01, B117 and B118 |
| C-2 | a read-only diagnostic layer that reports function eligibility and issues no command | B81, B120, P24 | low. A separation-of-concerns choice |

## D. Insufficiently developed

| element | state |
|---|---|
| bounded runtime action authority (FORGE) | not implemented; not tested by XSYS-001 |
| temporal reasoning inside the CSIA engine | v2 is atemporal; windows exist only in one experiment's adapter |
| multiple-fault diagnosis | common-cause retention only; XSYS-001 is single-fault |
| real-hardware validation | none; XSYS-001 is PX4 SIH simulation |
| comparison against established methods | none (no MMAE, IMM, DBN, set-valued observer or ArduPilot/PX4 baseline) |
| the matched-by-construction validation design (MNC-2) | a methodology. It is listed for completeness; it is unlikely to be regarded as technology |

## E. High prior-art risk

| element | why the risk is high | prior art |
|---|---|---|
| any broad claim to distinguish actuator from actuator-sensor/telemetry faults using the plant response | the EPOS text states it on engines; P01, P15 | P03–P05, P25, P01, P15 |
| compensation-imbalance statistics for motor diagnosis | fielded open-source code | B130 (V4) |
| ambiguity groups ranked by evidence | patented | P06 |
| structural-temporal propagation reasoning on aircraft | patented | P07 |
| diagnosis confidence gating reconfiguration or authority | patented; standards exist | P24, P08, B81 |

## Summary for the attorney conversation

- **Worth a conversation:** C-1, with the prior art listed beside it.
- **Probably not worth one on its own:** everything in A and E, and B-3,
  because of the ArduPilot code.
- **Not ready for one:** everything in D.
