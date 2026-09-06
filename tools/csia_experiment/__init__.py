"""Experiment orchestration for the physical-validation campaigns.

DELIBERATELY THIN, AND BUILT ON WHAT EXISTS.

`csia/simulation/contract.py` already implements the evidence chain: six
stages, RULE A (every instrument has a null control) and RULE B (no mechanism
attribution without the intermediate quantity), with a three-valued verdict
whose third value -- INVALID_SCENARIO -- is the one that stops a broken
injection from becoming a published detector weakness.

None of that is reimplemented here. `validity.py` EXTENDS the verdict
vocabulary with the five outcomes a physical campaign has and a simulator
campaign does not, and `manifest.py` makes a trial record immutable once
written. The orchestrator is the thing that had no home: the loop that plans
trials, runs them, adjudicates each one against machine-executable predicates,
and reconciles the arithmetic at the end.
"""
