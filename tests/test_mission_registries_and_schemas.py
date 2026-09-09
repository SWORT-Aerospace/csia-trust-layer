"""Registries, schemas, provenance and the replay separation.

The load-bearing test in this file is
`test_the_replay_artifact_never_claims_the_pipeline_is_deterministic`. The
mission replay is deterministic given its inputs and the core replay that
would produce those inputs is not, and an artifact that reported only the
first would be quoting half a sentence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_mission.provenance import (ProvenanceChain,         # noqa: E402
                                     configuration_hash, content_hash)
from csia_mission.registry import (AircraftManifest,          # noqa: E402
                                   MEASURED, PROVISIONAL, PayloadModule,
                                   RegistryError, SensorTransform, UNKNOWN,
                                   load_registry)

RESULTS = os.path.join(ROOT, "research", "mission", "results")
XR = os.path.join(ROOT, "hardware", "xr1")


def _load(name):
    path = os.path.join(RESULTS, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} not generated")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ registry

def test_a_provisional_transform_must_state_its_basis():
    t = SensorTransform("t", "s", "datum", translation_status=PROVISIONAL)
    with pytest.raises(RegistryError, match="must state its `basis`"):
        t.validate()


def test_a_mass_without_a_status_and_a_status_without_a_mass_both_fail():
    with pytest.raises(RegistryError, match="mass_status=UNKNOWN"):
        PayloadModule("m", "t", mass_kg=1.0, mass_status=UNKNOWN).validate()
    with pytest.raises(RegistryError, match="no mass but mass_status"):
        PayloadModule("m", "t", mass_kg=None,
                      mass_status=MEASURED).validate()


def test_only_defined_or_measured_transforms_are_usable_for_residuals():
    good = SensorTransform("t", "s", "d", translation_status=MEASURED,
                           rotation_status=MEASURED)
    assert good.usable_for_residuals
    for bad in (PROVISIONAL, UNKNOWN):
        t = SensorTransform("t", "s", "d", translation_status=bad,
                            rotation_status=MEASURED, basis="stated")
        assert not t.usable_for_residuals


def test_a_dangling_transform_reference_is_refused():
    from csia_mission.registry import ModuleRegistry
    reg = ModuleRegistry()
    with pytest.raises(RegistryError, match="not registered"):
        reg.add_module(PayloadModule("m", "t", transform_id="ghost"))


def test_the_xr_registry_loads_and_admits_it_is_unusable():
    path = os.path.join(XR, "XR1_PAYLOAD_AND_TRANSFORMS.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    reg = load_registry(doc)
    assert reg.modules and reg.transforms
    prov = reg.provisional_entries()
    assert len(prov["transforms"]) == len(reg.transforms), (
        "a transform has been promoted out of PROVISIONAL/UNKNOWN. XR-1 has "
        "not been built, so no transform can have been measured; if one "
        "genuinely was, update this test in the same commit and say which "
        "article was measured.")
    assert doc["usable_for_physical_residual_analysis"] == "NONE"


def test_the_xr_draft_profile_is_marked_non_flight():
    path = os.path.join(XR, "XR1_DRAFT_PROFILE.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    assert doc["status"] == "NON_FLIGHT_DRAFT"
    assert doc["vehicle"]["total_mass_kg"] is None, (
        "a total mass computed from placeholders is a placeholder wearing a "
        "total's clothes")
    assert doc["vehicle"]["total_mass_status"] == "UNKNOWN"
    assert "battery envelope" in " ".join(
        doc["must_be_measured_before_cad_freeze"])


def test_every_supplied_number_in_the_draft_profile_carries_a_status():
    path = os.path.join(XR, "XR1_DRAFT_PROFILE.yaml")
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    for name, item in sorted((doc.get("items") or {}).items()):
        value_keys = [k for k in item
                      if k.endswith(("_mm", "_g", "_kg"))
                      and item[k] is not None]
        for k in value_keys:
            status_key = k.rsplit("_", 1)[0] + "_status"
            alt = {"dimensions_mm": "dimensions_status",
                   "mass_g": "mass_status", "mass_kg": "mass_status",
                   "envelope_mm": "envelope_status",
                   "core_module_mm": "core_module_status",
                   "carrier_envelope_mm": "carrier_envelope_status",
                   "reserved_envelope_mm": "reserved_envelope_status",
                   "reserved_mass_g": "reserved_mass_status"}
            status_key = alt.get(k, status_key)
            assert status_key in item, (
                f"{name}.{k} carries a number with no {status_key}. A number "
                f"without provenance is not carried in this profile.")


def test_the_aircraft_manifest_hashes_and_lists_its_holes():
    m = AircraftManifest(airframe_id="XR-1-DRAFT-000",
                         fc_module_id="mod_fc_kakute")
    assert len(m.config_hash) == 64
    assert "battery_id" in m.unresolved()
    # A different configuration is a different hash.
    m2 = AircraftManifest(airframe_id="XR-1-DRAFT-000",
                          fc_module_id="mod_fc_fmuv6c")
    assert m.config_hash != m2.config_hash, (
        "swapping the flight computer must change the configuration hash, or "
        "certificates issued under one board silently apply to the other")


# ---------------------------------------------------------------- provenance

def test_a_broken_provenance_link_is_detected():
    c = ProvenanceChain()
    c.append("RAW", {"a": 1}, {"out": 1}, "v1", "cfg", 0.0)
    c.append("CANONICAL_EVIDENCE", content_hash({"unrelated": True}),
             {"out": 2}, "v1", "cfg", 1.0)
    v = c.verify()
    assert not v["intact"]
    assert any(p["problem"] == "BROKEN_LINK" for p in v["problems"])


def test_configuration_drift_within_a_chain_is_detected():
    c = ProvenanceChain()
    a = c.append("RAW", {"a": 1}, {"out": 1}, "v1", "cfg_A", 0.0)
    c.append("CANONICAL_EVIDENCE", a.output_hash, {"out": 2}, "v1",
             "cfg_B", 1.0)
    assert any(p["problem"] == "CONFIGURATION_DRIFT"
               for p in c.verify()["problems"])


def test_an_out_of_order_stage_is_detected():
    c = ProvenanceChain()
    a = c.append("MISSION_REPORT", {"a": 1}, {"o": 1}, "v", "cfg", 0.0)
    c.append("RAW", a.output_hash, {"o": 2}, "v", "cfg", 1.0)
    assert any(p["problem"] == "OUT_OF_ORDER"
               for p in c.verify()["problems"])


def test_an_unknown_stage_is_refused():
    c = ProvenanceChain()
    with pytest.raises(ValueError, match="unknown provenance stage"):
        c.append("MADE_UP_STAGE", {}, {}, "v", "cfg", 0.0)


def test_the_chain_never_claims_tamper_evidence():
    c = ProvenanceChain()
    c.append("RAW", {"a": 1}, {"o": 1}, "v", "cfg", 0.0)
    v = c.verify()
    assert "not tamper evidence" in v["what_this_does_not_prove"]
    assert "signed" in v["what_this_does_not_prove"]


def test_the_configuration_hash_covers_vehicle_payload_and_software():
    base = configuration_hash({"v": 1}, {"p": 1}, {"s": 1})
    assert base != configuration_hash({"v": 2}, {"p": 1}, {"s": 1})
    assert base != configuration_hash({"v": 1}, {"p": 2}, {"s": 1})
    assert base != configuration_hash({"v": 1}, {"p": 1}, {"s": 2})


def test_the_content_hash_is_key_order_independent():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


# ------------------------------------------------------------------- schemas

def test_the_committed_schemas_match_their_dataclasses():
    proc = subprocess.run(
        [sys.executable, "tools/xr/emit_schemas.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_the_schemas_declare_their_csia_specific_fields():
    path = os.path.join(ROOT, "csia_mission", "schemas",
                        "CapabilitySupportCertificate.json")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    sv = doc["properties"]["semantics_version"]
    assert "x-csia-specific" in sv, (
        "the one genuinely CSIA-specific field must be NAMED as such rather "
        "than disguised, or the neutrality claim is not checkable")


def test_certificate_schemas_carry_no_certified_vocabulary():
    """The words may appear ONLY in a denial.

    THIS GUARD FIRED ON THE DENIAL FIRST. The certificate schema's
    description reads "Not certified, not certification-grade", and a bare
    substring scan read that as the violation. It is the EIGHTH time in this
    repository that a forbidden-word guard has tripped over prose stating the
    very rule it enforces, and the second in this extension.

    The pattern is now unmistakable enough to state as a rule: a
    forbidden-word check whose only cheap fix is to delete the sentence
    explaining the rule is a check that makes the repository worse. Every one
    of them needs to look at CONTEXT, not presence.
    """
    base = os.path.join(ROOT, "csia_mission", "schemas")
    negations = ("not ", "never ", "no ", "cannot ", "is not")
    for name in sorted(os.listdir(base)):
        blob = open(os.path.join(base, name), encoding="utf-8").read().lower()
        flat = " ".join(blob.split())
        for overclaim in ("certification-grade", "airworthy", "certified"):
            start = 0
            while True:
                i = flat.find(overclaim, start)
                if i < 0:
                    break
                window = flat[max(0, i - 40):i]
                assert any(n in window for n in negations), (
                    f"{name} uses {overclaim!r} outside a denial: "
                    f"...{flat[max(0, i - 60):i + 60]}...")
                start = i + len(overclaim)


def test_every_certificate_status_string_is_experimental():
    """The positive form of the check above, which cannot pass vacuously."""
    from csia_mission.capability import CAPABILITY_CERT_STATUS
    from csia_mission.product import PRODUCT_CERT_STATUS
    for status in (CAPABILITY_CERT_STATUS, PRODUCT_CERT_STATUS):
        assert status.startswith("EXPERIMENTAL_"), status


# -------------------------------------------------------------------- replay

def test_the_replay_artifact_never_claims_the_pipeline_is_deterministic():
    """THE LOAD-BEARING TEST IN THIS FILE.

    The extension is deterministic given its inputs. The core replay that
    would produce those inputs does not reproduce them at the declared
    tolerance. An artifact reporting only the first is quoting half a
    sentence.

    UPDATED WITH HF-018. The old assertion was `all_divergent is True`, and
    HF-004's closure retired it: the categorical divergence is 0 on both
    platforms. The load-bearing claim did NOT retire with it -- it moved to
    the numeric side, where ArduPilot reproduces ZERO of 2248 decisions
    within 1e-12. So the guard now watches that, which is the thing the
    extension actually depends on.
    """
    doc = _load("MISSION_REPLAY.json")
    assert doc["extension_determinism"]["verdict"] == \
        "DETERMINISTIC_GIVEN_ITS_INPUTS"
    core = doc["core_replay_limitation"]
    assert core["available"], "the core replay status is no longer reported"
    assert core["all_within_numeric_tolerance"] is False, (
        "the core replay now reproduces every value within the declared "
        "tolerance. If that is real, the pipeline determinism claim can be "
        "strengthened -- update the ledger and this test together. If a "
        "tolerance was widened instead, revert it.")
    assert core["per_platform_numeric"], (
        "the numeric breakdown is gone; `all_divergent` alone no longer "
        "carries the limitation and must not be the only thing reported")
    assert "NOT DEMONSTRATED DETERMINISTIC" in doc["what_may_not_be_concluded"]
    assert doc["evidence_sequence_is_synthetic"] is True
