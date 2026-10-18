"""Metamorphic relations: what must NOT change the support verdict, and what must.

WHY METAMORPHIC
---------------
For most of these there is no expected number to assert against. What is
knowable is a RELATION between two runs: rename every hypothesis and the
structural answer must be the same answer with the names substituted. That is
checkable without an oracle, and it catches the class of defect where a layer
quietly depends on something it has no business depending on -- a label, an
ordering, a score, a logging path.

THE LAST TEST IS THE CONTROL
----------------------------
Eight relations here assert that a verdict does NOT move. A firewall that
returned a constant would pass all eight. So the file ends with the opposite
relation: changing a LOAD-BEARING discriminator MUST be capable of moving the
verdict. Without it, the other eight establish nothing.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from csia_assurance import (SUPPORTED_UNIQUE, build_certificate,  # noqa: E402
                            qualify, SEMANTICS_VERSION)
from csia_assurance.firewall import SCHEMA                        # noqa: E402


def base(**over):
    rec = {
        "schema": SCHEMA, "timestamp": 100.0, "config_hash": "cfg-1",
        "software_hash": "sw-1", "evidence_hash": "ev-1",
        "canonical_sample_present": True, "leader": "nominal",
        "signatures": {"nominal": [], "gps_fault": ["rel_a"],
                       "imu_bias": ["rel_b"], "mag_interference": ["rel_c"]},
        # All three active, so the base verdict is SUPPORTED_UNIQUE. The
        # control test at the bottom needs a base that CAN move; a base that
        # was already AMBIGUOUS would make it unfalsifiable.
        "gates": {"rel_a": 1.0, "rel_b": 1.0, "rel_c": 1.0},
        "evidence_states": {"rel_a": "ACTIVE", "rel_b": "ACTIVE",
                            "rel_c": "ACTIVE"},
    }
    rec.update(over)
    return rec


def _structure(v):
    """The verdict reduced to what a rename or reorder must preserve."""
    return (v.state, tuple(sorted(v.competitors_without_witness)),
            tuple(sorted((k, tuple(sorted(d)))
                         for k, d in v.witnesses.items())))


# --- relations that must NOT move the verdict ------------------------------

def test_renaming_hypotheses_preserves_the_structure():
    """Labels are identifiers, not evidence."""
    rec = base()
    mapping = {"nominal": "H0", "gps_fault": "H1", "imu_bias": "H2",
               "mag_interference": "H3"}
    renamed = base(
        leader=mapping[rec["leader"]],
        signatures={mapping[k]: v for k, v in rec["signatures"].items()})
    a, b = qualify(rec), qualify(renamed)
    assert a.state == b.state
    assert ({mapping[c] for c in a.competitors_without_witness}
            == set(b.competitors_without_witness))
    assert ({mapping[k]: v for k, v in a.witnesses.items()}
            == dict(b.witnesses))


def test_reordering_hypotheses_preserves_the_verdict():
    rec = base()
    reordered = base(signatures=dict(reversed(list(
        rec["signatures"].items()))))
    assert _structure(qualify(rec)) == _structure(qualify(reordered))


def test_reordering_evidence_terms_preserves_the_verdict():
    rec = base()
    assert _structure(qualify(rec)) == _structure(qualify(base(
        gates=dict(reversed(list(rec["gates"].items()))),
        evidence_states=dict(reversed(list(
            rec["evidence_states"].items()))))))


@pytest.mark.parametrize("field,value", [
    ("leader_weight", 0.999999),
    ("ranking", ["nominal", "gps_fault", "imu_bias", "mag_interference"]),
    ("posterior", {"nominal": 0.97, "gps_fault": 0.01}),
    ("score", 12345.6),
])
def test_changing_ranking_values_cannot_move_the_verdict(field, value):
    """P1. The firewall must not read the score it is qualifying."""
    assert _structure(qualify(base())) == _structure(
        qualify(base(**{field: value})))


@pytest.mark.parametrize("priors", [
    {"nominal": 0.99, "gps_fault": 0.005},
    {"nominal": 0.25, "gps_fault": 0.25, "imu_bias": 0.25},
])
def test_changing_priors_cannot_move_the_verdict(priors):
    """P2."""
    assert _structure(qualify(base())) == _structure(
        qualify(base(priors=priors)))


def test_changing_unrelated_evidence_cannot_move_a_target_pairs_support():
    """P4, at the record level.

    `rel_c` discriminates only mag_interference. Toggling it must not change
    the nominal-vs-gps_fault witness.
    """
    on = qualify(base(gates={"rel_a": 1.0, "rel_b": 1.0, "rel_c": 1.0}))
    off = qualify(base(gates={"rel_a": 1.0, "rel_b": 1.0, "rel_c": 0.0}))
    assert on.witnesses["gps_fault"] == off.witnesses["gps_fault"]


def test_duplicating_a_semantically_identical_inactive_term_changes_nothing():
    rec = base()
    dup = base(
        signatures={**rec["signatures"],
                    "mag_interference": ["rel_c", "rel_c_copy"]},
        gates={**rec["gates"], "rel_c_copy": 0.0},
        evidence_states={**rec["evidence_states"], "rel_c_copy": "ACTIVE"})
    assert qualify(rec).state == qualify(dup).state
    assert (qualify(rec).witnesses["gps_fault"]
            == qualify(dup).witnesses["gps_fault"])


def test_changing_the_display_name_does_not_change_edge_identity():
    """A human-readable label is not an identifier."""
    rec = base(display_names={"rel_a": "GNSS Doppler (channel 0)"})
    assert _structure(qualify(base())) == _structure(qualify(rec))


def test_changing_the_logging_path_does_not_change_the_scientific_result():
    """Run the same record in two interpreters with different log targets.

    A subprocess, because an in-process check could not tell the difference
    between "logging does not affect the result" and "logging was never
    configured".
    """
    rec = base()
    script = (
        "import json, os, sys\n"
        "sys.path.insert(0, %r)\n"
        "import logging\n"
        "logging.basicConfig(filename=os.environ['CSIA_TEST_LOG'],\n"
        "                    level=logging.DEBUG)\n"
        "from csia_assurance import qualify\n"
        "rec = json.loads(sys.argv[1])\n"
        "v = qualify(rec)\n"
        "print(json.dumps({'state': v.state,\n"
        "                  'w': {k: list(x) for k, x in v.witnesses.items()}},\n"
        "                 sort_keys=True))\n" % ROOT)
    outs = []
    for name in ("log-a.txt", "log-b.txt"):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CSIA_TEST_LOG=os.path.join(d, name))
            proc = subprocess.run(
                [sys.executable, "-c", script, json.dumps(rec)],
                cwd=ROOT, env=env, capture_output=True, text=True,
                timeout=180)
            assert proc.returncode == 0, proc.stderr[-1500:]
            outs.append(proc.stdout.strip())
    assert outs[0] == outs[1]


# --- the control: something MUST be able to move it ------------------------

def test_changing_a_load_bearing_discriminator_can_move_the_verdict():
    """Without this, a firewall returning a constant passes everything above.

    `rel_a` is the only thing separating nominal from gps_fault. Switching it
    off must change the verdict; if it does not, the eight relations above
    established nothing at all.
    """
    before = qualify(base())
    assert before.state == SUPPORTED_UNIQUE
    after = qualify(base(gates={"rel_a": 0.0, "rel_b": 1.0, "rel_c": 1.0}))
    assert after.state != before.state, (
        "switching off the only discriminator between nominal and gps_fault "
        "did not change the verdict; the firewall is not reading its input")
    assert after.competitors_without_witness == ("gps_fault",)


def test_a_certificate_changes_when_the_evidence_that_justified_it_changes():
    """The same control, one layer up."""
    a = base()
    ca = build_certificate(qualify(a), a, SEMANTICS_VERSION)
    b = base(gates={"rel_a": 0.0, "rel_b": 1.0, "rel_c": 1.0},
             evidence_hash="ev-2")
    cb = build_certificate(qualify(b), b, SEMANTICS_VERSION)
    assert ca.certificate_hash != cb.certificate_hash
    assert ca.complete is True and cb.complete is False
