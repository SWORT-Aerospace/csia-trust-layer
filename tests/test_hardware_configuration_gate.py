"""Proofs for the BLOCKED / no-fake-constants hardware policy.

WHAT THIS POLICY IS AGAINST
---------------------------
Three specific ways a synthetic number becomes a hardware claim:

  * a constant nobody checked reaches silicon, because a plausible value in a
    source file is indistinguishable from a checked one;
  * a live run that cannot proceed quietly becomes a fake run, and files a
    manifest that reads like a bench run;
  * a result that only shows a configuration was well-formed gets reported as
    though a device had been exercised.

Each of the six tests below plants one of those and requires it to be refused.
The tests build their own registries wherever possible: pinning the real one's
counts would turn any legitimate datasheet work into a test failure, and what
needs protecting is the DECISION, not today's numbers.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import csia_hardware_gate as gate                      # noqa: E402
from csia_hardware_gate import gate as gate_module     # noqa: E402
from csia_hardware_gate import registry as reg         # noqa: E402


def _registry(tmp_path, entries, documents=()):
    path = tmp_path / "CONSTANTS.yaml"
    path.write_text(yaml.safe_dump({
        "schema": "csia.hardware.governed_constants/1",
        "documents": list(documents),
        "constants": list(entries),
    }), encoding="utf-8")
    return path


def _entry(**over):
    base = {"name": "tca9548a.supply_voltage", "kind": "voltage",
            "units": "V", "status": reg.MISSING}
    base.update(over)
    return base


# ------------------------------------------- 1. MISSING blocks live init

def test_a_missing_constant_blocks_live_initialisation(tmp_path):
    constants = reg.load_registry(_registry(tmp_path, [_entry()]))
    with pytest.raises(gate.HardwareConfigurationBlocked) as caught:
        gate.require_live_hardware_permitted("open the bus", constants)
    assert caught.value.status == gate.BLOCKED_CONFIGURATION
    assert [c.name for c in caught.value.constants] == \
        ["tca9548a.supply_voltage"]


def test_missing_resolves_to_blocked_and_never_to_fake(tmp_path):
    constants = reg.load_registry(_registry(tmp_path, [_entry()]))
    decision = gate.resolve(gate.LIVE, constants=constants)
    assert decision.status == gate.BLOCKED_CONFIGURATION
    assert decision.status != gate.FAKE_DRIVER
    assert decision.hardware_touched is False


# --------------------------------------- 2. UNVERIFIED blocks live init

def test_an_unverified_constant_blocks_live_initialisation(tmp_path):
    constants = reg.load_registry(_registry(
        tmp_path, [_entry(status=reg.UNVERIFIED,
                          declared_in="csia_bus_provenance.datasheet.X")]))
    with pytest.raises(gate.HardwareConfigurationBlocked):
        gate.require_live_hardware_permitted("open the bus", constants)


def test_a_verified_claim_without_a_document_is_downgraded_not_believed(
        tmp_path):
    """The only way to earn VERIFIED is a hashed document and a page."""
    constants = reg.load_registry(_registry(
        tmp_path, [_entry(status=reg.VERIFIED, value=3.3)]))
    assert constants[0].status == reg.UNVERIFIED
    assert constants[0].value is None, (
        "a downgraded entry must not keep the value it claimed; that value "
        "was never checked against anything")
    with pytest.raises(gate.HardwareConfigurationBlocked):
        gate.require_live_hardware_permitted("open the bus", constants)


def test_a_verified_claim_whose_document_hash_differs_is_downgraded(tmp_path):
    doc = tmp_path / "ds.pdf"
    doc.write_bytes(b"%PDF-1.4 not the document that was hashed\n")
    constants = reg.load_registry(_registry(
        tmp_path,
        [_entry(status=reg.VERIFIED, value=3.3, source_document="ds",
                source_page_section="Table 6.3, p.9")],
        documents=[{"document_id": "ds", "path": "ds.pdf",
                    "sha256": "0" * 64}]),
        root=tmp_path)
    assert constants[0].status == reg.UNVERIFIED
    assert any("hashes to" in p for p in constants[0].problems)


def test_a_fully_evidenced_constant_is_verified_and_permits_live(tmp_path):
    """The positive case, so the gate is not merely always-refusing."""
    doc = tmp_path / "ds.pdf"
    doc.write_bytes(b"%PDF-1.4 the real thing\n")
    constants = reg.load_registry(_registry(
        tmp_path,
        [_entry(status=reg.VERIFIED, value=3.3, source_document="ds",
                source_page_section="Table 6.3, p.9")],
        documents=[{"document_id": "ds", "path": "ds.pdf",
                    "sha256": reg.sha256(doc)}]),
        root=tmp_path)
    assert constants[0].status == reg.VERIFIED
    assert constants[0].value == 3.3
    gate.require_live_hardware_permitted("open the bus", constants)
    assert gate.resolve(gate.LIVE, constants=constants).status == \
        gate.LIVE_HARDWARE_NOT_REACHABLE, (
        "a verified configuration with no device must report NOT_REACHABLE, "
        "which is a different fact from a blocked configuration")


@pytest.mark.parametrize("body", [
    "constants: []\n",                         # governs nothing
    "constants:\n  - {name: x}\n",             # missing required fields
    "constants:\n  - {name: x, kind: wat, units: V, status: MISSING}\n",
    "constants:\n  - {name: x, kind: voltage, units: V, status: FINE}\n",
    "not-a-mapping\n",
])
def test_a_malformed_registry_is_rejected(tmp_path, body):
    bad = tmp_path / "CONSTANTS.yaml"
    bad.write_text(body, encoding="utf-8")
    with pytest.raises(reg.RegistryMalformed):
        reg.load_registry(bad)


def test_an_unreadable_registry_blocks_rather_than_passes(monkeypatch):
    """If the file that decides is broken, the answer is still no.

    The dangerous shape would be a registry that fails open: unreadable, so
    nothing was found blocking, so live proceeds.
    """
    def explode(*a, **k):
        raise reg.RegistryMalformed("synthetic: unreadable")

    monkeypatch.setattr(gate_module, "load_registry", explode)
    assert gate.static_configuration_status().status == \
        gate.BLOCKED_CONFIGURATION
    with pytest.raises(gate.HardwareConfigurationBlocked) as caught:
        gate.require_live_hardware_permitted("open the bus")
    assert "malformed" in str(caught.value)
    assert gate.resolve(gate.LIVE).status == gate.BLOCKED_CONFIGURATION


# ------------------------- 3. fake fixtures only when explicitly selected

def test_mode_has_no_default_and_an_unstated_mode_is_rejected():
    for bad in ("", None, "auto", "default", "fake", "Fake"):
        with pytest.raises(ValueError):
            gate.resolve(bad)


def test_fake_is_reached_only_by_asking_for_it(tmp_path):
    assert gate.resolve(gate.FAKE).status == gate.FAKE_DRIVER
    constants = reg.load_registry(_registry(tmp_path, [_entry()]))
    # Every other route must refuse rather than arrive at FAKE_DRIVER.
    assert gate.resolve(gate.LIVE, constants=constants).status == \
        gate.BLOCKED_CONFIGURATION


def test_a_blocked_live_run_does_not_open_a_port_and_does_not_go_fake(
        tmp_path):
    """End-to-end through the real CLI, against the real registry."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/hardware/e2m_acquire.py"),
         "--port", "/dev/ttyACM-does-not-exist",
         "--run-id", "blocked-run", "--out", str(tmp_path)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "BLOCKED_CONFIGURATION" in proc.stdout
    assert "FAKE" not in proc.stdout.replace("FAKE_DRIVER", ""), (
        "a blocked live run must not mention a fake device; it did not run one")
    assert not list(tmp_path.glob("*.jsonl")), (
        "a blocked live run wrote a run log; it must produce no run at all")


