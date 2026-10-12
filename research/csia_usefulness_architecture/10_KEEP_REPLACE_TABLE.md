# Phase 21: keep, refactor, replace, generalize, deprecate, remove, add

CSIA usefulness architecture review, 2026-09-29. Sources `Snnn` are defined in
`SOURCES.md`.

**The full table is `ARCHITECTURE_DECISIONS.csv`.** It has one row per
mechanism and every column the brief requires:

- current state;
- decision;
- why;
- evidence;
- existing method to reuse;
- migration risk;
- backward-compatibility impact;
- test required;
- priority.

**Rows.** AD-01 to AD-29 are the 29 mechanisms the brief lists, in its
order. AD-30 to AD-34 are mechanisms the audit found and that needed a
decision.

## 1. Summary

| decision | count | mechanisms |
|---|---|---|
| KEEP | 10 | temporal trust logic (v1); function graph; signature matrix; ambiguity semantics; latency logic; C runtime; Python reference; FORGE boundary; minimum resolving subsets; e-process research |
| REFACTOR | 6 | v2 localization; v2 attribution; evidence predicates; SupportCertificate (becomes a decision trace); UNSUPPORTED semantics; the parallel state vocabularies |
| GENERALIZE | 9 | EvidenceRecord (wrapped); temporal-window handling (becomes contracts); monitor interfaces (per-producer); ledger; configuration handling; dependency handling; monitor health; provenance; downstream API (2.1.0) |
| ADD | 7 | source identity; estimator-mode awareness; controller-mode awareness; correlation policy; invalidation; expiration; disagreement handling |
| REPLACE_WITH_EXISTING_METHOD | 1 | the planned bespoke dual-timescale CUSUM (the textbook CUSUM bank and autopilot drift monitors already exist) |
| DEPRECATE | 1 | the v1 opt-in actuation path, for the target architecture only; the frozen code is untouched |
| REMOVE | 0 | — |

## 2. Why nothing is removed

No mechanism met all three removal criteria:

- **unvalidated**;
- **harmful** as it stands;
- **unused**.

The mechanisms closest to removal each fail at least one:

- **The SupportCertificate.** It is experimental and had two recorded
  defects, both fixed. Its content is useful, so it is refactored into a
  trace rather than removed (AD-08).
- **The parallel vocabularies.** They carry research results, so they are
  mapped rather than deleted (AD-31).
- **The actuation path.** It is frozen code, so it is deprecated rather than
  removed (AD-30).

Removing validated or frozen work because the new architecture looks cleaner
is exactly what the brief forbids.

## 3. The decisions that carry the most weight

1. **AD-04, EvidenceRecord: GENERALIZE by wrapping.** The frozen record is
   carried **unchanged** inside an envelope. That one choice is what lets
   every other change happen outside the frozen core (S045) and keeps every
   existing consumer and test working.
2. **AD-02 and AD-10, localization and UNSUPPORTED: REFACTOR, not REPLACE.**
   The set-elimination algorithm is cheap, validated and matches
   consistency-based diagnosis (S032). Only its inputs (admissibility,
   independence) and its output names change. Replacing it with a Bayesian
   or belief-function engine would re-import scores that v2 rejected for
   good reasons (S001).
3. **AD-03, attribution: REFACTOR.** The probe in this review showed UNIQUE
   can be licensed by an unrelated record (S044a). That is a correctness
   issue in frozen code, and it is the highest-severity finding of the
   audit (FM-20).
4. **AD-11, AD-20, AD-21, AD-24, AD-25: the admissibility block.** These are
   the XSYS-001 lesson turned into mechanisms: windows, controller and
   estimator context, invalidation and expiry.
5. **AD-32: REPLACE_WITH_EXISTING_METHOD.** The one place where the plan was
   to build something bespoke that already exists (S030).

## 4. Priorities

| priority | meaning | rows |
|---|---|---|
| P0 | Horizon 1; needed for the first experiment or fixes a HIGH-severity silent failure | AD-02, AD-03, AD-04, AD-10, AD-11, AD-21, AD-22, AD-24, AD-25, AD-29 |
| P1 | Horizon 1-2 | AD-05, AD-06, AD-08, AD-13, AD-17, AD-18, AD-19, AD-20, AD-23, AD-26, AD-27, AD-28, AD-30 |
| P2 | Horizon 2 | AD-07, AD-09, AD-12, AD-15, AD-31, AD-32 |
| P3 | Horizon 3 or no action | AD-01, AD-14, AD-16, AD-33, AD-34 |

## 5. The freeze

Every REFACTOR, GENERALIZE and ADD above is designed to live **outside**
`csia/` and `csia/v2/`, as an overlay that reads frozen outputs. That shape
is permitted today for research by the cross-system exception (S029).

Making the new path the **default** requires both of these:

- the engineering freeze to lift, which needs both paper submission-candidate
  tags (S029);
- gates D-F (`13_MIGRATION_AND_VALIDATION.md`).

AD-20 (estimator-mode awareness) additionally touches a domain the freeze
forbids ("estimator domain"). It reads estimator status as context and adds
no estimator plugin. Whether that reading is permitted is an **owner
decision**, flagged here rather than assumed.
