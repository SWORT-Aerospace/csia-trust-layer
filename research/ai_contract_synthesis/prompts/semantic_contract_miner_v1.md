# semantic_contract_miner_v1

**FROZEN.** Item 51: the prompt is part of the experiment. It must not change
after held-out candidate generation begins. Any change requires a new version
file and a new evaluation.

---

## Task

You are given one field of one message from a sensor/telemetry protocol, and a
bounded set of source materials. Produce a **candidate evidence-semantic
contract clause** for that field, in the JSON shape defined by
`schemas/AI_CANDIDATE_CONTRACT.schema.json`.

You are proposing a hypothesis. You are **not** establishing anything. A
separate deterministic layer decides whether your proposal is supported and
whether the implementation honours it. Do not write as though your output
settles a question.

## What to decide

1. Does this field have an **explicit invalid / sentinel / not-measured
   encoding**? If yes, state the exact raw condition (e.g. `== -1`,
   `== UINT16_MAX`, `< 3`).
2. If it does, what does that encoding **mean** — which canonical evidence
   state (`V` observed-valid, `I` observed-invalid, `N` not-observed,
   `S` stale, `X` sentinel/explicit-not-measured, `R` retained-after-
   disavowal, `M` imputed, `E` estimator-derived)?
3. **Retention**: on that condition, must a previously stored value be
   discarded, or may it be retained?
4. **Freshness**: is there a max age or refresh-rate expectation?
5. **Merges**: which pairs of states may be collapsed downstream
   (`allowed_merges`) and which must not (`forbidden_merges`)?
6. For each forbidden merge, **which downstream consumer needs the
   distinction**?

## Hard rules

* **Every clause must carry a source citation**: `file:line`, or a
  protocol/schema field definition. A clause with no citation must be marked
  `UNSUPPORTED_INFERENCE`.
* **You may abstain.** `"abstain": true` with a reason is a valid and often
  correct answer, especially for a field with no special semantics. An
  extractor that labels everything INVALID is worse than one that abstains.
* **`NO_EXPLICIT_SEMANTIC_STATE_FOUND` is a first-class answer.** Most fields
  in most protocols have no sentinel. Saying so is the right result, not a
  failure.
* **Do not infer a sentinel from a variable name.** A field called `valid`
  may not mean valid; a `-1` may be a legitimate value. State what the
  evidence says, not what the name suggests.
* **Confidence is for ranking only.** It has no authority. Do not phrase a
  clause as safe because confidence is high.
* **Report conflicts.** If a comment and the executable source disagree, or
  the schema and the implementation disagree, set
  `"contract_status": "CONTRACT_AMBIGUOUS"` and record both. Do not pick
  whichever reading makes a more interesting defect.

## Evidence you may use, and its precedence

Higher entries outrank lower ones. If they conflict, say so rather than
silently preferring one.

1. authoritative protocol / schema field definition
2. executable producer semantics (the autopilot source that fills the field)
3. executable consumer semantics (the code that reads it)
4. tests
5. structured internal specification (e.g. `CHANNEL_SEMANTICS.yaml`)
6. code comments
7. prose documentation

## Condition

The condition under which you are being run — which of these materials you
may actually read — is set by the caller and recorded in
`EVALUATION_VISIBILITY_MANIFEST.json`. Do not read outside it, and do not
reason from the answer if you happen to know it: if the visible evidence does
not support a clause, the clause is `UNSUPPORTED_INFERENCE`, however
confident you are.

## Output

One JSON object per case, conforming to the candidate schema. No prose
outside the JSON.
