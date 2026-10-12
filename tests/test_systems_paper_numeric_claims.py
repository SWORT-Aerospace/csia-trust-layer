"""Precise numbers in the systems manuscript, checked against their artifacts.

WHY THIS FILE EXISTS
--------------------
`papers/csia_systems/PAPER1_ARTIFACT_MAP.yaml` binds the figures, tables and
thirteen headline scalars. It does not bind every number that appears in
running prose, and `--strict-numbers` reports 49 unmapped literals. Auditing
those by hand found one wrong:

    "Note which term dominates: S_0(T_0 - T*) = 125 against M(T* - e_f) = 1.0"

125 is an IDEALISED version of the same term. It comes from the generating
script's own docstring (`research/wp_c8/escalation_algebra.py`:
"S_0(T_0 - T*) = 500 * 0.25 = 125"), which uses the theoretical concentration
cap 1/(1 - rho_max) = 500 and T_0 = 1.0. The manuscript had transcribed a
docstring illustration as if it were a result.

The canonical chain, recomputed independently:

    S_0 = 475.6775   MEASURED settled Beta mass, not the cap 500
    T_0 = 0.999791   MEASURED settled trust, not 1.0
    T*  = 0.75       FailsafeConfig.nav_caution
    475.6775 * (0.999791 - 0.75) = 118.8199584...  ->  118.82

A CORRECTION TO AN EARLIER VERSION OF THIS DOCSTRING, left visible rather than
overwritten. It said 118.82 followed from "the measured T_0 = 0.98764". No such
value exists anywhere in this repository. It was back-solved from
118.82 / 500 + 0.75, and it reproduces 118.82 only because 500 * 0.23764 =
118.82 exactly -- an arithmetic coincidence that looked like a derivation. The
VALUE was right both times; the account of where it came from was not.
`test_the_mass_term_inputs_are_the_measured_ones` below pins S_0 and T_0
themselves, so the explanation cannot drift again the way the value could not.

The rest of the audit came back clean, and the checks are kept rather than
discarded: a number that was verified once and then left unguarded is a number
that drifts on the next regeneration. Each test below re-derives its value from
the artifact instead of restating it.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "papers", "csia_systems", "main.tex")


def _artifact(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return json.load(fh)


def _tex():
    with open(TEX, encoding="utf-8") as fh:
        return fh.read()


def test_the_escalation_delay_decomposition_matches_its_artifact():
    """The defect this file was written for."""
    d = _artifact("research", "wp_c8", "results", "escalation_algebra.json")
    mass = d["what_dominates_N_star"]["mass_term_S0_times_T0_minus_Tstar"]
    margin = d["what_dominates_N_star"]["margin_term_M_times_Tstar_minus_ef"]
    tex = _tex()

    assert f"= {mass}" in tex, (
        f"the manuscript does not print the artifact's banked-agreement term "
        f"{mass}. If the artifact was regenerated, update the sentence in "
        f"section 'The glitch non-alarm has a tested cause' and scalar S13 "
        f"together.")
    assert f"M(T^* - e_f) = {margin}" in tex, margin
    assert "= 125$" not in tex, (
        "125 is back. It is escalation_algebra.py's DOCSTRING illustration -- "
        "the cap 500 times an idealised (1.0 - 0.75) -- not the measured "
        "term, and it appears in no result artifact.")
    # The claim the sentence actually makes, checked rather than assumed.
    assert mass / margin > 100, (
        f"the mass term no longer dominates the margin term by two orders of "
        f"magnitude ({mass} vs {margin}); the sentence's conclusion has "
        f"changed, not just its number")


def test_the_escalation_boundary_and_grid_match_their_artifact():
    d = _artifact("research", "wp_c8", "results", "response_surface.json")
    eb = d["escalation_boundary"]
    tex = _tex()
    assert eb["grid_correct_of_total"] == "19/21"
    assert eb["grid_misclassified"] == 2
    assert "19 correctly" in tex and "21 cells" in tex
    offsets = sorted(c["ticks_from_boundary"] for c in eb["misclassified_cells"])
    assert offsets == [-12.3, 0.7], offsets
    for rendered in ("+0.7", "-12.3"):
        assert rendered.replace("-", "$-$") in tex or rendered in tex, rendered
    assert f"{eb['predicted_N_star_ticks']:.1f}" == "93.3"
    assert round(eb["boundary_ticks"]) == 118


def test_the_one_ungated_relation_numbers_match_their_artifact():
    """The temp_gps escape: bit-identical value, collapsed fresh fraction."""
    d = _artifact("research", "wp_c6", "results", "field_set_universe.json")
    esc = d["informativeness_of_the_one_escape"]
    assert esc["value_identical_clean_vs_denial"] is True
    clean, denial = esc["traces"]["clean"], esc["traces"]["denial"]
    for field in ("mean", "min", "max"):
        assert clean[field] == denial[field], (
            f"temp_gps {field} is no longer identical between the clean and "
            f"denial runs; the manuscript's 'bit-identical' claim is stale")
    tex = _tex()
    assert f"mean {clean['mean']}" in tex
    assert f"min {clean['min']}" in tex
    assert str(denial["channel_fresh_fraction"]) in tex
    assert d["n_outside"] == 1, (
        f"{d['n_outside']} relations now sit outside C_h; the manuscript says "
        f"formal containment is 'incomplete by one relation'")


def test_the_real_autopilot_denial_numbers_match_their_artifact():
    d = _artifact("research", "wp_c6", "results", "q_gvalid_campaign.json")
    denial = [f for f in d["per_flight"]
              if f["arm"] == "denial" and f.get("reached_injection")]
    assert denial, "no denial flight reached injection"
    f = denial[0]
    tex = _tex()
    assert f"{f['p_closed_after_injection']:.3f}" == "0.984"
    causes = dict(f["top_causes_20s_after_injection"])
    assert f"p = {causes['nominal']}" in tex
    assert f"p = {causes['gps_fault']}" in tex
    caution = [a for a in f["alarms"] if a["level"] == "CAUTION"]
    assert caution, "the denial flight no longer reaches CAUTION"
    assert f"{caution[0]['t']:.1f}" == "61.5"


def test_the_recovery_delay_matches_its_artifact():
    d = _artifact("research", "wp_c7", "results", "false_healthy.json")
    arm = d["per_arm"]["denial_recovered"]
    a, dep = (arm["recovery_delay_abstaining_s"],
              arm["recovery_delay_deployed_s"])
    assert a == dep, (
        f"the two policies no longer recover together ({a} vs {dep}); the "
        f"manuscript says 'both policies return to health after' one figure")
    assert f"{a:.2f}" == "5.71", a
    assert "5.71" in _tex()


def test_the_design_rule_enforcement_is_not_silently_skipped():
    """The manuscript says the rule 'is enforced in the project's test suite'.

    `tests/test_signature_design_rule.py` reaches its audit module through
    `pytest.importorskip`, because research/ is not an installed package. That
    is the right call for a research import -- and it means an import failure
    turns the enforcement into a SKIP, which reports green while enforcing
    nothing, and the manuscript's claim would quietly become false.

    So the import is asserted here rather than skipped.
    """
    import importlib

    mod = importlib.import_module("research.wp_c3.design_rule_audit")
    from csia.diagnosis.bayes import CAUSES

    violations, _at_risk, _ = mod.audit(CAUSES)
    found = {(v["hypothesis"], v["feature"], g)
             for v in violations for g in v["closed_by_this_hypothesis"]}
    assert found == {("gps_fault", "phys_gps", "gvalid")}, (
        f"the audited violation set is {sorted(found)}; the manuscript states "
        f"exactly one violation, gps_fault / phys_gps / gvalid")


def test_the_mass_term_inputs_are_the_measured_ones():
    """S_0 and T_0, pinned as VALUES rather than as a story about them.

    The mass term 118.82 was correct while the published explanation of where
    it came from was wrong twice: once as "500 * 0.25" (the script's idealised
    docstring illustration, transcribed into the manuscript as a result) and
    once as "the measured T_0 = 0.98764" (a back-solve that reproduces 118.82
    by coincidence). Pinning the product alone could not catch either. Pinning
    the FACTORS can.
    """
    from decimal import Decimal

    d = _artifact("research", "wp_c8", "results", "escalation_algebra.json")
    ver = d["verification_against_shipping_trustcore"]
    s0, t0 = ver["settled_mass_S0"], ver["settled_trust_T0"]
    mass = d["what_dominates_N_star"]["mass_term_S0_times_T0_minus_Tstar"]

    assert s0 == 475.6775, (
        f"settled mass S_0 is {s0}; it was 475.6775 when the manuscript's "
        f"118.82 was derived. NOTE it is NOT the theoretical cap 500 -- "
        f"conflating the two is how 125 got into the paper")
    assert t0 == 0.999791, (
        f"settled trust T_0 is {t0}; it was 0.999791. It is NOT 1.0, and it "
        f"is NOT 0.98764, which appears nowhere in this repository")
    assert ver["concentration_cap_1_over_1_minus_rho_max"] == 500.0, (
        "the theoretical cap is no longer 500, so the 125 illustration in "
        "escalation_algebra.py's docstring needs revisiting too")

    exact = Decimal(str(s0)) * (Decimal(str(t0)) - Decimal("0.75"))
    assert float(round(exact, 2)) == mass, (
        f"S_0 * (T_0 - T*) = {exact}, which rounds to {round(exact, 2)}, but "
        f"the artifact reports {mass}")


def test_the_conclusion_compares_the_two_TERMS_not_a_mass_against_a_term():
    """The last surviving member of the 125 family.

    The Conclusion's practical advice read "the belief mass banked during calm
    flight, 500 units against an evidence margin worth 1". Two things were
    wrong with it. 500 is the THEORETICAL CAP 1/(1-rho_max); the mass actually
    banked is 475.6775. And it compared a raw mass against a PRODUCT: the
    margin figure 1.0 is M(T* - e_f), so the like-for-like partner is the mass
    TERM S_0(T_0 - T*) = 118.82, not S_0 itself.

    Same defect as the 125 in Section 7, in a different disguise -- the
    idealised cap standing in for the measured quantity -- which is why it
    survived that correction. The Conclusion now quotes both terms of N*.
    """
    d = _artifact("research", "wp_c8", "results", "escalation_algebra.json")
    ver = d["verification_against_shipping_trustcore"]
    mass = d["what_dominates_N_star"]["mass_term_S0_times_T0_minus_Tstar"]
    margin = d["what_dominates_N_star"]["margin_term_M_times_Tstar_minus_ef"]
    tex = _tex()

    assert "500 units" not in tex, (
        "the Conclusion is quoting the concentration cap as the banked mass "
        f"again. The cap is {ver['concentration_cap_1_over_1_minus_rho_max']}; "
        f"the mass banked is {ver['settled_mass_S0']}; and the figure that "
        f"belongs beside the margin term is the mass TERM {mass}.")
    assert f"${mass}$ against ${margin}$" in tex, (
        f"the Conclusion no longer compares the two terms of N* as "
        f"{mass} against {margin}")
