"""The paired-design fix: an independent baseline window.

`PREREGISTRATION_AMENDMENT_4.md`. The completed phase's change metric saturated
because the nominal and fault windows shared a seed, which made
``V_fault - V_nominal = -dR.I_true`` exact and cancelled every plant-common
nuisance. These tests pin the three baseline sources, prove the cancellation is
actually broken, and check that the guard which used to forbid this still
forbids the accidental version of it.
"""
from __future__ import annotations

import pytest

from csia_independent_validation import followup_partitions as fp
from csia_independent_validation import runner
from csia_independent_validation.truth import GroundTruth, TruthPair

DEV = fp.seeds("development")


def cell(**overrides) -> runner.Cell:
    base = dict(plant="Q1", drift_state="nominal", magnitude=0.010,
                seed=DEV[0])
    base.update(overrides)
    return runner.Cell(**base)


# --- the partitions -------------------------------------------------------

def test_the_followup_manifest_is_pinned():
    assert fp.manifest_hash() == (
        "b6af853781b62631dde39c5b0c83a623a3c3c458d7936d10ac2ccb8218702515")


def test_no_followup_seed_is_a_phase_one_seed():
    fp.assert_disjoint_from_phase_one()


def test_no_companion_collides_with_a_campaign_seed():
    fp.assert_companions_are_not_fault_seeds()


def test_companions_are_derived_not_offset():
    """`seed + 1` is a choice somebody could have made differently."""
    seeds = fp.seeds("development")
    companions = [fp.companion(s) for s in seeds]
    offsets = {c - s for s, c in zip(seeds, companions)}
    assert len(offsets) == len(seeds), "companions look like a fixed offset"


def test_the_followup_final_partition_is_sealed():
    with pytest.raises(PermissionError):
        fp.seeds("final")


# --- the three baseline sources ------------------------------------------

def test_paired_crn_uses_the_same_action_and_seed():
    campaign = runner.Campaign()
    target = cell(nominal_source="paired_crn")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action == action
    assert baseline_seed == target.seed


def test_independent_seed_keeps_the_action_and_moves_the_seed():
    campaign = runner.Campaign()
    target = cell(nominal_source="independent_seed")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action == action
    assert baseline_seed == fp.companion(target.seed)
    assert baseline_seed != target.seed


def test_independent_window_moves_the_action_too():
    campaign = runner.Campaign()
    target = cell(nominal_source="independent_window")
    action = runner.st.p2_compensated(runner.observable())
    baseline_action, baseline_seed = campaign._baseline(action, target)
    assert baseline_action.name == runner.REFERENCE_ACTION
    assert baseline_seed == fp.companion(target.seed)


def test_an_unknown_nominal_source_is_refused():
    with pytest.raises(ValueError):
        runner.Cell(plant="Q1", drift_state="nominal", magnitude=0.010,
                    seed=1, nominal_source="whatever")


# --- the cancellation is actually broken ---------------------------------

def test_the_paired_design_cancellation_is_broken_by_an_independent_window():
    """The whole point of the amendment, measured.

    Under the paired design the change error is the finite-sample EIV term and
    nothing else. Once the baseline comes from a different window it carries
    the baseline's own estimation error too, which is orders of magnitude
    larger.
    """
    campaign = runner.Campaign()
    errors = {}
    for source in runner.NOMINAL_SOURCES:
        row = campaign.row("P2_compensated", cell(nominal_source=source))
        errors[source] = abs(row["e_delta_r"])
    assert errors["independent_seed"] > 10 * errors["paired_crn"]
    assert errors["independent_window"] > 10 * errors["paired_crn"]


def test_the_point_error_is_untouched_by_the_baseline_choice():
    """`AE_R` scores the fault window alone, so it must not move."""
    campaign = runner.Campaign()
    values = {source: campaign.row("P2_compensated",
                                   cell(nominal_source=source))["ae_r"]
              for source in runner.NOMINAL_SOURCES}
    assert len(set(values.values())) == 1


