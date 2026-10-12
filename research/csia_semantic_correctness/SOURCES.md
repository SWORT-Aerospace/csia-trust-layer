# Sources and search log

CSIA semantic correctness audit, 2026-09-29. Literature is cited as `Lnn`.
Repository files are cited by path.

## Verification levels

| level | meaning |
|---|---|
| V0 | search summary only |
| V1 | abstract |
| V2 | substantial text |
| V3 | complete text |
| V4 | exact lines read or executed |

**External literature.** Every item is **V0** and carries
REQUIRES_EXTERNAL_FULL_TEXT_VERIFICATION. Scholarly hosts are unreachable
from this environment, as recorded in every earlier package. Each item is
used **only for a name or a definition**, never for a result this package
depends on. Every result here comes from executing the repository's own
code.

## 1. Literature

| id | source | used for | level |
|---|---|---|---|
| L01 | Reiter, "A theory of diagnosis from first principles" (1987); de Kleer and Williams (1987). Summaries of consistency-based diagnosis | the vocabulary "consistent hypothesis" and "no consistent hypothesis"; weak-fault models, where supersets of diagnoses are diagnoses | V0 |
| L02 | fault detection and isolation: **fault isolability** from a fault signature matrix; structural analysis (e.g. Blanke et al.; Frisk, Krysander and Jung) | "a residual isolates fault i from fault j only if it is sensitive to one and not the other": the relevance notion for an attribution discriminator | V0 |
| L03 | Parikh, **relevance-sensitive axiom (P)** for belief revision (1999); full characterization in Aravanis, Peppas and Williams, JAIR (2019) | "revising by information about one compartment must not change the other compartment" | V0 |
| L04 | Kraus, Lehmann and Magidor (1990): preferential and rational consequence, **cautious** and **rational monotony**, and the **irrelevance problem**, as summarized in the Stanford Encyclopedia of Philosophy entry "Non-monotonic Logic" | the monotonicity and irrelevance terms in Part 12 | V0 |
| L05 | Kleene's **strong three-valued logic** (K3) and SQL NULL semantics | the criterion for missing evidence: unknown is neither true nor false | V0 |
| L06 | Chen, Cheung and Yiu, metamorphic testing (1998); Segura, Fraser, Sánchez and Ruiz-Cortés, "A survey on metamorphic testing", IEEE TSE (2016); Chen et al., ACM Computing Surveys 51(1) (2018) | metamorphic relations; invariance relations | V0 |
| L07 | Claessen and Hughes, "QuickCheck" (ICFP 2000); MacIver, Hypothesis and integrated shrinking. **Installed version 6.168.0** read by import in the repository environment | the property-based strategy in `METAMORPHIC_TEST_PLAN.md` §3 | V0 (papers); V4 (installed version) |
| L08 | Feathers, *Working Effectively with Legacy Code* (2004): **characterization tests** | tests that pin current behaviour before a change | V0 |
| L09 | empirical studies of exception-handling anti-patterns: "catch and do nothing", **error hiding**, "information swallowed" faults | the classification of the predicate catch-all | V0 |
| L10 | Denœux, cautious conjunctive rule for non-distinct evidence, Artificial Intelligence (2008): **idempotent** combination | duplication and correlated evidence. The same source as the architecture package's S060 | V0 |
| L11 | de Kleer, ATMS (1986); de Kleer and Williams, GDE (1987): assumption labels | dependency-aware counting (not proposed here). The same source as the architecture package's S061 | V0 |

## 2. Repository sources (read or executed in this audit)

| path | what | level |
|---|---|---|
| `csia/v2/attribution.py`, `localization.py`, `signatures.py`, `evidence.py`, `engine.py`, `explanation.py`, `plugin_runtime.py`, `api.py`, `domains/*.py`, `profiles/*.py` | frozen v2 Phase C code. The four reasoning files are byte-identical to freeze commit `50c5d35` | V4 |
| `engineering/v2/CROSS_DOMAIN_RELATION_SPEC.md` | the UNIQUE rule as specified (§2) | V4 |
| `engineering/v2/V2_PHASEC_GATE.json`, `LOCALIZATION_RESULTS.csv`, `V2_SCENARIO_RESULTS.json`, `V2_CHATGPT_REVIEW_REPORT.md` | recorded Phase C results the corrections would disagree with | V4 |
| `csia_assurance/firewall.py` | the "active witness against every competitor" rule, reused by C1 | V4 |
| `research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py`, `stage1_evidence.py`, `stage2_score.py` | how XSYS-001 used v2; imported and called unchanged for the replay | V4 |
| `research/xsys_001_confirmatory_campaign/stage1/STAGE1.json`, `stage2/RESULTS.json`, `stage2/PRIMARY_RESULT_RECORD.json` | sealed data; read only; SHA-256 of STAGE1.json checked against its seal | V4 |
| `tests/test_v2_framework.py`, `test_v2_localization.py`, `test_v2_scenarios.py`, `test_v2_api_ledger.py`, `test_v2_domains.py`, `test_phase_c_freeze.py` | the coverage audit | V4 |
| `docs/CURRENT_PROGRAM_STATE.md`; `PAPER_I_SCOPE_GUARD.md`; `papers/csia_systems/main.tex` | governance; what the public claims depend on | V4 |

## 3. Search log (this phase)

| id | query | produced |
|---|---|---|
| Q1 | `fault isolability fault signature matrix residual insensitive to both faults cannot isolate structural analysis` | L02 |
| Q2 | `Parikh relevance-sensitive belief revision language splitting axiom irrelevant information should not change beliefs` | L03 |
| Q3 | `consistency-based diagnosis Reiter adding observations monotonic diagnoses weak fault model conflicts` | L01 |
| Q4 | `metamorphic testing survey Segura Chen metamorphic relations permutation invariance` | L06 |
| Q5 | `KLM nonmonotonic inference cautious monotonicity rational monotonicity irrelevance problem Lehmann Magidor` | L04 |
| Q6 | `Kleene strong three-valued logic unknown conjunction missing values SQL NULL "all" quantifier unknown` | L05 |
| Q7 | `exception swallowing empty catch block anti-pattern empirical study error handling bugs` | L09 |
| Q8 | `characterization tests legacy code Feathers pin down current behavior before changing` | L08 |
| Q9 | `QuickCheck Claessen Hughes 2000 property-based testing Haskell; Hypothesis Python property-based testing MacIver shrinking` | L07 |

L10 and L11 were searched in the architecture phase (its AQ7 and AQ8) and are
re-cited here.
