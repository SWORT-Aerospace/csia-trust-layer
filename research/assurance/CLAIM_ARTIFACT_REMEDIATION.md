# Claim-artifact provenance remediation

Scope: the **21 artifacts** that `papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml`
and `papers/gate_conditioning/GATE_PAPER_ARTIFACT_MAP.yaml` cite as backing a
stated number, as identified by `tools/assurance/evidence_gate_audit.py`.

This remediation is **read-only**. It records what is known about each
artifact's provenance and verifies what can be verified without running
anything. It changes no artifact, no manifest, no preregistration, no paper
and no frozen file.

---

## The distinction this document refuses to blur

**Hash pinning detects later modification. Evidence gating controls whether a
result may be generated or refreshed at all.**

They are not degrees of the same thing. A hash tells you a file changed after
somebody recorded it; it tells you nothing about the state of the tree the
file was produced from, and nothing about whether it may be produced again.
The register added here is a *detection* mechanism. After this work, **all 21
artifacts remain ungated** — the count of evidence-gated artifacts in this
repository is still one, and that one is `BUILD_PROVENANCE.json`.

Anything in this document that says VALIDATED means integrity, never
governance.

---

## COMPLETED

Work finished and checked in.

| item | where |
|---|---|
| Register of all 21 claim-backing artifacts | `research/assurance/CLAIM_ARTIFACT_REGISTER.yaml` |
| Read-only verifier | `tools/assurance/claim_artifact_verify.py` |
| Tests for all nine required scenarios, plus read-only and no-bypass guards | `tests/test_claim_artifact_verify.py` |
| This document | `research/assurance/CLAIM_ARTIFACT_REMEDIATION.md` |

Each register entry carries the fifteen required fields plus
`generator_evidence`, which records **how** the generator was established
rather than leaving the reader to assume it was proven.

---

## VALIDATED

What the verifier actually proves, on this checkout:

- **21/21** artifacts exist.
- **21/21** recorded SHA-256 digests match the files on disk — **no drift**.
- **19/21** name a generator that exists; the other two are reported, not
  filled in.
- **17/21** generators were confirmed by reading the source and finding a
  write of the artifact's path.
- **0** declared input artifacts are missing — because none are declared
  anywhere (see UNPROVEN).

Verifier verdicts: **VALID 16 · UNREGENERABLE 3 · UNKNOWN 2 · DRIFT 0 ·
MISSING 0**, exit code 0.

VALID here means *this file is unchanged since the register recorded it and
its declared provenance resolves*. It does not mean the artifact is gated,
reproducible on another machine, or correct.

---

## UNPROVEN

True gaps. Each is recorded in the register as `MISSING` or `UNKNOWN` rather
than filled with something plausible.

**Input artifacts are undeclared for all 21.** Neither artifact map nor any
generating script declares, per artifact, which input files it consumes. The
maps' figure rows do carry an `inputs` field, but it names the *producing
script*, not an input artifact; recording that as an input would have made the
register look more complete than it is. Every entry therefore reads
`input_artifacts: [UNKNOWN]`. The dependency graph behind the papers' numbers
is not currently written down anywhere.

**Environment requirements are undeclared per artifact.** The maps carry one
repository-wide `environment` block (Python 3.12/3.13, ArduCopter 3.3 SITL).
That is not a per-artifact requirement and was not copied in as though it
were.

**Two artifacts have no locatable generator.**

- `campaigns/bench.json` — read by `research/phase2/build_manifest.py` and
  listed by the evidence exporter, but nothing found writes it. The map's
  `benchmark_gate` asserts CI regenerates it bit-identically; the command that
  would do so is not named in the map and was not located. The assertion may
  well be true — it is simply not evidenced here.
- `research/math-paper/PRIOR_ART_MATRIX.csv` — maintained by hand, and
  correctly so. Its rows are `WEB_SEARCH_ONLY` / `CANDIDATE_UNVERIFIED`, one
  `NOT_FOUND_NEEDS_HUMAN`. A matching hash says nothing about whether the
  citations are real; that needs a human with publisher access.

