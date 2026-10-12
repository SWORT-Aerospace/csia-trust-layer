# Owner authorization — verbatim

Recorded exactly as given by the program owner. It is reproduced here without
paraphrase because it is the only thing that makes this work permissible, and
a paraphrased authorization is not an authorization.

> Andres Felipe Pena Avila, owner of the CSIA/SWORT research program,
> explicitly authorizes continued Active Evidence Acquisition research in the
> energy domain on an isolated research branch.
>
> This authorization:
>
> * permits simulator-only research, implementation, tests, bounded
>   multi-hour campaigns, documentation, commits, and a normal push to the
>   existing research branch;
> * permits extending the research-only `csia_active_evidence/` modules and
>   component simulator;
> * does not modify or cancel the dual-paper freeze;
> * does not permit modification of the frozen CSIA core, production
>   defaults, deployed authority, failsafe behavior, historical frozen
>   artifacts, or paper claims;
> * does not permit real hardware operation, motor/propeller operation,
>   battery loading, HIL actuation, armed-vehicle operation, flight testing,
>   merging, tagging, force-pushing, or opening a PR;
> * does not authorize novelty, certification, airworthiness,
>   production-readiness, or formal-safety claims;
> * keeps all new energy-domain results quarantined as post-freeze,
>   research-only evidence until separately reviewed.

## The governing rule this does not repeal

`docs/CURRENT_PROGRAM_STATE.md` §1 lists **energy domain** among the
FORBIDDEN work areas while the dual-paper freeze holds, and states that it
governs where documents disagree. **That rule stands unchanged and that file
has not been edited.** This document records a narrow, owner-authorized
exception for one research branch, not a revision of the rule.

Anyone reading `docs/CURRENT_PROGRAM_STATE.md` will still find the
prohibition. Anyone reading this branch will find the exception and its
limits. Neither has been rewritten to make the other look consistent.

## What this authorization is read as forbidding, in this work

Stated positively so that a reviewer can check compliance rather than take it
on trust:

| forbidden | how it is held |
|---|---|
| frozen-core modification | no module under `csia_active_evidence/` imports a frozen path; asserted by AST test |
| production default change | no file outside `csia_active_evidence/`, `tools/research/`, `tests/` and `research/` is touched except append-only ledgers and their coupled counts |
| deployed authority change | nothing here can transmit; asserted by AST test |
| hardware operation | no hardware exists in this environment and no interface to any is imported |
| novelty claim | `PRIOR_ART_MATRIX.md` is `BLOCKED_EXTERNAL_ACCESS`; no file here uses "novel", "first", "unprecedented" |
| certification claim | the certificate's passing state is named `CERTIFIED_IN_MODEL`, and the name is the disclaimer |
| paper claim | no row in `research/systems-paper/CLAIMS.csv` or `docs/math/PROOF_STATUS.md` is touched |

## Quarantine status

**POST-FREEZE, RESEARCH-ONLY, AWAITING SEPARATE REVIEW.** No result in
`research/active_evidence/realized_current/` may be cited by either
manuscript, by any claim table, or by any readiness document until that
review happens.
