# THE TWO PAPERS, AND WHY THEY ARE TWO

Brief PART D.

**Neither paper depends on CSIA v2 or on Forge.** v2 may appear in FUTURE WORK
only, and `tools/publication/phase_guard.py` fails a Phase-I build that
references a later phase.

---

## The mathematical paper

**Posterior Distortion from Hypothesis-Dependent Validity Gating in Runtime
Diagnosis.** `papers/gate_conditioning/`, formal core in
`research/math-paper/FORMAL_CORE.md`.

**What it answers:** *why* omitted or hypothesis-dependent validity can
distort interpretation.

A runtime diagnostic layer decides, per tick, which evidence is *applicable*.
That decision is a coarsening mechanism the system designed for itself. Write
`q` for the posterior from active evidence alone and `p` for the one actually
produced; then `p = q · w / E_q[w]`, every pairwise log-posterior ratio picks
up an additive, evidence-independent offset `log(w_a/w_b)`, and when no active
term distinguishes a pair their ratio is **pinned to the prior** for as long
as the gate stays shut.

Its scope is algebra plus one structural condition. It contains no vehicle, no
autopilot and no flight. Every proposition in it is labelled **KNOWN**
(`NOVELTY_AUDIT.md`); the contribution is the runtime formulation, the
static-checkability of the condition, and the pointer to a system that fails
it.

## The systems paper

**Self-Occlusion and Threshold-Crossing Persistence in a Cross-Sensor
Diagnostic Layer** — *Source-Grounded Characterization and Current-Stack
Replication.* `papers/csia_systems/`.

**What it answers:** *where* the mechanism occurs in a real implemented
diagnostic layer, and what it costs.

Mechanism A: validity/freshness gating removes the discriminating evidence
between hypotheses. Measured on a deployed layer, with an independent checker
that imports none of the production analysis and agrees 378,000/378,000
(`research/systems-paper/MECHANISM_A.md`).

Mechanism B: history/persistence materially changes threshold-crossing
behaviour, and the effect depends on the threshold and the scenario. Measured
across four arms (`MECHANISM_B.md`).

Its scope is measurement of one deployed layer, on a frozen baseline, with
two scope corrections the project's own campaign forced.

## The seam between them

```
    MATHEMATICAL PAPER                    SYSTEMS PAPER
    ------------------                    -------------
    why it can happen                     where it does happen
    algebra + one condition               measurement of one layer
    no vehicle                            one multirotor, one bench
    P3: pinned to the prior         -->   200 consecutive ticks, measured
    C3: concentration != support    -->   SUPPORT_LOST_FOR_REQUIRED_INFORMATION
    the condition is static         -->   the checker evaluates it from a
                                          committed YAML table
```

The systems paper may **cite** P3 and C3 as the closed-form account of what it
measures. The mathematical paper may **cite** the measurement as an
implemented instance. Neither is load-bearing for the other:

- delete the systems paper and the mathematical results still hold; they lose
  their worked instance;
- delete the mathematical paper and the systems measurements still stand; they
  lose their closed-form explanation.

## What each may NOT do

| | |
|---|---|
| the mathematical paper may not | claim any proposition is new; claim sharpness for P6; use "confidence" for a posterior; cite the unlocated bounded-likelihood-ratio reference |
| the systems paper may not | make an observability claim; call a bench number a field number; conflate the WP-C4 arms with the `csia/scenarios.py` catalogue; quote the 18.4% figure without its 5.1-point startup decomposition |
| **neither** may | depend on CSIA v2, on Forge, or on any Phase-II ArduCopter 4.8 result |

## Shared artifacts, and who owns them

| artifact | owner | the other paper's use |
|---|---|---|
| `research/math-paper/results/proof_audit.json` | mathematical | cited by the systems paper for P3 |
| `research/systems-paper/results/checker_agreement.json` | systems | cited by the mathematical paper as the implemented instance |
| `research/formalization/diagnostic_signature_matrix.yaml` | shared | the structural input to both |
| `docs/math/PROOF_STATUS.md` | mathematical, **for the e-process work (T-1…T-5)** | **not** the register for P1–P6; `FORMAL_CORE.md` is |

**A naming trap, recorded.** `docs/math/PROOF_STATUS.md` governs the
*anytime-valid evidence* claims (T-1…T-5, e-processes, Ville's inequality).
It does **not** govern P1–P6. Those are two bodies of work that both live
under "the mathematical paper", and a reader who assumes one register covers
both will find contradictions that are not there. Similarly
`docs/research/PAPER1_EMPIRICAL_SECTION.md` belongs to the **mathematical**
paper despite its filename, as `RESEARCH_STATE.md` §3.3 records.

## Order of work

**Systems paper is priority #1**, mathematical paper #2, per the management
decision. The systems paper's blocker is a bibliography nobody can verify from
this environment; the mathematical paper's blocker is that its manuscript does
not exist. Neither is a research problem.
