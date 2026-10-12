"""Phase 7 — CSIA-Lite, the independent reproduction (H6).

H6 is killed if the reference implementation cannot reproduce the two
mechanisms, or can only do so by importing the production modules. Both halves
are tested: the import half in a fresh interpreter, the reproduction half by
making Lite and production answer the same randomized questions.

**The cross-check is only worth something because the two take different
routes.** `csia_consequence.support` decides separability with set algebra;
`lite` builds a likelihood and asks whether the log-likelihood ratio can be
non-zero. Agreement between a set answer and a numeric answer is evidence
about the claim. Agreement between two copies of the same set operation would
be evidence about copy-paste.

The limit is stated in `lite.py` and repeated here because it belongs next to
the passing tests: independent of the CODE, not of the author.
"""
from __future__ import annotations

import itertools
import pathlib
import random
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LITE_DIR = ROOT / "research" / "consequence" / "csia_lite"
sys.path.insert(0, str(LITE_DIR))

import lite                                               # noqa: E402

from csia_consequence import partitions, support as production  # noqa: E402


# --- H6, first half: no production import ---------------------------------

def test_lite_imports_no_csia_module_in_a_fresh_interpreter():
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import lite;"
        "print(sorted(m for m in sys.modules if m.split('.')[0]"
        ".startswith('csia')))" % str(LITE_DIR))
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]", proc.stdout


def test_lite_uses_only_the_standard_library():
    text = (LITE_DIR / "lite.py").read_text(encoding="utf-8")
    imports = [ln.strip() for ln in text.splitlines()
               if ln.startswith(("import ", "from ")) and "__future__" not in ln]
    allowed = {"import math", "from typing import Dict, Iterable, Mapping, "
                              "Sequence, Tuple"}
    assert set(imports) <= allowed, imports


def _code_only(source: str) -> str:
    """Source with comments and string literals removed.

    Checking raw text would let a prose mention of the forbidden operation
    fail the test, and would let a `#` comment satisfy it. Tokenizing is the
    only way to ask about the CODE.
    """
    import io as _io
    import tokenize
    kept = []
    for token in tokenize.generate_tokens(_io.StringIO(source).readline):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        kept.append(token.string)
    return " ".join(kept)


def test_the_verdict_path_never_computes_a_symmetric_difference():
    """The whole value of the cross-check rests on this.

    Scoped to the three functions that DECIDE -- `log_likelihood`,
    `max_abs_llr` and `separable`. `support()` is deliberately not included:
    after the numeric verdict is already taken, it reports which features
    separate a pair using `(k in A) != (k in B)`, which is a symmetric
    difference in all but spelling. That is reporting, not deciding, and
    pretending otherwise by writing a check that happens to pass would be
    worse than saying it here.

    If a later edit moves set logic into the deciding path, Lite becomes a
    copy of the production rule and the agreement test below stops being
    evidence about anything.
    """
    import inspect
    for function in (lite.log_likelihood, lite.max_abs_llr, lite.separable):
        code = _code_only(inspect.getsource(function))
        assert "symmetric_difference" not in code, function.__name__
        assert "^" not in code, function.__name__
        assert "difference" not in code, function.__name__


# --- H6, second half: the two mechanisms ----------------------------------

def test_mechanism_one_a_gate_closes_with_nothing_stale():
    low = {"a": {"f1", "f2"}, "b": {"f1", "f3"}, "c": {"f1"}}
    gates = {"f1": 1.0, "f2": 1.0, "f3": 1.0}
    demo = lite.occlusion_demo(low, gates, {"f1": True, "f2": True,
                                            "f3": False}, closing="f2")
    assert demo["all_measurements_fresh_throughout"] is True
    assert demo["support_before"] == lite.IDENTIFIABLE
    assert demo["support_after"] == lite.AMBIGUOUS
    assert demo["support_changed"] is True


