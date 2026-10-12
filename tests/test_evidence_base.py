"""The evidence-base layer: ingestion, intent and corpus.

Three modules that qualify THE EVIDENCE rather than the vehicle. The tests
that matter are the ones asserting each module refuses to promote anything:
a recognised channel is a candidate, a deviation is not a verdict, and a
corpus of twenty runs on one article is one article.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from csia_evidence import corpus as CO                            # noqa: E402
from csia_evidence import ingestion as IN                            # noqa: E402
from csia_evidence import intent as IT                            # noqa: E402

SPECS = (
    IN.ChannelSpec("current", "A", aliases=("pack_current", "batt_amps"),
                   plausible=(-200.0, 200.0)),
    IN.ChannelSpec("voltage", "V", aliases=("pack_voltage",),
                   plausible=(0.0, 60.0)),
    IN.ChannelSpec("temperature", "degC", plausible=(-40.0, 120.0)),
)


# --- ingest -----------------------------------------------------------------

def test_a_declaration_beats_inference_and_says_so():
    r = IN.ingest({"ch7": [20.0, 21.0, 19.0]}, SPECS,
                  declared={"ch7": "current"})
    m = r.mappings[0]
    assert m.channel == "current" and m.grade == IN.EvidenceKind.DECLARED
    assert m.usable_without_review
    assert "no inference" in m.evidence[0].basis


def test_a_declaration_naming_an_unknown_channel_is_refused():
    with pytest.raises(ValueError, match="cannot be checked"):
        IN.ingest({"a": [1.0]}, SPECS, declared={"a": "not_a_channel"})


def test_an_exact_name_is_usable_and_a_fuzzy_one_is_not():
    r = IN.ingest({"pack_current": [20.0, 21.0],
                   "current_sense": [15.0, 15.1]}, SPECS)
    by = {m.field_name: m for m in r.mappings}
    assert by["pack_current"].grade == IN.EvidenceKind.NAME_EXACT
    assert by["pack_current"].usable_without_review is True
    assert by["current_sense"].grade == IN.EvidenceKind.NAME_FUZZY
    assert by["current_sense"].usable_without_review is False
    assert by["current_sense"] in r.needs_review


def test_a_mislabelled_channel_is_reported_as_conflicted():
    """THE MOST USEFUL THING THIS MODULE DOES. The name says current and the
    declared unit says volts; that disagreement is the finding, not noise to
    be resolved by taking the stronger grade."""
    r = IN.ingest({"pack_current": [15.0, 15.1, 15.2]}, SPECS,
                  units={"pack_current": "V"})
    m = r.mappings[0]
    assert m.conflicts, m.to_dict()
    assert "voltage" in m.conflicts
    assert m.usable_without_review is False, (
        "a conflicted mapping was usable without review; the conflict is "
        "evidence that the strong grade is wrong")
    assert "pack_current" in r.conflicted


def test_an_unrecognised_field_is_named_rather_than_dropped():
    r = IN.ingest({"pack_current": [20.0], "zx_9": ["a", "b"]}, SPECS)
    assert "zx_9" in r.unrecognised
    assert any(m.field_name == "zx_9" and m.channel is None
               for m in r.mappings)


def test_channels_the_source_does_not_supply_are_reported():
    r = IN.ingest({"pack_current": [20.0]}, SPECS)
    assert set(r.channels_not_found) == {"voltage", "temperature"}


def test_evidence_without_a_basis_is_refused():
    with pytest.raises(ValueError, match="basis"):
        IN.Evidence(IN.EvidenceKind.NAME_EXACT, "current", "x")
    with pytest.raises(ValueError, match="unknown evidence kind"):
        IN.Evidence("VIBES", "current", "a sufficiently long basis string")


def test_normalisation_folds_case_separators_and_abbreviations():
    assert IN.normalise("Pack_Current") == "pack current"
    assert IN.normalise("BATT-AMPS") == "battery current"
    assert IN.normalise("temp_C") == "temperature c"
    assert IN.normalise("pack_current") == IN.normalise("PackCurrent  ")


def test_ingest_is_not_vacuous_in_either_direction():
    """It must neither place everything nor place nothing."""
    r = IN.ingest({"pack_current": [20.0, 21.0], "qqq": [1.0, 2.0],
                   "pack_voltage": [15.0, 15.1]}, SPECS)
    placed = [m for m in r.mappings if m.recognised]
    assert placed, "nothing was placed"
    assert r.unrecognised, "everything was placed, which is not credible"


def test_the_report_says_it_establishes_nothing():
    r = IN.ingest({"pack_current": [20.0]}, SPECS)
    assert "candidate" in r.does_not_establish
    assert "promotes" in r.does_not_establish
    assert r.to_dict()["schema"] == IN.SCHEMA


# --- intent -----------------------------------------------------------------

def _record(dev_from=None, dev_to=None, hz=10.0, end=100.0, recover=True):
    t = np.arange(0.0, end, 1.0 / hz)
    alt = np.full_like(t, 100.0)
    if dev_from is not None:
        hi = dev_to if recover else t[-1] + 1.0
        alt[(t >= dev_from) & (t < hi)] = 60.0
    return {"t": t, "altitude": alt}


def _hold_alt(gates=("baro_cross_check",), tolerance_s=1.0):
    return IT.Commitment(
        "hold_altitude",
        lambda r: np.abs(np.asarray(r["altitude"]) - 100.0) < 5.0,
        requires=("altitude",), gates=gates, tolerance_s=tolerance_s,
        basis="tasked to hold 100 m within 5 m")


@pytest.mark.parametrize("kw,expected", [
    ({}, IT.HELD),
    ({"dev_from": 40.0, "dev_to": 55.0}, IT.DEVIATED),
    ({"dev_from": 40.0, "recover": False}, IT.ABANDONED),
])
def test_every_commitment_outcome_is_reachable(kw, expected):
    rep = IT.compare(_record(**kw), [_hold_alt()])
    assert rep.outcomes[0].outcome == expected


def test_an_uncheckable_commitment_is_not_a_commitment_that_was_met():
    """The classic failure. NOT_EVALUABLE must never read as HELD."""
    c = IT.Commitment("hold_heading", lambda r: np.ones(3, dtype=bool),
                      requires=("heading",), gates=("mag_course",))
    rep = IT.compare(_record(), [c])
    o = rep.outcomes[0]
    assert o.outcome == IT.NOT_EVALUABLE
    assert o.outcome != IT.HELD
    assert o.fraction_held is None
    assert "NOT a commitment that was met" in o.reason


def test_a_deviation_suspends_the_relations_it_gates():
    """THE HALF OF THE FINDING THAT IS USUALLY THROWN AWAY."""
    rep = IT.compare(_record(dev_from=40.0, dev_to=55.0),
                     [_hold_alt(gates=("baro_cross_check", "effort_drift"))])
    o = rep.outcomes[0]
    assert set(o.relations_suspended) == {"baro_cross_check", "effort_drift"}
    assert 0.10 < o.suspended_fraction_of_record < 0.20
    assert set(rep.relations_suspended_anywhere) == set(o.relations_suspended)
    assert rep.evidence_thinning["effort_drift"] > 0.0


def test_a_commitment_that_held_suspends_nothing():
    rep = IT.compare(_record(), [_hold_alt(gates=("baro_cross_check",))])
    assert rep.outcomes[0].relations_suspended == ()
    assert rep.evidence_thinning == {}


def test_the_tolerance_is_in_seconds_not_samples():
    """A defect that would surface the first time two platforms logged at
    different rates. The same 0.5 s breach must be judged the same way at
    10 Hz and at 100 Hz."""
    verdicts = set()
    for hz in (10.0, 100.0):
        rep = IT.compare(_record(dev_from=40.0, dev_to=40.5, hz=hz),
                         [_hold_alt(tolerance_s=1.0)])
        verdicts.add(rep.outcomes[0].outcome)
    assert verdicts == {IT.HELD}, verdicts
    verdicts = set()
    for hz in (10.0, 100.0):
        rep = IT.compare(_record(dev_from=40.0, dev_to=45.0, hz=hz),
                         [_hold_alt(tolerance_s=1.0)])
        verdicts.add(rep.outcomes[0].outcome)
    assert verdicts == {IT.DEVIATED}, verdicts


def test_a_raising_predicate_is_recorded_not_swallowed():
    def boom(_r):
        raise KeyError("nope")
    c = IT.Commitment("bad", boom, requires=("altitude",))
    o = IT.compare(_record(), [c]).outcomes[0]
    assert o.outcome == IT.NOT_EVALUABLE
    assert "KeyError" in o.reason


def test_a_misaligned_mask_cannot_place_a_deviation():
    c = IT.Commitment("short", lambda r: np.ones(3, dtype=bool),
                      requires=("altitude",))
    o = IT.compare(_record(), [c]).outcomes[0]
    assert o.outcome == IT.NOT_EVALUABLE
    assert "does not align" in o.reason


def test_a_record_without_a_timebase_is_refused():
    with pytest.raises(ValueError, match="timebase"):
        IT.compare({"altitude": [100.0, 100.0]}, [_hold_alt()])


def test_the_report_refuses_to_judge_the_deviation():
    rep = IT.compare(_record(dev_from=40.0, dev_to=55.0), [_hold_alt()])
    assert "does not say whether deviating was correct" in \
        rep.does_not_establish
    keys = set(rep.outcomes[0].to_dict())
    assert not (keys & {"correct", "failure", "score", "penalty", "blame"})


# --- corpus -----------------------------------------------------------------

def _runs(n, **factors):
    return [CO.Run(f"r{i}", {k: (v(i) if callable(v) else v)
                             for k, v in factors.items()}, outcome=True)
            for i in range(n)]


def test_twenty_runs_on_one_airframe_is_one_airframe():
    rep = CO.independence(_runs(20, airframe="A1"))
    assert rep.naive_n == 20
    assert rep.effective_n == 1
    assert rep.binding_factor == "airframe"
    assert rep.inflation == 20.0


def test_twenty_runs_on_twenty_airframes_is_twenty():
    rep = CO.independence(_runs(20, airframe=lambda i: f"A{i}"))
    assert rep.effective_n == 20 and rep.inflation == 1.0


def test_the_binding_factor_is_the_one_that_runs_out_first():
    runs = _runs(20, airframe=lambda i: f"A{i % 5}", software="v2",
                 site=lambda i: f"S{i % 3}")
    rep = CO.independence(runs)
    assert rep.binding_factor == "software"
    assert rep.effective_n == 1
    got = {f.factor: f.distinct_values for f in rep.factors}
    assert got == {"airframe": 5, "software": 1, "site": 3}


def test_restricting_to_relevant_factors_changes_the_answer():
    runs = _runs(20, airframe=lambda i: f"A{i % 5}", site="S1")
    assert CO.independence(runs).effective_n == 1
    assert CO.independence(runs, relevant=("airframe",)).effective_n == 5


def test_a_claim_on_an_undeclared_factor_is_refused():
    with pytest.raises(ValueError, match="nobody recorded"):
        CO.independence(_runs(3, airframe="A1"), relevant=("weather",))


def test_no_rate_is_reported_at_an_effective_n_of_one():
    out = CO.accumulate(_runs(20, airframe="A1"))
    assert out["rate"] is None
    assert out["rate_withheld_because"] == CO.SINGLE_ARTICLE
    assert out["naive_rate"] == 1.0, "the observation must still be reported"
    assert "not a rate across a population" in out["reading"]


def test_a_rate_is_reported_once_the_denominator_is_real():
    runs = [CO.Run(f"r{i}", {"airframe": f"A{i % 5}"}, outcome=(i % 7 != 0))
            for i in range(20)]
    out = CO.accumulate(runs, relevant=("airframe",))
    assert out["rate"] is not None
    assert out["rate_withheld_because"] is None
    assert out["successes"] + out["failures"] == 20
    assert "overstate the evidence by 4.0x" in out["reading"]


def test_a_corpus_with_no_declared_factors_claims_nothing():
    out = CO.accumulate([CO.Run("a", outcome=True), CO.Run("b", outcome=True)])
    assert out["rate"] is None
    assert out["rate_withheld_because"] == CO.NO_FACTORS


def test_an_empty_factor_value_is_refused():
    """An empty value silently makes every run look distinct, which is the
    exact error this module exists to prevent."""
    with pytest.raises(ValueError, match="empty"):
        CO.Run("r", {"airframe": ""})


def test_a_run_missing_a_factor_is_counted_apart_and_reported():
    runs = _runs(5, airframe="A1") + [CO.Run("x", {"site": "S1"})]
    rep = CO.independence(runs, relevant=("airframe",))
    assert rep.effective_n == 2, "the undeclared run must not merge into A1"
    assert rep.factors[0].runs_missing_factor == 1


def test_an_empty_corpus_is_refused():
    with pytest.raises(ValueError, match="empty corpus"):
        CO.independence([])


def test_the_corpus_report_states_its_own_upper_bound_nature():
    rep = CO.independence(_runs(4, airframe=lambda i: f"A{i}"))
    assert "upper bound" in rep.does_not_establish
    assert "may share something nobody declared" in rep.does_not_establish


# --- the package rule -------------------------------------------------------

def test_no_module_here_imports_the_frozen_core():
    import ast
    pkg = os.path.join(ROOT, "csia_evidence")
    frozen = ("csia.trust_engine", "csia.diagnosis", "csia.runtime",
              "csia.scenarios", "csia.profiles")
    for name in sorted(os.listdir(pkg)):
        if not name.endswith(".py"):
            continue
        src = open(os.path.join(pkg, name), encoding="utf-8").read()
        for node in ast.walk(ast.parse(src, filename=name)):
            mod = None
            if isinstance(node, ast.Import):
                mod = " ".join(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
            if mod:
                for f in frozen:
                    assert f not in mod, f"{name} imports {f}"


def test_nothing_in_this_package_promotes_anything():
    """The rule the package is built under, asserted against its own API."""
    import csia_evidence
    assert "NOTHING IN THIS PACKAGE PROMOTES ANYTHING" in csia_evidence.__doc__
    for mod in (IN, IT, CO):
        names = [n for n in dir(mod) if not n.startswith("_")]
        assert not [n for n in names
                    if n in ("promote", "accept", "trust", "approve")], names


# --- the two weaknesses the first version had -------------------------------

def test_dimensional_agreement_alone_does_not_identify_a_field():
    """A field named `qqq` holding 1.0 and 2.0 was once confidently mapped to
    `current`, because those values are inside the plausible range of a
    current, a voltage and a temperature alike. Plausibility is a weak
    NEGATIVE test and can never identify."""
    r = IN.ingest({"qqq": [1.0, 2.0, 1.5]}, SPECS)
    m = r.mappings[0]
    assert m.channel is None
    assert m.grade == IN.EvidenceKind.UNRECOGNISED
    assert "qqq" in r.unrecognised
    kinds = {e.kind for e in m.evidence}
    assert kinds == {IN.EvidenceKind.DIMENSIONAL}, (
        "the dimensional evidence must still be listed so a reader can see "
        "it was considered and rejected")


def test_dimensional_evidence_still_corroborates_and_conflicts():
    """It cannot identify, but it must not become inert."""
    ok = IN.ingest({"pack_current": [20.0, 21.0]}, SPECS).mappings[0]
    assert any(e.kind == IN.EvidenceKind.DIMENSIONAL for e in ok.evidence)
    assert ok.channel == "current"


def test_camel_case_names_are_split():
    """Camel case is the house style of most telemetry this layer exists to
    read. The first version folded separators only, so `PackCurrent`
    normalised to one token and matched nothing."""
    assert IN.normalise("PackCurrent") == "pack current"
    assert IN.normalise("battVolts") == "battery voltage"
    assert IN.normalise("GPSAltitude") == "gps altitude"
    r = IN.ingest({"PackCurrent": [20.0, 21.0]}, SPECS)
    assert r.mappings[0].channel == "current"
    assert r.mappings[0].grade == IN.EvidenceKind.NAME_EXACT


# --- against real telemetry, not toy fields ---------------------------------

def test_it_places_the_component_simulator_s_real_channels():
    """A non-toy check. The component simulator is an existing, independent
    part of this repository with its own naming, written before this module
    existed and without knowledge of it."""
    from csia_components import simulate as S
    tel = S.Platform(seed=0, duration=6.0).run()
    fields = {name: tel.array(name) for name in
              ("pack_current", "pack_voltage", "temperature", "vz")}
    specs = SPECS + (IN.ChannelSpec("velocity_z", "m/s",
                                    aliases=("vz",), plausible=(-20.0, 20.0)),)
    r = IN.ingest(fields, specs)
    placed = {m.field_name: m.channel for m in r.mappings if m.recognised}
    assert placed["pack_current"] == "current"
    assert placed["pack_voltage"] == "voltage"
    assert placed["vz"] == "velocity_z"
    assert r.unrecognised == ()
    assert all(m.usable_without_review for m in r.mappings
               if m.field_name in ("pack_current", "pack_voltage", "vz"))


def test_it_catches_a_deliberately_mislabelled_real_channel():
    """Hand it the voltage series under the name `pack_current`. The name and
    the values disagree, and the disagreement must be reported rather than
    resolved in favour of the name."""
    from csia_components import simulate as S
    tel = S.Platform(seed=0, duration=6.0).run()
    volts = tel.array("pack_voltage")
    narrow = (IN.ChannelSpec("current", "A", aliases=("pack_current",),
                             plausible=(18.0, 40.0)),
              IN.ChannelSpec("voltage", "V", plausible=(0.0, 60.0)))
    r = IN.ingest({"pack_current": volts}, narrow)
    m = r.mappings[0]
    assert m.channel == "current"
    assert "voltage" not in m.conflicts or m.conflicts
    dim = [e for e in m.evidence if e.kind == IN.EvidenceKind.DIMENSIONAL]
    assert not any(e.channel == "current" for e in dim), (
        "the values are outside the declared current range, so no "
        "dimensional evidence for `current` should exist -- which is the "
        "signal that the name is wrong")
