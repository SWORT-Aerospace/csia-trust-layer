"""Ready-made analyses: each input kind the Analyzer accepts, wired once.

| function | input | producers | semantic core |
|---|---|---|---|
| `v2_scenario(name)` | a frozen CSIA v2 scenario | the v2 domain plugins (legacy adapter) | 2.1.1 with successor profile r2 (aircraft), or the frozen profile |
| `cusum_scenario(name)` | a frozen v1 scenario (`csia/scenarios.py`) | the frozen v1.1 CUSUM bank | 2.1.1 + r2 (the CUSUM claims carry no symptom: the result is the evidence, its lineage and coverage) |
| `xsys_trial(analysis_id)` | one XSYS-001 trial, from the sealed stage-1 features | W_RPM, W_DYN, W_CTRL (+ the PX4 estimator when the flight's ULog is given) | 2.1.1 with the XSYS-001 research specification |
| `ulog(path)` | a PX4 ULog | the PX4 estimator | 2.1.1 + r2 |

Each returns `Run(results, inputs, gate, contracts)`, which
`report.machine_report` turns into a report.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from csia_semantic_core import Corrections, SemanticCore21
from csia_semantic_core.admission import EpochContext
from csia_semantic_core.profile_overlay import load_successor

from . import profile_gate as PG
from .adapters import cusum as CU
from .adapters import px4_estimator as PX
from .adapters import v2_domains as V2
from .adapters import xsys_witness as XW
from .analyzer import FlightAssuranceAnalyzer
from .contract import load_contracts

REPO = Path(__file__).resolve().parents[1]
V2_TICKS = 60      # the tick count the v2 localization tests and the corpus use


@dataclass
class Run:
    results: list
    inputs: dict
    gate: object
    contracts: dict
    analyzer: object = None


def _sha(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aircraft_setup(successor: str | None = "aircraft_successor_r2"):
    """(engine, core, gate, overlay) for the aircraft profile: 2.1.1 with the
    successor profile, gated once on one NOMINAL tick's declarations."""
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS
    from csia.v2.profiles.aircraft import build_aircraft_engine
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    ov = load_successor(successor) if successor else None
    engine = build_aircraft_engine()
    core = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True,
                                      pacing=ov.pacing_map() if ov else None)
    sample = SC.run(engine, SCENARIOS["NOMINAL"], ticks=1,
                    payload_for=example_payload_feed("clean"))[0].records
    return engine, core, PG.gate(ov, sample, engine.functions), ov


# ------------------------------------------------------------------ v2 corpus
def v2_scenario(name: str, ticks: int = V2_TICKS) -> Run:
    from csia.v2 import scenarios as SC
    from csia.v2.profiles import SCENARIOS, build_engine_for
    from csia.v2.profiles.aircraft_scenarios import example_payload_feed
    sc = SCENARIOS[name]
    engine = build_engine_for(sc)
    feed = (example_payload_feed(getattr(sc, "v1_1_variant", "clean"))
            if sc.system == "aircraft" else None)
    res = SC.run(engine, sc, ticks=ticks, payload_for=feed)
    ov = load_successor(V2.SUCCESSOR[sc.system]) if sc.system in V2.SUCCESSOR else None
    base = V2.PROFILE_BASE[sc.system]
    contracts = V2.legacy_contracts(engine, base)
    core = SemanticCore21.from_engine(engine, Corrections.revised(), trace=True,
                                      pacing=ov.pacing_map() if ov else None)
    gate = PG.gate(ov, res[0].records, engine.functions)
    an = FlightAssuranceAnalyzer(core, contracts, gate, base)
    out = []
    for sa in res:
        recs = ov.apply(sa.records) if ov else sa.records
        out.append(an.step(float(sa.t), V2.envelopes(recs, sa.t, contracts)))
    return Run(out, {"kind": "v2_scenario", "scenario": name, "system": sc.system,
                     "ticks": ticks}, gate, contracts, an)


# ------------------------------------------------------------------ CUSUM
def cusum_scenario(name: str) -> Run:
    import numpy as np

    from csia.scenarios import run_scenario
    _title, _faults, td, _hist, _diag = run_scenario(name)
    _engine, core, gate, _ov = aircraft_setup()
    contracts = load_contracts("cusum_v1_1_sequential")
    an = FlightAssuranceAnalyzer(core, contracts, gate, V2.AIRCRAFT_BASE)
    prod = CU.CusumProducer()
    cov = CU.coverage_notices()
    out = []
    names = sorted(td.fresh)
    for k in range(len(td.t)):
        t = float(td.t[k])
        fresh = {n: bool(td.fresh[n][k]) for n in names}
        phys = {n: (float(lam[k]), float(np.asarray(g).flat[min(k, np.asarray(g).size - 1)]))
                for n, (lam, g) in td.physics.items()}
        out.append(an.step(t, prod.step(t, phys, fresh), coverage=cov))
    return Run(out, {"kind": "cusum_v1_scenario", "scenario": name, "ticks": len(td.t)},
               gate, contracts, an)


# ------------------------------------------------------------------ XSYS-001
def xsys_key() -> dict:
    return json.loads((XW.CAMPAIGN / "stage0/KEY.json").read_text())


