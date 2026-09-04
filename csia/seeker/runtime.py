"""Seeker online runtime: drives the UNMODIFIED CSIA cores.

Computes per-tick comparator edges + physics self-models for the three
seeker nodes and feeds them to TrustCore (trust) and DiagnosisCore
(attribution), then a small seeker escalation policy (SeekerPolicy) that
reuses the FailsafeLevel ladder. No core file is modified.

Graph (3 nodes, mirroring the quad edge+gate+physics pattern):
  Edge A  bearing_agreement : ir_seeker.az  vs rf_seeker.az
          gate = RF lock AND IR SNR proxy above floor (mirrors the quad
          mag/GPS-course speed-gate: bearing only trusted when the seeker
          actually sees the target)
  Edge B  rangerate_ins      : rf_seeker.closing vs INS-projected closing
          = (v_i_ins - v_t_known) . LOS_hat(rf az); gate = closing phase.
          (Uses known target velocity — valid in this synthetic setup; on a
          real system this term comes from the track filter. Documented.)
  phys_rf phys_rf_seeker      : rf.closing vs -d/dt(EW-smoothed rf.range)
  phys_ir phys_ir_seeker      : rf-derived 1/R^2 irradiance vs ir.intensity
  phys_ins phys_ins           : |ins.vel| vs |d/dt(EW-smoothed ins.pos)|

Consistency convention identical to the quad: lam = (resid/sigma)^2 per df,
EW-smoothed (alpha 0.15); c = exp(-max(0, lam-1)/2); gate in [0,1]. Sigmas
are the combined endpoint noise budgets from sensors.py — engineering
defaults, not tuned to the results.
"""

import time
from dataclasses import dataclass, field

import numpy as np

from ..diagnosis.bayes import DiagnosisCore
from ..runtime.failsafe import Action, FailsafeLevel
from ..trust_engine.engine import EngineConfig, TrustCore
from . import sensors as S
from .engagement import generate_engagement
from .sensors import sample_ins, sample_ir, sample_rf

NODES = ("ir_seeker", "rf_seeker", "ins")

# Edge/physics noise budgets (combined endpoint sigmas; see sensors.py).
SIG_BEARING = float(np.hypot(S.IR_AZ_SIGMA, S.RF_AZ_SIGMA))   # rad
SIG_RANGERATE = 2.5     # m/s (RF range-rate + INS projection + margin)
SIG_PHYS_RF = 6.0       # m/s (window-differenced smoothed range noise budget)
SIG_PHYS_IR = 0.05      # fractional irradiance
SIG_PHYS_INS = 1.5      # m/s (window-differenced smoothed position)
RATE_WIN = 50           # ticks (0.5 s at 100 Hz) baseline for rate estimates:
                        # single-tick differencing at 100 Hz amplifies sensor
                        # noise ~100x, so physics self-models estimate rate
                        # over a fixed window instead.
SNR_GATE_LO, SNR_GATE_HI = 1.5, 2.5   # IR intensity a.u. -> bearing gate
CLOSING_GATE = 50.0     # m/s, Edge B closing-phase gate
DETECT_TRUST = 0.85     # actionable trust threshold (mirrors quad line)

# Cause table for DiagnosisCore. Each cause lists features expected LOW.
SEEKER_CAUSES = {
    "nominal": [],
    "ir_decoy": ["bearing_agreement"],
    "rf_jam": ["bearing_agreement", "rangerate_ins", "phys_rf_seeker"],
}


class _EW:
    def __init__(self, a):
        self.a = a; self.y = None
    def update(self, x):
        x = np.asarray(x, float)
        self.y = x.copy() if self.y is None else (1 - self.a) * self.y + self.a * x
        return self.y


@dataclass
class SeekerConfig:
    caution: float = 0.75
    critical: float = 0.55
    dwell_up: float = 0.25      # s a condition must persist to escalate
    dwell_down: float = 1.0     # s of health to de-escalate
    arm_time: float = 2.5       # s warmup: rate-windows fill (0.5 s) + EW
                                # smoothers converge + Beta prior settles.
                                # Analogous to the quad's 10 s prior-
                                # convergence window; metrics exclude it.