def test_the_fake_path_is_still_reachable_and_is_labelled(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/hardware/e2m_acquire.py"),
         "--fake", "--sweeps", "2", "--run-id", "fake-run",
         "--out", str(tmp_path)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAKE" in proc.stdout
    assert "NOT evidence about any hardware" in proc.stderr


# --------------------------------------------- 4. replay is deterministic

def test_replay_is_deterministic(tmp_path):
    """The same log replayed twice yields identical observations."""
    from csia_e2m.replay import replay

    run = tmp_path / "run.jsonl"
    subprocess.run(
        [sys.executable, str(ROOT / "tools/hardware/e2m_acquire.py"),
         "--fake", "--sweeps", "4", "--run-id", "run", "--out", str(tmp_path)],
        capture_output=True, text=True, cwd=str(ROOT), check=True)
    assert run.exists()

    first = [o.as_dict() for o in replay(run)]
    second = [o.as_dict() for o in replay(run)]
    assert first == second, "replay is not deterministic over the same log"
    assert first, "replay produced nothing, so determinism is untested"

    # and it is a REPLAY, never promoted to a hardware statement
    assert gate.resolve(gate.REPLAY_MODE).status == gate.REPLAY
    assert gate.resolve(gate.REPLAY_MODE).hardware_touched is False


# ------------------------- 5. the frozen CSIA core cannot access hardware

FROZEN = json.loads(
    (ROOT / "docs/v1/FROZEN_BASELINE.json").read_text(encoding="utf-8"))

HARDWARE_IMPORTS = ("serial", "smbus", "smbus2", "spidev", "RPi", "gpiozero",
                    "periphery", "usb", "csia_e2m.transport",
                    "csia_hardware_gate", "csia_bus_provenance")


@pytest.mark.parametrize("rel", sorted(FROZEN["files"]))
def test_the_frozen_core_cannot_reach_hardware(rel):
    """No frozen module imports a hardware interface, directly or by name.

    The frozen core is the part of CSIA that is not allowed to change. If it
    could open a bus, every argument that it is a pure decision layer would
    depend on nobody having done so yet.
    """
    source = (ROOT / rel).read_text(encoding="utf-8")
    for name in HARDWARE_IMPORTS:
        assert f"import {name}" not in source, \
            f"{rel} imports {name}; the frozen core must not reach hardware"
        assert f"from {name}" not in source, \
            f"{rel} imports from {name}; the frozen core must not reach hardware"


def test_the_frozen_core_list_is_not_empty():
    """Guards the guard: an empty list would make the test above vacuous."""
    assert FROZEN["files"], "the frozen baseline lists no files"


# ---------------- 6. no hardware result is emitted with a VALIDATED status

def test_no_terminal_status_asserts_validation():
    for status in gate.TERMINAL_STATUSES:
        for forbidden in gate.FORBIDDEN_RESULT_STATUSES:
            assert status != forbidden
        assert "VALIDATED" not in status


def test_every_decision_reports_hardware_validated_false(tmp_path):
    constants = reg.load_registry(_registry(tmp_path, [_entry()]))
    decisions = [gate.resolve(gate.FAKE), gate.resolve(gate.REPLAY_MODE),
                 gate.resolve(gate.LIVE, constants=constants)]
    for decision in decisions:
        assert decision.as_dict()["hardware_validated"] is False
        assert decision.status in gate.TERMINAL_STATUSES


def test_the_package_declares_no_hardware_validation():
    assert gate.HARDWARE_VALIDATED is False
    import csia_bus_provenance
    assert csia_bus_provenance.HARDWARE_VALIDATED is False


def test_a_verified_static_configuration_is_not_a_hardware_claim(tmp_path):
    """The one non-blocking status must still not read as hardware evidence."""
    doc = tmp_path / "ds.pdf"
    doc.write_bytes(b"%PDF-1.4\n")
    constants = reg.load_registry(_registry(
        tmp_path,
        [_entry(status=reg.VERIFIED, value=3.3, source_document="ds",
                source_page_section="p.9")],
        documents=[{"document_id": "ds", "path": "ds.pdf",
                    "sha256": reg.sha256(doc)}]),
        root=tmp_path)
    decision = gate.static_configuration_status(constants)
    assert decision.status == gate.VERIFIED_STATIC_CONFIGURATION
    assert decision.hardware_touched is False
    assert "says nothing about" in decision.detail


# ----------------------------------- the shipped registry, as data

def test_the_shipped_registry_loads_and_currently_blocks():
    """Today every constant is unverified. Recorded as a fact, not pinned."""
    constants = reg.load_registry()
    assert constants, "the shipped registry declares no constants"
    assert all(c.status in reg.DECLARED_STATUSES for c in constants)
    verified = [c for c in constants if c.status == reg.VERIFIED]
    assert not verified, (
        "a constant is marked VERIFIED. If a datasheet was genuinely checked "
        "in, this assertion is the thing to update -- deliberately, in that "
        "commit, so the change is reviewed rather than absorbed.")


def test_no_shipped_entry_carries_a_value_without_evidence():
    """The no-fake-constants rule, stated as a property of the file."""
    for c in reg.load_registry():
        if c.status != reg.VERIFIED:
            assert c.value is None, (
                f"{c.name} is {c.status} but carries a value; an unevidenced "
                f"number in the registry is exactly the guessed constant this "
                f"policy forbids")


# ------------------------------- the operator-facing status, as a contract

REPORTER = ROOT / "tools/hardware/hardware_gate_status.py"


@pytest.mark.parametrize("args,status,code", [
    ([], "BLOCKED_CONFIGURATION", 3),
    (["--mode", "FAKE"], "FAKE_DRIVER", 0),
    (["--mode", "REPLAY"], "REPLAY", 0),
    (["--mode", "LIVE"], "BLOCKED_CONFIGURATION", 3),
])
def test_the_reporter_distinguishes_the_terminal_statuses(args, status, code):
    proc = subprocess.run([sys.executable, str(REPORTER), *args],
                          capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == code, proc.stdout + proc.stderr
    assert f"STATUS: {status}" in proc.stdout


def test_the_reporter_never_reports_a_validation():
    proc = subprocess.run([sys.executable, str(REPORTER), "--json"],
                          capture_output=True, text=True, cwd=str(ROOT))
    report = json.loads(proc.stdout)
    assert report["hardware_validated"] is False
    assert report["hardware_touched"] is False
    for forbidden in gate.FORBIDDEN_RESULT_STATUSES:
        assert report["status"] != forbidden


def test_blocked_and_not_reachable_have_different_exit_codes():
    """The distinction that stops a config defect reading as a missing cable."""
    import tools.hardware.hardware_gate_status as reporter
    assert reporter.EXIT[gate.BLOCKED_CONFIGURATION] != \
        reporter.EXIT[gate.LIVE_HARDWARE_NOT_REACHABLE]
    assert set(reporter.EXIT) == set(gate.TERMINAL_STATUSES), (
        "the reporter must map every terminal status to an exit code")


def test_the_frozen_core_pulls_in_no_hardware_module_even_transitively():
    """Stronger than the grep above: import each frozen module with every
    hardware interface poisoned, and require the import to succeed.

    A grep only sees the frozen file itself. This catches a frozen module that
    reaches hardware through something it imports, which is the shape the grep
    would miss and the one nobody would notice.
    """
    program = r'''
import importlib, json, sys

BLOCKED = ("serial", "smbus", "smbus2", "spidev", "RPi", "gpiozero",
           "periphery", "usb", "csia_e2m", "csia_bus_provenance",
           "csia_hardware_gate")

class Poison:
    def find_module(self, name, path=None):
        return self.find_spec(name, path)
    def find_spec(self, name, path=None, target=None):
        root = name.split(".")[0]
        if root in BLOCKED or name in BLOCKED:
            raise AssertionError(
                "the frozen core imported %r, which reaches hardware" % name)
        return None

sys.meta_path.insert(0, Poison())

frozen = json.load(open("docs/v1/FROZEN_BASELINE.json"))["files"]
mods = []
for f in sorted(frozen):
    if not f.endswith(".py"):
        continue
    m = f[:-3].replace("/", ".")
    mods.append(m[:-9] if m.endswith(".__init__") else m)

for m in mods:
    importlib.import_module(m)
print("OK", len(mods))
'''
    proc = subprocess.run([sys.executable, "-c", program],
                          capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 0, (
        "importing the frozen core reached a hardware module:\n"
        + proc.stdout + proc.stderr)
    assert proc.stdout.startswith("OK "), proc.stdout
    assert int(proc.stdout.split()[1]) >= 12
