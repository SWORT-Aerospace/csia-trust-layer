"""Phase C §§15–20 — the two interfaces, and that they mean the same thing.

The external path is a trust boundary and stays one. The internal path is not
a boundary at all, and this file is the evidence that the distinction is about
WHERE validation belongs rather than about doing less of it.
"""

import ast
import copy
import json
import os

import pytest

from csia.v1_1 import output_api as API
from csia.v2 import scenarios as SC
from csia.v2.domain import Snapshot
from csia.v2.ingest import (SUPPORTED_MAJOR_MINOR, IngestRejected,
                            NavigationDomainInput)
from csia.v2.ledger import (V2AssuranceLedger, V2LedgerContext,
                            plugin_manifest_hash)
from csia.v2.profiles import SCENARIOS, build_engine_for
from csia.v2.profiles.aircraft_scenarios import load_v1_1_example

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARIANTS = ("clean", "fixloss", "shared_source")


@pytest.fixture(params=VARIANTS)
def payload(request):
    return load_v1_1_example(request.param)


# ------------------------------------------- the validator change (§15)
def test_the_cached_validator_is_behaviourally_identical():
    """The 28 ms was `jsonschema.validate` recompiling the schema every call,
    not the cost of validating. Replacing it with a validator built once is
    an implementation change, and this asserts that — same accept/reject AND
    the same error message, including which error is chosen when a payload
    violates several rules at once.
    """
    import jsonschema
    good = load_v1_1_example("clean")
    sch = API.schema()

    def mutations():
        yield {k: v for k, v in good.items() if k != "timestamp"}
        yield dict(good, timestamp="soon")
        yield dict(good, assurance=dict(good["assurance"], level="VIBES"))
        q = copy.deepcopy(good)
        q["trust"]["nodes"]["gps"] = "high"
        yield q
        q = copy.deepcopy(good)
        del q["diagnosis"]["posterior"]
        yield q
        q = copy.deepcopy(good)
        q["diagnosis"]["posterior"] = 5.0
        yield q
        q = copy.deepcopy(good)
        q["extra_field_here"] = 1
        yield q
        q = copy.deepcopy(good)
        q["function_eligibility"] = []
        yield q
        yield "not a payload at all"
        yield {}

    def outcome(fn, doc):
        try:
            fn(doc)
            return ("OK", "")
        except Exception as exc:
            return (type(exc).__name__, str(exc))

    for doc in [good, *mutations()]:
        reference = outcome(lambda d: jsonschema.validate(d, sch), doc)
        ours = outcome(API.validate, doc)
        assert ours == reference, (reference, ours)


def test_validation_is_still_actually_performed():
    """A cached validator that validated nothing would also be fast."""
    with pytest.raises(Exception):
        API.validate({})
    with pytest.raises(Exception):
        API.validate(dict(load_v1_1_example("clean"), timestamp="soon"))


# ---------------------------------------------- the two ingest paths
def test_both_paths_produce_the_same_typed_input(payload):
    ext = NavigationDomainInput.from_external_payload(payload)
    internal = NavigationDomainInput.from_trusted_payload(payload)
    assert ext.semantic_key() == internal.semantic_key()
    assert ext.provenance_path == "external"
    assert internal.provenance_path == "internal"


def test_the_provenance_path_is_excluded_from_the_semantic_key():
    """It records WHICH interface was used and is expected to differ.
    Including it would make the equivalence test pass for the wrong reason —
    by never being equal."""
    p = load_v1_1_example("clean")
    a = NavigationDomainInput.from_external_payload(p)
    b = NavigationDomainInput.from_trusted_payload(p)
    assert a != b, "the objects differ, and that difference is the path"
    assert a.semantic_key() == b.semantic_key()


def test_the_external_path_still_rejects_what_the_monitor_rejects():
    good = load_v1_1_example("clean")
    for bad in (dict(good, schema_version="9.9.9"),
                {k: v for k, v in good.items() if k != "diagnosis"},
                dict(good, timestamp="soon")):
        with pytest.raises(IngestRejected):
            NavigationDomainInput.from_external_payload(bad)


def test_the_internal_path_is_version_locked_by_construction():
    """§20. It is not a validation shortcut for untrusted input; a payload
    from another schema version cannot become one of these at all."""
    bad = dict(load_v1_1_example("clean"), schema_version="2.0.0")
    with pytest.raises(IngestRejected, match="version-locked"):
        NavigationDomainInput.from_trusted_payload(bad)
    assert SUPPORTED_MAJOR_MINOR == ("1.1",)


def test_the_internal_path_still_rejects_a_foreign_detector():
    """The frozen CUSUM constants are checked on both paths: a payload from a
    differently configured detector means something different, and no amount
    of being in-process makes that safe to assume away."""
    bad = copy.deepcopy(load_v1_1_example("clean"))
    bad["sequential"]["h"] = 5.0
    with pytest.raises(IngestRejected, match="frozen detector"):
        NavigationDomainInput.from_trusted_payload(bad)


def test_the_internal_path_raises_rather_than_guessing_on_a_malformed_dict():
    """It does less checking, not none, and what it does not check it does
    not paper over either."""
    with pytest.raises(IngestRejected):
        NavigationDomainInput.from_trusted_payload({})
    with pytest.raises(IngestRejected):
        NavigationDomainInput.from_trusted_payload(
            {k: v for k, v in load_v1_1_example("clean").items()
             if k != "diagnosis"})


