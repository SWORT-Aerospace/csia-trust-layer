# Gate_Conditioning_v2_2 — reproduction package

This package reproduces every computed number in the manuscript
*Posterior Distortion from Hypothesis-Dependent Validity Gating in Runtime
Diagnosis*, from the sources it carries, on a machine that has never seen
the originating project.

It needs no version-control checkout, no external autopilot source tree, no
hidden files, no untracked measurement output, and — once dependencies are
installed from the wheels included here — no network.

---

## What this package does and does not establish

**It establishes** that the manuscript's numeric and symbolic verification
re-runs and produces the same values, digit for digit, from the same seeded
generator; and that the paper's attribution discipline holds.

**It does not establish** that anything in the paper was measured on
hardware, because nothing in the paper was.

The limitations below are the paper's own and are repeated here so a reader
of this package meets them without having to go looking:

- **No empirical data.** This package contains no measurement of any
  physical system. Nothing here was recorded from an aircraft, a bench, a
  simulator-in-the-loop rig or a hardware-in-the-loop rig.
- **The numerical examples are model-generated.** Every number the audit
  produces comes from pseudo-random instances drawn from a seeded generator
  defined in `source/proof_audit.py`. They illustrate and check the algebra.
  They are not observations, and reproducing them says nothing about any
  vehicle.
- **No flight validation.** None was performed, and none is claimed.
- **No certification claim.** Nothing here is evidence of airworthiness,
  compliance, or qualification under any standard or authority.
- **No novelty claim beyond what is explicitly proved.** Every proposition
  in the paper is labelled KNOWN in `source/NOVELTY_AUDIT.md`. The claim the
  paper makes is the runtime-diagnostic formulation, the fact that the
  condition is decidable statically from a signature table before the system
  runs, and the implemented instance — not the algebra.
- **Priority is claimed for none of it.** `scripts/srcattr_controls.py`
  checks that the manuscript asserts no priority, and fails if it does.
- **The bibliography is UNVERIFIED.** No publisher record was reachable from
  the authoring environment. Every row of `source/PRIOR_ART_MATRIX.csv` is
  web-search-only or candidate-unverified, and one is marked as needing a
  human. The controls in this package check that this state is *disclosed*.
  They do not verify a single citation, and no script here can.

---

## Contents

```
Gate_Conditioning_v2_2.pdf        the manuscript, built from source/
source/
  Gate_Conditioning_v2_2.tex      the manuscript source
  references.bib                  the bibliography
  proof_audit.py                  symbolic + numeric verification
  FORMAL_CORE.md                  the proofs
  NOVELTY_AUDIT.md                per-proposition novelty status
  PRIOR_ART_MATRIX.csv            prior art, with verification status
  GATE_PAPER_ARTIFACT_MAP.yaml    which artifact backs which table
scripts/
  reproduce.py                    regenerate the computed artifacts
  srcattr_controls.py             source-attribution controls
  verify_outputs.py               compare generated against expected
  verify_environment.py           record and check the environment
  check_self_contained.py         fail if anything reaches outside
expected_outputs/                 the JSON this package expects to generate
vendor/wheels/                    dependency wheels, for offline install
requirements.txt                  pinned dependency versions
PYTHON_VERSION.txt                the interpreter this was produced with
SHA256SUMS                        digests; see step 7 for the exclusions
SOURCE_ARCHIVE.zip                the whole package, for the clean rebuild
README_REPRODUCE.md               this file
```

Running the scripts creates `outputs/`, which is not part of the package and
is not covered by `SHA256SUMS`.

---

## 1. Create a fresh virtual environment

Run every command from the package directory.

```sh
python3.12 -m venv .venv
```

If `python3.12` is not on the path, any CPython 3.12 will do; see
`PYTHON_VERSION.txt` for the exact version these outputs were produced with.
`scripts/verify_environment.py` fails if the major.minor differs, so a
mismatch is reported rather than absorbed.

## 2. Install dependencies

Offline, from the wheels in this package — no network:

```sh
./.venv/bin/python -m pip install --no-index --find-links vendor/wheels -r requirements.txt
```

The vendored wheels are built for CPython 3.12 on x86-64 Linux. On another
interpreter or architecture the offline install will not find a usable
wheel; in that case drop `--no-index --find-links vendor/wheels` and install
from an index, which is the one step in this procedure that touches a
network. Nothing after step 2 does.

`sympy` is pinned because the audit's symbolic pass uses it. Without it the
numeric pass still runs and still reproduces every number in the paper; the
`symbolic.available` field records which of the two you got.

## 3. Run reproduce.py

