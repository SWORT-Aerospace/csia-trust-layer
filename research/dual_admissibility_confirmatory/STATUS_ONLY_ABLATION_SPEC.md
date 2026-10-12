# Status-only ablation specification

Item 9. The confirmatory primary result must not depend on the strong h_acc
relation, because on the one real recording that relation is what produced the
effect (+0.138 coupled, +0.002 from the split).

## C2 — what it may use

`C2_STATUS_ONLY` admits, as diagnostic evidence, **only frozen categorical
facts about observation**:

| Category | Source | Runtime predicate |
|---|---|---|
| `OBSERVED_VALID` | `GPS_RAW_INT.fix_type >= 3` | a message arrived within `MSG_FRESH_S` and reported a 3D fix |
| `OBSERVED_INVALID` | `GPS_RAW_INT.fix_type < 3` | a message arrived within `MSG_FRESH_S` and reported no fix |
| `NOT_OBSERVED` | no message | no message within `MSG_FRESH_S` |

`MSG_FRESH_S = STALE_TIMEOUT_S["gps"] = 0.5 s`, reused rather than chosen.

## C2 — what it may NOT use

* **`h_acc`, in any form.** No magnitude, no transform, no threshold. This is
  the whole point of the ablation.
* `satellites_visible`, `eph`, `epv`, `v_acc`, `vel_acc`, `hdg_acc` — every
  numeric receiver-health field.
* The invalid navigation **value**: `gnss.position`, `gnss.velocity` remain
  inadmissible under every arm, enforced by the frozen core, not by the
  wrapper.
* Any new detector of any kind.

## Why this makes the ablation meaningful

The primary endpoint is a **decision rule over categorical observation state**
(`PRIMARY_ENDPOINT_SPEC.md`), not a likelihood magnitude. So C2 needs no
evidence *strength* at all — it needs only for the category to survive to the
decision point. Detector dominance cannot explain a categorical distinction
that carries no magnitude.

This also resolves an inconsistency in the exploratory package. There, the
status feature was encoded as a binary consistency `c ∈ {0,1}` — the strongest
encoding the frozen likelihood domain permits — which made it simultaneously
the only thing that worked under sustained invalidity and *actively harmful*
under intermittent invalidity (exploratory N1: `S2a` scored 0.000 on M1
against `S1`'s 0.837). Moving the primary endpoint off the posterior removes
that encoding from the primary result entirely.

The binary encoding is still exercised, but only in the **secondary**
posterior endpoints, where its known pathology is expected and will be
reported.

## The matched coupled control

`C2` is scored against **`C0`**, which carries the identical categorical
evidence but gates it by `D = A`. Under matched `A = 0`, `D = A = 0`, so the
category is discarded and `C0`'s classifier can only output `UNRESOLVED`.

That is a one-factor comparison: same evidence, same classifier, one boolean.

## The failure this ablation is designed to be able to report

> If `C2` cannot discriminate the mechanisms under matched `A`, the
> architectural claim fails at its strongest point and no further arm may be
> added to rescue it.

Concretely: adding `h_acc` back (that is, falling back to `C1`) after seeing
`C2` fail is **forbidden** by this specification. `C1` is scored, but it cannot
be promoted to the primary result after the fact. If `C2` fails and `C1`
succeeds, the reported conclusion is *the effect requires the h_acc detector*,
which is the detector-dominance finding, not an architectural one.