**Two generators rest on the map's assertion, not on readable source.**
`mechanism_a_a2_trust_ardupilot.json` and `mechanism_a_p1_trust_px4.json` are
produced by `tools/csia_experiment/extract_trust_a2.py`, which writes through
a runtime `--out` argument and so never names either path in its source.
`generator_evidence` reads `DECLARED_BY_ARTIFACT_MAP_ONLY` for both.

**The audit's claim-backing tier is regex-based.** Two of the 21
(`campaigns/bench.json`, `PRIOR_ART_MATRIX.csv`) are cited through
`benchmark_artifact` and a `formal_sources` path rather than an `artifact:`
field. The tier found them, but a differently-shaped citation could be missed
by the same regex, so 21 is a floor rather than a proven ceiling.

---

## BLOCKED

Cannot be cleared from this environment, by anyone, without something this
repository does not have.

- **Re-running the SITL campaigns.** Three artifacts
  (`mechanism_a_a2_*`, `mechanism_a_p1_*`, `q_gvalid_campaign.json`) derive
  from ArduCopter/PX4 SITL runs. The autopilot binary is not vendored here.
  They are `VERIFIABLE_ONLY` and the verifier reports them `UNREGENERABLE`,
  which is a terminal state, not an outstanding task.
- **Verifying the prior-art matrix.** Needs publisher access; every egress
  route to `doi.org`, `dblp.org` and `api.crossref.org` is denied from this
  environment.
- **Confirming the `campaigns/bench.json` CI regeneration claim.** Requires
  either the CI definition that performs it or the command that writes the
  file; neither was located.

---

## NOT ATTEMPTED

Deliberately out of scope, with the reason.

- **Adding an evidence gate to any of the 21.** Gating these changes how
  locked results and preregistered campaigns may be regenerated. That is a
  decision with consequences for frozen work, and the brief for this task was
  a read-only remediation.
- **Regenerating any artifact,** including the 16 marked `REGENERABLE`.
  Regenerating a claim-backing artifact changes the evidence under a published
  number; nothing here needed it, so nothing here did it.
- **Adding these artifacts to any SHA manifest.** Existing manifests were not
  to be modified, and a new manifest would duplicate the register's detection
  role without adding gating.
- **Backfilling `input_artifacts` by reading each generator's imports and
  file reads.** Mechanically possible and genuinely useful, but it would
  produce an inferred dependency graph presented with the same authority as
  the declared fields. If it is done it should be a separate, clearly-labelled
  derivation.

---

## RECOMMENDED REMEDIATION

In the order I would do them.

1. **Declare `inputs` per artifact in both artifact maps.** This is the
   largest real gap and the cheapest to close, because the authors know the
   answers. It makes the register's `input_artifacts` field meaningful and
   gives the verifier something to check.
2. **Name the command that regenerates `campaigns/bench.json`,** or, if CI
   performs it, cite the CI job in the map beside the `benchmark_gate`
   assertion. An asserted reproducibility anchor that nobody can locate is
   weaker than the assertion implies.
3. **Have `extract_trust_a2.py` record its own output path** in the artifact
   it writes, as `proof_audit.json` and `checker_agreement.json` already do.
   That converts two `DECLARED_BY_ARTIFACT_MAP_ONLY` entries into
   self-evidencing ones without touching the locked results themselves.
4. **Then, and only as a separate decision, consider evidence-gating the
   `REGENERABLE` subset** through the pattern in
   `tools/assurance/provenance_workflow.py`: a write requires a green suite,
   passing blocking guards, an unchanged frozen core and verifying manifests.
   The 3 `UNREGENERABLE` artifacts should *not* be gated — gating what cannot
   be regenerated adds a check that can never run.
5. **Widen the audit's claim-backing tier** beyond `artifact:` fields so the
   21 is a proven ceiling rather than a floor.

---

## Reproduce

```sh
python tools/assurance/evidence_gate_audit.py
python tools/assurance/claim_artifact_verify.py
python -m pytest tests/test_evidence_gate_audit.py tests/test_claim_artifact_verify.py -q
```

The verifier exits nonzero on hash drift or missing provenance, and has no
option that would let it repair either.
