# Preregistration Amendment 5 — H8 as written is vacuous

**Written after reading the development partition and before the follow-up's
validation or sealed partitions are read.** Development exists to find this
kind of defect; that is what it is for, and finding one there is the system
working rather than a result being managed.

It does not touch the completed sealed phase-one campaign, and it does not
weaken a threshold, move a gate or change a metric definition. It records that
one of Amendment 4's three hypotheses cannot fail, and adds the version that
can.

## 1. What development showed

Amendment 4 §3 states H8 as:

> Under `independent_seed` and `independent_window`, `A_s` on the change metric
> is no longer constant across arms: at least one deployable arm differs from
> another by more than 0.05.

On the development partition, 9504 rows:

| level | `A_s` spread across all eleven arms | exceeds 0.05 |
|---|---|---|
| `paired_crn` — **the control** | 1.0000 | **yes** |
| `independent_seed` | 0.9236 | yes |
| `independent_window` | 1.0000 | yes |

**The control passes the test.** A check that the control passes measures
nothing. This is `VACUOUS_IN_ENVELOPE` in the taxonomy this phase already
built for exactly this failure (`csia_independent_validation/vacuity.py`,
`COUNTEREXAMPLE_LOG.md` IV-25): constant over the admissible domain, so the
outcome was fixed before any data arrived.

The cause is `P0_passive`. It emits no probe at all — mean injected energy
0.0000 A·s across all 864 of its development rows, against 14.0–71.3 A·s for
every other arm — so it never resolves under any baseline whatever, and
`A_s = 0` for it at all three levels. The spread between P0 and any excited arm
is therefore ~1.0 by construction, at every level, including the control.

Amendment 4 §1 described the saturation correctly — *"`A_s` on the change
metric is 0.933 for every arm except passive. Thirteen arms are
indistinguishable"* — and then §3 stated the hypothesis without carrying the
exception across. The prose was right and the statistic was not.

## 2. The correction

**H8 as written in Amendment 4 is reported unchanged, and reported as
vacuous.** It is not deleted, not quietly restated, and not dropped from the
artifact. Its number stands next to the control's number so a reader sees why
it means nothing.

**H8′ is the version with the exception carried across.** Over the arms that
actually inject a probe:

> Restricted to arms with non-zero mean injected energy, `A_s` on the change
> metric is constant across arms under `paired_crn` (spread ≤ 0.05), and is not
> constant under `independent_seed` and `independent_window` (spread > 0.05).

Two differences from H8, both load-bearing:

1. **The control is part of the claim.** H8′ fails if the control is *not*
   flat, which is the property that made H8 unfalsifiable. A statistic whose
   control is unconstrained is not a test.
2. **"Excited" is measured, not named.** The excluded set is
   `{arm : mean energy_as == 0}`, computed from the campaign's own rows. On
   development that set is exactly `{P0_passive}`. Writing `P0_passive` into
   the code would be a hand-pick that happens to be right today.

`H8_SPREAD` stays 0.05. No threshold moves.

## 3. Predeclared falsifiers, restated

`H8′` fails if the `paired_crn` control is not flat over the excited arms — in
which case the saturation was never the clean artifact §1 described, and the
follow-up's premise is wrong. It also fails if either broken level stays flat,
in which case breaking the pairing did not break the saturation.

Both outcomes are accepted in advance. The second would mean the follow-up
found nothing, and the first would mean phase one's diagnosis of its own
saturation was incomplete. Either is reportable and neither is repairable by
retuning.

## 4. What is not changed

`H9` and `H10` are untouched: both already constrain the control explicitly
(H9 requires the paired plants to agree to within 5% before its comparison
counts; H10 is a rank correlation between two measured orderings), and neither
is satisfiable by a degenerate arm.

`TAU_R_RELATIVE`, `TAU_R_ABSOLUTE`, `COVERAGE_TARGET`, the resolve predicates,
the magnitude grid, the action space, the plant families, the certificate, the
evaluator, the partitions and every phase-one conclusion are unchanged.

The follow-up's sealed partition has not been opened at the time this is
written, and this amendment is committed before it is.