class SeekerPolicy:
    """Engagement-confidence ladder. Reuses FailsafeLevel; new conditions."""

    def __init__(self, cfg: SeekerConfig | None = None):
        self.cfg = cfg or SeekerConfig()
        self.level = FailsafeLevel.NORMAL
        self.transitions = []
        self._since = {}
        self._below = None

    def _conditions(self, t, trust):
        cfg = self.cfg
        out = {}
        for ch in ("ir_seeker", "rf_seeker"):
            if trust[ch] < cfg.critical:
                out[f"crit_{ch}"] = (FailsafeLevel.CRITICAL,
                    f"{ch} trust {trust[ch]:.2f} < {cfg.critical} — targeting "
                    f"channel unreliable",
                    [Action("INHIBIT_TERMINAL_COMMIT",
                            "hold terminal commit; engagement confidence low",
                            {"channel": ch}),
                     Action("HANDOVER_TO_ALT_SEEKER",
                            "lean on the trusted seeker channel",
                            {"prefer": "rf_seeker" if ch == "ir_seeker"
                             else "ir_seeker"})])
        for ch in NODES:
            if cfg.critical <= trust[ch] < cfg.caution:
                out[f"caut_{ch}"] = (FailsafeLevel.CAUTION,
                    f"{ch} trust {trust[ch]:.2f} degraded",
                    [Action("DEWEIGHT_CHANNEL", "reduce fusion weight",
                            {"channel": ch})])
        return out

    def update(self, t, trust):
        cfg = self.cfg
        if t < cfg.arm_time:
            return []
        conds = self._conditions(t, trust)
        for k in list(self._since):
            if k not in conds:
                del self._since[k]
        for k in conds:
            self._since.setdefault(k, t)
        active = {k: v for k, v in conds.items()
                  if t - self._since[k] >= cfg.dwell_up}
        target = max((v[0] for v in active.values()),
                     default=FailsafeLevel.NORMAL)
        issued = []
        if target > self.level:
            self._below = None
            reasons = [v[1] for v in active.values()]
            issued = [a for v in active.values() for a in v[2]]
            self._transition(t, target, reasons, issued)
        elif target < self.level:
            if self._below is None:
                self._below = t
            if t - self._below >= cfg.dwell_down:
                self._below = None
                self._transition(t, target,
                                 [v[1] for v in active.values()] or
                                 ["conditions cleared"], [])
        else:
            self._below = None
        return issued

    def _transition(self, t, level, reasons, actions):
        prev = self.level
        self.level = level
        self.transitions.append({"t": round(t, 3), "from": prev.name,
                                 "to": level.name, "reasons": reasons,
                                 "actions": [(a.name, a.params) for a in actions]})


@dataclass
class SeekerResult:
    t: np.ndarray
    trust: dict                 # node -> array
    diag: dict                  # cause -> array
    causes: list
    edges: dict                 # feature -> (consistency array, gate array)
    transitions: list
    mean_latency_us: float
    states: list = field(default_factory=list)