def xsys_trial(analysis_id: str, variant: str = "V3_TEMPORAL", ulog_path=None,
               estimator_tick_s: float = 0.1) -> Run:
    """The trial's checkpoints C1 and C3, all four motors, the witnesses a
    variant consults. With `ulog_path` (the trial's flight log), the PX4
    estimator's evidence over [onset - 1 s, onset + 15 s] joins the same
    analysis on the same time axis (seconds from onset)."""
    key = xsys_key()["trials"]
    oid = next(o for o, k in key.items() if k["analysis_id"] == analysis_id)
    data = json.loads((XW.CAMPAIGN / "stage1/STAGE1.json").read_text())
    feats = data["trials"][oid]["features"]
    _S1, XA, _XF = XW.pipeline()
    base = "research/xsys_confirmatory_001/pipeline/xsys_v2_adapter.py"
    core = SemanticCore21((XA.SPEC,), XA.PREDICATES, (), Corrections.revised(), trace=True)
    gate = PG.not_applicable("xsys001_research_spec", base,
                             "the XSYS-001 symptom specification has no function table")
    names = list(XW.CONTRACT_FILES)
    est, onset_s = None, None
    inputs = {"kind": "xsys_trial", "analysis_id": analysis_id, "opaque_id": oid,
              "variant": variant, "truth": key[oid]["truth"],
              "stage1_sha256": _sha(XW.CAMPAIGN / "stage1/STAGE1.json")}
    if ulog_path is not None:
        names.append("px4_ekf2_estimator_status")
        log = PX.EstimatorLog.from_ulog(ulog_path)
        est = PX.EstimatorProducer(log)
        onset_s = _xsys_onset_s(ulog_path, key[oid])
        inputs.update({"ulog": log.origin, "onset_s_in_log": round(onset_s, 6)})
    contracts = load_contracts(*names)
    an = FlightAssuranceAnalyzer(core, contracts, gate, base)
    ticks = []
    if est is not None:
        n = int(round(15.0 / estimator_tick_s))
        ticks = [round(-1.0 + i * estimator_tick_s, 6) for i in range(int(1.0 / estimator_tick_s))]
        ticks += [round(i * estimator_tick_s, 6) for i in range(n + 1)]
    ticks = sorted(set(ticks) | set(XW.CHECKPOINT_T.values()))
    cps = {v: k for k, v in XW.CHECKPOINT_T.items()}
    out = []
    for t in ticks:
        envs, epochs = [], None
        if t in cps:
            for subj in sorted(feats):
                envs += XW.envelopes(subj, feats[subj], variant, cps[t])
        if est is not None:
            envs += _shift(est.step(onset_s + t), onset_s)
            cur, ev = est.context(onset_s + t)
            epochs = EpochContext(cur, ev)
        out.append(an.step(t, envs, epochs=epochs, events={XW.ONSET: 0.0},
                           coverage=est.coverage_notices() if est else ()))
    return Run(out, inputs, gate, contracts, an)


def _shift(envs, onset_s):
    """Estimator envelopes on the trial's time axis (seconds from onset)."""
    from dataclasses import replace
    return [replace(e, content_time=e.content_time - onset_s,
                    produced_time=None if e.produced_time is None else e.produced_time - onset_s)
            for e in envs]


def _xsys_onset_s(ulog_path, trial_key) -> float:
    """The onset (t0) the frozen extraction uses, in seconds from log start."""
    S1, _XA, _XF = XW.pipeline()
    import xsys_extract as XE
    from pyulog import ULog
    flight = json.loads((XW.CAMPAIGN / "campaign/records" /
                         f"{trial_key['source_flight_id']}.json").read_text())
    u = ULog(str(ulog_path), ["parameter_update", "esc_status"])
    _tpu, t0_us, _v = XE.onset_time(u, flight["onset_param"])
    return (t0_us - u.start_timestamp) * 1e-6


# ------------------------------------------------------------------ PX4 ULog
def ulog(path, tick_s: float = 0.1, t_end=None) -> Run:
    return estimator_log(PX.EstimatorLog.from_ulog(path), tick_s, t_end)


def estimator_log(log, tick_s: float = 0.1, t_end=None) -> Run:
    """The PX4 estimator producer over a loaded log (`EstimatorLog.from_ulog`
    or `from_npz`)."""
    est = PX.EstimatorProducer(log)
    _engine, core, gate, _ov = aircraft_setup()
    contracts = load_contracts("px4_ekf2_estimator_status")
    an = FlightAssuranceAnalyzer(core, contracts, gate, V2.AIRCRAFT_BASE)
    last = est._stream[-1]["ts"] if est._stream else log.t0_us
    t_end = t_end if t_end is not None else (last - log.t0_us) * 1e-6
    out = []
    for i in range(int(t_end / tick_s) + 1):
        t = round(i * tick_s, 6)
        envs = est.step(t)
        cur, ev = est.context(t)
        out.append(an.step(t, envs, epochs=EpochContext(cur, ev),
                           coverage=est.coverage_notices()))
    kind = "px4_ulog" if "extract" not in log.origin else "px4_ulog_extract"
    return Run(out, {"kind": kind, "ulog": log.origin, "tick_s": tick_s,
                     "selector": est._lane_mode}, gate, contracts, an)