```sh
./.venv/bin/python scripts/reproduce.py
```

Writes `outputs/proof_audit.json`. Takes well under a minute.

## 4. Run srcattr_controls.py

```sh
./.venv/bin/python scripts/srcattr_controls.py
```

Writes `outputs/srcattr_controls.json`. Each control is run twice: against
the manuscript, and against a planted violation. A control that passes its
planted violation is vacuous, and the script fails on that alone — so a
zero exit means the controls both held and were capable of failing.

## 5. Verify all JSON outputs

```sh
./.venv/bin/python scripts/verify_outputs.py
```

Compares every generated JSON against `expected_outputs/`, using canonical
JSON ordering, and prints PASS or FAIL per file. Exits nonzero on any
unexplained mismatch.

Exactly three fields are exempt, each declared in the script with a reason,
each checked for presence and type rather than passed over: `/commit`
(this package is not a version-control checkout, so `UNKNOWN` is the normal
value), `/symbolic/sympy_version`, and `/symbolic/available`. Nothing else
is exempt: every deviation, count, slack, seed, trial count and verdict is
compared exactly, and floats are compared as exact canonical text rather
than within a tolerance.

One generated file, `environment_record.json`, is declared not-compared,
because every field in it describes the machine that produced it. It is
checked by step 6 instead.

### The residual-diagnostic canonicalization rule

**11 fields are compared as a symbol rather than as a number, and you should
know exactly which and why.**

`numeric/worst_deviation/*` and two of the three `numeric/bound_max_slack/*`
entries record the largest observed value of a quantity that is
*mathematically zero*. What they measure is accumulated floating-point
roundoff, which is a property of the machine rather than of the proposition.

This was not hypothetical. An independent run of this package reported
`P5b_KL_p_q_identity` as `1.7763568394002505e-15` where the package expected
`1.5334955527634975e-15`. The cause is reproducible on demand: that residual
is the maximum over 20000 trials of

    |kl_pq - (p @ log(w) - log(E_q[w]))|

and `p @ log(w)` is a five-term dot product. Reduced in BLAS order it gives
the first value; reduced pairwise it gives the second, *exactly*. numpy picks
the order from the build's SIMD width and BLAS. Nothing mathematical
separates the two numbers.

**The rule.** At the two paths above, and nowhere else, a value whose
magnitude is at or below `RESIDUAL_CEILING = 1e-12` is replaced — on both the
expected and the generated side, by the same function — with the literal
string `ROUNDOFF<=1e-12` before comparison. A value **above** the ceiling is
compared exactly, as is every other field in the artifact.

**This is not a tolerance, and the difference is not cosmetic.** A tolerance
relaxes every comparison by some epsilon and absorbs real changes with it.
This rule is scoped to eleven named fields; it yields a *symbol* rather than a
rounded number, so a canonicalized value cannot be read back as a
measurement; and it stops at a declared ceiling, above which there is no rule
at all.

**Where the ceiling came from.** Measured margins in this artifact:

| quantity | value |
|---|---|
| largest residual anywhere in the artifact | `3.552714e-15` |
| **RESIDUAL_CEILING** | **`1e-12`** |
| the audit's own numerical tolerance | `1e-09` |
| smallest substantive float (`bound_max_slack/P6b_TV_bound`) | `8.381251e-05` |

The ceiling sits about 281x above the largest roundoff value and about 1000x
below the tolerance the audit already applies to itself, with the nearest
substantive number eight further orders of magnitude away.

**`P6b_TV_bound` is not canonicalized**, even though it lives inside an
allowlisted container, because at `-8.38e-05` it is four hundred million
times the ceiling. The magnitude decides, not the container. A test plants a
change to exactly this field and requires it to fail.

**Compared exactly, always:** seeds, trial counts, hypothesis counts, every
`bound_violations_beyond_1e-9` count, every `verdict` boolean, the tolerance
itself, every symbolic truth value, and every substantive numeric result.

**What the rule cannot do.** It cannot convert a true bound violation into a
pass: a violation changes an integer count and a verdict boolean, both
compared exactly. `tests/test_repro_package_canonicalization.py` in the
originating repository plants a violation, a verdict flip, a changed seed, a
changed trial count, a residual grown past the ceiling and a changed
substantive slack, and requires every one of them to fail.

**What it does not fix.** It makes the *comparison* portable. It does not
make the residuals themselves reproducible across platforms — they are not,
and the stored `expected_outputs/proof_audit.json` still contains this
machine's raw values rather than canonicalized ones, so that what the
generator actually emitted stays on the record.

## 6. Verify environment versions

```sh
./.venv/bin/python scripts/verify_environment.py
```