def test_every_source_is_reachable_for_every_arm():
    campaign = runner.Campaign()
    for source in runner.NOMINAL_SOURCES:
        for arm in ("P0_passive", "P2_compensated", "S2_threshold"):
            row = campaign.row(arm, cell(nominal_source=source))
            assert row["nominal_source"] == source


def test_rows_record_which_window_the_baseline_came_from():
    campaign = runner.Campaign()
    row = campaign.row("P2_compensated",
                       cell(nominal_source="independent_window"))
    assert row["baseline_action"] == runner.REFERENCE_ACTION
    assert row["baseline_seed"] == fp.companion(row["seed"])


# --- the guard that used to forbid this still forbids the accident -------

def _truth(seed, plant="Q1", realized=0.040):
    return GroundTruth(plant=plant, r0_nominal=0.040, r0_realized=realized,
                       fault_label="none", seed=seed)


def test_a_mismatched_pair_is_still_refused_by_default():
    with pytest.raises(ValueError):
        TruthPair(nominal=_truth(1), fault=_truth(2, realized=0.050))


def test_independence_must_be_spelled_out_to_be_allowed():
    pair = TruthPair(nominal=_truth(1), fault=_truth(2, realized=0.050),
                     independent_windows=True)
    assert pair.true_delta_r == pytest.approx(0.010)


def test_the_plant_guard_survives_independence():
    """Different windows, yes. Different plants, never."""
    with pytest.raises(ValueError):
        TruthPair(nominal=_truth(1, plant="Q0"),
                  fault=_truth(2, plant="Q1", realized=0.050),
                  independent_windows=True)


# --- the follow-up campaign tool ------------------------------------------
#
# The reductions, not the run. A campaign takes an hour; the arithmetic that
# turns it into a verdict takes microseconds and is where a wrong answer would
# actually hide.

from tools.research import iv_followup_campaign as fc   # noqa: E402


def test_the_followup_omits_every_ceiling():
    """Amendment 4 section 4. A ceiling here would need `nominal_source`
    threaded through the arena, and a regret number that ignored the factor
    would be worse than no regret number."""
    assert len(fc.FOLLOWUP_ARMS) == 11
    for arm in fc.FOLLOWUP_ARMS:
        assert not arm.startswith("P7"), arm


def test_the_preregistered_thresholds_match_the_amendment():
    assert fc.H8_SPREAD == 0.05
    assert fc.H9_FACTOR == 2.0
    assert fc.H9_CONTROL_TOLERANCE == 0.05
    assert fc.H10_RHO == 0.7


def test_spearman_is_tie_aware():
    """Average ranks. Midranks on a tied block, not first-seen order."""
    assert fc._ranks([3.0, 1.0, 2.0]) == [3.0, 1.0, 2.0]
    assert fc._ranks([1.0, 1.0, 2.0]) == [1.5, 1.5, 3.0]
    assert fc._ranks([5.0, 5.0, 5.0]) == [2.0, 2.0, 2.0]


def test_spearman_agrees_with_the_textbook_case():
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert fc.spearman(a, a) == pytest.approx(1.0)
    assert fc.spearman(a, list(reversed(a))) == pytest.approx(-1.0)
    # Monotone but not linear: rank correlation is still exactly one.
    assert fc.spearman(a, [1.0, 4.0, 9.0, 16.0, 25.0]) == pytest.approx(1.0)


def test_spearman_refuses_a_constant_vector():
    """This is the case that matters: the sealed change metric IS constant
    across thirteen arms. A correlation against a constant is undefined, and
    reporting 0.0 would read as 'the orderings disagree' -- a claim the data
    does not make."""
    assert fc.spearman([1.0, 2.0, 3.0, 4.0], [7.0] * 4) is None
    assert fc.spearman([2.0] * 4, [1.0, 2.0, 3.0, 4.0]) is None


