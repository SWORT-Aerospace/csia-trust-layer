# Active evidence acquisition — preregistration

**Committed BEFORE any run of `tools/research/active_evidence_campaign.py`.**
`git log` on this file against the results commit is the audit trail. The
grid, the predictions, the tolerances, the classification rule and the
stopping rule are fixed here so that a result cannot be rescued afterwards by
widening any of them.

**Nothing in the frozen v1 core is modified by this work.** `FROZEN_PATHS` —
`csia/trust_engine`, `csia/diagnosis`, `csia/runtime/online.py`,
`csia/runtime/failsafe.py`, `csia/scenarios.py`, `csia/profiles.py` — are not
read, not imported and not edited by any module in `csia_active_evidence/`.

## 0. A governance conflict, recorded rather than routed around

`docs/CURRENT_PROGRAM_STATE.md` §1 lists **energy domain** among the
FORBIDDEN work areas while the dual-paper freeze holds, and that file states
it governs where documents disagree. The anchor problem here is pack internal
resistance, which is the energy domain on any reading.

This work proceeds on the program owner's explicit instruction, and the
conflict is recorded here rather than resolved quietly. What follows is the
narrowing that keeps it inside the spirit of §1:

* no frozen path is touched, and no frozen behaviour changes;
* nothing in `csia/` is modified, added to, or imported for modification;
* no product claim, no readiness change, no paper claim, no figure, no row
  in `research/systems-paper/CLAIMS.csv` or `docs/math/PROOF_STATUS.md`;
* the same narrowing under which `csia_components/` was built (MX-035,
  MX-036), which already covers power, thermal and impedance relations.

A reader who concludes this should not have been built has the ledger entry
and this section to act on. Nothing here is hidden behind a different name.

## 1. What is being tested, and what is NOT

**Tested.** One claim, stated as a falsifiable prediction:

> Given a resistance change `delta_r`, a platform noise model, and a
> reference resistance, `identifiability.probe_requirement` returns three
> necessary conditions. A probe that MEETS all three resolves `delta_r` in an
> independent simulator; a probe that FAILS any one does not.

**Not tested.** Whether the decision is a good idea; whether any authorizer
would grant it; whether a real vehicle behaves like the simulator; whether
the hypothesis set is complete; anything about safety.

## 2. The environment, pinned

| item | value | how it was fixed |
|---|---|---|
| plant | `csia_components/simulate.py` at this commit | committed before this run |
| loop rate | 50 Hz | `csia_components.simulate.LOOP_HZ` |
| pack model | `PACK_OCV_FULL/EMPTY`, `PACK_R_NOMINAL`, `PACK_CAPACITY_AH` | frozen constants in that module |
| probe library | `csia_active_evidence/probes.py`, 7 probes | committed before this run |
| noise model | measured from clean simulator runs by the campaign | not asserted here |
| interpreter | `.venv/bin/python` | `Makefile` `PY` |

**The plant is not the derivation.** `identifiability.py` was derived and
verified against a generator written inside `tests/test_identifiability.py`
which imports nothing from `csia_components`. The simulator is an
INDEPENDENT check in the only sense available without hardware: it was
written first, for a different purpose (MX-036), by a path that did not know
about this error model. That is a weak form of independence and §7 says so.

## 3. Arms

| arm | probes | what it is for |
|---|---|---|
| MEETS | every probe the requirement accepts | must resolve `delta_r` |
| FAILS | every probe the requirement rejects | must not resolve `delta_r` |
| NULL | `hold` (zero amplitude) | must resolve nothing, at any `delta_r` |

The NULL arm is **Rule A**: if `hold` resolves a resistance change, the
instrument is broken and no arm may be read.

## 4. The grid, fixed here

* `delta_r` ∈ {0.005, 0.010, 0.020, 0.040} Ω, spanning below and above the
  0.040 Ω nominal so the discriminating band is **bracketed, not assumed**.
* seeds {0, 100, 200, 300, 400}; seed offset 0 must reproduce the frozen
  simulator exactly.
* `k_sigma` = 3.0, `bias_fraction` = 0.25, both declared, neither swept.
* reference seed 999, **held out**, never scored. Same train-on-test
  defence as MX-030.

## 5. Preregistered quantities, and nothing else may be reported as a result

1. `resolved` per (probe, delta_r): whether the two packs' estimates separate
   by more than `k_sigma` times the measured scatter.
2. `predicted_met` per (probe, delta_r): the requirement's verdict.
3. The 2×2 agreement table between them, over all cells.
4. Per-cell measured mean and scatter of the estimate.

## 6. The classification rule, fixed in advance

A cell is `AGREE` when `predicted_met == resolved`. A cell is
`FALSE_POSITIVE` when the requirement said yes and the simulator did not
resolve — **the dangerous direction**, because it authorises a probe that
cannot answer. A cell is `FALSE_NEGATIVE` when the requirement said no and
the simulator resolved anyway — conservative, and reported separately.

## 7. What would falsify the claim

**Any FALSE_POSITIVE falsifies it.** The requirement is stated as a set of
NECESSARY conditions predicted to be SUFFICIENT; a single probe that meets
all three and fails to resolve is a counterexample and is reported as one.

FALSE_NEGATIVES do not falsify it — they show the requirement is
conservative, which is the safe direction — but the count is reported, and a
requirement that rejects everything useful is recorded as a defect of its own.

## 8. Abort conditions

* the NULL arm resolves anything → the whole run is void;
* seed offset 0 does not reproduce the frozen simulator → void;
* the instrument controls fail → no artifact is written at all;
* fewer than two probes land in each of MEETS and FAILS across the grid →
  the grid does not discriminate and the run is reported as
  `GRID_DOES_NOT_DISCRIMINATE`, not as agreement.

## 9. What this campaign cannot establish

That the model holds on hardware; that the probe library is complete; that
the authorizer's limits are right; that any of this is safe; that any of it
is new. The prior-art search could not be run from this host — see
`PRIOR_ART_MATRIX.md` — so **no novelty may be claimed for anything here**.

## 10. Status

PREREGISTERED. Not yet run at the time of this file's commit.
