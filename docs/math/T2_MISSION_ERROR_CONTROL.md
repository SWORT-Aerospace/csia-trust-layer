# T-2 — Mission-Level Error Control (DESIGN, not proof)

**Status: OPEN.** This document scopes the theorem; nothing here is claimed.

## Problem
One flight monitors H hypotheses across P phases with restarts and recovery.
Per-hypothesis Ville bounds do not compose into a mission guarantee.

## Budget
`alpha_mission` allocated over hypotheses × severity classes × phases.
Candidate: fixed allocation matrix A with Σ A ≤ alpha_mission (valid trivially
by union bound); refinement via e-BH (Wang–Ramdas), which controls FDR under
ARBITRARY dependence — the right property since hypotheses share residuals.

## Restarts (the hard part — informed by T-1's measured counterexample)
- Every restarted e-process MUST condition on its first post-restart
  observation (measured violation 0.196 otherwise; pinned by test).
- A restart consumes budget: alert level for restart r uses alpha_r with
  Σ_r alpha_r ≤ the hypothesis's allocation (alpha-spending). Candidate
  schedule: alpha_r = alpha_h · 2^-(r+1) · normalization.
- **Unused-budget recycling is PROHIBITED until formally justified**: naive
  recycling re-introduces the optional-stopping problem the e-process exists
  to solve. If justified later, only via a predictable spending sequence.

## Context changes
Context transition = new nominal model. Options to evaluate: (a) parallel
per-context processes with per-context budget; (b) one process with
context-conditioned e-values (valid if each factor is conditionally valid in
its context — regime cell measured OK at 0.0475). (b) is preferred; proof
obligation: predictability of the context label.

## Recovery / re-arming
After an alert resolves, re-arming starts a NEW process under the restart
budget; evidence from the resolved episode is ledgered, never carried forward
(carrying it forward double-counts against the new null).

## Proof obligations
1. Union-bound baseline (should be immediate) — target PROVED.
2. e-BH applicability with shared residuals — cite + verify conditions.
3. Spending-schedule validity under predictable restarts.
4. Counterexample: budget recycling breaking the mission bound (simulate).
5. Falsification harness: multi-hypothesis, multi-restart null sweep
   extending tools/simulate_anytime_validity.py.