def test_spearman_declines_a_sample_too_small_to_rank():
    assert fc.spearman([1.0, 2.0], [1.0, 2.0]) is None
    assert fc.spearman([1.0, 2.0, 3.0], [1.0, 2.0]) is None


def _row(**kw):
    base = dict(arm="P2_lag_aware", plant="Q1", drift_state="nominal",
                magnitude=0.010, seed=1, nominal_source="paired_crn",
                resolved=True, m_r_out=1.0, ae_r=1e-4, e_delta_r=1e-6,
                state="CERTIFIED_IN_MODEL", abstention=None, action="a",
                baseline_action="a", baseline_seed=1, block="main",
                energy_as=50.0)
    base.update(kw)
    return base


def test_h10_reports_undefined_rather_than_a_number_when_one_side_is_flat():
    rows = []
    for index, arm in enumerate(fc.FOLLOWUP_ARMS):
        for magnitude in (0.002, 0.040):
            rows.append(_row(arm=arm, magnitude=magnitude,
                             nominal_source="independent_window",
                             resolved=index % 2 == 0))
            # point metric identical for every arm -> constant A_s
            rows.append(_row(arm=arm, magnitude=magnitude,
                             nominal_source="paired_crn", ae_r=1e-9))
    verdict = fc.assess_h10(rows)
    assert verdict["spearman_rho"] is None
    assert verdict["verdict"] == "UNDEFINED_ONE_SIDE_IS_CONSTANT"


def test_h9_says_precondition_failed_rather_than_rejected():
    """If the paired_crn control does not behave as the amendment predicts,
    H9's comparison has no reference and the honest answer is neither
    SUPPORTED nor REJECTED."""
    rows = []
    for plant, value in zip(("Q0", "Q1", "Q2"), (1e-6, 5e-6, 9e-6)):
        rows.append(_row(plant=plant, e_delta_r=value,
                         nominal_source="paired_crn"))
        rows.append(_row(plant=plant, e_delta_r=value,
                         nominal_source="independent_seed"))
        rows.append(_row(plant=plant, e_delta_r=value * 10,
                         nominal_source="independent_window"))
    verdict = fc.assess_h9(rows)
    assert verdict["control_precondition_holds"] is False
    assert verdict["verdict"] == "PRECONDITION_FAILED"


def test_h9_is_supported_only_when_the_control_is_flat_and_the_break_is_not():
    rows = []
    for plant, factor in zip(("Q0", "Q1", "Q2"), (1.0, 3.0, 9.0)):
        rows.append(_row(plant=plant, e_delta_r=1e-6,
                         nominal_source="paired_crn"))
        rows.append(_row(plant=plant, e_delta_r=1e-6 * factor,
                         nominal_source="independent_seed"))
        rows.append(_row(plant=plant, e_delta_r=1e-6 * factor,
                         nominal_source="independent_window"))
    verdict = fc.assess_h9(rows)
    assert verdict["control_precondition_holds"] is True
    assert verdict["by_source"]["independent_window"]["ratio"] == \
        pytest.approx(9.0)
    assert verdict["verdict"] == "SUPPORTED"


def test_the_point_metric_invariance_check_catches_a_contaminated_factor():
    """`nominal_source` touches the baseline only. If AE_R ever moves with it
    the factor is leaking, and every H8/H9/H10 reading is void."""
    clean = [_row(nominal_source=source, ae_r=2.5e-4)
             for source in runner.NOMINAL_SOURCES]
    assert fc.point_metric_invariance(clean)["identical_everywhere"] is True

    dirty = list(clean)
    dirty[2] = _row(nominal_source="independent_window", ae_r=2.6e-4)
    report = fc.point_metric_invariance(dirty)
    assert report["identical_everywhere"] is False
    assert report["max_ae_r_spread_across_levels"] == pytest.approx(1e-5)
    assert report["first_offenders"]


