"""Guards for the reproduction package's residual-canonicalization rule.

THE FAILURE THIS RULE EXISTS FOR
--------------------------------
An independent run of Gate_Conditioning_v2_2_REPRO_PACKAGE reported
P5b_KL_p_q_identity as 1.7763568394002505e-15 where the package expected
1.5334955527634975e-15. Both are the max, over 20000 trials, of a quantity
that is mathematically zero; the number measures accumulated roundoff. The
difference is reproducible on demand by changing nothing but the order the
five terms of `p @ log(w)` are added in -- BLAS order gives the first value,
pairwise order gives the second exactly. numpy picks the order from the
build's SIMD width and BLAS, so the artifact was not portable.

WHAT THESE TESTS PROTECT
------------------------
That the rule normalizes machine roundoff and NOTHING else. The danger of
any such rule is that it quietly widens into a tolerance and starts absorbing
real changes, so the tests below plant each kind of real change and require
it to still fail -- especially a true bound violation, which must never be
convertible into a pass.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PKG = os.path.join(ROOT, "Gate_Conditioning_v2_2_REPRO_PACKAGE")
VERIFY = os.path.join(PKG, "scripts", "verify_outputs.py")
EXPECTED = os.path.join(PKG, "expected_outputs", "proof_audit.json")


def _load():
    spec = importlib.util.spec_from_file_location("_verify_outputs", VERIFY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v = _load()


@pytest.fixture
def expected():
    with open(EXPECTED, encoding="utf-8") as fh:
        return json.load(fh)


def _set(doc, path, value):
    cur = doc
    keys = path.strip("/").split("/")
    for k in keys[:-1]:
        cur = cur[k]
    cur[keys[-1]] = value
    return doc


def _agrees(expected_doc, mutated):
    ok, problems, _exempt, canon = v.compare(expected_doc, mutated)
    return ok, problems, canon


# ------------------------------------------- 1. roundoff IS normalized

def test_the_reported_platform_divergence_is_normalized(expected):
    """The exact number an independent run reported must now agree."""
    import copy
    got = copy.deepcopy(expected)
    _set(got, "/numeric/worst_deviation/P5b_KL_p_q_identity",
         1.7763568394002505e-15)
    ok, problems, canon = _agrees(expected, got)
    assert ok, problems
    assert any(c["path"].endswith("P5b_KL_p_q_identity") for c in canon)


@pytest.mark.parametrize("value", [
    0.0, 5.551115123125783e-17, 3.552713678800501e-15, 1e-13, 9.9e-13,
    1e-12,                      # exactly at the ceiling, still roundoff
    -1.7763568394002505e-15,    # sign must not matter
])
def test_any_value_at_or_below_the_ceiling_is_roundoff(expected, value):
    import copy
    got = copy.deepcopy(expected)
    _set(got, "/numeric/worst_deviation/P1_reweighting_identity", value)
    ok, problems, _ = _agrees(expected, got)
    assert ok, problems


def test_both_sides_go_through_the_same_function(expected):
    """The rule must not be able to make two values agree by treating the
    expected and the generated side differently."""
    import copy
    got = copy.deepcopy(expected)
    _set(got, "/numeric/worst_deviation/P2_log_ratio_identity", 1e-16)
    ok, _p, canon = _agrees(expected, got)
    assert ok
    entry = [c for c in canon if c["path"].endswith("P2_log_ratio_identity")]
    assert entry and entry[0]["both_sides_qualified"] is True


# ------------------------------- 2. a meaningful change STILL fails

@pytest.mark.parametrize("path,value", [
    ("/numeric/worst_deviation/P5b_KL_p_q_identity", 1e-11),
    ("/numeric/worst_deviation/P1_reweighting_identity", 1.1e-12),
    ("/numeric/worst_deviation/P7b_shift_is_the_withheld_contribution", 1e-9),
    ("/numeric/worst_deviation/P3_pinned_to_prior", 0.5),
])
def test_a_residual_above_the_ceiling_is_compared_exactly(expected, path,
                                                          value):
    """Above the ceiling there is no rule at all -- exact comparison."""
    import copy
    got = copy.deepcopy(expected)
    _set(got, path, value)
    ok, problems, _ = _agrees(expected, got)
    assert not ok, f"{path}={value} was absorbed; the rule has become a " \
                   f"tolerance"
    assert any(path in p for p in problems)


def test_a_substantive_float_inside_an_allowlisted_container_is_exact(
        expected):
    """bound_max_slack holds two roundoff values AND one real measurement.

    P6b_TV_bound is -8.38e-05. If the rule keyed on the container rather than
    the magnitude, a real slack would be canonicalized away. This is the test
    that would catch that.
    """
    import copy
    got = copy.deepcopy(expected)
    _set(got, "/numeric/bound_max_slack/P6b_TV_bound",
         -8.391251191391659e-05)
    ok, problems, canon = _agrees(expected, got)
    assert not ok, "a real bound slack was swallowed by the residual rule"
    assert not any(c["path"].endswith("P6b_TV_bound") for c in canon)


# --------------- 3. a true bound violation can never become a pass

@pytest.mark.parametrize("path,value", [
    ("/numeric/bound_violations_beyond_1e-9/P6a_log_ratio_bounded_by_R", 1),
    ("/numeric/bound_violations_beyond_1e-9/P6b_TV_bound", 1),
    ("/numeric/bound_violations_beyond_1e-9/"
     "P8_pinned_pair_margin_never_exceeds_R", 3),
])
def test_a_violation_count_cannot_be_canonicalized(expected, path, value):
    import copy
    got = copy.deepcopy(expected)
    _set(got, path, value)
    ok, problems, canon = _agrees(expected, got)
    assert not ok, "a bound violation was silently converted into a pass"
    assert not canon or all(path != c["path"] for c in canon)


@pytest.mark.parametrize("path,value", [
    ("/verdict/bounds_hold_numerically", False),
    ("/verdict/identities_hold_numerically", False),
    ("/verdict/P4_sufficient_condition_never_violated", False),
    ("/verdict/tolerance", 1e-6),
])
def test_verdicts_and_the_tolerance_are_exact(expected, path, value):
    import copy
    got = copy.deepcopy(expected)
    _set(got, path, value)
    ok, problems, _ = _agrees(expected, got)
    assert not ok, f"{path} is not compared exactly"


@pytest.mark.parametrize("path,value", [
    ("/numeric/seed", 20260904),
    ("/numeric/trials", 19999),
    ("/numeric/hypotheses_per_instance", 6),
    ("/numeric/P4/instances", 19999),
    ("/numeric/P4/condition_Delta_gt_R_met", 2722),
    ("/numeric/P4/argmax_agreed_when_condition_met", 2720),
    ("/numeric/P8/pinned_pairs_that_were_the_top_two_under_q", 2283),
    ("/numeric/P8_escape/draws", 199999),
    ("/numeric/P8_escape/fired_fraction", 0.07),
])
def test_seeds_counts_and_substantive_results_are_exact(expected, path,
                                                        value):
    import copy
    got = copy.deepcopy(expected)
    _set(got, path, value)
    ok, problems, _ = _agrees(expected, got)
    assert not ok, f"{path} is not compared exactly"


@pytest.mark.parametrize("prop", [
    "P1_reweighting_identity", "P2_log_ratio_identity", "P3_pinned_to_prior",
    "P5a_KL_q_p_is_jensen_gap", "P5b_KL_p_q_identity",
    "C2_constant_w_implies_p_equals_q",
])
def test_symbolic_truth_values_are_exact(expected, prop):
    import copy
    got = copy.deepcopy(expected)
    _set(got, f"/symbolic/results/{prop}", False)
    ok, problems, _ = _agrees(expected, got)
    assert not ok, f"symbolic result {prop} is not compared exactly"


# ------------------------------------------------- the rule's own shape

def test_the_rule_is_not_a_broad_tolerance():
    """Scoped to named paths, and a symbol rather than a rounded number."""
    assert v.RESIDUAL_CEILING == 1e-12
    assert v.RESIDUAL_DIAGNOSTIC_PREFIXES == (
        "/numeric/worst_deviation/", "/numeric/bound_max_slack/")
    assert isinstance(v.ROUNDOFF_SYMBOL, str)
    assert not v.is_residual_path("/numeric/seed")
    assert not v.is_residual_path("/verdict/bounds_hold_numerically")
    assert not v.is_residual_path("/numeric/bound_violations_beyond_1e-9/X")
    assert v.is_residual_path("/numeric/worst_deviation/P5b_KL_p_q_identity")


def test_the_ceiling_sits_between_the_measured_margins(expected):
    """Chosen from measurement, not convenience: it must be above every
    residual in the artifact and far below the audit's own tolerance and the
    nearest substantive number."""
    residuals, substantive = [], []
    for path, value in v.flatten(expected).items():
        if not isinstance(value, float):
            continue
        if v.is_residual_path(path):
            (residuals if abs(value) <= v.RESIDUAL_CEILING
             else substantive).append(abs(value))
    assert residuals, "no residuals found; the prefixes are stale"
    assert max(residuals) < v.RESIDUAL_CEILING / 100, (
        "the ceiling is less than 100x above the largest measured residual; "
        "it is too close to the noise it is meant to bracket")
    tolerance = expected["verdict"]["tolerance"]
    assert v.RESIDUAL_CEILING < tolerance / 100, (
        "the ceiling is not far below the audit's own tolerance")
    assert substantive, (
        "no substantive value found inside an allowlisted container; if that "
        "is now true the magnitude test is untested by real data")
    assert min(substantive) > v.RESIDUAL_CEILING * 1000


def test_a_non_float_at_a_residual_path_is_left_alone():
    """Strings and integers must pass through untouched."""
    for value in ("ROUNDOFF<=1e-12", 0, 1, True, None):
        out, changed = v.canonicalize_residual(
            "/numeric/worst_deviation/X", value)
        assert out is value and changed is False


# ------------------------------- the REPORT must not misdescribe itself

def _run_verifier(tmp_path, mutate):
    """Run the real script against a mutated copy of expected_outputs/."""
    import copy as _copy
    import shutil
    import subprocess

    outputs = tmp_path / "outputs"
    outputs.mkdir()
    expected_dir = os.path.join(PKG, "expected_outputs")
    for name in os.listdir(expected_dir):
        if name.endswith(".json"):
            shutil.copy(os.path.join(expected_dir, name), outputs / name)

    target = outputs / "proof_audit.json"
    doc = json.loads(target.read_text(encoding="utf-8"))
    mutate(doc)
    target.write_text(json.dumps(doc, indent=2, sort_keys=True),
                      encoding="utf-8")

    proc = subprocess.run([sys.executable, VERIFY, "--outputs", str(outputs)],
                          capture_output=True, text=True)
    return proc


def _block_for(stdout, path_suffix):
    """The lines the report printed about one canonicalized path."""
    lines = stdout.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if "residual canonicalized" in ln and ln.rstrip().endswith(
                path_suffix):
            start = i
            break
    if start is None:
        return []
    block = [lines[start]]
    for ln in lines[start + 1:]:
        if "residual canonicalized" in ln:
            break
        block.append(ln)
    return block


def test_the_report_does_not_claim_both_sides_when_only_one_qualified(
        tmp_path):
    """A verifier that misdescribes its own comparison is worse than a noisy
    one. With expected 1.53e-15 and generated 1e-11, exactly ONE side is at or
    below the ceiling; the comparison correctly fails, and the report must not
    print 'both <= 1e-12' about it.
    """
    proc = _run_verifier(tmp_path, lambda d: d["numeric"]["worst_deviation"]
                         .__setitem__("P5b_KL_p_q_identity", 1e-11))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    block = _block_for(proc.stdout, "worst_deviation/P5b_KL_p_q_identity")
    assert block, proc.stdout
    assert "ONE SIDE ONLY" in block[0], block
    assert not any("both <= 1e-12" in ln for ln in block), (
        "the report claimed both sides were at or below the ceiling when only "
        "the expected side was; that is a false statement about the "
        "comparison the verifier actually performed:\n" + "\n".join(block))
    # the other residuals, which genuinely do qualify on both sides, must be
    # unaffected -- the fix must not simply delete the honest message
    assert "both <= 1e-12" in proc.stdout


def test_the_report_does_say_both_sides_when_both_qualified(tmp_path):
    """The honest counterpart: the reported platform divergence really does
    have both sides at or below the ceiling, and the report says so."""
    proc = _run_verifier(
        tmp_path,
        lambda d: d["numeric"]["worst_deviation"].__setitem__(
            "P5b_KL_p_q_identity", 1.7763568394002505e-15))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    block = _block_for(proc.stdout, "worst_deviation/P5b_KL_p_q_identity")
    assert block, proc.stdout
    assert "ONE SIDE ONLY" not in block[0], block
    assert any("both <= 1e-12" in ln for ln in block), block
    assert "ONE SIDE ONLY" not in proc.stdout


# ------------------- the README's numbers must match the artifact

README = os.path.join(PKG, "README_REPRODUCE.md")


def test_the_readme_margin_table_matches_the_artifact(expected):
    """Every number the README states about the rule is checked against the
    artifact it describes.

    The README is the only place a reader learns why the ceiling sits where it
    does. A stale figure there is a dishonest justification even when the code
    is correct, and this guard exists because one was found: the P6b margin
    was written as "four hundred million" when it is about eighty-four
    million.
    """
    text = open(README, encoding="utf-8").read()

    flat = v.flatten(expected)
    residuals = [abs(x) for p, x in flat.items()
                 if isinstance(x, float) and v.is_residual_path(p)
                 and abs(x) <= v.RESIDUAL_CEILING]
    substantive = [abs(x) for p, x in flat.items()
                   if isinstance(x, float) and v.is_residual_path(p)
                   and abs(x) > v.RESIDUAL_CEILING]
    tolerance = expected["verdict"]["tolerance"]

    assert f"{max(residuals):e}" in text, (
        f"the README does not state the largest residual "
        f"{max(residuals):e}")
    assert f"{min(substantive):e}" in text, (
        f"the README does not state the smallest substantive float "
        f"{min(substantive):e}")

    # the count of canonicalized fields
    n = len(residuals)
    assert f"{n} fields" in text or f"**{n} fields" in text, (
        f"the README does not say {n} fields are canonicalized")

    # the three ratios, each to the nearest figure the README rounds to
    assert f"{round(v.RESIDUAL_CEILING / max(residuals))}x" in text, (
        "the README's ceiling-to-largest-residual ratio is stale")
    assert f"{round(tolerance / v.RESIDUAL_CEILING)}x" in text, (
        "the README's tolerance-to-ceiling ratio is stale")

    ratio = min(substantive) / v.RESIDUAL_CEILING
    assert 8.0e7 < ratio < 9.0e7, ratio
    assert "eighty-four million" in text, (
        f"the README misstates the P6b margin; it is {ratio:.3g}x the "
        f"ceiling, about eighty-four million")
