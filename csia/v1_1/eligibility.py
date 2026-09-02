"""Function-specific eligibility — Phase 4 §§6–13.

The question this layer answers is not "is the GPS healthy". It is **"is this
particular vehicle function still justifiable on the evidence that exists?"**

Three properties are structural rather than promised:

1. **No new thresholds.** Every trust requirement in
   `FUNCTION_REQUIREMENTS.yaml` names a field of the FROZEN `FailsafeConfig`
   and inherits its value. `_Threshold.resolve` looks the name up; there is no
   number to copy and therefore none to drift.

2. **The policy cannot see ground truth.** `Observation` is a frozen dataclass
   whose fields are exactly §9's permitted inputs. There is no field for a
   scenario name, an injected-fault label, a filename or a simulator
   parameter, so a policy that tried to consult one would not compile.

3. **A high posterior alone is never eligibility.** §10. A leader at 0.9998
   with zero discriminating evidence against `gps_fault` fires
   `SUPPORT_LOST_FOR_REQUIRED_INFORMATION`, which is INELIGIBLE for a
   `REQUIRE_IDENTIFIABLE` function — and it fires *independently* of
   freshness, so removing the freshness rule would not rescue it.

A sequential alarm degrades and never attributes (§11): the CUSUM says the
evidence changed, and the diagnosis is the only thing permitted to say why.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields

import yaml

from ..runtime.failsafe import FailsafeConfig, FailsafeLevel
from . import reason_codes as RC

_DEFAULT_REQUIREMENTS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "engineering", "v1_1", "FUNCTION_REQUIREMENTS.yaml")

SUPPORT_POLICIES = ("REQUIRE_IDENTIFIABLE", "TOLERATE_AMBIGUITY")


# ---------------------------------------------------------------- inputs
@dataclass(frozen=True)
class Observation:
    """One tick of the inputs §9 permits, and nothing else.

    Deliberately absent: scenario label, injected-fault label, ground truth,
    filename, simulator parameter. Adding one would be a policy that can see
    the answer, which is the failure §9 exists to prevent, and a test asserts
    this field set.
    """

    t: float
    trust: dict                       # {node: float}
    fresh: dict                       # {node: bool}
    observable: frozenset             # nodes present in the input at all
    relation_gates: dict              # {relation: gate}  (max over edges)
    sequential_alarms: frozenset      # covered nodes currently alarming
    leader: str
    posterior: float
    support_state: str
    leader_identifiable: bool
    non_identifiable_against: frozenset
    prior_sensitive: bool
    neutral_leader: str               # leader under a uniform prior
    active_evidence_count: int
    discriminating_evidence: dict     # {competitor: n_terms}
    assurance_level: int              # FailsafeLevel value
    missing_reason: dict = field(default_factory=dict)   # {node: enum|None}


# ---------------------------------------------------------- requirements
@dataclass(frozen=True)
class _Threshold:
    """A trust requirement stated by NAME, resolved from FailsafeConfig."""

    inherits: str
    node: str | None = None
    group: tuple = ()
    reduce: str = "max"

    def resolve(self, cfg: FailsafeConfig) -> float:
        if not hasattr(cfg, self.inherits):
            raise ValueError(
                f"trust requirement inherits {self.inherits!r}, which is not "
                f"a FailsafeConfig field. Requirements may only inherit "
                f"declared engineering thresholds.")
        return float(getattr(cfg, self.inherits))

    @property
    def subject(self) -> str:
        return self.node or f"max({', '.join(self.group)})"

    def value(self, trust: dict):
        if self.node is not None:
            return trust.get(self.node)
        vals = [trust[n] for n in self.group if n in trust]
        if not vals:
            return None
        return max(vals) if self.reduce == "max" else min(vals)


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    summary: str
    required_sources: tuple
    required_source_groups: tuple
    required_relations: tuple
    trust_requirements: tuple
    sensitive_hypotheses: frozenset
    support_policy: str
    max_assurance_level: int

    @property
    def all_required_nodes(self) -> tuple:
        out = list(self.required_sources)
        for g in self.required_source_groups:
            out.extend(g)
        for th in self.trust_requirements:
            if th.node:
                out.append(th.node)
            out.extend(th.group)
        return tuple(sorted(set(out)))


@dataclass(frozen=True)
class Requirements:
    version: str
    functions: dict
    omitted: dict

    @classmethod
    def load(cls, path: str | None = None) -> "Requirements":
        with open(path or _DEFAULT_REQUIREMENTS, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        funcs = {}
        for name, row in doc["functions"].items():
            ths = []
            for t in row.get("trust_requirements", []):
                ths.append(_Threshold(inherits=t["inherits"],
                                      node=t.get("node"),
                                      group=tuple(t.get("group", ())),
                                      reduce=t.get("reduce", "max")))
            policy = row["support_policy"]
            if policy not in SUPPORT_POLICIES:
                raise ValueError(f"{name}: unknown support_policy {policy!r}")
            funcs[name] = FunctionSpec(
                name=name,
                summary=row["summary"],
                required_sources=tuple(row.get("required_sources", ())),
                required_source_groups=tuple(
                    tuple(g) for g in row.get("required_source_groups", ())),
                required_relations=tuple(row.get("required_relations", ())),
                trust_requirements=tuple(ths),
                sensitive_hypotheses=frozenset(
                    row.get("sensitive_hypotheses", ())),
                support_policy=policy,
                max_assurance_level=int(
                    FailsafeLevel[row["max_assurance_level"]]))
        return cls(version=doc["version"], functions=funcs,
                   omitted=doc.get("omitted", {}))


# --------------------------------------------------------------- verdict
@dataclass(frozen=True)
class Verdict:
    function: str
    state: str
    reason_codes: tuple
    required_inputs_available: bool
    support_sufficient: bool
    detail: dict = field(default_factory=dict)

    def row(self) -> dict:
        return {"function": self.function, "state": self.state,
                "reason_codes": "|".join(self.reason_codes),
                "required_inputs_available": self.required_inputs_available,
                "support_sufficient": self.support_sufficient}


# ---------------------------------------------------------------- policy
class EligibilityPolicy:
    """Deterministic. Same observation in, same verdict out, every time.

    `evaluate` is the pure per-tick rule set. `update` adds the dwell
    hysteresis, which inherits `FailsafeConfig.dwell_up` / `dwell_down` — the
    same declared numbers the safety path already uses — so eligibility cannot
    chatter on a threshold crossing (§30).
    """

    def __init__(self, requirements: Requirements | None = None,
                 cfg: FailsafeConfig | None = None, *, dwell: bool = True):
        self.req = requirements or Requirements.load()
        self.cfg = cfg or FailsafeConfig()
        self.use_dwell = dwell
        for spec in self.req.functions.values():      # fail fast, not at tick
            for th in spec.trust_requirements:
                th.resolve(self.cfg)
        self._state = {n: None for n in self.req.functions}
        self._candidate = {n: (None, None) for n in self.req.functions}
        self._since = {n: None for n in self.req.functions}

    # -- the rules ------------------------------------------------------
    def _evaluate_one(self, spec: FunctionSpec, obs: Observation) -> Verdict:
        fired = []          # (code, state, detail)

        def fire(code, **detail):
            fired.append((code,
                          RC.severity_of(code, spec.support_policy), detail))

        # UNKNOWN: the policy cannot evaluate its own requirements ------
        for node in spec.all_required_nodes:
            if node not in obs.observable:
                fire("REQUIRED_SOURCE_NOT_OBSERVABLE", source=node)
        if (spec.support_policy == "REQUIRE_IDENTIFIABLE"
                and obs.support_state == "NO_APPLICABLE_EVIDENCE"):
            fire("SUPPORT_ANALYSIS_UNAVAILABLE")

        # required sources -------------------------------------------------
        for node in spec.required_sources:
            if node in obs.observable and not obs.fresh.get(node, False):
                code = _ABSENCE_CODE.get(obs.missing_reason.get(node),
                                         "REQUIRED_SOURCE_NOT_FRESH")
                fire(code, source=node)

        # redundant groups: any-of, and losing redundancy is degradation ---
        for group in spec.required_source_groups:
            live = [n for n in group
                    if n in obs.observable and obs.fresh.get(n, False)]
            if not live:
                fire("REQUIRED_SOURCE_GROUP_EXHAUSTED", group=list(group))
            elif len(live) < len(group):
                for n in group:
                    if n not in live:
                        # §33: carry the producer's own reason even here,
                        # where the group is still satisfied and the code is
                        # about redundancy rather than about absence.
                        fire("REDUNDANT_SOURCE_UNAVAILABLE", source=n,
                             absence=obs.missing_reason.get(n))

        # relation evidence must exist to be checkable ---------------------
        if spec.required_relations:
            if not any(float(obs.relation_gates.get(r, 0.0)) > 1e-9
                       for r in spec.required_relations):
                fire("REQUIRED_RELATION_NOT_APPLICABLE",
                     relations=list(spec.required_relations))

        # inherited trust requirements ------------------------------------
        for th in spec.trust_requirements:
            limit = th.resolve(self.cfg)
            val = th.value(obs.trust)
            if val is not None and float(val) < limit:
                fire("TRUST_BELOW_INHERITED_REQUIREMENT",
                     subject=th.subject, value=round(float(val), 4),
                     inherits=th.inherits, limit=limit)

        # assurance boundary ----------------------------------------------
        if int(obs.assurance_level) > spec.max_assurance_level:
            fire("ASSURANCE_BEYOND_FUNCTION_BOUNDARY",
                 level=FailsafeLevel(int(obs.assurance_level)).name,
                 boundary=FailsafeLevel(spec.max_assurance_level).name)

        # support: the section 10 rule ------------------------------------
        unresolved = sorted(spec.sensitive_hypotheses
                            & set(obs.non_identifiable_against))
        support_sufficient = not unresolved
        if unresolved:
            fire("SUPPORT_LOST_FOR_REQUIRED_INFORMATION",
                 hypotheses=unresolved)
        elif obs.leader in spec.sensitive_hypotheses:
            # named, bounded, identified -- a different situation
            fire("NAMED_CAUSE_AFFECTS_FUNCTION", leader=obs.leader)
        # Prior sensitivity counts only where it concerns a hypothesis THIS
        # function depends on being false. §7's requirement is "no unresolved
        # ambiguity affecting THE REQUIRED INFORMATION", and a prior-driven
        # name for a fault the function does not depend on does not affect it.
        # The first implementation fired on any prior-sensitive leader; see
        # FUNCTION_ELIGIBILITY_SPEC.md §6 for the correction and its effect.
        if (spec.support_policy == "REQUIRE_IDENTIFIABLE"
                and obs.prior_sensitive
                and ({obs.leader, obs.neutral_leader}
                     & spec.sensitive_hypotheses)):
            fire("PRIOR_SENSITIVE_LEADER")

        # sequential alarm: degrade, never attribute (section 11) ---------
        for node in sorted(set(spec.all_required_nodes)
                           & set(obs.sequential_alarms)):
            fire("SEQUENTIAL_ALARM_ON_REQUIRED_SOURCE", source=node)

        if not fired:
            return Verdict(spec.name, RC.ELIGIBLE, ("ALL_REQUIREMENTS_MET",),
                           True, True, {})

        state = RC.worst(s for _c, s, _d in fired)
        inputs_ok = not any(
            c in _INPUT_CODES for c, _s, _d in fired)
        return Verdict(
            function=spec.name, state=state,
            reason_codes=tuple(c for c, _s, _d in fired),
            required_inputs_available=inputs_ok,
            support_sufficient=support_sufficient,
            detail={c: d for c, _s, d in fired if d})

    def evaluate(self, obs: Observation) -> dict:
        """Pure rules, no hysteresis. Deterministic and total."""
        return {name: self._evaluate_one(spec, obs)
                for name, spec in sorted(self.req.functions.items())}

    # -- dwell ----------------------------------------------------------
    def update(self, obs: Observation) -> dict:
        """Apply the inherited dwell so eligibility cannot chatter (§30).

        Escalation to a more restrictive state requires `dwell_up` seconds of
        persistence; relaxation requires `dwell_down`. Both are FailsafeConfig
        fields — the same declared numbers the frozen safety path uses.
        """
        raw = self.evaluate(obs)
        if not self.use_dwell:
            self._state = {n: v.state for n, v in raw.items()}
            return raw
        out = {}
        for name, v in raw.items():
            cur = self._state[name]
            if cur is None:                       # first tick: adopt
                self._state[name] = v.state
                out[name] = v
                continue
            if v.state == cur:
                self._candidate[name] = (None, None)
                out[name] = v
                continue
            cand, since = self._candidate[name]
            if cand != v.state:
                self._candidate[name] = (v.state, obs.t)
                out[name] = Verdict(name, cur, v.reason_codes,
                                    v.required_inputs_available,
                                    v.support_sufficient, v.detail)
                continue
            need = (self.cfg.dwell_up
                    if RC.SEVERITY_RANK[v.state] > RC.SEVERITY_RANK[cur]
                    else self.cfg.dwell_down)
            if obs.t - since >= need:
                self._state[name] = v.state
                self._candidate[name] = (None, None)
                out[name] = v
            else:
                out[name] = Verdict(name, cur, v.reason_codes,
                                    v.required_inputs_available,
                                    v.support_sufficient, v.detail)
        return out


#: Codes that mean an INPUT was missing, as opposed to evidence being weak.
_INPUT_CODES = frozenset({
    "REQUIRED_SOURCE_NOT_OBSERVABLE", "REQUIRED_SOURCE_NOT_FRESH",
    "REQUIRED_SOURCE_GROUP_EXHAUSTED", "REQUIRED_RELATION_NOT_APPLICABLE",
    "SOURCE_ABSENT_SENTINEL", "SOURCE_ABSENT_STALE",
    "SOURCE_ABSENT_NOT_RECEIVED", "SOURCE_ABSENT_NO_3D_FIX",
})

#: §33: preserve the producer's own reason where the ingest layer knows it.
_ABSENCE_CODE = {
    "SENTINEL": "SOURCE_ABSENT_SENTINEL",
    "STALE": "SOURCE_ABSENT_STALE",
    "NOT_RECEIVED": "SOURCE_ABSENT_NOT_RECEIVED",
    "NO_3D_FIX": "SOURCE_ABSENT_NO_3D_FIX",
}

OBSERVATION_FIELDS = tuple(f.name for f in fields(Observation))
