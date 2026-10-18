# What the simulator can and cannot decide

## The claim this file exists to bound

`tools/research/active_evidence_campaign.py` reports
`NO_COUNTEREXAMPLE_IN_THIS_GRID` for the prediction that a probe meeting
three closed-form conditions resolves a stated resistance change. That
sentence is exactly what it says and nothing more.

## What "independent" means here

`csia_components/simulate.py` was written first, for MX-036, to test a
different set of claims, by a path that contained no error model. It carries
a closed-loop PI controller, state of charge falling as charge is drawn, a
thermal model, quantised sampling and four independent noise channels — none
of which appear in the derivation, and one of which (the closed loop)
produced the finding in `DERIVATIONS.md` §6 that the derivation did not
anticipate.

**That is a weak sense of independence.** Both the plant and the derivation
assume a linear terminal-voltage law `V = E - I R`. An error common to both
cannot be caught by comparing them. Specifically, agreement here does NOT
rule out:

| excluded | why it matters |
|---|---|
| RC / diffusion dynamics | a real pack's terminal voltage depends on recent current history, not only present current. A probe whose timescale is near the RC time constant would see a frequency-dependent apparent resistance that neither model has |
| temperature coupling | `R` falls as cells warm. A probe that itself heats the pack changes the quantity it is measuring |
| cell imbalance | one weak cell in series does not behave like a lumped resistance |
| state-of-charge curvature | the drift is modelled as linear over the window. Near an empty pack the OCV curve is not linear over 12 s |
| non-Gaussian or correlated noise | both sides assume independent Gaussian samples. A shunt with 1/f noise breaks the sqrt(N) scaling in the variance condition |
| actuator authority limits | the plant clips duty to [0, 2]. A real vehicle near its thrust limit cannot execute the commanded probe at all, and would return a smaller excitation than requested with no flag |
| anything about safety | no envelope here is certified, measured, or reviewed by anyone who owns a vehicle |

## Statistical limits of the campaign itself

* the "resolved" verdict compares two populations of **5 seeds**, so the
  scatter estimate has 4 degrees of freedom and roughly 35% relative
  sampling error. Re-running the one false-negative cell at 5, 20 and 40
  seeds gave scatters of 0.00119, 0.00134 and 0.00129 — the verdict is
  stable, but a cell whose gap-to-scatter ratio sits near 3 could flip;
* 28 cells, 4 deltas, 7 probes, one plant, one platform mass, one hover
  condition. The grid brackets the discriminating band by construction but
  it is small;
* the campaign scores a DIFFERENTIAL comparison — the same probe on two
  packs — so any bias common to both runs cancels. It is therefore
  structurally incapable of catching a bias error, which is why the
  realisation measurement in `DERIVATIONS.md` §6 had to be taken
  separately. It was, and it found one.

## What would change the verdict

Hardware. Nothing in `research/active_evidence/` is above evidence tier
**E0** (desktop simulation). The repository's tier ladder runs E0 to E5 and
this work has not reached E1.