def test_h8_needs_both_broken_levels_for_an_unqualified_verdict():
    def area_rows(source, spread):
        out = []
        for index, arm in enumerate(fc.FOLLOWUP_ARMS):
            resolved = index == 0 or not spread
            for magnitude in (0.002, 0.040):
                out.append(_row(arm=arm, magnitude=magnitude,
                                nominal_source=source, resolved=resolved))
        return out

    rows = (area_rows("paired_crn", False)
            + area_rows("independent_seed", True)
            + area_rows("independent_window", False))
    verdict = fc.assess_h8(rows)
    assert verdict["levels_that_broke_saturation"] == ["independent_seed"]
    assert verdict["verdict"] == "PARTIALLY_SUPPORTED"

    rows = (area_rows("paired_crn", False)
            + area_rows("independent_seed", False)
            + area_rows("independent_window", False))
    assert fc.assess_h8(rows)["verdict"] == "REJECTED"


# --- the report renderer --------------------------------------------------

from tools.research import iv_followup_report as fr        # noqa: E402


def _document(**overrides):
    reduction = {
        "regret": "not computed.",
        "point_metric_invariance": {
            "matched_groups_compared": 12,
            "max_ae_r_spread_across_levels": 0.0,
            "identical_everywhere": True,
            "first_offenders": [],
        },
        "by_nominal_source": {
            source: {
                "n": 10,
                "resolved_fraction_change": 0.5,
                "median_abs_e_delta_r": value,
                "by_arm_and_drift": {"P2_lag_aware/nominal": {}},
                "false_certificates_change_metric": [],
                "false_certificates_point_metric": [],
                "state_counts": {},
            }
            for source, value in zip(fr.SOURCES, (1e-6, 1e-4, 3e-4))
        },
        "H8_saturation_is_a_design_artifact": {
            "threshold": 0.05, "statement": "s8", "falsifier": "f8",
            "by_source": {s: {"A_s_by_arm": {"P2_lag_aware": 0.9},
                              "spread": 0.0, "exceeds_threshold": False}
                          for s in fr.SOURCES},
            "levels_that_broke_saturation": [],
            "verdict": "REJECTED",
            "vacuity": {"verdict": "DISCRIMINATING",
                        "control_also_exceeds_the_threshold": False,
                        "why": "the control does not exceed the threshold",
                        "superseded_by": "H8_prime"},
            "H8_prime": {
                "statement": "s8p",
                "preregistration": "PREREGISTRATION_AMENDMENT_5.md",
                "excited_arms": ["P2_lag_aware"], "excluded_arms": [],
                "excluded_because": "mean energy_as == 0",
                "by_source": {s: {"A_s_by_excited_arm": {"P2_lag_aware": 0.9},
                                  "spread": 0.0, "flat": True}
                              for s in fr.SOURCES},
                "control_is_flat": True,
                "levels_that_broke_saturation": [],
                "verdict": "REJECTED",
                "falsifier": "f8p",
            },
        },
        "H9_change_metric_recovers_plant_structure": {
            "factor_threshold": 2.0, "control_tolerance": 0.05,
            "statement": "s9", "falsifier": "f9",
            "by_source": {s: {"median_abs_e_delta_r":
                              {"Q0": 1e-6, "Q1": 1e-6, "Q2": 1e-6},
                              "ratio": 1.0} for s in fr.SOURCES},
            "control_precondition_holds": True,
            "verdict": "REJECTED",
        },
        "H10_ordering_is_preserved": {
            "rho_threshold": 0.7, "statement": "s10", "falsifier": "f10",
            "arms": ["P2_lag_aware"],
            "A_s_change_independent_window": {"P2_lag_aware": 0.9},
            "A_s_point_paired_crn": {"P2_lag_aware": 0.8},
            "spearman_rho": None,
            "verdict": "UNDEFINED_ONE_SIDE_IS_CONSTANT",
            "if_rejected": "conditional on the metric",
        },
    }
    document = {
        "partition": "final", "seeds": [1, 2, 3],
        "partition_manifest_sha256": "aa",
        "phase_one_partition_manifest_sha256": "bb",
        "arms": ["P2_lag_aware"],
        "arms_omitted": ["P7b_oracle"],
        "reference_action": "cosine3_10A_8s",
        "preregistration": "PREREGISTRATION_AMENDMENT_4.md + "
                           "PREREGISTRATION_AMENDMENT_5.md",
        "n_rows": 30, "plant_simulations": 60, "elapsed_s": 12.0,
        "what_this_is_not": "Simulator only.",
        "reduction": reduction,
    }
    document.update(overrides)
    return document