def test_the_typed_input_cannot_be_mutated_by_a_domain():
    """The plugin contract's determinism has to survive the caller too."""
    inp = NavigationDomainInput.from_trusted_payload(
        load_v1_1_example("clean"))
    with pytest.raises(TypeError):
        inp.trust["gps"] = 0.0
    with pytest.raises(Exception):
        inp.timestamp = 99.0


# ------------------------------------------- §18: end-to-end equivalence
def _run(scenario_name, use_internal, ticks=40):
    """One scenario through one interface, with its ledger."""
    sc = SCENARIOS[scenario_name]
    engine = build_engine_for(sc)
    led = V2AssuranceLedger(V2LedgerContext(
        profile=sc.system, software_sha="TEST", configuration_hash="TEST",
        plugin_manifest_hash=plugin_manifest_hash(engine)))
    base = load_v1_1_example(sc.v1_1_variant)
    typed = NavigationDomainInput.from_trusted_payload(base)
    results = []
    for snap in SC.SnapshotSource(sc, ticks=ticks):
        if use_internal:
            snap = Snapshot(t=snap.t, signals=snap.signals,
                            v1_1_input=typed.with_timestamp(snap.t))
        else:
            snap = Snapshot(t=snap.t, signals=snap.signals,
                            v1_1_payload=dict(base, timestamp=snap.t))
        a = engine.evaluate(snap)
        results.append(a)
        led.observe(a)
    return results, led


@pytest.mark.parametrize("name", ["NOMINAL", "REGULATOR_FAILURE",
                                  "ESTIMATOR_LATE", "SHARED_SOURCE",
                                  "PACKET_LOSS", "CPU_OVERLOAD"])
def test_the_two_interfaces_produce_identical_everything(name):
    """§18. Zero tolerance for discrete outputs: the same domain evidence,
    the same function results, the same cross-domain result, the same ledger
    events including their hashes."""
    ext, ext_led = _run(name, use_internal=False)
    internal, int_led = _run(name, use_internal=True)
    assert [a.to_dict() for a in ext] == [a.to_dict() for a in internal]
    assert ([e.to_dict() for e in ext_led.events]
            == [e.to_dict() for e in int_led.events])


def test_there_is_only_one_record_builder():
    """The equivalence above is structural, not a promise to keep two code
    paths in step: `evaluate` converges both interfaces onto one typed input
    before any evidence exists, and `_evaluate_input` is the only thing that
    builds records."""
    nav = os.path.join(ROOT, "csia", "v2", "domains", "navigation.py")
    tree = ast.parse(open(nav, encoding="utf-8").read())

    def calls_record(fn):
        # An actual `self._record(...)` CALL, found in the syntax tree.
        # Matching the string "record" would also match this docstring, which
        # is how a check like this quietly stops testing anything.
        return any(isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "_record"
                   for n in ast.walk(fn))

    builders = sorted(n.name for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and calls_record(n))
    # `_missing` emits the one UNAVAILABLE record for an absent or refused
    # input, which is a failure mode rather than transcription. Everything
    # that transcribes v1.1 lives in `_evaluate_input`.
    assert builders == ["_evaluate_input", "_missing"], builders


def test_a_typed_input_of_the_wrong_type_is_refused_not_ignored():
    engine = build_engine_for(SCENARIOS["NOMINAL"])
    a = engine.evaluate(Snapshot(t=0.0, signals={},
                                 v1_1_input={"not": "typed"}))
    codes = {c for r in a.records for c in r.reason_codes}
    assert "V1_1_PAYLOAD_REJECTED" in codes


def test_the_typed_input_wins_when_both_are_present():
    """A host holding the typed object has already crossed whatever boundary
    there was; re-reading the dict would be doing the work twice."""
    p = load_v1_1_example("clean")
    typed = NavigationDomainInput.from_trusted_payload(p).with_timestamp(7.0)
    engine = build_engine_for(SCENARIOS["NOMINAL"])
    both = engine.evaluate(Snapshot(
        t=7.0, signals={}, v1_1_payload=load_v1_1_example("fixloss"),
        v1_1_input=typed))
    only = engine.evaluate(Snapshot(t=7.0, signals={}, v1_1_input=typed))
    assert both.to_dict()["evidence"] == only.to_dict()["evidence"]


# ------------------------------------------------ §20: no security regression
def test_the_external_boundary_is_the_only_documented_entry_for_untrusted():
    """A grep-proof version of §20: `from_trusted_payload` must say what it
    requires, and nothing in the repo may call it on data that crossed a
    boundary. The second half is a review rule; this asserts the first, and
    asserts the callers that do exist are the harness and the tests."""
    src = open(os.path.join(ROOT, "csia", "v2", "ingest.py"),
               encoding="utf-8").read()
    assert "same process" in src and "version-locked" in src
    offenders = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "csia")):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            if path.endswith(os.path.join("v2", "ingest.py")):
                continue
            text = open(path, encoding="utf-8").read()
            if "from_trusted_payload" in text:
                offenders.append(os.path.relpath(path, ROOT))
    assert offenders == [], (
        f"{offenders} call the internal constructor; under §20 the shipped "
        f"library should reach it only through a host that has declared the "
        f"in-process, version-locked precondition")


def test_json_is_never_produced_on_the_internal_path():
    """The internal form is never serialised per tick — that is the point."""
    p = load_v1_1_example("clean")
    typed = NavigationDomainInput.from_trusted_payload(p)
    with pytest.raises(TypeError):
        json.dumps(typed)
