# Prior art — INCOMPLETE, ACCESS DENIED

## Verdict

**The required prior-art search could not be run from this host.**
Per the governing brief's own rule — *if full texts are inaccessible, mark the
novelty search INCOMPLETE and prohibit novelty claims* — and per
`docs/CURRENT_PROGRAM_STATE.md` §9.3, *no citation is invented to make a guard
pass*:

> **NO NOVELTY, PRIORITY OR ORIGINALITY CLAIM MAY BE MADE FOR ANY PART OF
> `csia_active_evidence/`.** Not in code, not in a docstring, not in a commit
> message, not in a paper.

This matches the standing state of the repository's other two prior-art
matrices: `research/math-paper/PRIOR_ART_MATRIX.csv` is `COVERAGE COMPLETE,
VERIFICATION BLOCKED` with every row `WEB_SEARCH_ONLY`, and
`papers/BIB_VERIFICATION_LEDGER.yaml` has 0 of 11 entries verified.

## The refusals, verbatim

Every scholarly endpoint returned HTTP 000 at the client. The agent proxy
status reports `connect_rejected` — *gateway answered 403 to CONNECT (policy
denial or upstream failure)* — for:

```
arxiv.org:443
api.semanticscholar.org:443
api.crossref.org:443
api.openalex.org:443
```

These are the same four hosts already recorded as blocked in
`docs/CURRENT_PROGRAM_STATE.md` under publication blockers 1, 3 and 4. This
is not a new finding and it is not a research problem; it needs a human with
publisher access.

## What the repository already knows it must read

`forge/PRIOR_ART_REQUIRED.md` is the standing list and it already names the
literature this work sits inside. It is reproduced here as the READING LIST
THAT HAS NOT BEEN DONE, not as a citation list:

| topic | why it bears on this work | status |
|---|---|---|
| active fault diagnosis / auxiliary-signal design | the central idea: designing an input that makes faults distinguishable. If this field has the result below, this work is a re-derivation | **NOT READ** |
| optimal input design, Fisher-information experiment design | `probe_requirement` inverts an error model into a condition on the input's second moments. This is the classical form of that question | **NOT READ** |
| errors-in-variables regression, attenuation bias | the module's failure mode 2 is textbook EIV attenuation | **NOT READ — expected to be KNOWN** |
| Dulmage–Mendelsohn structural FDI | structural identifiability, already in `forge/PRIOR_ART_REQUIRED.md` | **NOT READ** |
| Sampath et al., diagnosability of discrete-event systems | the set-valued elimination in `updater.py` | **NOT READ** |
| Matei et al., ACM TCPS 8(1) 2024, DOI 10.1145/3631612 | `forge/PRIOR_ART_REQUIRED.md` records this as covering *"interventions to disambiguate uncertain diagnosis"* — the closest named prior art in the repository to this package's entire purpose | **NOT READ — HIGHEST PRIORITY** |
| battery impedance estimation by current excitation | the anchor problem exactly | **NOT READ** |
| runtime assurance, simplex architecture | the ALLOW/CLIP/DENY separation in `authority.py` | **NOT READ** |

## The honest expectation

The author's expectation, recorded before any reading, so that it can be
checked later: **the attenuation-bias result is certainly known**, optimal
input design is certainly known, and the specific combination — inverting a
local error model into a necessary excitation condition and gating the
resulting action behind an independent authorizer that can clip it — is
**most likely also known**, in the active-fault-diagnosis literature that
`forge/PRIOR_ART_REQUIRED.md` already lists as required reading.

Recording that expectation is not a substitute for the search. The search is
`INCOMPLETE`.

## Status

`INCOMPLETE — ACCESS DENIED`. Clears when a human with publisher access works
`forge/PRIOR_ART_REQUIRED.md` §§3–4 plus the rows above.
