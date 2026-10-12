# SELECTED CANDIDATE — STAGE 0 PROMPT

Item 43. This is the complete prompt for the next Claude Code run, to be used
**only if ChatGPT approves candidate B**.

> ## ⛔ DO NOT EXECUTE THIS PROMPT IN THE SESSION THAT WROTE IT.
> Item 36 and item 43 both forbid it. Nothing below has been executed: no
> detector exists, no CSIA file was touched, no threshold was changed, no
> scored data was generated. **No physical HIL was executed** — no hardware
> is present in this environment, and the HIL path named in §10 is a
> feasibility estimate, design only.

---

```
# =====================================================================
# CSIA — EVIDENCE INDEPENDENCE STAGE 0
#
# RUNTIME COLLAPSE OF EFFECTIVE EVIDENCE INDEPENDENCE
# AT AN ASSURANCE MONITOR'S INPUT
#
# PRIOR-ART GATE FIRST. EXPERIMENT SECOND. NO PRODUCTION CHANGE.
# =====================================================================
#
# BASE COMMIT: <the commit that carries research/frontier_selection/>
# NEW DIRECTORY: research/evidence_independence/
#
# READ FIRST, IN THIS ORDER:
#   research/frontier_selection/SELECTED_CANDIDATE.md
#   research/frontier_selection/SELECTED_CANDIDATE_FORMAL_TARGET.md
#   research/frontier_selection/SELECTED_CANDIDATE_STAGE0_DESIGN.md
#   research/frontier_selection/SEARCH_PROTOCOL.md   (§0 especially)
#
# =====================================================================
# 1. HARD GATE — PRIOR ART. NO CODE UNTIL THIS PASSES.
# =====================================================================
#
# The stage that selected this candidate could not read a single paper in
# full text. Every source is PARTIAL_SOURCE_ONLY. The candidate's status is
# PROVISIONAL for that reason and for no other.
#
# 1.1 Obtain and READ IN FULL:
#
#   S063  Testing conditional independence to determine shared information
#         in a data/signal fusion process
#   S060  Noack et al., Decentralized data fusion with inverse covariance
#         intersection, Automatica 2017
#   S062  Managing data incest in a distributed sensor network
#   S041  Ruchkin et al., Confidence Composition for Monitors of
#         Verification Assumptions, ICCPS 2022
#   S016  Ain't No Stopping Us Monitoring Now, TOSEM 2025
#
# 1.2 Obtain ARP4761 (or an authoritative technical summary of common-mode
#     analysis, zonal safety analysis and particular-risks analysis) and
#     answer IN WRITING:
#
#       "Is runtime kappa anything other than ARP4761 common-mode
#        analysis recomputed at each tick?"
#
#     If the answer is no, or cannot be established:
#     STOP. Record the kill. Do not reword the candidate.
#
# 1.3 Run two prior-art searches NOT run in the selection stage:
#
#       (a) data provenance theory - why-provenance, where-provenance,
#           how-provenance, lineage in dataflow systems
#       (b) fault-tree minimal cut sets, reliability block diagrams
#
#     kappa may already be one of these objects under another name.
#
# 1.4 If ANY source above computes a runtime effective-independence count
#     for a safety monitor's verdict:
#
#       STOP. Write research/evidence_independence/PRIOR_ART_GATE.md
#       recording the kill, commit it, and end the stage.
#       DO NOT adjust the candidate so that it survives.
#
# 1.5 Write PRIOR_ART_GATE.md regardless of outcome, with:
#       - which full texts were obtained and which were not
#       - what each says about runtime dependency accounting
#       - the ARP4761 answer
#       - the explicit verdict: PROCEED or KILL
#
# =====================================================================
# 2. SOURCE FREEZE
# =====================================================================
#
# 2.1 Record, before any analysis:
#       - git commit of csia-trust-layer
#       - git commit / version of ArduPilot at /home/user/ardupilot/ardupilot
#       - git commit / version of PX4 at /home/user/px4
#       - sha256 of every log file used
#       - the exact parameter set and build configuration of each SITL run
#     into research/evidence_independence/SOURCE_FREEZE.json
#
# 2.2 The frozen v1 core is untouchable:
#       csia/trust_engine, csia/diagnosis, csia/runtime/online.py,
#       csia/runtime/failsafe.py, csia/scenarios.py, csia/profiles.py
#     tests/test_v1_frozen.py must pass before and after.
#     If any file under csia/ is modified, the whole stage is void.
#
# 2.3 Do NOT modify any existing research package. Prior reports are
#     provenance (item 0 of the selection brief) and stay byte-identical.
#
# =====================================================================
# 3. PREREGISTRATION - FREEZE BEFORE MEASURING
# =====================================================================
#
# 3.1 BEFORE computing any kappa, write and commit PREREGISTRATION.md
#     containing:
#       - the monitored verdict set V under study, enumerated
#       - the nominal independence kappa-hat for each verdict, WITH the
#         source of that number (design doc, architectural assertion, or
#         the channel count the cross-check compares)
#       - the positive-control channel pair (must yield kappa = 2)
#       - the negative-control channel pair (must yield kappa = 1)
#       - the rule for choosing the injection vertex c
#       - the three nulls H0a, H0b, H0c verbatim from the Stage-0 design
#
# 3.2 kappa-hat may NEVER be adjusted after kappa is computed.
#     If a kappa-hat turns out to be wrong, record the correction as a
#     REFUTED PREDICTION and keep both numbers. Do not overwrite.
#
# 3.3 The injection vertex c is chosen by the frozen rule, not by which
#     choice produces a difference.
#
# =====================================================================
# 4. THE PROVENANCE GRAPH
# =====================================================================
#
# 4.1 Build G_t = (V, E_t) by READING SOURCE:
#       - producer side: ArduPilot and PX4
#       - consumer side: the three CSIA decode paths
#       - the 106-field MAVLink + uORB universe already enumerated in
#         research/ai_contract_synthesis/ is the starting vertex set
#
# 4.2 EVERY edge carries a locator (file:line) and the cited text.
#     A verifier must re-open each file at check time and confirm the
#     construct is still there. Reuse the discipline in
#     research/semantic_authority_conflict/authorities.py - on its first
#     run that verifier caught five bad citations, and it will again.
#
# 4.3 An edge without a verified locator is DROPPED, not assumed.
#
# 4.4 kappa is therefore an UPPER BOUND on effective independence.
#     Label it that way in every artifact and in every sentence.
#     A deficit found under an upper bound is real. An absence of deficit
#     under an upper bound proves nothing.
#
# =====================================================================
# 5. MANIPULATION CHECKS
# =====================================================================
#
# 5.1 POSITIVE CONTROL: the preregistered independent pair must yield
#     kappa = 2. If not, the graph is over-connected. VOID the run.
#
# 5.2 NEGATIVE CONTROL: the preregistered shared pair must yield
#     kappa = 1. If not, the graph is under-connected - the dangerous
#     direction. VOID the run.
#
# 5.3 NULL CONTROL: every cross-arm comparison is repeated on an
#     all-nominal trace. Anything that differs on the nominal control is
#     CONFOUNDED_BY_CONTROL and counts for nothing.
#
# 5.4 INJECTION CHECK: in Arm 2, confirm the injected fault actually
#     reached vertex c. An injection that did not land is a void trial,
#     not a negative result.
#
# 5.5 REPRODUCIBILITY: the provenance audit must be byte-identical across
#     two independent runs. If not, VOID.
#
# =====================================================================
# 6. WHAT TO MEASURE
# =====================================================================
#
# 6.1 PRIMARY: (verdict, tick range, cut vertex, was-it-signalled) for
#     every verdict where kappa_t < kappa-hat.
#
# 6.2 REPORT KAPPA FOR EVERY VERDICT, INCLUDING THOSE WITH NO DEFICIT.
#     Reporting only the deficits is selective reporting and voids the
#     result.
#
# 6.3 SECONDARY: graph time-variation; channel co-movement under the
#     upstream fault; cross-check silence; failsafe ACTION difference;
#     cross-platform replication ArduPilot vs PX4; whether each deficit
#     is already design-declared.
#
# 6.4 Warm-up >= 12.0 s before scoring the ACTION endpoint. The failsafe
#     returns [] below arm_time = 10.0 s; this bit a previous package.
#     Use integer tick indices and tau = k * dt. Float accumulators drift.
#
# =====================================================================
# 7. HARD STOPS
# =====================================================================
#
# STOP AND RECORD A KILL if:
#   - the gate in section 1 finds the runtime computation already exists
#   - runtime kappa cannot be distinguished from ARP4761 CCA
#   - Arm 1 finds kappa = kappa-hat everywhere (H0a wins)
#   - every deficit is design-declared (H0b wins)
#   - a control fails and can only be repaired by weakening the citation
#     requirement
#
# STOP AND REPORT A NULL RESULT - NOT A KILL - if:
#   - deficits exist, are not design-declared, and NO action differs
#     (H0c wins). This is the most likely outcome. It is a legitimate
#     negative finding about a real autopilot stack. Report it as the
#     result. Do NOT widen the search until something moves.
#
# NEVER:
#   - adjust kappa-hat after seeing kappa
#   - choose c after seeing which choice helps
#   - relax the file:line requirement to admit a convenient edge
#   - re-run a void trial with adjusted parameters and report run two
#   - report only the verdicts that showed a deficit
#   - tune any threshold anywhere for any reason
#
# DO NOT:
#   - modify CSIA production behaviour
#   - modify any existing research package
#   - build a runtime detector, a new production class, or a monitor that
#     acts on kappa. Stage 0 MEASURES. It does not DEFEND.
#   - run a large campaign
#   - write a paper
#   - claim novelty
#   - fly anything
#
# =====================================================================
# 8. ARTIFACTS
# =====================================================================
#
# research/evidence_independence/
#   PRIOR_ART_GATE.md
#   SOURCE_FREEZE.json
#   PREREGISTRATION.md
#   PROVENANCE_GRAPH.json
#   PROVENANCE_CITATIONS.csv
#   EFFECTIVE_INDEPENDENCE.csv        (every verdict, deficit or not)
#   INDEPENDENCE_DEFICITS.csv         (primary endpoint)
#   GRAPH_TIME_VARIATION.json
#   UPSTREAM_INJECTION_RESULTS.csv
#   CONTROLS.json
#   CROSS_PLATFORM.csv
#   BASELINE_COMPARISON.md
#   CLAIM_LEDGER.json
#   CHATGPT_REVIEW_REPORT.md
#   README.md
#
# tests/test_evidence_independence.py must guard:
#   - no file under csia/ is touched; test_v1_frozen.py passes
#   - every provenance edge resolves to a live file:line
#   - controls C1-C4 recorded and passing, or the run marked VOID
#   - EFFECTIVE_INDEPENDENCE.csv contains every verdict in the
#     preregistered set (no selective reporting)
#   - kappa is described as an upper bound wherever it is described
#   - no "PROVED - POSSIBLE NOVEL CONTRIBUTION" in the claim ledger
#     unless the section-1 gate passed on FULL TEXT
#   - refuted predictions are kept, with kept: true
#
# Makefile target: `make evidence-independence`
#
# =====================================================================
# 9. CLAIM LEDGER VOCABULARY
# =====================================================================
#
# Only: KNOWN/SUBSUMED | PROVED - NOVELTY NOT ESTABLISHED |
#       PROVED - POSSIBLE NOVEL CONTRIBUTION | EMPIRICAL ONLY |
#       PROVISIONAL | CONJECTURE | REFUTED
#
# PROVED - POSSIBLE NOVEL CONTRIBUTION requires the section-1 gate to
# have passed on FULL TEXT. Snippets never suffice. If full text was
# still unobtainable, the ceiling remains PROVISIONAL and the stage says
# so in its first paragraph.
#
# Preserve every prior verdict verbatim:
#   generic evidence-semantic equivalence checking .... KNOWN/SUBSUMED
#   dual operational/diagnostic admissibility ........ KNOWN/SUBSUMED
#   AI-assisted contract synthesis ................... HEURISTICS_SUFFICIENT
#   conflicting semantic authorities ................. ENGINEERING_INCONSISTENCY_ONLY
#
# =====================================================================
# 10. HOSTILE REVIEW - ANSWER ALL TEN IN THE REPORT
# =====================================================================
#
# A. "This is already known under another name."
#    -> name the names. CCF, coincident failure, data incest, minimal cut
#       sets, common-mode analysis. Say which one it is not, and why,
#       against FULL TEXT.
#
# B. "This is just a UAV application of standard theory."
#    -> concede the theory is standard. The claim is the measurement.
#
# C. "Your result depends on one simulator bug."
#    -> the primary endpoint comes from SOURCE, evaluated on REAL logs.
#       A simulator cannot create a provenance edge. Say so with the
#       file:line evidence.
#
# D. "Your formal theorem is a trivial corollary."
#    -> CONCEDE. It is a corollary of Menger. Do not defend it.
#
# E. "Your baseline already solves the problem."
#    -> run design-time CCA and Covariance Intersection as explicit
#       baselines. Let them win if they win.
#
# F. "The effect vanishes after controlling for common cause / history /
#    timing."
#    -> report the null control and the positive control. If the effect
#       vanishes, say the effect vanished.
#
# G. "No physical relevance."
#    -> the bench HIL path costs $100-$500 and needs one Pixhawk-class FC
#       plus one GNSS module. If Stage 0 cannot motivate it, say so.
#
# H. "You require labels or assumptions unavailable online."
#    -> no labels, no fitted parameters, no thresholds. This is the
#       strongest answer available. Do not weaken it by adding a
#       threshold anywhere.
#
# I. "Your contribution is merely integration."
#    -> partly true. If the measurement reveals nothing the design-time
#       analysis missed, the contribution IS merely integration and the
#       direction should be abandoned. Say that explicitly.
#
# J. "This is another novelty pivot after earlier hypotheses failed."
#    -> concede the chronology in full: eleven abandoned directions
#       before this one. The only answer is the section-1 full-text
#       audit. If that audit was not possible, the answer is that there
#       is no answer yet.
#
# =====================================================================
# FINAL RULE FOR THIS STAGE
# =====================================================================
#
# Read before you measure.
# Measure before you claim.
# Report the null when the null wins.
#
# The most likely outcome of this stage is H0c: the deficits are real,
# undeclared, and change nothing. That is a result. Write it down and
# stop.
# =====================================================================
```
