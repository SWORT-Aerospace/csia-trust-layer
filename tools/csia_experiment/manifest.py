"""Trial manifests: written once, hashed, and refused if rewritten.

WHAT A MANIFEST IS FOR
----------------------
A result file says what happened. A manifest says **what was running when it
happened**, and it is the half that decays: six months later the interesting
question is never "what was the latency" but "was that the run before or after
the adapter change".

So a manifest pins, at trial time and from the live objects rather than from
memory: the repository HEAD, the frozen-core tag and whether it resolves, the
vehicle-profile hash, the deployment-config hash as the flight log computes it,
the adapter and contract versions, the preregistration path and hash, and the
adjudicated trial state with the predicate that decided it.

IMMUTABILITY IS ENFORCED, NOT REQUESTED
----------------------------------------
`write()` refuses to overwrite an existing manifest whose content differs, and
returns quietly if the content is byte-identical. There is no `--force`.

The reason is specific to this program. A trial manifest that can be edited
after the fact is not evidence, it is a note; and the edit that gets made is
never a malicious one -- it is "fix the typo in the scenario name", made three
weeks later, by which time nobody can tell whether the run it describes is the
run whose numbers are in the paper.

A trial that needs different metadata is a NEW TRIAL with a new id. That is the
same rule FAILURE_LEDGER.yaml applies to reruns, and for the same reason: "we
reran it and it worked" is a different fact from "it worked".

WHAT IS DELIBERATELY NOT HERE
------------------------------
No metric computation, no scoring, no pass/fail. A manifest records the
conditions and the adjudicated state; deciding what a campaign of them MEANS is
the report's job, and keeping the two apart is what stops a manifest from being
quietly rewritten to make a report come out.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")))

from tools.csia_experiment.validity import adjudicate  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SCHEMA = "csia.research.trial_manifest/1"

#: The freeze the diagnostic claims are made against.
FROZEN_TAG = "csia-v1.0-research-final"


class ManifestError(RuntimeError):
    """A manifest that would overwrite, or that cannot pin its conditions."""


def _git(*args) -> Optional[str]:
    try:
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _sha256_file(path: str) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def canonical_hash(payload: dict) -> str:
    """The manifest's identity. Sorted keys, no whitespace variance."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def provenance(profile_path: Optional[str] = None,
               deployment_path: Optional[str] = None,
               adapter=None) -> dict:
    """Everything that decides what a trial's numbers mean, measured now.

    `frozen_core_tag_resolves` is not decoration. The four freeze tags in this
    repository are LOCAL ONLY -- the tag push was refused with HTTP 403 -- so on
    a fresh clone the tag does not exist and the freeze test skips, which reads
    as green. A manifest that silently omitted this would let a trial claim the
    frozen core without anything having checked.
    """
    out = {
        "head": _git("rev-parse", "HEAD"),
        "dirty": bool(_git("status", "--porcelain")),
        "frozen_core_tag": FROZEN_TAG,
        "frozen_core_tag_resolves": bool(_git("rev-parse", "--verify",
                                              f"{FROZEN_TAG}^{{commit}}")),
        "frozen_core_diff_empty": None,
        "profile_path": profile_path,
        "profile_sha256": _sha256_file(profile_path) if profile_path else None,
        "deployment_path": deployment_path,
        "deployment_config_hash": None,
        "adapter": None,
    }

    if out["frozen_core_tag_resolves"]:
        from csia.aircraft.firewall import FROZEN_PATHS
        diff = _git("diff", "--stat", FROZEN_TAG, "--", *FROZEN_PATHS)
        out["frozen_core_diff_empty"] = (diff == "")

    if deployment_path:
        from csia.deploy.deployment import load as load_deployment
        dep = load_deployment(deployment_path)
        out["deployment_config_hash"] = dep.config_hash
        out["deployment_schema"] = dep.schema

    if adapter is not None:
        out["adapter"] = {
            "platform": adapter.platform,
            "version": getattr(adapter, "adapter_version", None),
            "contract_version": getattr(adapter.contract, "version", None),
        }
        fidelity = getattr(adapter, "fidelity", None)
        if callable(fidelity):
            out["adapter"]["fidelity"] = fidelity()
        admissible = getattr(adapter, "admissible_as_evidence", None)
        if admissible is not None:
            out["adapter"]["admissible_as_evidence"] = admissible
    return out


@dataclass
class TrialManifest:
    trial_id: str
    campaign: str
    scenario: str
    prereg_path: Optional[str] = None
    record: dict = field(default_factory=dict)
    provenance_: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def payload(self) -> dict:
        adj = adjudicate(self.record)
        body = {
            "schema": SCHEMA,
            "trial_id": self.trial_id,
            "campaign": self.campaign,
            "scenario": self.scenario,
            "prereg_path": self.prereg_path,
            "prereg_sha256": _sha256_file(self.prereg_path)
            if self.prereg_path else None,
            "record": self.record,
            "adjudication": adj.to_dict(),
            "provenance": self.provenance_,
            "notes": self.notes,
        }
        # The hash covers everything ABOVE it and nothing else, so a manifest
        # cannot be re-hashed to match after an edit without the edit showing.
        body["manifest_sha256"] = canonical_hash(body)
        return body

    def path(self, campaign_dir: str) -> str:
        return os.path.join(campaign_dir, f"{self.trial_id}.json")

    def write(self, campaign_dir: str) -> str:
        """Write once. Refuse to change. No force flag exists.

        Byte-identical content is a no-op rather than an error: re-running a
        deterministic orchestrator over an already-recorded campaign should not
        fail, and it is the one case where "the file is already there" carries
        no information loss.
        """
        os.makedirs(campaign_dir, exist_ok=True)
        target = self.path(campaign_dir)
        body = self.payload()
        blob = json.dumps(body, indent=2, sort_keys=True) + "\n"

        if os.path.exists(target):
            with open(target, encoding="utf-8") as fh:
                existing = fh.read()
            if existing == blob:
                return target
            old = json.loads(existing).get("manifest_sha256")
            raise ManifestError(
                f"{target} already exists with different content "
                f"(recorded {old}, would write {body['manifest_sha256']}).\n"
                f"A trial manifest is written once. If the conditions were "
                f"different, this is a DIFFERENT TRIAL and needs a new "
                f"trial_id -- the same rule the failure ledger applies to "
                f"reruns. There is deliberately no --force.")

        with open(target, "w", encoding="utf-8") as fh:
            fh.write(blob)
        return target


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        body = json.load(fh)
    stored = body.get("manifest_sha256")
    recomputed = canonical_hash({k: v for k, v in body.items()
                                 if k != "manifest_sha256"})
    if stored != recomputed:
        raise ManifestError(
            f"{path}: manifest_sha256 is {stored}, content hashes to "
            f"{recomputed}. The file was edited after it was written. It is "
            f"no longer evidence about the run it describes.")
    return body


def campaign_records(campaign_dir: str) -> list:
    """Every manifest in a campaign, hash-verified on the way in."""
    if not os.path.isdir(campaign_dir):
        return []
    out = []
    for name in sorted(os.listdir(campaign_dir)):
        if name.endswith(".json") and not name.startswith("_"):
            out.append(load(os.path.join(campaign_dir, name)))
    return out
