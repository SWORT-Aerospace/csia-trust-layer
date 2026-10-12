# Prior-art matrix — AI-assisted contract synthesis with deterministic verification

Items 3–5. Searched August 2026, **before** the prototype was built, because
item 3 says to kill the direction first.

## Method, and its limit

Web search returning titles, venues and extracted snippets. **Full-text
retrieval is blocked by this environment's egress policy for every scholarly
host tried** (`dl.acm.org`, `arxiv.org`, `link.springer.com`,
`conf.researchr.org` — all `EGRESS_BLOCKED`). Every row rests on title, venue
and snippet, not on a reading of the paper.

That cuts one way: **it can only cause prior art to be understated.** The
`KNOWN/SUBSUMED` findings below are therefore safe; the "surviving
difference" column should be assumed too generous.

## Headline

**The integrated architecture this package proposes is already published, and
was published at a top software-engineering venue in 2025.**

> **Validating Network Protocol Parsers with Traceable RFC Document
> Interpretation** — ISSTA 2025 / *Proc. ACM Softw. Eng.*

Per its abstract and the returned snippets, it: uses LLMs to translate RFC
documents into formal protocol message specifications; explicitly treats the
LLM output as a **quasi-oracle that may contain hallucinations**; validates
real parser implementations in C, Python and Go against it; and — decisively
— **traces each inconsistency back to the relevant RFC section in order to
decide whether it stems from LLM hallucination or from a parser bug**. It
reports 69 bugs, 36 confirmed.

That is: docs → LLM-generated specification → independent verification →
counterexample localisation → **explicit separation of specification error
from implementation error**. Items 25 and 26 describe that separation as the
core of the proposed contribution. It exists.

## Item 5's kill condition, applied literally

> If close prior art already demonstrates: source/docs → LLM-generated
> evidence/status contracts → independent verification → counterexample
> localisation **on autonomous/cyber-physical interfaces**, mark
> KNOWN/SUBSUMED.

The ISSTA work is on **network protocols**, not cyber-physical interfaces,
and its specifications are **message formats**, not evidence/status
semantics. So the literal conjunction was not found in one paper, and the
kill condition does not fire on its own terms.

It is close enough that this should not be over-read. The architecture is
`KNOWN/SUBSUMED`; what was not found is that architecture pointed at
sensor-validity semantics in an autonomy stack. Per the previous package's
own conclusion about combinations of established techniques, that is a
domain instantiation, not a contribution.

## Matrix

Columns are item 4's A–J. **A** infers specs from code · **B** uses an
LLM · **C** targets data/status/provenance rather than functional
invariants · **D** targets autonomy/avionics/CPS · **E** independent
deterministic verifier · **F** minimal counterexamples · **G** first-
transformation localisation · **H** diagnostic/assurance consequence ·
**I** separates AI confidence from verification status · **J** evaluates
hallucinated contracts.

