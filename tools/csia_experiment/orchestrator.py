"""csia-experiment: plan trials, adjudicate them, and make the sums balance.

WHAT THIS IS FOR
----------------
The repository can already run a scenario and produce a result. What it had no
home for is the campaign around a result: planning N trials before any of them
runs, recording the ones that did not run, adjudicating each against
machine-executable predicates rather than an operator's opinion, and refusing
to print a summary whose arithmetic does not close.

THE ORDER MATTERS AND IS ENFORCED
----------------------------------
`plan` writes every trial id BEFORE any trial runs, each as NOT_ATTEMPTED. A
campaign that has no plan has no denominator, and a denominator computed after
the fact is whatever survived.

`run` fills in trials. It cannot add a trial id the plan does not contain --
that is not a rule about tidiness, it is what stops a campaign from growing
extra arms until one of them works.

`report` reconciles. If planned != valid + invalid + not_attempted it raises
rather than printing.

BACKENDS, AND THE ONE THAT REFUSES
-----------------------------------
  simulated   a deterministic in-process backend. Produces NO evidence about
              any vehicle and says so in every manifest it writes.
  replay      drives the ReplayAdapter over a recorded log.
  hardware    REFUSES, with the reason and a pointer to
              USER_ACTION_REQUIRED.md section D. No hardware has been
              purchased, so a hardware backend that silently produced numbers
              would be producing them from nothing.

The refusal is the honest implementation. A stub that returns plausible
readings is the single most dangerous thing this file could contain.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")))

from tools.csia_experiment import manifest as M          # noqa: E402
from tools.csia_experiment.validity import (             # noqa: E402
    TrialState, adjudicate, reconcile)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CAMPAIGN_ROOT = os.path.join(ROOT, "campaigns", "physical_validation")

PLAN_NAME = "_plan.json"


class OrchestratorError(RuntimeError):
    pass


# ------------------------------------------------------------------ planning

def plan_campaign(campaign_dir: str, campaign: str, scenario: str,
                  n_trials: int, prereg_path: Optional[str] = None) -> dict:
    """Write the denominator before anything runs. Refuses to overwrite."""
    os.makedirs(campaign_dir, exist_ok=True)
    target = os.path.join(campaign_dir, PLAN_NAME)
    plan = {
        "schema": "csia.research.campaign_plan/1",
        "campaign": campaign,
        "scenario": scenario,
        "n_trials": n_trials,
        "prereg_path": prereg_path,
        "prereg_sha256": M._sha256_file(prereg_path) if prereg_path else None,
        "trial_ids": [f"{campaign}-{i:03d}" for i in range(1, n_trials + 1)],
        "planned_at_head": M._git("rev-parse", "HEAD"),
        "note": ("Written BEFORE any trial ran. Every id here is counted in "
                 "the denominator whether or not it produces a result; a "
                 "campaign whose denominator is decided afterwards reports "
                 "whatever survived."),
    }
    blob = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if os.path.exists(target):
        with open(target, encoding="utf-8") as fh:
            if fh.read() == blob:
                return plan
        raise OrchestratorError(
            f"{target} already exists with a different plan. Re-planning a "
            f"campaign after trials have run changes its denominator, which "
            f"is the one thing a plan exists to fix. Use a new campaign name.")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return plan


def load_plan(campaign_dir: str) -> dict:
    target = os.path.join(campaign_dir, PLAN_NAME)
    if not os.path.exists(target):
        raise OrchestratorError(
            f"{campaign_dir} has no {PLAN_NAME}. Run `plan` first: a campaign "
            f"without a plan has no denominator.")
    with open(target, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ backends

def backend_simulated(trial_id: str, scenario: str, **kw) -> dict:
    """Deterministic, in-process, and honest about what it is worth.

    Produces a record that adjudicates VALID, with `evidence_tier: E0` and an
    explicit `admissible_as_evidence: False`. It exercises the orchestrator; it
    says nothing about any vehicle.
    """
    return {
        "attempted": True,
        "backend": "simulated",
        "evidence_tier": "E0",
        "admissible_as_evidence": False,
        "admissibility_note": (
            "SIMULATED BACKEND. This record exercises the orchestrator and "
            "carries no measurement of any vehicle, simulated or real. It "
            "must never be counted in a campaign result."),
        "prereg_deviations": [],
        "operator_abort": False,
        "rig_faults": [],
        "null_controls": [{"name": "no_injection", "quiet": True,
                           "measured": 0.0, "tolerance": 0.0}],
        "first_break": None,
        "stages": {},
    }


def backend_hardware(trial_id: str, scenario: str, **kw) -> dict:
    raise OrchestratorError(
        "the hardware backend is not implemented, and a stub would be worse "
        "than its absence.\n\n"
        "No flight controller, companion computer or fault-injection rig has "
        "been purchased -- see USER_ACTION_REQUIRED.md section D and "
        "hardware/validation_rig/PURCHASE_JUSTIFICATION.csv. A backend that "
        "returned plausible readings would produce E2 and E3 numbers from "
        "nothing, and they would be indistinguishable from measurements in "
        "every downstream file.\n\n"
        "PAPER_IMPACT_LEDGER.yaml records E2-E5 as NOT_STARTED. That stays "
        "true until hardware exists.")


BACKENDS = {
    "simulated": backend_simulated,
    "hardware": backend_hardware,
}


# ------------------------------------------------------------------- running

def run_trial(campaign_dir: str, trial_id: str, backend: str,
              profile_path: Optional[str] = None,
              deployment_path: Optional[str] = None,
              record_override: Optional[dict] = None) -> str:
    plan = load_plan(campaign_dir)
    if trial_id not in plan["trial_ids"]:
        raise OrchestratorError(
            f"{trial_id} is not in the plan for campaign "
            f"{plan['campaign']!r}. Adding a trial to a running campaign "
            f"grows the numerator without the denominator, which is how a "
            f"campaign acquires arms until one of them works.")

    if record_override is not None:
        record = dict(record_override)
        record.setdefault("attempted", True)
        record.setdefault("backend", backend)
    else:
        fn = BACKENDS.get(backend)
        if fn is None:
            raise OrchestratorError(
                f"unknown backend {backend!r}; have {sorted(BACKENDS)}")
        record = fn(trial_id, plan["scenario"],
                    profile_path=profile_path,
                    deployment_path=deployment_path)

    adapter = None
    if profile_path:
        from csia.aircraft.profile import load as load_profile
        from csia.deploy.edge import _adapter_for
        adapter = _adapter_for(load_profile(profile_path).autopilot)

    man = M.TrialManifest(
        trial_id=trial_id, campaign=plan["campaign"],
        scenario=plan["scenario"], prereg_path=plan.get("prereg_path"),
        record=record,
        provenance_=M.provenance(profile_path, deployment_path, adapter))
    return man.write(campaign_dir)


# ----------------------------------------------------------------- reporting

def report(campaign_dir: str) -> dict:
    """Reconcile the campaign. Raises rather than printing an open sum."""
    plan = load_plan(campaign_dir)
    written = {m["trial_id"]: m for m in M.campaign_records(campaign_dir)}

    records = []
    for trial_id in plan["trial_ids"]:
        man = written.get(trial_id)
        # A planned trial with no manifest IS the not-attempted case, and it is
        # counted here rather than quietly dropped.
        records.append(man["record"] if man else {"attempted": False})

    orphans = sorted(set(written) - set(plan["trial_ids"]))
    if orphans:
        raise OrchestratorError(
            f"manifests exist for trials not in the plan: {orphans}. Either "
            f"the plan was replaced or trials were added; both change the "
            f"denominator after the fact.")

    summary = reconcile(records)
    summary["campaign"] = plan["campaign"]
    summary["scenario"] = plan["scenario"]
    summary["prereg_path"] = plan.get("prereg_path")
    summary["trials"] = [
        {"trial_id": tid,
         "state": adjudicate(rec).state.value,
         "backend": rec.get("backend"),
         "evidence_tier": rec.get("evidence_tier"),
         "admissible_as_evidence": rec.get("admissible_as_evidence")}
        for tid, rec in zip(plan["trial_ids"], records)]

    inadmissible = [t["trial_id"] for t in summary["trials"]
                    if t["state"] == TrialState.VALID.value
                    and t["admissible_as_evidence"] is False]
    if inadmissible:
        summary["admissibility_warning"] = (
            f"{len(inadmissible)} trial(s) adjudicate VALID but are marked "
            f"admissible_as_evidence: False -- they exercised the pipeline "
            f"and measured nothing: {inadmissible}. VALID means the evidence "
            f"chain closed, NOT that the evidence is admissible. Any campaign "
            f"result quoting these is quoting the orchestrator, not a "
            f"vehicle.")
    return summary


# ---------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="csia-experiment",
        description="Plan, run and reconcile validation campaigns. Writes "
                    "immutable trial manifests; starts no mode with command "
                    "authority.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="write the denominator before any trial")
    p.add_argument("--dir", required=True)
    p.add_argument("--campaign", required=True)
    p.add_argument("--scenario", required=True)
    p.add_argument("--trials", type=int, required=True)
    p.add_argument("--prereg", default=None)

    r = sub.add_parser("run", help="run one planned trial")
    r.add_argument("--dir", required=True)
    r.add_argument("--trial", required=True)
    r.add_argument("--backend", default="simulated", choices=sorted(BACKENDS))
    r.add_argument("--profile", default=None)
    r.add_argument("--deployment", default=None)

    s = sub.add_parser("report", help="reconcile and summarise")
    s.add_argument("--dir", required=True)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "plan":
            out = plan_campaign(args.dir, args.campaign, args.scenario,
                                args.trials, args.prereg)
        elif args.cmd == "run":
            out = {"manifest": run_trial(
                args.dir, args.trial, args.backend,
                profile_path=args.profile, deployment_path=args.deployment)}
        else:
            out = report(args.dir)
    except (OrchestratorError, M.ManifestError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":                              # pragma: no cover
    sys.exit(main())