def test_the_report_prints_a_rejection_verbatim():
    """There is no branch in the renderer that softens a rejected
    hypothesis, and this is what stops one being added."""
    text = fr.render(_document())
    # H8, H8' and H9 in the fixture. H8' is a separate verdict line and must
    # be printed too, not folded into H8's.
    assert text.count("**Verdict: REJECTED.**") == 3
    assert "**Verdict: UNDEFINED_ONE_SIDE_IS_CONSTANT.**" in text
    for falsifier in ("f8", "f8p", "f9", "f10"):
        assert falsifier in text


def test_the_report_prints_an_undefined_rho_as_a_dash_not_a_zero():
    text = fr.render(_document())
    assert "Spearman ρ = **—**" in text
    assert "0.0000** against a floor" not in text


def test_the_report_says_regret_was_not_computed():
    text = fr.render(_document())
    assert "**Regret.** not computed." in text
    assert "no comparison to a sealed-campaign regret" in text.lower() or \
        "sealed-campaign regret" in text


def test_the_report_refuses_to_claim_novelty_or_certification():
    text = fr.render(_document()).lower()
    assert "nothing here is a novelty claim" in text
    assert "no certified safety artifact" in text
    for forbidden in ("first to", "state of the art", "novel contribution",
                      "airworthy", "production ready"):
        assert forbidden not in text


def test_the_report_surfaces_a_contaminated_factor_instead_of_hiding_it():
    document = _document()
    document["reduction"]["point_metric_invariance"] = {
        "matched_groups_compared": 12,
        "max_ae_r_spread_across_levels": 1e-5,
        "identical_everywhere": False,
        "first_offenders": [{"cell": ["P2_lag_aware", "Q1", "nominal",
                                      0.01, 7], "ae_r": {"paired_crn": 1.0}}],
    }
    text = fr.render(document)
    assert "identical everywhere: **no**" in text
    assert "Offending cells" in text


# --- H8', Amendment 5 -----------------------------------------------------

def _h8_rows(source, *, passive_zero=True, excited_spread=0.0):
    """Rows shaped like a campaign: one zero-energy arm, ten excited ones."""
    out = []
    for index, arm in enumerate(fc.FOLLOWUP_ARMS):
        passive = arm == "P0_passive"
        energy = 0.0 if (passive and passive_zero) else 50.0
        for magnitude in (0.002, 0.040):
            if passive and passive_zero:
                resolved = False
            elif excited_spread and index == 1:
                resolved = False
            else:
                resolved = True
            out.append(_row(arm=arm, magnitude=magnitude, resolved=resolved,
                            nominal_source=source, energy_as=energy))
    return out


def test_excited_arms_is_measured_not_a_hard_coded_name():
    """Naming P0_passive in the code would be a hand-pick that happens to be
    right today. The property is zero injected energy."""
    rows = _h8_rows("paired_crn")
    assert "P0_passive" not in fc.excited_arms(rows)
    assert len(fc.excited_arms(rows)) == len(fc.FOLLOWUP_ARMS) - 1

    # Give the passive arm energy and it comes back; take it away from another
    # arm and that one leaves. Nothing is keyed on the string.
    energised = [dict(r, energy_as=50.0) for r in rows]
    assert "P0_passive" in fc.excited_arms(energised)
    drained = [dict(r, energy_as=0.0) if r["arm"] == "P2_compensated" else r
               for r in rows]
    assert "P2_compensated" not in fc.excited_arms(drained)


