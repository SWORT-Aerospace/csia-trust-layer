"""The committed proof audit still matches what the script produces today.

WHY THIS EXISTS
---------------
`research/math-paper/results/proof_audit.json` is the mathematical paper's
verification artifact: Table "Verification" in the manuscript, the P4 counts in
its MAP remark, the P7/P8 rows in `FORMAL_CORE.md` and bindings PB-17, PB-18,
PB-30..PB-32 are all transcribed from it. Every other load-bearing artifact in
this repository has a staleness gate --- the dataset manifest regenerates
byte-identically in CI, the Phase C artifacts are hash-frozen, the artifact
maps and prose bindings are checked both directions --- and this one did not.

Nothing checked that the committed JSON was produced by the committed script.
A reader who reruns `make proof-audit` and gets different numbers has no way
to tell an error from a drift nobody noticed.

WHAT IS AND IS NOT COMPARED
---------------------------
`commit` is EXCLUDED and the exclusion is asserted by name. The artifact
records the commit it was generated at, so it is deliberately not
bit-reproducible across commits even though its scientific content is
deterministic. A blanket "ignore fields that differ" would defeat the check
entirely; naming the one exempt field keeps everything else strict.

Everything else --- every worst deviation, every bound slack, every count,
every symbolic verdict --- must match exactly. These are floating-point
values compared for EQUALITY, deliberately: the audit is seeded and
single-threaded, so on the same interpreter it either reproduces exactly or
something changed that a reader deserves to know about.

    python tools/publication/proof_audit_check.py
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPT = os.path.join(ROOT, "research", "math-paper", "proof_audit.py")
ARTIFACT = os.path.join(ROOT, "research", "math-paper", "results",
                        "proof_audit.json")

#: The only field allowed to differ between generations. Named, not matched.
VOLATILE = ("commit",)

#: sympy is optional (it is not a declared project dependency). When it is
#: absent the script records `symbolic.available == False`, which is a
#: different document rather than a wrong one, so the symbolic block is
#: compared only when both sides actually have it.
_SYMBOLIC = "symbolic"


def _load_module():
    spec = importlib.util.spec_from_file_location("_proof_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _diff(want, got, path=""):
    """Every leaf that differs, as a flat list of readable lines."""
    out = []
    if isinstance(want, dict) and isinstance(got, dict):
        for k in sorted(set(want) | set(got)):
            if k not in want:
                out.append(f"{path}/{k}: only in regenerated ({got[k]!r})")
            elif k not in got:
                out.append(f"{path}/{k}: only in committed ({want[k]!r})")
            else:
                out += _diff(want[k], got[k], f"{path}/{k}")
    elif isinstance(want, list) and isinstance(got, list):
        if len(want) != len(got):
            out.append(f"{path}: length {len(want)} -> {len(got)}")
        else:
            for i, (a, b) in enumerate(zip(want, got)):
                out += _diff(a, b, f"{path}[{i}]")
    elif want != got:
        out.append(f"{path}: committed {want!r} != regenerated {got!r}")
    return out


def main() -> int:
    if not os.path.exists(ARTIFACT):
        print(f"PROOF AUDIT CHECK: FAIL -- {ARTIFACT} does not exist. "
              f"Run `make proof-audit`.")
        return 1

    committed = json.load(open(ARTIFACT, encoding="utf-8"))
    assert "commit" in committed, (
        "the artifact has no `commit` field, so the volatile-field exemption "
        "below is protecting nothing")

    mod = _load_module()
    regenerated = {"numeric": mod.numeric(), _SYMBOLIC: mod.symbolic()}

    want = copy.deepcopy(committed)
    for field in VOLATILE:
        want.pop(field, None)
    # Compare only the blocks the regeneration produces; the rest of the
    # document (paper title, generation command, novelty note) is prose and is
    # checked by the tests that read it.
    want = {k: v for k, v in want.items() if k in regenerated}

    if not committed.get(_SYMBOLIC, {}).get("available"):
        want.pop(_SYMBOLIC, None)
        regenerated.pop(_SYMBOLIC, None)
        print("  note: committed artifact has no symbolic pass; comparing "
              "the numeric block only")
    elif not regenerated[_SYMBOLIC].get("available"):
        want.pop(_SYMBOLIC, None)
        regenerated.pop(_SYMBOLIC, None)
        print("  note: sympy is not installed here, so the committed "
              "symbolic pass cannot be re-checked; comparing numeric only")
    else:
        # sympy's own version is environmental, not a result.
        want[_SYMBOLIC] = dict(want[_SYMBOLIC])
        regenerated[_SYMBOLIC] = dict(regenerated[_SYMBOLIC])
        want[_SYMBOLIC].pop("sympy_version", None)
        regenerated[_SYMBOLIC].pop("sympy_version", None)

    drift = _diff(want, regenerated)
    if drift:
        print("PROOF AUDIT CHECK: FAIL -- the committed artifact is not what "
              "the committed script produces:")
        for line in drift[:40]:
            print("   ", line)
        if len(drift) > 40:
            print(f"    ... and {len(drift) - 40} more")
        print("\nRe-run `make proof-audit` AND propagate every number that "
              "moved: the manuscript's verification table and MAP remark, "
              "FORMAL_CORE.md sections 7/9a/10, and "
              "research/PROSE_NUMERIC_BINDINGS.yaml. Regenerating the "
              "artifact alone leaves the prose stating figures that no "
              "longer exist.")
        return 1

    n = len(committed["numeric"]["worst_deviation"])
    print(f"PROOF AUDIT CHECK: PASS -- {n} identities, "
          f"{len(committed['numeric']['bound_max_slack'])} bounds and every "
          f"count reproduce exactly (commit field exempt by name)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
