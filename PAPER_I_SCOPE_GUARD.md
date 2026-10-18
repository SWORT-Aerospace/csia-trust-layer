# Paper I scope guard

**PAPER I'S SCIENTIFIC SCOPE IS FROZEN. THE MISSION-ASSURANCE EXTENSION DOES
NOT ENTER IT.**

---

## What Paper I is about

| # | subject |
|---|---|
| 1 | source-grounded diagnostic mechanisms |
| 2 | the **support / ranking distinction** |
| 3 | current-stack **repeated software validation** (E1) |
| 4 | negative controls |
| 5 | Mechanism B |
| 6 | the frozen E1 evidence, and only that |

Its state is **E1 — CURRENT-STACK REPEATED SOFTWARE VALIDATION**, frozen at
`research/physical_validation/E1_FREEZE_MANIFEST.yaml`.

## What may not happen

| forbidden | why |
|---|---|
| describing a capability contract, product contract, certificate, forge-seed table or planner gate **as an E1 result** | E1 measured none of them. They did not exist when it was frozen |
| citing a `csia_mission/` artifact as **evidence for an E1 claim** | the mission layer consumes E1's semantics; it does not evidence them |
| citing the **disaster-corridor benchmark** as validation of anything in Paper I | it is a synthetic software benchmark on constructed evidence sets. No sensor produced any of it |
| presenting the **six experimental metrics** as Paper I results | they measure the mission layer, not the diagnostic mechanism |
| any **novelty or priority claim** for a mission-layer idea | `docs/mission/NOVELTY_CLASSIFICATION.md`: `NOVELTY_NOT_ESTABLISHED` on every row, and no literature search has been done |
| implying XR-1 exists, flies, or has been tested | it has not been built |
| letting the **XR-1 documents** contribute a number to Paper I | every dimension in them is `GIVEN` or `PROVISIONAL`, and none is a measurement of anything Paper I discusses |

## What is permitted

**Future work, described as future work.** Something of the following shape,
if it earns its space:

> The support semantics validated here qualify a single diagnostic
> attribution. Whether they compose upward — into statements about vehicle
> capabilities, and then about the usability of the data products a mission
> collects — is a separate question. An experimental extension exploring that
> composition exists in this repository and is **not evidenced by the work
> reported here**.

Three properties make that acceptable: it claims nothing, it says explicitly
that the extension is not evidenced by E1, and it does not name a result.

## The one place the two touch legitimately

`csia_mission` consumes the **output** of `csia_assurance`, which qualifies the
output of the frozen core. That is a dependency in one direction:

```
frozen core -> firewall -> capability -> product     (permitted)
frozen core <- firewall <- capability <- product     (does not exist)
```

The downward direction is the architecture. The upward direction is not
implemented, is not implementable through any API in this repository, and its
absence is what makes this guard enforceable rather than aspirational.

## Enforcement

`tests/test_paper_i_scope_guard.py` checks that:

- `papers/csia_systems/main.tex` contains no mission-layer vocabulary in a
  results context;
- `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` names no artifact under
  `csia_mission/` or `research/mission/`;
- `E1_FREEZE_MANIFEST.yaml` is byte-unchanged.

A guard that only exists as prose is a guard nobody runs.

## The state of Paper I after this extension

| | |
|---|---|
| scientific scope changed | **NO** |
| manuscript modified | **NO** |
| artifact map modified | **NO** |
| E1 freeze manifest modified | **NO** |
| claim table modified | **NO** |
| future-work candidate offered | yes, the paragraph above, **unused** |
