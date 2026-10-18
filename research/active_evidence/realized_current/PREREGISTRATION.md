# Realized-Current Excitation Certificate — preregistration

**Committed BEFORE any outcome-producing search of this campaign.**
`git log` on this file against the results commit is the audit trail.

Base: `a0209cb` (MX-037) and `44712a8` (MX-038), both ancestors of HEAD.

## 0. Authorization and quarantine

`OWNER_AUTHORIZATION.md` in this directory carries the program owner's
authorization verbatim, and records that
`docs/CURRENT_PROGRAM_STATE.md` §1's energy-domain prohibition **stands
unchanged and was not edited**. This is a narrow exception on one research
branch. Every result here is **post-freeze, research-only, quarantined**.

## 1. What is already known, and is therefore NOT preregistered

Declared so that nothing below can be presented as a prediction that was in
fact a measurement. All of this was measured before this file existed:

1. **MX-037.** A probe meeting three closed-form necessary conditions
   resolves a stated resistance change; 28 cells, 20 met-and-resolved, 7
   failed-and-unresolved, **0 false positives**, 1 conservative false
   negative.
2. **MX-037, AE-F5.** Command palindromy does **not** survive the closed
   loop. Realized lever arms reached -1.138 s against a commanded ~1e-16.
3. **MX-038.** Over an 8-hypothesis bank, active probing was a **net loss**
   against passive: 6 unresolved against 5, summed over a three-point
   magnitude bracket, with every active arm identical while costing 0.00 to
   4.50 A·s.
4. **MX-038 mechanism.** Every action opens `source_impedance` and closes
   `effort_drift`.
5. **Measured this session, before this file.** Removing `effort_drift` from
   the signature **reverses** MX-038: passive goes to 9 unresolved while
   every active arm stays at 6. **The MX-038 negative was an artifact of one
   stationarity-gated relation.** This is prior knowledge here, not a
   prediction.
6. **Still true after that reversal:** the free mission manoeuvre arm ties
   the selected probe at 6. Probing still does not beat waiting.

## 2. Hypotheses

`H1 — command/realization gap.` A probe meeting symmetry and excitation
conditions in command space can fail them in realized-current space under
closed-loop lag. *(Partly known from AE-F5; restated so the RCEC's ability to
DETECT it is what is tested.)*

`H2 — compensable gap.` At least one deterministic closed-loop-aware
strategy among P2, P3, P4 reduces realized drift coupling `|S_tI/S_II|`
while preserving or increasing realized `S_II`, relative to P1.

`H3 — diagnostic value.` On locked seeds, at least one realized-current
strategy separates nominal from target `R0` rise more often than P0, P1 and
P5 at matched duration and comparable energy.

`H4 — conservative certification.` No `CERTIFIED_IN_MODEL` is issued when
realized telemetry fails the excitation or error requirements, **even when
the fault causes a visually large voltage change**.

`H5 — open-set integrity.` Omitted dynamic faults return
`UNKNOWN_OR_MODEL_MISMATCH` or ambiguity, never a confident `R0` label.

`H6 — mission comparison.` If an ordinary mission manoeuvre produces
equivalent information at lower cost, the correct answer is to wait.

## 3. Falsification conditions, fixed here

The claim is falsified or sharply narrowed if any of these holds:

* P2 to P4 do not outperform P1 after matched-cost comparison;
* gains disappear under the one-RC model;
* selected commands satisfy predicted but not realized conditions;
* a true modeled hypothesis is excluded;
* an unknown fault is forced into a known label;
* any declared constraint is violated;
* success depends on one seed, one phase, or one exact plant parameter;
* active probing is not better than waiting for a mission manoeuvre;
* the certificate accepts pure-noise excitation;
* drift cancellation depends on future samples unavailable online;
* safety clipping invalidates the information claim but the certificate
  remains valid.

## 4. Primary outcomes, defined before measurement

Per arm and per scenario:

| outcome | definition |
|---|---|
| realized `S_II` | `sum (I_k - Ibar)^2` on the **measured** current over the evaluation window |
| realized drift coupling | `S_tI / S_II`, seconds |
| drift bias | `d_max * |S_tI/S_II|`, ohms |
| resolution margin | `c*|dR_target| - (|B_total| + q*SE)`, ohms |
| certificate state | one of the ten declared states, never collapsed to pass/fail |
| incremental energy | amp-seconds of excess charge over holding station; **zero by definition for P0 and P6** |
| false certification | `CERTIFIED_IN_MODEL` issued where the target change is not in fact resolvable |

## 5. Fixed constants, never swept

`c = 0.5` (resolution fraction), `k_sigma = 3.0`, `S_II_min` and
`gamma_tI_max` derived from the declared error budget rather than chosen,
locked seeds `{7000, 7100, ..., 7900}`, development seeds `{0..400}`,
calibration seed `999`. **No seed crosses a partition.**

## 6. Arms

P0 passive; P1 naive palindromic command; P2 delay-compensated command; P3
model-predictive waveform shaping; P4 feedback moment-balancing; P5
random-safe matched; P6 ordinary mission manoeuvre; P7 oracle
realized-current waveform, **analysis only, never presented as executable**.

## 7. Controls: the campaign is invalid unless all pass

The seventeen controls listed in the work order, implemented in
`tests/test_rcec.py` and in the campaign's own control pair. Named here so a
missing one is visible: constant current fails excitation; an analytically
time-orthogonal current passes drift coupling; pure noise cannot create
excitation; **a large voltage step at constant current does not certify**;
an adequate waveform resolves an obvious change; an inadequate one is
rejected; an unsafe candidate is denied; a clipped waveform is re-evaluated
and cannot inherit a proposal certificate; an aborted waveform cannot be
complete; an omitted fault does not become a known label; every swept
parameter changes its intended output; RNG streams stay aligned; windows lie
inside the horizon; units are checked; missing configuration is
not-comparable rather than defaulted; mutation tests kill `S_tI` sign
reversal, current-noise removal, reversed safety inequalities, forced-best
action and stale-certificate reuse; derived reports fail when raw artifacts
are perturbed.

## 8. What this campaign cannot establish, stated in advance

Fixed here so it cannot be softened after a good result:

1. **robust operation across real battery chemistries** — no real cell data
   exists in this repository and none is obtainable from this host. Every
   battery parameter below is synthetic and normalized;
2. **reliable behaviour on hardware** — E0, simulation only;
3. **novelty relative to the literature** — scholarly access is denied by
   organization policy, rechecked this session;
4. **production integration** — forbidden by the authorization above;
5. **any formal safety guarantee** — Monte Carlo satisfaction of a
   constraint is empirical evidence, not a proof.

## 9. Status

PREREGISTERED. Not yet run at the time of this file's commit.