def test_mechanism_two_the_posterior_still_answers_when_support_is_gone():
    """The posterior does not become undefined, it becomes uniform -- and a
    consumer taking argmax reads a winner out of a coin flip."""
    low = {"a": {"f2"}, "b": {"f3"}}
    gates = {"f2": 0.0, "f3": 0.0}
    report = lite.support(["a", "b"], low, gates)
    assert report["state"] == lite.NON_IDENTIFIABLE
    post = lite.posterior(["a", "b"], low, gates, {"f2": True, "f3": False})
    assert abs(sum(post.values()) - 1.0) < 1e-12
    assert post["a"] == pytest.approx(0.5)
    assert post["b"] == pytest.approx(0.5)


def test_a_feature_low_under_both_contributes_exactly_zero():
    """The cancellation, checked as arithmetic rather than asserted."""
    low = {"a": {"shared"}, "b": {"shared"}}
    gates = {"shared": 1.0}
    assert lite.max_abs_llr("a", "b", low, gates) == 0.0
    for obs in ({"shared": True}, {"shared": False}):
        assert (lite.log_likelihood("a", low, gates, obs)
                == lite.log_likelihood("b", low, gates, obs))


def test_the_closed_form_extreme_matches_a_brute_force_search():
    """`max_abs_llr` avoids enumerating 2**n observations. This enumerates
    them for a small case and checks the shortcut was right."""
    low = {"a": {"f1", "f2"}, "b": {"f2", "f3"}}
    gates = {"f1": 1.0, "f2": 0.4, "f3": 0.7, "f4": 0.0}
    features = sorted(gates)
    brute = 0.0
    for bits in itertools.product([True, False], repeat=len(features)):
        obs = dict(zip(features, bits))
        brute = max(brute, abs(lite.log_likelihood("a", low, gates, obs)
                               - lite.log_likelihood("b", low, gates, obs)))
    assert lite.max_abs_llr("a", "b", low, gates) == pytest.approx(brute)


def test_a_single_hypothesis_is_not_an_identification():
    report = lite.support(["only"], {"only": {"f1"}}, {"f1": 1.0})
    assert report["state"] == lite.NON_IDENTIFIABLE
    assert report["reason"] == "SINGLE_HYPOTHESIS"


@pytest.mark.parametrize("gates,message", [
    ({"f1": 1.4}, "not in"),
    ({"f1": -0.1}, "not in"),
])
def test_an_impossible_gate_weight_is_refused(gates, message):
    with pytest.raises(lite.LiteError, match=message):
        lite.support(["a", "b"], {"a": {"f1"}, "b": set()}, gates)


def test_a_low_set_naming_an_ungated_feature_is_refused():
    with pytest.raises(lite.LiteError, match="no gate"):
        lite.support(["a", "b"], {"a": {"ghost"}, "b": set()}, {"f1": 1.0})


# --- the cross-check ------------------------------------------------------

def _production_state(hypotheses, low_sets, gates):
    report = production.classify(
        hypotheses=tuple(hypotheses),
        low_sets={h: frozenset(v) for h, v in low_sets.items()},
        gates=dict(gates), timestamp_s=0.0,
        provenance="tests/test_consequence_lite.py cross-check")
    return report.status


def test_lite_and_production_agree_on_randomized_cases():
    """500 randomized instances. A disagreement is a real finding about one
    of the two and is reported as the instance, not as a count."""
    # The seed comes from the preregistered DEVELOPMENT partition, which is
    # where the preregistration says harness construction belongs. Not a
    # hand-picked literal, and not the validation or locked partition.
    rng = random.Random(partitions.seeds("development")[0])
    features = [f"f{i}" for i in range(6)]
    disagreements = []
    for _ in range(500):
        names = [f"h{i}" for i in range(rng.randint(1, 4))]
        low_sets = {n: set(rng.sample(features, rng.randint(0, 4)))
                    for n in names}
        gates = {f: rng.choice([0.0, 0.0, 0.25, 1.0]) for f in features}
        mine = lite.support(names, low_sets, gates)["state"]
        theirs = _production_state(names, low_sets, gates)
        if mine != theirs:
            disagreements.append((names, low_sets, gates, mine, theirs))
    assert disagreements == [], disagreements[:3]


