"""Sequential change detection — the CUSUM bank kept by Phase 3B.

**Known prior art. No algorithmic novelty is claimed:** this is Page's 1954
one-sided CUSUM, used as an engineering baseline. It was promoted from the
Phase 3B ablation harness into the runtime because Phase 3B measured it
improving five of nine mechanisms with zero regressions and zero clean alarms,
not because it is interesting.

    z_t = (lam_t - mu0) / sigma0        standardised PRE-TRANSFORM residual
    S_t = max(0, S_{t-1} + z_t - k)     one-sided CUSUM
    alarm when S_t > h

    k = 0.5      textbook, set by design
    h = 500      smallest value on a fixed grid giving ZERO alarms on the
                 clean nominal arm; see engineering/v1_1/SEQUENTIAL_DETECTOR_SPEC.md

`lam` is the pre-transform smoothed chi-square the layer already computes
(`td.physics[n] = (lam, gate)`), never the post-transform consistency: the
consistency floors every sub-unity chi-square to exactly 1.0, which gave
sigma0 = 0 for gps, mag and battery and made the detector unable to alarm
anywhere but gps.

GATING. A gated-out or stale sample is not evidence and does not enter the
statistic. This mirrors what the frozen runtime does to the same quantity
(`csia/runtime/online.py:613`).

COVERAGE, STATED UP FRONT. In-control statistics exist for five nodes:
`gps`, `mag`, `battery`, `motor_esc`, `vibration`. `baro` is excluded because
its clean-arm sigma0 is degenerate (exactly 0.0 over 1500 ticks). **There is
no per-IMU physics chi-square in this construction, so this bank cannot see
`imu0` or `imu1` at all.** That is why the trust recursion is retained, and it
is a coverage fact, not a defect to be papered over.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Textbook slack. Set by design, never tuned against a fault outcome.
CUSUM_K = 0.5

#: Selected by the zero-clean-alarm rule on a fixed grid. The textbook
#: h = 5.0 FAILED here (2681 clean alarm ticks under v1.1) and is retained as
#: a committed negative result in SEQUENTIAL_DETECTOR_SPEC.md.
CUSUM_H = 500.0

#: Gate/freshness cut-off, matching the frozen core's own epsilon.
GATE_EPS = 1e-9

#: In-control mean and standard deviation of the pre-transform smoothed
#: chi-square, derived from the CLEAN arm and from nowhere else. Frozen here
#: so the runtime does not re-estimate them from live data — an in-control
#: statistic re-estimated during a fault stops being in-control.
#:
#: Reproduce:  python engineering/v1_1/ablation/b4_verify.py
#: A test re-derives these from the clean scenario and asserts equality.
IN_CONTROL = {
    "battery":   (0.03777180955748877, 0.023591096327858184),
    "gps":       (0.6367516755642384,  0.3916758980801501),
    "mag":       (0.003894119674481343, 0.002566076206215175),
    "motor_esc": (0.1285936759136795,  0.03315064072428847),
    "vibration": (0.025427388135084314, 0.013755742784080371),
}

#: Nodes with no sequential residual, and why. Kept explicit so that "no
#: alarm" is never silently read as "no fault".
NO_RESIDUAL = {
    "baro": "clean-arm sigma0 is degenerate (0.0 over 1500 ticks)",
    "imu0": "no per-IMU physics chi-square exists in this construction",
    "imu1": "no per-IMU physics chi-square exists in this construction",
}

COVERED_NODES = tuple(sorted(IN_CONTROL))


@dataclass
class CusumBank:
    """Stateful per-node CUSUM. One float of state per covered node.

    This is the form Phase 5 ports: `float S[N_SEQ_NODES]`, one add, one
    max and one compare per covered node per tick.
    """

    k: float = CUSUM_K
    h: float = CUSUM_H
    stats: dict = field(default_factory=lambda: dict(IN_CONTROL))
    S: dict = field(default_factory=dict)
    alarming: set = field(default_factory=set)

    def __post_init__(self):
        self.S = {n: 0.0 for n in self.stats}
        self.alarming = set()

    def covers(self, node: str) -> bool:
        return node in self.stats

    def update(self, node: str, lam: float, active: bool) -> bool:
        """Advance one node by one tick. Returns True iff S > h this tick.

        `active` is gate-and-freshness. An inactive tick is skipped entirely:
        the statistic is neither advanced nor reset, because absence of
        evidence is not evidence of change.
        """
        if node not in self.S:
            return False
        if not active:
            return node in self.alarming
        mu0, sigma0 = self.stats[node]
        z = (float(lam) - mu0) / sigma0
        s = max(0.0, self.S[node] + z - self.k)
        self.S[node] = s
        if s > self.h:
            self.alarming.add(node)
            return True
        self.alarming.discard(node)
        return False

    def step(self, physics: dict, fresh: dict) -> dict:
        """Advance every covered node from one tick of the frozen inputs.

        `physics` is `{node: (lam, gate)}` exactly as the frozen comparator
        produces it; `fresh` is `{node: bool}`. Returns `{node: alarm}` for
        the covered nodes only — never a key for a node with no residual.
        """
        out = {}
        for node in self.stats:
            if node not in physics:
                continue
            lam, gate = physics[node]
            active = float(gate) > GATE_EPS and bool(fresh.get(node, True))
            out[node] = self.update(node, float(lam), active)
        return out

    @property
    def any_alarm(self) -> bool:
        return bool(self.alarming)

    def state(self) -> dict:
        """Serialisable detector state for the ledger and the output API."""
        return {"k": self.k, "h": self.h,
                "S": {n: round(v, 6) for n, v in sorted(self.S.items())},
                "alarming": sorted(self.alarming)}