Records the Python version, the operating system, the installed version of
every pinned dependency, the SHA-256 of every script and source file, and
the SHA-256 of `SOURCE_ARCHIVE.zip`. Exits nonzero if a dependency is
missing or differs from its pin, or if the interpreter's major.minor differs
from `PYTHON_VERSION.txt`.

In a tree unpacked by step 8 the archive's own hash is reported as absent,
with the reason: an archive does not contain itself. Hash the archive where
you obtained it.

Use `--record-only` to write the record and exit zero anyway, which is what
you want when you are deliberately reproducing on a different toolchain and
want the difference recorded rather than treated as a failure.

## 7. Verify SHA-256 hashes

```sh
sha256sum --check SHA256SUMS
```

`SHA256SUMS` covers every file in the package **except three, each by
construction**:

- **`SHA256SUMS` itself.** A manifest cannot contain its own digest; adding
  a line changes the file and invalidates the line. This is the standard
  self-hash exclusion and it is stated rather than left for the reader to
  infer. To check it, compute `sha256sum SHA256SUMS` and compare against a
  digest published separately; `scripts/verify_environment.py` also records
  it.
- **`SOURCE_ARCHIVE.zip`.** The archive *contains* the manifest, so hashing
  the archive inside the manifest would be circular: adding the digest
  changes the manifest, which changes the archive, which changes the digest.
  The manifest is built first and the archive second. The archive's digest
  is recorded by `scripts/verify_environment.py`, and that is the value to
  publish alongside this package.
- **`outputs/`**, which does not exist until you run the scripts and is
  generated, not shipped.

Every other file is covered. Because the archive carries the manifest, this
step also works on a tree unpacked by step 8.

On a system without `sha256sum`, `shasum -a 256 --check SHA256SUMS` behaves
the same way.

## 8. Rebuild from SOURCE_ARCHIVE.zip in an empty directory

This is the test that decides whether the package is self-contained. It
unpacks the archive somewhere with nothing else in it and runs the whole
procedure there.

```sh
cd "$(mktemp -d)"
unzip -q <path-to>/SOURCE_ARCHIVE.zip
sha256sum --check SHA256SUMS
python3.12 -m venv .venv
./.venv/bin/python -m pip install --no-index --find-links vendor/wheels -r requirements.txt
./.venv/bin/python scripts/reproduce.py
./.venv/bin/python scripts/srcattr_controls.py
./.venv/bin/python scripts/check_self_contained.py
./.venv/bin/python scripts/verify_outputs.py
./.venv/bin/python scripts/verify_environment.py
```

Every one of those must exit zero.

`scripts/check_self_contained.py` is the check that fails if anything in the
package refers to the originating version-control project, an absolute path,
the external autopilot checkout, a Windows drive path, untracked logs, a
network service, or a file outside the package. It works two ways: a static
scan of the package's files, and a run-time probe that instruments file
opening and fails on any path that resolves outside the package directory.
The second exists because a path assembled at run time from pieces no static
scan could join still has to be opened.

---

## Rebuilding the PDF (optional)

The PDF is included, so this is only for a reader who wants to rebuild it.
It needs a LaTeX installation, which this package does not carry and does
not check for.

```sh
cd source
pdflatex -interaction=nonstopmode -halt-on-error Gate_Conditioning_v2_2.tex
bibtex Gate_Conditioning_v2_2
pdflatex -interaction=nonstopmode -halt-on-error Gate_Conditioning_v2_2.tex
pdflatex -interaction=nonstopmode -halt-on-error Gate_Conditioning_v2_2.tex
```

The shipped PDF was built with that sequence and is 12 pages.

---

## Two things to know about how this package was assembled

**`source/proof_audit.py` is vendored byte-identical** to the script that
produced the paper's numbers. `scripts/reproduce.py` imports it and sets two
module attributes before running it — the output path, and a wrapper around
the revision helper so that a machine with no version-control tool installed
gets `UNKNOWN` instead of an error. Neither touches a number, a seed, a
tolerance or a proposition. Nothing else about the file is changed, and its
digest is in `SHA256SUMS` so the claim is checkable.

**`source/Gate_Conditioning_v2_2.tex` differs from the manuscript it was
copied from in exactly one token**: `\bibliography{refs}` became
`\bibliography{references}`, because this package names the bibliography
`references.bib`. No mathematics, equation, number, limitation, claim status
or wording was touched.

**The name `srcattr_controls.py` was interpreted.** The originating project
carries no artifact by that name. This package reads it as *source
attribution*, and the script's own docstring says so, so that a reader who
meant something else can see immediately that it checked something else.