class SeekerRuntime:
    def __init__(self, tick_hz=100.0, engine_cfg=None, policy_cfg=None):
        self.tick_hz = tick_hz
        self.core = TrustCore(NODES, engine_cfg or EngineConfig())
        self.diag = DiagnosisCore(SEEKER_CAUSES)
        self.policy = SeekerPolicy(policy_cfg)
        from collections import deque
        self._lamA = _EW(0.15); self._lamB = _EW(0.15)
        self._lamPr = _EW(0.15); self._lamPi = _EW(0.15); self._lamPn = _EW(0.15)
        self._rng_s = _EW(0.1); self._pos_s = _EW(0.1)
        self._rng_buf = deque(maxlen=RATE_WIN + 1)
        self._pos_buf = deque(maxlen=RATE_WIN + 1)

    def run(self, eng, ir, rf, ins):
        dt = eng.dt
        n = eng.n
        v_t = eng.v_t  # known target velocity (synthetic setup)
        rec_t, rec_trust = [], {nm: [] for nm in NODES}
        rec_diag = {c: [] for c in self.diag.names}
        rec_feat = {k: ([], []) for k in
                    ("bearing_agreement", "rangerate_ins",
                     "phys_rf_seeker", "phys_ir_seeker", "phys_ins")}
        lat_sum = 0.0; nt = 0
        C = lambda lam: float(np.exp(-0.5 * max(0.0, lam - 1.0)))
        for k in range(1, n):
            t0 = time.perf_counter()
            az_ir = ir["az"][k]; inten = ir["intensity"][k]
            az_rf = rf["az"][k]; rng_rf = rf["range"][k]; clo_rf = rf["closing"][k]
            lock = bool(rf["lock"][k]); v_ins = ins["vel"][k]; p_ins = ins["pos"][k]

            # --- Edge A: bearing agreement -------------------------------
            resA = (az_ir - az_rf + np.pi) % (2 * np.pi) - np.pi
            lamA = float(self._lamA.update((resA / SIG_BEARING) ** 2))
            snr_gate = float(np.clip((inten - SNR_GATE_LO)
                                     / (SNR_GATE_HI - SNR_GATE_LO), 0, 1))
            gateA = snr_gate * (1.0 if lock else 0.0)

            # --- Edge B: RF range-rate vs INS-projected closing ----------
            los = np.array([np.cos(az_rf), np.sin(az_rf), 0.0])
            clo_ins = float((v_ins - v_t[k]) @ los)
            lamB = float(self._lamB.update(((clo_rf - clo_ins) / SIG_RANGERATE) ** 2))
            gateB = 1.0 if clo_rf > CLOSING_GATE else 0.0

            # --- phys_rf: RF closing vs range-derived closing ------------
            # rate over a RATE_WIN baseline (single-tick diff at 100 Hz is
            # ~100x too noisy). Gated off until the window fills.
            rng_sm = float(self._rng_s.update(rng_rf))
            self._rng_buf.append(rng_sm)
            gatePr = 1.0
            if len(self._rng_buf) > RATE_WIN:
                drng = (self._rng_buf[-1] - self._rng_buf[0]) / (RATE_WIN * dt)
                lamPr = float(self._lamPr.update(((clo_rf + drng) / SIG_PHYS_RF) ** 2))
            else:
                lamPr = float(self._lamPr.y) if self._lamPr.y is not None else 0.0
                gatePr = 0.0

            # --- phys_ir: 1/R^2 irradiance vs measured intensity ---------
            inten_pred = S.IR_K / max(rng_rf, 1.0) ** 2
            resPi = (inten - inten_pred) / max(inten_pred, 1e-9)
            lamPi = float(self._lamPi.update((resPi / SIG_PHYS_IR) ** 2))
            gatePi = 1.0 if lock else 0.0

            # --- phys_ins: |vel| vs windowed |d(pos)/dt| -----------------
            pos_sm = self._pos_s.update(p_ins)
            self._pos_buf.append(pos_sm)
            gatePn = 1.0
            if len(self._pos_buf) > RATE_WIN:
                dpos = (self._pos_buf[-1] - self._pos_buf[0]) / (RATE_WIN * dt)
                lamPn = float(self._lamPn.update(
                    ((np.linalg.norm(v_ins) - np.linalg.norm(dpos)) / SIG_PHYS_INS) ** 2))
            else:
                lamPn = float(self._lamPn.y) if self._lamPn.y is not None else 0.0
                gatePn = 0.0

            edges = {
                "bearing_agreement": ("ir_seeker", "rf_seeker", lamA, gateA),
                "rangerate_ins": ("rf_seeker", "ins", lamB, gateB),
            }
            phys = {
                "rf_seeker": (lamPr, gatePr),
                "ir_seeker": (lamPi, gatePi),
                "ins": (lamPn, gatePn),
            }
            hist = {nm: None for nm in NODES}
            vr = {nm: None for nm in NODES}
            fresh = {nm: True for nm in NODES}
            res = self.core.step(edges, phys, hist, vr, fresh)

            feats = {
                "bearing_agreement": (C(lamA), gateA),
                "rangerate_ins": (C(lamB), gateB),
                "phys_rf_seeker": (C(lamPr), gatePr),
                "phys_ir_seeker": (C(lamPi), gatePi),
                "phys_ins": (C(lamPn), gatePn),
            }
            post = self.diag.step(feats)
            trust_now = {nm: res[nm]["trust"] for nm in NODES}
            self.policy.update(float(eng.t[k]), trust_now)
            lat_sum += (time.perf_counter() - t0) * 1e6; nt += 1

            rec_t.append(eng.t[k])
            for nm in NODES:
                rec_trust[nm].append(trust_now[nm])
            for c in self.diag.names:
                rec_diag[c].append(post[c])
            rec_feat["bearing_agreement"][0].append(C(lamA)); rec_feat["bearing_agreement"][1].append(gateA)
            rec_feat["rangerate_ins"][0].append(C(lamB)); rec_feat["rangerate_ins"][1].append(gateB)
            rec_feat["phys_rf_seeker"][0].append(C(lamPr)); rec_feat["phys_rf_seeker"][1].append(gatePr)
            rec_feat["phys_ir_seeker"][0].append(C(lamPi)); rec_feat["phys_ir_seeker"][1].append(gatePi)
            rec_feat["phys_ins"][0].append(C(lamPn)); rec_feat["phys_ins"][1].append(gatePn)

        return SeekerResult(
            t=np.array(rec_t),
            trust={nm: np.array(v) for nm, v in rec_trust.items()},
            diag={c: np.array(v) for c, v in rec_diag.items()},
            causes=self.diag.names,
            edges={k: (np.array(v[0]), np.array(v[1])) for k, v in rec_feat.items()},
            transitions=self.policy.transitions,
            mean_latency_us=lat_sum / max(nt, 1))


def run_seeker(scenario_faults, tick_hz=100.0, seed=0, duration=20.0):
    """Full pipeline for one run. Deterministic given seed."""
    eng = generate_engagement(tick_hz=tick_hz, duration=duration)
    ir = sample_ir(eng, scenario_faults, seed + 1)
    rf = sample_rf(eng, scenario_faults, seed + 2)
    ins = sample_ins(eng, scenario_faults, seed + 3)
    return eng, SeekerRuntime(tick_hz=tick_hz).run(eng, ir, rf, ins)
