# Decision required: the 0.700 evidence-floor range

**Status: OPEN. A human has to choose. Nothing here has been applied, and
nothing here can be applied without a deliberate re-freeze** —
`papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` is hashed by the E1 freeze
manifest.

This is the one prose literal the binding tools classified
`REVIEW_PROSE_AND_ARTIFACT_DISAGREE`. It is not a typo and not a tooling
failure; the prose and the artifact are each internally correct and describe
different sets of cells.

---

## The sentence

`papers/csia_systems/main.tex:901`, closing the paragraph on the ticks
required before escalation:

> Both misses lie near the line, at $+0.7$ and $-12.3$ ticks, and the model
> assumes a constant $e_f$ where **the measured floor ranges 0.678 to 0.700**.

## What the artifact holds

`research/wp_c8/results/response_surface.json`,
`/evidence_floor_confirmation`:

| field | value |
|---|---|
| `predicted_e_f` | 0.7 |
| `observed_range` | **[0.6785, 0.9422]** |
| `cells_whose_min_evidence_equals_0_700` | 8 |
| `of_cells` | 21 |

and its own statement:

> the algebra predicts that destroying only the physics residual floors fused
> evidence at `w_nbr+w_temp+w_stat = 0.70`. Cells whose residual saturates
> land on 0.7000 to four decimals. Cells slightly below it are ones where the
> neighbour term also degraded, which lowers `e_f` further and is consistent
> with the same equation.

## Where they disagree

The lower end matches: 0.6785 → 0.678. **The upper end does not.** The
artifact's range tops out at **0.9422**, not 0.700.

0.700 is the *algebraic saturation value* — the 8 of 21 cells whose residual
saturates land exactly on 0.7000. The other 13 cells have minimum evidence
*above* 0.700, up to 0.9422, because their fault never drove the physics
residual to saturation at all.

So the prose's "0.678 to 0.700" is the band spanned by the cells that
**reach** the floor. It silently excludes the 13 cells that do not, and the
artifact stores no scalar for the quantity the sentence actually names. That
is why it cannot be bound: **the binding target does not exist.**

Neither side is wrong about a number. The sentence describes a selection the
artifact does not record.

## Why it matters more than a decimal place

The sentence is defending a modelling assumption — that $e_f$ is constant —
against two misclassified cells. Quoting 0.678–0.700 makes the assumption look
tight (a 3% band). Across all 21 cells the real spread is 0.678–0.942, and for
the 13 non-saturating cells the constant-$e_f$ assumption is wrong in the
*opposite* direction and by considerably more. A reader checking whether the
two misses are explained by $e_f$ variation is entitled to the wider number.

## The options

**A — quote the artifact's range as it stands.** Replace with "the measured
floor ranges 0.678 to 0.942". *Cost:* 0.9422 is not a floor observation; that
cell never approached the floor, so this overstates the variation *of the
floor* while fixing the understatement *of the spread*. It trades one
imprecision for another.

**B — state the selection explicitly (recommended).** Something like: "the
model assumes a constant $e_f$; of the 21 cells, 8 saturate at exactly 0.7000
and the rest range from 0.678, where the neighbour term also degraded, up to
0.942, where the residual never saturated." *Cost:* longer. *Benefit:* every
number in it is in the artifact, and the selection stops being invisible.

**C — add the scalar, then bind.** Record the quantity the prose means — the
range over saturating-or-below cells — as a named field in
`response_surface.json`, and bind the literal to it. *Cost:* requires
regenerating the artifact and a deliberate re-freeze. *Benefit:* the sentence
becomes checkable by the binding guard instead of exempt from it.

**B and C are compatible**, and together are what I would do: say the whole
thing in prose, and record the derived quantity so the claim is machine-
checkable next time.

## What is NOT on the table

Binding 0.700 to one of the four candidates the tool surfaced. They are
`TRUST_BELOW_INHERITED_REQUIREMENT/limit = 0.7` (a *threshold*, twice) and two
`min_trust_per_node/battery` values from the stress campaign. All four share
the digits and nothing else. MX-013 records a tool binding two of five such
proposals wrongly; picking the least implausible candidate here would repeat
exactly that.

## Who decides

Whoever owns the claim. This is an editorial judgement about what the sentence
is asserting, and no measurement settles it — which is why it is written down
here rather than resolved by a tool.
