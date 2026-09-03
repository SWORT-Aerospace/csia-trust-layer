"""§§23, 24, 31, 33 — the v2 ledger, the v2 API, and the boundaries.

The API tests are mostly about what the document may NOT contain. A schema is
easy to extend and hard to un-extend, and two of the fields that would be most
natural to add — a system health score, and a recommended action — would each
undo a commitment made deliberately elsewhere.
"""

import ast
import json
import os

import pytest

from csia.v2 import api as API
from csia.v2 import scenarios as SC
from csia.v2.ledger import (V2AssuranceLedger, V2LedgerContext,
                            plugin_manifest_hash)
from csia.v2.profiles import SCENARIOS, build_engine_for
from csia.v2.profiles.aircraft_scenarios import example_payload_feed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, "csia", "v2")


def run_with_ledger(name, ticks=40):
    sc = SCENARIOS[name]
    engine = build_engine_for(sc)
    led = V2AssuranceLedger(V2LedgerContext(
        profile=sc.system, software_sha="TEST", configuration_hash="TEST",
        plugin_manifest_hash=plugin_manifest_hash(engine)))
    feed = (example_payload_feed(sc.v1_1_variant)
            if sc.system == "aircraft" else None)
    results = []
    for snap in SC.SnapshotSource(sc, ticks=ticks, payload_for=feed):
        a = engine.evaluate(snap)
        results.append(a)
        led.observe(a)
    return engine, led, results


# =============================================================== §23 ledger
def test_the_ledger_records_the_domain_and_component_not_just_the_state():
    """§23. A v1.1 event says a function changed; a v2 event has to answer
    which domain and which component, or the extra domains bought nothing."""
    _, led, _ = run_with_ledger("REGULATOR_FAILURE")
    fn_events = [e for e in led.events
                 if e.event_type == "FUNCTION_STATE_CHANGED"]
    assert fn_events
    for e in fn_events:
        assert e.domain and e.component and e.limiting_domain
        assert e.affected_functions


def test_a_change_of_limiting_domain_opens_an_event_of_its_own():
    """"Still degraded, but now because of power rather than compute" is
    exactly what an investigator needs, and a state-only ledger loses it."""
    from csia.v2.ledger import EVENT_TYPES
    assert "LIMITING_DOMAIN_CHANGED" in EVENT_TYPES


def test_the_attribution_is_carried_in_every_event():
    """It changes: the same function can be INELIGIBLE with a unique cause
    at one tick and an ambiguous one at another."""
    _, led, _ = run_with_ledger("SHARED_RAIL")
    for e in led.events:
        assert set(e.attribution) == {"verdict", "candidates", "common_cause",
                                      "unsupported", "discriminators"}


def test_dependencies_reach_the_ledger_so_a_common_cause_is_legible_later():
    _, led, _ = run_with_ledger("SHARED_RAIL")
    assert any(e.dependencies for e in led.events)


def test_the_chain_verifies_and_detects_a_rewritten_event():
    _, led, _ = run_with_ledger("CPU_OVERLOAD")
    ok, problems = led.verify_chain()
    assert ok and not problems
    led.events[3].new_state = "ELIGIBLE"                  # tamper
    ok, problems = led.verify_chain()
    assert not ok and problems


def test_the_ledger_replays_identically():
    """§23's determinism. Event ids are hashes of content and sequence, never
    random, so the same trace on the same software gives the same ids."""
    _, a, _ = run_with_ledger("POWER_SAG")
    _, b, _ = run_with_ledger("POWER_SAG")
    assert [e.to_dict() for e in a.events] == [e.to_dict() for e in b.events]


def test_the_plugin_manifest_hash_makes_a_mismatched_replay_detectable():
    air = build_engine_for(SCENARIOS["NOMINAL"])
    bench = build_engine_for(SCENARIOS["TS_NOMINAL"])
    assert plugin_manifest_hash(air) != plugin_manifest_hash(bench)
    assert plugin_manifest_hash(air) == plugin_manifest_hash(
        build_engine_for(SCENARIOS["NOMINAL"]))


