# External sources needed, and exactly why

Novelty status: **`BLOCKED_EXTERNAL_ACCESS`.**

Connectivity rechecked this session. `arxiv.org`, `export.arxiv.org`,
`api.crossref.org`, `api.openalex.org`, `api.semanticscholar.org` and
`doi.org` all returned HTTP 000, with the agent proxy reporting
`connect_rejected` — *the egress proxy denied the CONNECT (organization
policy)*. No scholarly full text is reachable and none is stored in this
repository.

Per the work order, structurally denied endpoints were not retried for hours.

## What is needed, and what each blocks

| # | source | sections required | what it blocks |
|---|---|---|---|
| 1 | Pillai, Desai, Pattipati, Balasingam, *An Improved Approach to Estimate the Internal Resistance of a Battery During the HPPC Test*, arXiv:2505.06410 | the bias derivation and its assumptions | **highest priority.** The work order describes it as showing why the naive ΔV/ΔI estimate is biased when open-circuit voltage changes. On that description it is the same drift-aliasing term as `DERIVATION.md` §2. Until read, that derivation is recorded as a **re-derivation of a known result** |
| 2 | Matei et al., ACM TCPS 8(1) 2024, DOI 10.1145/3631612 | the intervention-selection method | `forge/PRIOR_ART_REQUIRED.md` records it as covering *interventions to disambiguate uncertain diagnosis*, the closest named prior art in this repository to this package's purpose |
| 3 | Ni, Ornik, Chou, Coogan, arXiv:2606.19590 | methods, assumptions, limitations | whether an interval-reachability certificate already subsumes the RCEC's error decomposition |
| 4 | Kong, McMahon, Lahijanian, arXiv:2509.04708 | the diagnosability definition and unmodelled-fault treatment | whether the open-set residual check is already standard |
| 5 | Daniels et al., arXiv:2508.12010 / SysTol 2025 | the volume-based cost and excitation design | whether informative-excitation selection here is a special case |
| 6 | Lovas, Drones 10(5) 395, DOI 10.3390/drones10050395 | actuation rank, excitation construction, baselines | direct UAV propulsion probing prior art |
| 7 | Sun et al., DOI 10.1016/j.isatra.2026.06.044 | the bi-level formulation | whether the waveform search is a known form |
| 8 | Harirchi/Luo/Ozay; Singh/Ding/Ozay/Yong | model invalidation, input design via affine abstraction | the set-membership lineage |
| 9 | Vovk et al., DOI 10.1016/j.patcog.2025.111841 | the validity limitations | needed **before** any anytime-valid stopping arm is added; none is implemented here for exactly this reason |
| 10 | Hultberg, Zachariah, Ribeiro, arXiv:2602.04364 | what is guaranteed under distribution shift | same |

## The specific question a reader should answer first

Does the literature already contain a certificate that, from **realized**
telemetry, decomposes the error in an online resistance estimate into drift
aliasing, errors-in-variables attenuation, a frequency-dependent polarization
bound, a scale-error term and a sampling term, combines them by union bound,
and refuses to certify when any term is undeclared?

If yes, this is a re-implementation and must be described as one.

## Until then

No file in this work may use "novel", "first", "unprecedented" or
"publication-ready". `PRIOR_ART_MATRIX.md` in the parent directory carries
the eleven rows with every full-text cell marked NOT READ.
