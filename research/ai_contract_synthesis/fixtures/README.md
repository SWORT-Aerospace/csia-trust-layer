# NON-SCORED hallucination fixtures

**These are TOOL-VALIDATION FIXTURES. Nothing here is a scientific result and
nothing here is a statement about CSIA.**

Each file is a small synthetic decoder written so that a plausible reading of
it is wrong. They exist to answer item 23's question: when the miner proposes
an incorrect semantic rule, does the deterministic layer stop it from
becoming a confirmed defect?

Every fixture is paired with a deliberately WRONG candidate contract in
`../candidates/NONSCORED_HALLUCINATION.json`, and the outcome is measured by
`../verification/containment.py`.

None of these files is imported by CSIA. They are never executed by the
production runtime.