def test_the_ledger_never_calls_itself_a_blockchain():
    """The mechanism is a simple hash chain for detecting a missing or
    reordered event, and describing it as anything more would be a claim
    nothing here supports."""
    _, led, _ = run_with_ledger("NOMINAL", ticks=3)
    note = led.to_dict()["chain_note"].lower()
    assert "not a blockchain" in note
    assert "not tamper-proof" in note
    source = open(os.path.join(V2, "ledger.py"), encoding="utf-8").read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Name)):
            label = getattr(node, "name", "") or getattr(node, "id", "")
            assert "blockchain" not in label.lower()


def test_a_ledger_module_never_uses_a_random_identifier():
    """§17's rule, inherited: an id that is not a function of content cannot
    be reproduced by a replay."""
    tree = ast.parse(open(os.path.join(V2, "ledger.py"),
                          encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name not in ("uuid", "random", "secrets", "time")
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in ("uuid", "random", "secrets",
                                               "time")
        elif isinstance(node, ast.Attribute):
            assert node.attr not in ("uuid4", "uuid1", "random", "token_hex")


# ================================================================== §24 API
def _doc(name="REGULATOR_FAILURE"):
    engine, led, results = run_with_ledger(name)
    return API.build(results[-1], profile="aircraft",
                     provenance={"software_sha": "TEST"},
                     declarations=engine.declarations(),
                     ledger_events=[e.to_dict() for e in led.events[-2:]])


def test_the_v2_document_validates_and_carries_what_section_16_asks_for():
    doc = API.validate(_doc())
    assert doc["schema_version"] == "2.0.0"
    assert doc["system"] in API.SYSTEM_STATES
    assert doc["domains"] and doc["functions"] and doc["evidence"]
    for row in doc["functions"].values():
        assert "limiting_domain" in row


def test_v2_ingests_v1_1_and_does_not_change_schema_1_1_0():
    """§24. One direction only: v2 reads v1.1 payloads and writes its own
    document. It has no path back to the v1.1 producer, so a v1.1 consumer
    sees byte-identical output whether or not v2 exists."""
    doc = _doc()
    assert doc["ingests"]["csia_output_v1_1"] == "1.1.0"
    from csia.v1_1 import output_api as V1API
    assert V1API.SCHEMA_VERSION == "1.1.0"


def test_the_only_thing_v2_imports_from_v1_1_is_the_payload_parser():
    """Checked by parsing the import graph rather than promised in prose."""
    seen = []
    for base, _dirs, files in os.walk(V2):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                mod = ""
                if isinstance(node, ast.ImportFrom):
                    mod = ("." * node.level) + (node.module or "")
                elif isinstance(node, ast.Import):
                    mod = ",".join(a.name for a in node.names)
                if "v1_1" in mod:
                    seen.append((os.path.relpath(path, ROOT), mod))
    assert seen, "the wrapper must import the parser from somewhere"
    allowed_v1_1 = {
        # the strict parser, which IS the external trust boundary
        "v1_1.monitor",
        # Phase C: the internal path reads two frozen detector CONSTANTS to
        # reject a payload produced by a differently configured detector. It
        # reads `CUSUM_K` and `CUSUM_H` and computes nothing -- a test above
        # asserts no detector is stepped in `ingest.py`.
        "v1_1.sequential",
    }
    for path, mod in seen:
        tail = mod.lstrip(".")
        assert tail in allowed_v1_1 or mod.endswith("v1_1.monitor"), (
            f"{path} imports {mod!r}; v2 may consume the published payload "
            f"and the frozen detector constants, and nothing else from v1.1")


def test_an_unknown_major_version_is_refused_not_coerced():
    doc = dict(_doc(), schema_version="3.0.0")
    with pytest.raises(API.SchemaVersionError, match="unsupported"):
        API.validate(doc)


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("functions"),
    lambda d: d.pop("attribution"),
    lambda d: d.update(system="MOSTLY_FINE"),
    lambda d: d["domains"].update(POWER="PROBABLY_OK"),
    lambda d: d["functions"]["LOGGING"].update(state="SORT_OF"),
    lambda d: d["functions"]["LOGGING"].pop("limiting_domain"),
    lambda d: d["attribution"].update(verdict="PRETTY_SURE"),
])
def test_every_malformed_document_is_rejected_with_no_permissive_path(mutate):
    doc = _doc()
    mutate(doc)
    with pytest.raises(API.SchemaVersionError):
        API.validate(doc)