| Work | Year | Venue | Task | Output language | A | B | C | D | E | F | G | H | I | J | Closest overlap | Surviving difference |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Validating Network Protocol Parsers with Traceable RFC Document Interpretation** | 2025 | ISSTA / PACMSE | RFC → message-format spec → validate C/Python/Go parsers | protocol format spec | ✓ (docs) | ✓ | ✗ | ✗ | ✓ | partial | ✓ traceable to RFC section | ✗ | ✓ quasi-oracle framing | **✓ explicitly separates hallucination from parser bug** | **Total on the architecture, including the hallucination/implementation split** | message formats, not evidence-quality states; no CPS; no downstream consumer |
| **SpecSyn — LLM synthesis and refinement of formal specifications** | 2026 | arXiv | code → specs, refined by semantic-non-equivalent mutation and variant discrimination | program specs | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | partial | ✗ | Total on generate-and-verify with strength assessment | functional specs, not status semantics |
| **PROSPER — extracting protocol specifications using LLMs** | 2023 | ACM | RFC → protocol spec | protocol spec | ✓ | ✓ | ✗ | ✗ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | High on docs→spec extraction | no verifier loop |
| **FlowFSM / RAG-based protocol state-machine inference; PSMBENCH** | 2025 | arXiv | RFC → FSM, with a 1,580-page benchmark and 108 validated states | FSM | ✓ | ✓ | ✗ | ✗ | partial | ✗ | ✗ | ✗ | ✗ | ✗ | High on doc→formal-model extraction **and on building a reference set for it** | no implementation conformance |
| **Quokka; LLM loop-invariant synthesis with verifier feedback; VeriAct; SpecGen** | 2025–26 | arXiv | invariants/specs with iterative verifier-guided refinement | ACSL, Dafny, VeriFast | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ | ✗ | partial | ✗ | **Total on B3** — one-or-more verifier-feedback revisions is the standard loop | functional correctness, not evidence semantics |
| **AutoACSL** — LLM + CPG static analysis for ACSL | 2026 | arXiv | code → ACSL, static analysis in the loop | ACSL | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | High on hybrid symbolic+LLM extraction | — |
| **Daikon** | 2001– | Sci. Comput. Program. | dynamic invariant detection | invariant templates | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | n/a | ✗ | Total on non-AI specification mining, and the baseline every LLM paper compares to | no LLM, no status semantics |
| **SafePilot; agentic requirement formalization → UPPAAL SMC; RAFT** | 2026 | arXiv | NL requirements → temporal logic / model-checker queries for CPS | LTL/OCL/UPPAAL | ✗ (from requirements) | ✓ | ✗ | **✓** | ✓ | ✓ | ✗ | ✗ | partial | ✗ | Total on "LLM formalizes specs for a CPS and a model checker consumes them" | starts from written requirements, not from source; no sensor-status semantics |
| **Neuro-symbolic verification / automated-reasoning guardrails (e.g. ARc); neuro-symbolic verification for process control** | 2025–26 | Springer, industry | check LLM output against symbolic rules before it is acted on | logic | ✗ | ✓ | ✗ | partial | ✓ | ✗ | ✗ | ✗ | **✓** | **✓ this IS hallucination containment** | **Total on item 24's containment principle** | general-purpose guardrails, not contract synthesis |
| **ParDiff** | 2024 | OOPSLA | static differential analysis of protocol parsers | symbolic FSA | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | partial | ✗ | n/a | n/a | Total on cross-implementation differential comparison (cited in the previous package too) | no AI, no status semantics |

## Item 4's questions, answered

* **A** infer specs from code — **KNOWN/SUBSUMED**, since Daikon (2001).
* **B** with an LLM — **KNOWN/SUBSUMED**, a crowded 2024–26 literature.
* **C** targeting data/status/provenance rather than functional invariants —
  **NOT FOUND.** This is the one column with no hit. It is a domain gap, not
  a methodological one.
* **D** autonomy/avionics/CPS — **KNOWN/SUBSUMED** (SafePilot, RAFT, the
  UPPAAL work).
* **E** independent deterministic verifier — **KNOWN/SUBSUMED**.
* **F** minimal counterexamples — **KNOWN/SUBSUMED**.
* **G** first-transformation localisation — the ISSTA work localises to an
  RFC section; localising to a *pipeline stage* is the previous package's
  contribution, already assessed there as not novel.
* **H** diagnostic/assurance consequence — **NOT FOUND** attached to AI
  spec-mining. Also the thinnest gap the previous package found, and it did
  not survive scrutiny there either.
* **I** separating AI confidence from verification status — **KNOWN**, and
  named as such by the ISSTA quasi-oracle framing and by the guardrail
  literature.
* **J** evaluating hallucinated contracts — **KNOWN.** The ISSTA work's
  central mechanism.

**Two of ten columns are unoccupied, and both are about the domain rather
than the method.**

## What prior art kills outright

1. Any claim that AI-generated formal specifications are new. Crowded field.
2. Any claim that verifier-feedback refinement is new. Standard; one revision
   is the conservative end of the usual loop.