def test_the_cross_check_would_notice_a_disagreement():
    """A test that never fails proves nothing. This breaks Lite's verdict on
    purpose and checks the comparison catches it."""
    names = ["h0", "h1"]
    low_sets = {"h0": {"f0"}, "h1": {"f1"}}
    gates = {"f0": 1.0, "f1": 1.0}
    assert lite.support(names, low_sets, gates)["state"] == lite.IDENTIFIABLE
    assert _production_state(names, low_sets, gates) == lite.IDENTIFIABLE

    original = lite.separable
    lite.separable = lambda *a, **k: False
    try:
        broken = lite.support(names, low_sets, gates)["state"]
    finally:
        lite.separable = original
    assert broken != _production_state(names, low_sets, gates)


def test_the_likelihood_constants_do_not_decide_the_answer():
    """Separability must be a structural fact, not an artefact of P_LOW and
    P_HIGH. Any distinct pair strictly inside (0, 1) must give the same
    verdicts."""
    names = ["h0", "h1", "h2"]
    low_sets = {"h0": {"f0", "f1"}, "h1": {"f1"}, "h2": {"f1"}}
    gates = {"f0": 1.0, "f1": 0.3, "f2": 0.0}
    baseline = lite.support(names, low_sets, gates)["state"]
    saved = (lite.P_LOW, lite.P_HIGH)
    try:
        for low_p, high_p in [(0.99, 0.01), (0.6, 0.4), (0.51, 0.49),
                              (0.2, 0.8)]:
            lite.P_LOW, lite.P_HIGH = low_p, high_p
            assert lite.support(names, low_sets, gates)["state"] == baseline, \
                (low_p, high_p)
    finally:
        lite.P_LOW, lite.P_HIGH = saved


def test_lite_holds_no_authority():
    assert lite.HAS_ACTUATOR_AUTHORITY is False
    assert lite.HARDWARE_VALIDATED is False
    assert lite.IMPORTS_CSIA is False


# --- the demonstration artifact -------------------------------------------

DEMO = ROOT / "research" / "consequence" / "results" / "CSIA_LITE_DEMO.json"


def _demo_doc():
    import json
    return json.loads(DEMO.read_text(encoding="utf-8"))


def test_the_demo_artifact_is_what_a_fresh_run_produces():
    """Every number in CSIA_LITE.md is quoted from this file, so a stale file
    is a wrong document. Rebuilding and comparing is the only check that
    catches it."""
    sys.path.insert(0, str(LITE_DIR))
    import demo
    assert demo.build() == _demo_doc(), (
        "research/consequence/results/CSIA_LITE_DEMO.json is stale; "
        "re-run research/consequence/csia_lite/demo.py")


def test_the_demo_shows_a_gate_closing_with_nothing_stale():
    doc = _demo_doc()
    assert doc["support_all_gates_open"]["state"] == lite.IDENTIFIABLE
    after = doc["support_after_one_gate_closes"]
    assert after["state"] == lite.AMBIGUOUS
    assert after["unseparated"] == [["h_pitot_blocked", "h_wind_shear"]]
    assert doc["occlusion_demo"]["all_measurements_fresh_throughout"] is True


def test_the_unseparated_pairs_log_likelihood_ratio_is_exactly_zero():
    """Not 'small'. The terms cancel, so the number is 0.0."""
    doc = _demo_doc()
    assert doc["pairwise_max_abs_llr_closed"][
        "h_pitot_blocked|h_wind_shear"] == 0.0
    assert doc["pairwise_max_abs_llr_open"][
        "h_pitot_blocked|h_wind_shear"] > 0.0


def test_the_posterior_hands_back_a_tie_dressed_as_a_leader():
    """The consequence a consumer sees: argmax over a tie."""
    doc = _demo_doc()["occlusion_demo"]
    assert doc["posterior_after_leader_is_a_tie"] is True
    assert doc["posterior_after_leaders"] == ["h_pitot_blocked",
                                              "h_wind_shear"]
    assert doc["posterior_after_sums_to_one"] is True
    assert doc["max_posterior_after"] > 0.49


def test_the_demo_declares_what_it_did_not_do():
    doc = _demo_doc()
    assert doc["executed_an_autopilot"] is False
    assert doc["touched_hardware"] is False
    assert doc["evidence_level"] == "DETERMINISTIC_SIMULATION"
    assert "not a measurement" in doc["what_this_is_not"].lower()
    assert "not a second party" in doc["what_this_is_not"].lower()