def test_the_document_may_not_grow_a_scalar_system_health():
    """§3's rule is not only about the record type. A "system health: 82%"
    field would re-import exactly the false comparability that keeping
    evidence categorical exists to prevent."""
    for banned in ("score", "health", "confidence", "index", "grade"):
        doc = dict(_doc())
        doc[banned] = 0.82
        with pytest.raises(API.SchemaVersionError, match="forbidden"):
            API.validate(doc)


def test_the_api_answers_the_autopilots_question_and_issues_no_command():
    """§33's worked example, as an actual call. CSIA answers; the autopilot
    owns the switching action."""
    doc = _doc()
    answer = API.function_eligible(doc, "PRECISION_NAVIGATION")
    assert answer["eligible"] is False
    assert answer["limiting_domain"] == "POWER"
    assert answer["reason_codes"]
    # The fallback is the HOST's own declaration, reported back. Reporting a
    # host's declaration to it is not CSIA choosing anything.
    assert answer["fallback"] == "COARSE_NAVIGATION"
    for key in answer:
        assert key not in ("command", "action", "switch_to", "do")


def test_an_unknown_function_is_answered_honestly_not_guessed():
    answer = API.function_eligible(_doc(), "TELEPORTATION")
    assert answer["eligible"] is None and answer["state"] == "UNKNOWN"
    assert "does not declare" in answer["why"]


def test_the_api_module_exposes_no_way_to_command_anything():
    """§33: CSIA remains independent assurance middleware."""
    tree = ast.parse(open(os.path.join(V2, "api.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            for verb in ("command", "send", "set_mode", "switch", "actuate",
                         "write", "arm", "disarm", "land", "rtl"):
                assert verb not in node.name.lower(), node.name


def test_the_limiting_report_is_the_central_column_of_section_17():
    report = API.limiting_report(_doc())
    assert "POWER" in report["limiting"]
    assert "INERTIAL_CONTINUATION" in report["unlimited"]


def test_the_document_is_json_serialisable_and_stable():
    doc = _doc()
    assert json.dumps(doc, sort_keys=True) == json.dumps(_doc(),
                                                         sort_keys=True)


# =========================================================== §§31, 32 AI
def test_no_ml_or_llm_is_anywhere_in_the_deterministic_decision_path():
    """§31. The AI analyst of §§31-32 is documented and deliberately not
    built; this asserts nothing crept in through an import."""
    banned = ("torch", "tensorflow", "sklearn", "keras", "transformers",
              "openai", "anthropic", "onnx", "xgboost", "llama", "joblib")
    offenders = []
    for base, _dirs, files in os.walk(V2):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(base, name)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.ImportFrom):
                    mods = [node.module or ""]
                elif isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                for mod in mods:
                    root = mod.split(".")[0].lower()
                    if root in banned:
                        offenders.append(f"{name}: {mod}")
    assert not offenders, offenders


def test_the_decision_path_imports_nothing_beyond_the_standard_library():
    """Determinism and replay are the promise. A third-party numeric library
    in the decision path would make the answer depend on its version."""
    allowed = {"csia", "dataclasses", "enum", "abc", "json", "hashlib",
               "typing", "__future__", "os", "collections", "math",
               "importlib", "types"}
    offenders = []
    for base, _dirs, files in os.walk(V2):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(base, name),
                                  encoding="utf-8").read())
            for node in ast.walk(tree):
                mods = []
                if isinstance(node, ast.ImportFrom):
                    if node.level:                      # relative: in-package
                        continue
                    mods = [node.module or ""]
                elif isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                for mod in mods:
                    if mod.split(".")[0] not in allowed:
                        offenders.append(f"{name}: {mod}")
    assert not offenders, offenders
