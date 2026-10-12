# Full-text verification queue

**2026-09-30. Part 55 of the shadow-validation brief.**

**Current level of every external source: V0.** Each was recalled or
summarised, not read in full in this phase. The only sources read at V4 are
repository files and the PX4 tree at `547e2ca`.

**Ranking:**
- **P0:** a source that could change an engineering decision taken or
  recommended here.
- **P1:** one that could change a recommendation's form but not whether to
  make it.
- **P2:** background.

**No obvious fix waits on this queue.** Fault policy B, the successor profile
and the validator all rest on repository measurements, not on these sources.

| rank | source | identifier to locate | current level | exact claim to verify | CSIA decision it affects | what changes if the source contradicts us |
|---|---|---|---|---|---|---|
| P0-1 | PX4 EKF2 documentation and source, at the version being deployed, not only `547e2ca` | docs.px4.io "ECL/EKF2"; `src/modules/ekf2` at the target commit | V4 at `547e2ca`; V0 elsewhere | (a) output publication gated on new IMU data; (b) EKF2Selector resets relative test ratios and bumps `instance_changed_count` on a switch; (c) `pos_test_ratio` is low-pass filtered | G-2 decision (R5, R5a and R5b rejected or deferred; starvation paced by the IMU); the E1 epoch design; the estimator integration example | if GNSS loss can stop EKF2 output on the deployed version, R5b becomes valid and G-2 can be resolved by profile. If lane switches do not reset per-lane state, the epoch rule must reset it itself |
| P0-2 | structural isolability / MSO-based diagnosis (Krysander, Åslund and Frisk; Blanke et al., *Diagnosis and Fault-Tolerant Control*) | book; journal papers | V0 | that structural isolability of a fault set against given observables can be computed at design time from a structural model of CSIA's signature-matrix form | the recommendation to add a design-time isolability check (top five, item 5) | if the structural form needs models CSIA's signature matrix cannot supply, the check reduces to the observational-identity test used for MS_B4 and MS_B5 |
| P0-3 | Kleene strong three-valued logic; monotone evaluation of partial information | Kleene 1952; logic texts | V0 | a Kleene-evaluated elimination is monotone in information: adding known values never removes a survivor that remained under unknown values | policy B's "a fault can only widen, except through a failed refuter of the supported hypothesis" argument | if non-monotone cases exist for the conjunctive confirmers used here, policy B must also check confirmers |
| P0-4 | track-to-track correlation and double counting (Bar-Shalom and Campo 1986); covariance intersection (Julier and Uhlmann 1997) | journal papers | V0 | shared process noise or shared sources make estimates correlated, and treating them as independent over-counts information | the lineage-disjointness rule for corroboration | if established practice defines independence differently (for example through a residual cross-covariance), the lineage rule is a necessary condition only |
| P1-1 | Page 1954 CUSUM; Lorden 1971 minimax | Biometrika; Ann. Math. Stat. | V0 | CUSUM's optimality under a known in-control model; its detection delay against false-alarm trade-off | CUSUM contract fields (operating regime, validity) | the contract's "operating_regime" wording |
| P1-2 | Simplex / RTA (Sha 2001); ASTM F3269 runtime assurance | paper; standard | V0 | an RTA consumes monitor states and owns the switch decision | the CSIA / RTA boundary | the interface table in `METHOD_REUSE_MAP.md` §3 |
| P1-3 | dynamic assurance cases (Denney, Pai and Habli 2015) | ICSE / SafeComp-class paper | V0 | DACs re-evaluate argument confidence from runtime evidence | the CSIA / DAC boundary | the interface wording |
| P1-4 | assume-guarantee contracts (Benveniste et al. 2018) | monograph | V0 | contract structure: assumptions (regime) and guarantees (claim) | the evidence-contract minimum | field naming |
| P1-5 | mode-dependent residuals / closed-loop FDD | survey literature | V0 | residual validity is regime-dependent, and closed loops mask faults after compensation | the time- and state-rule framing | none to the measured XSYS result, which stands on its own data |
| P2-1 | the planner family the brief names "s-FEAST" | the brief's reference | V0, name only; **not identified in this phase** | what it plans over | only the anti-roadmap's "a consumer, not built here" | none |
| P2-2 | reachability (Mitchell, Bayen and Tomlin 2005); CBFs (Ames et al.); attainable moment sets (Durham 1993) | papers | V0 | — | the anti-roadmap only | none |
