# FUTURE RESEARCH FRONTIER

# POSSIBLE NOVEL CONTRIBUTION — NOT ESTABLISHED

Brief PART G. **Nothing here is claimed as novel. Nothing here is
implemented. Nothing here may be implemented.**

Two working concepts are recorded so they are not lost, together with the
literature each must be reduced against before anyone writes a line of code.
On present evidence **both are probably substantially covered**, and the
honest expectation is `SUBSUMED` or `ADJACENT`, not `GAP`.

---

## 1. Working concept — EVIDENCE-CONSTRAINED RESILIENCE UNDER NON-IDENTIFIABILITY

### Statement

At runtime let

    H_t  =  the hypotheses not ruled out by the evidence available at time t
    C    =  the candidate system configurations

**Candidate robust requirement.** A configuration `c ∈ C` is *admissible* only
if it is safe for **every** hypothesis in `H_t`.

The motivation is direct from what CSIA already measures: a recovery
configuration must not assume a uniquely identified cause when the diagnosis
is **structurally ambiguous**. Phase C's matched set B is the worked case —
five candidate causes reduce to two that no measurement on that airframe can
separate, and a reconfiguration that assumed "mechanical" would be wrong half
the time by construction.

### Why it is probably not new

| prior art | overlap | status |
|---|---|---|
| **Safe diagnosability** (Paoli & Lafortune, *Automatica* 2005) | detection must occur before a forbidden string is executed, so reconfiguration can be forced in time. The "act only when the evidence permits" structure is theirs | `CANDIDATE_UNVERIFIED` |
| **Robust / fault-tolerant control under uncertain diagnosis** (Blanke et al.) | acting safely across a set of possible faults is the classical FTC problem | `CANDIDATE_UNVERIFIED` |
| **Matei et al., ACM TCPS 8(1), 2024, DOI 10.1145/3631612** | diagnosis + prognostics + reconfiguration, *with interventions generated specifically to disambiguate uncertain diagnosis solutions* | `CANDIDATE_UNVERIFIED` |
| **Active fault diagnosis / active model discrimination** | designing inputs to increase separability subject to safety constraints | `CANDIDATE_UNVERIFIED` |

The only thing that looks different is the *source* of `H_t`: CSIA derives it
from **runtime evidence availability** — which terms are currently applicable
— rather than from language-level diagnosability computed offline. Whether
that difference is substantive is **not established** and is exactly what the
reduction must decide.

### What would have to be true for this to be a contribution

1. The existing literature computes admissibility against a fault set fixed at
   design time, and cannot express a hypothesis set that *shrinks and grows
   with gate state at runtime*. **Unverified.**
2. The runtime `H_t` is cheap to compute. **This one is established**:
   `research/systems-paper/independent_checker.py` computes it from a set
   symmetric difference, and localization costs 45.8 µs/tick in v2.
3. Admissibility over `H_t` is decidable at runtime for realistic `|C|`.
   **Unverified**, and this is where Z3 or CP-SAT would be used — not a
   hand-written solver.

## 2. Working concept — RECOVERY-INDUCED SELF-OCCLUSION

### Statement

> Can a recovery or reconfiguration remove the evidence required to verify its
> own correctness?

The question is a direct generalisation of what the systems paper measures. In
CSIA the *fault* removes the evidence that would name it. The frontier
question is whether a *response* can do the same thing: a reconfiguration that
disables, re-routes or de-weights a channel may destroy the term that would
have told anyone whether the reconfiguration worked.

Concretely, and this is checkable with machinery that already exists: let
`ACTIVE(c)` be the active term set under configuration `c`. Then a
reconfiguration `c → c'` is **self-occluding for the pair `(a,b)`** if

    ( LOW(a) △ LOW(b) ) ∩ ACTIVE(c)   ≠ ∅
    ( LOW(a) △ LOW(b) ) ∩ ACTIVE(c')  =  ∅

i.e. the move destroys the last term that distinguished the hypothesis it was
responding to from its rival. That is the same predicate the independent
checker already evaluates, applied to a *counterfactual* active set instead of
an observed one — which is why this is the cheaper of the two concepts to
investigate and why it should be investigated first.

### Why it is probably not new either

The general shape — an action that degrades observability — is the territory
of observability-aware control, dual control, and the exploration/exploitation
tension in active diagnosis. The specific naming may be new; the phenomenon
almost certainly is not.

**Do NOT call either idea novel.** The working term
*recovery-induced self-occlusion* is a label for a question, not a claim of
discovery.

## 3. Mandatory reduction before any implementation

Every item in `forge/PRIOR_ART_REQUIRED.md` §§3–4, plus:

- fault-tolerant control
- safe diagnosability
- safe controllability
- reconfigurability
- ambiguous-diagnosis recovery
- active fault diagnosis
- runtime certification
- conditional safety certificates
- digital-twin resilience
- autonomic computing
- dynamic reconfigurable discrete-event systems
- **System Resilience through Health Monitoring and Reconfiguration, ACM TCPS
  2024, DOI 10.1145/3631612**

Each must end with `SUBSUMED`, `ADJACENT` or `GAP` **written down**, and a
`GAP` needs the closest work located, read, and its specific difference
stated. "I did not find it" is not a gap.

## 4. Status

| | |
|---|---|
| implemented | **no** |
| authorised for implementation | **no** |
| claimed as novel | **no** |
| prior-art reduction complete | **no** |
| blocks either paper | **no** — neither paper depends on this, and v2 itself may appear only in FUTURE WORK |

The gate is `docs/CURRENT_PROGRAM_STATE.md`: both submission-candidate tags,
then the reduction, then — and only then — a decision about code.