def test_the_preregistered_h8_is_reported_as_vacuous_not_deleted():
    """The control passes it, so it measures nothing -- and it still appears
    in the artifact, with its number next to the control's."""
    rows = (_h8_rows("paired_crn")
            + _h8_rows("independent_seed", excited_spread=1)
            + _h8_rows("independent_window", excited_spread=1))
    block = fc.assess_h8(rows)
    assert block["by_source"]["paired_crn"]["exceeds_threshold"] is True
    assert block["vacuity"]["verdict"] == "VACUOUS_IN_ENVELOPE"
    assert block["vacuity"]["control_also_exceeds_the_threshold"] is True
    assert block["verdict"] == "SUPPORTED"      # and worth nothing
    assert "A_s_by_arm" in block["by_source"]["paired_crn"]


def test_h8_is_discriminating_when_no_arm_is_degenerate():
    """Vacuity is computed from the control, not asserted. Give every arm a
    probe and the literal statistic separates the levels again."""
    rows = []
    for source, spread in (("paired_crn", 0), ("independent_seed", 1),
                           ("independent_window", 1)):
        rows += [dict(r, energy_as=50.0)
                 for r in _h8_rows(source, passive_zero=False,
                                   excited_spread=spread)]
    block = fc.assess_h8(rows)
    assert block["by_source"]["paired_crn"]["exceeds_threshold"] is False
    assert block["vacuity"]["verdict"] == "DISCRIMINATING"


def test_h8_prime_excludes_the_zero_energy_arm_and_flattens_the_control():
    rows = (_h8_rows("paired_crn")
            + _h8_rows("independent_seed", excited_spread=1)
            + _h8_rows("independent_window", excited_spread=1))
    prime = fc.assess_h8(rows)["H8_prime"]
    assert prime["excluded_arms"] == ["P0_passive"]
    assert prime["by_source"]["paired_crn"]["spread"] == pytest.approx(0.0)
    assert prime["control_is_flat"] is True
    assert prime["verdict"] == "SUPPORTED"
    assert "P0_passive" not in prime["by_source"]["paired_crn"][
        "A_s_by_excited_arm"]


def test_h8_prime_fails_when_the_control_is_not_flat():
    """The property that made H8 unfalsifiable: an unconstrained control.
    H8' fails here rather than reporting a broken level as a success."""
    rows = (_h8_rows("paired_crn", excited_spread=1)
            + _h8_rows("independent_seed", excited_spread=1)
            + _h8_rows("independent_window", excited_spread=1))
    prime = fc.assess_h8(rows)["H8_prime"]
    assert prime["control_is_flat"] is False
    assert prime["verdict"] == "REJECTED_CONTROL_IS_NOT_FLAT"


def test_h8_prime_is_rejected_when_breaking_the_pairing_changes_nothing():
    rows = (_h8_rows("paired_crn")
            + _h8_rows("independent_seed")
            + _h8_rows("independent_window"))
    prime = fc.assess_h8(rows)["H8_prime"]
    assert prime["control_is_flat"] is True
    assert prime["levels_that_broke_saturation"] == []
    assert prime["verdict"] == "REJECTED"


# --- resolution with no signal behind it ----------------------------------