3. Any claim that treating LLM output as a fallible oracle is new. ISSTA 2025
   names it *quasi-oracle*.
4. Any claim that separating hallucination from implementation bug is new.
   ISSTA 2025 does exactly this, by tracing to the source document.
5. Any claim that hallucination containment via symbolic checking is new.
   Neuro-symbolic guardrails.
6. Any claim about building a reference set for doc-derived specifications
   being new. PSMBENCH.

## What survives, stated at its true size

A domain instantiation: pointing an established architecture at
**sensor evidence/status semantics in an autonomy ingest path**, and asking
whether the AI beats a mechanical baseline there.

`CHATGPT_REVIEW_REPORT.md` answers that question, and the answer is no — for
a reason that has nothing to do with prior art and is the most useful thing
in this package.

## Not searched, and it should be

* The MAVLink and DDS communities' own tooling for schema-driven validation.
* LLM-based extraction of *units* and *frames* (a sibling problem with the
  same shape and a much larger literature).
* Whether any RV-for-ROS tool has been pointed at quality metadata.
* IEC 61508 / DO-178C tool-qualification treatment of AI-assisted spec
  generation — the question a certification authority would ask first.

## Sources

Snippet-level only, per the method note.

- [Validating Network Protocol Parsers with Traceable RFC Document Interpretation (ISSTA 2025)](https://conf.researchr.org/details/issta-2025/issta-2025-papers/77/Validating-Network-Protocol-Parsers-with-Traceable-RFC-Document-Interpretation)
- [same, PACMSE](https://dl.acm.org/doi/10.1145/3728955)
- [SpecSyn: LLM-based Synthesis and Refinement of Formal Specifications](https://arxiv.org/abs/2604.21570)
- [PROSPER: Extracting Protocol Specifications Using Large Language Models](https://dl.acm.org/doi/10.1145/3626111.3628205)
- [An Agentic Flow for Finite State Machine Extraction using Prompt Chaining](https://arxiv.org/abs/2507.11222)
- [RAG-based LLM Evaluation for Protocol State Machine Inference](https://arxiv.org/abs/2502.15727)
- [Quokka: Accelerating Program Verification with LLMs via Invariant Synthesis](https://arxiv.org/pdf/2509.21629)
- [Guiding LLM-based Loop Invariant Synthesis via Feedback on Local Reasoning Errors](https://arxiv.org/pdf/2605.17914)
- [VeriAct: Agentic Synthesis of Correct and Complete Formal Specifications](https://arxiv.org/pdf/2604.00280)
- [AutoACSL: Synthesizing ACSL Specifications by Integrating LLMs with CPG-Based Static Analysis](https://arxiv.org/pdf/2606.20969)
- [Evaluating the Ability of LLMs to Generate Verifiable Specifications in VeriFast](https://arxiv.org/pdf/2411.02318)
- [The Daikon system for dynamic detection of likely invariants](https://www.researchgate.net/publication/222412498_The_Daikon_system_for_dynamic_detection_of_likely_invariants)
- [SafePilot: A Framework for Assuring LLM-enabled Cyber-Physical Systems](https://arxiv.org/html/2603.21523v1)
- [Towards an Agentic LLM-based Approach to Requirement Formalization from Unstructured Specifications](https://arxiv.org/html/2604.18228v1)
- [LLM-Based Property-Based Test Generation for Guardrailing Cyber-Physical Systems](https://link.springer.com/chapter/10.1007/978-3-032-07132-3_3)
- [A Neurosymbolic Approach to Natural Language Formalization and Verification](https://arxiv.org/html/2511.09008v2)
- [Neuro-Symbolic Verification of LLM Outputs for Data-Sensitive Domains](https://link.springer.com/chapter/10.1007/978-3-032-32335-4_30)
- [ParDiff: Practical Static Differential Analysis of Network Protocol Parsers (OOPSLA 2024)](https://dl.acm.org/doi/10.1145/3649854)