def test_zero_energy_resolutions_are_counted_and_the_certificate_refuses():
    """The change metric can score a resolution where no probe was injected.
    Both halves get a number: how often it happens, and how many of those the
    certificate let through."""
    rows = [
        _row(arm="P0_passive", energy_as=0.0, resolved=True,
             state="INSUFFICIENT_EXCITATION", nominal_source="independent_seed"),
        _row(arm="P0_passive", energy_as=0.0, resolved=False,
             state="INSUFFICIENT_EXCITATION", nominal_source="independent_seed"),
        _row(arm="P2_lag_aware", energy_as=50.0, resolved=True,
             nominal_source="independent_seed"),
    ]
    block = fc.resolution_without_excitation(rows)["by_source"]
    seed = block["independent_seed"]
    assert seed["zero_energy_rows"] == 2       # the excited arm is excluded
    assert seed["resolved_anyway"] == 1
    assert seed["rate"] == pytest.approx(0.5)
    assert seed["of_those_certified"] == 0
    assert seed["states"] == {"INSUFFICIENT_EXCITATION": 1}


def test_a_certified_zero_energy_resolution_would_be_counted_separately():
    """If the certificate ever did let one through, the count would move. It
    is a separate field precisely so a zero there means something."""
    rows = [_row(arm="P0_passive", energy_as=0.0, resolved=True,
                 state="CERTIFIED_IN_MODEL", nominal_source="paired_crn")]
    seed = fc.resolution_without_excitation(rows)["by_source"]["paired_crn"]
    assert seed["of_those_certified"] == 1


def test_the_report_prints_the_zero_energy_table():
    document = _document()
    document["reduction"]["resolution_without_excitation"] = {
        "by_source": {s: {"zero_energy_rows": 288, "resolved_anyway": 22,
                          "rate": 22 / 288, "of_those_certified": 0,
                          "states": {}} for s in fr.SOURCES},
        "what_it_shows": "the outcome metric can score a resolution",
    }
    text = fr.render(document)
    assert "## Resolution with nothing injected" in text
    assert "0.0764" in text


# --- the seal-opening record ----------------------------------------------

from tools.research import iv_followup_seal_record as sr    # noqa: E402


def test_the_seal_record_reads_a_recorded_exit_code_rather_than_asserting(
        tmp_path):
    green = tmp_path / "green.txt"
    green.write_text("....... [100%]\nPYTEST_EXIT=0\n")
    code, count, _ = sr._suite(green)
    assert code == 0 and count == 7

    red = tmp_path / "red.txt"
    red.write_text("F..\n3 passed\nPYTEST_EXIT=1\n")
    code, count, _ = sr._suite(red)
    assert code == 1 and count == 3


def test_the_seal_record_refuses_to_write_after_a_red_suite(tmp_path,
                                                            monkeypatch):
    """A record that says the seal was opened from a green tree, written from
    a red one, is worse than no record."""
    red = tmp_path / "red.txt"
    red.write_text("PYTEST_EXIT=1\n")
    monkeypatch.setattr(sr, "_dirty_paths", lambda: [])
    assert sr.main(red, force_dirty=False) == 1


def test_the_seal_record_refuses_to_write_from_a_dirty_tree(tmp_path,
                                                            monkeypatch):
    green = tmp_path / "green.txt"
    green.write_text("PYTEST_EXIT=0\n")
    monkeypatch.setattr(sr, "_dirty_paths", lambda: [" M some/file.py"])
    assert sr.main(green, force_dirty=False) == 1


def test_a_missing_exit_marker_is_not_read_as_success(tmp_path):
    """`pytest ... | tail` loses the exit status -- this phase's most
    repeated defect. A file with no marker must not pass for zero."""
    silent = tmp_path / "silent.txt"
    silent.write_text("........ [100%]\n")
    code, _, _ = sr._suite(silent)
    assert code is None


def test_the_seal_record_derives_the_frozen_core_digest_it_prints():
    """An earlier version printed `unknown` in the digest column, because
    BUILD_PROVENANCE.json records whether the core drifted but not its digest.
    A record that says `unknown` where a digest belongs looks complete and
    tells a reader nothing."""
    digest, count, differ = sr._frozen_core()
    assert count == 12
    assert differ == [], differ
    assert digest == (
        "b0b011c61426a70ead42e170855a2650d5c62feb640c7a50fffc27bb915ba5a8")
