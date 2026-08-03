"""Comparison baselines for the shared-power benchmark (slice 3D).

Implemented exactly as pre-registered in
docs/validation/SHARED_POWER_BASELINE_PROTOCOL.md, which was frozen before
this file was written and before any result was viewed.

Systems C and D deliberately reuse CSIA's own per-source severity
normalization, dwell and outer temporal window. If a CSIA margin survives that,
it cannot be attributed to a handicapped baseline. System D is the decisive
comparison — a hand-written shared-resource rule with no contradiction
handling — because beating System A (structurally single-source) proves nothing.

EVALUATION ONLY. Nothing here is part of the runtime.
"""

from dataclasses import dataclass, field

from .causal import (RESOURCE_TOPOLOGY, SOURCE_DEGRADED, SOURCE_INDICATORS,
                     normalize_severity)

VOTE_C = 0.70            # System B: an indicator votes "faulty" below this
DWELL_TICKS = 25         # Systems C, D — identical to CSIA
RECOVER_FACTOR = 0.6     # Systems C, D — identical to CSIA hysteresis
D_WINDOW_S = 9.0         # System D temporal window (CSIA's outer bound)
D_MIN_SOURCES = 2
RESOURCE = "MAIN_POWER_PACK"


@dataclass
class BaselineVerdict:
    """Shared output view — what every system can express."""
    system: str
    fault_detected: bool = False
    affected_sources: tuple = ()
    shared_resource: str | None = None
    shared_vs_independent: str = "ABSTAIN"   # SHARED | INDEPENDENT | ABSTAIN
    root_cause_supported: bool = True        # False for System A on shared
    abstained: bool = True
    t_first_detection: float | None = None
    t_root_cause: float | None = None
    t_exact_set: float | None = None
    notes: tuple = ()

    def to_dict(self):
        d = dict(self.__dict__)
        d["affected_sources"] = list(self.affected_sources)
        d["notes"] = list(self.notes)
        return d


def _per_source_severity(tick):
    """Severity per source from its OWN indicators. Shared by C, D and the
    observability rule so all use one definition."""
    out = {}
    for src, inds in SOURCE_INDICATORS.items():
        vals = []
        for n in inds:
            f = tick.get(n)
            if f is None or float(f[1]) <= 1e-9:
                continue
            vals.append(normalize_severity(float(f[0])))
        out[src] = max(vals) if vals else 0.0
    return out


# --- System B: majority voting -----------------------------------------------

def system_b_majority_vote(t, feats, truth_set) -> BaselineVerdict:
    """> 50% of a source's OWN valid indicators reading c < VOTE_C."""
    v = BaselineVerdict("B_MAJORITY_VOTE", root_cause_supported=False)
    held = {}
    first_det = None
    for k in range(len(t)):
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in feats.items()}
        voted = set()
        for src, inds in SOURCE_INDICATORS.items():
            valid = [n for n in inds
                     if n in tick and tick[n][1] > 1e-9]
            if not valid:
                continue
            yes = sum(1 for n in valid if tick[n][0] < VOTE_C)
            if yes / len(valid) > 0.5:          # ties -> not faulty
                voted.add(src)
        for s in voted:
            held[s] = held.get(s, 0) + 1
        for s in list(held):
            if s not in voted:
                held[s] = 0
        settled = tuple(sorted(s for s, n in held.items() if n >= DWELL_TICKS))
        if settled and first_det is None:
            first_det = float(t[k])
        if settled and v.t_exact_set is None and set(settled) == set(truth_set):
            v.t_exact_set = float(t[k])
        if settled:
            v.affected_sources = settled
    v.fault_detected = bool(v.affected_sources)
    v.abstained = not v.fault_detected
    v.t_first_detection = first_det
    v.shared_vs_independent = "ABSTAIN"      # cannot represent a shared cause
    v.notes = ("cannot name a shared resource",)
    return v


# --- System C: independent per-source thresholding ---------------------------

def system_c_per_source(t, feats, truth_set) -> BaselineVerdict:
    v = BaselineVerdict("C_PER_SOURCE_THRESHOLD", root_cause_supported=False)
    held, first_det = {}, None
    for k in range(len(t)):
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in feats.items()}
        sev = _per_source_severity(tick)
        for s, val in sev.items():
            if val >= SOURCE_DEGRADED:
                held[s] = held.get(s, 0) + 1
            elif val < SOURCE_DEGRADED * RECOVER_FACTOR:
                held[s] = 0
        settled = tuple(sorted(s for s, n in held.items() if n >= DWELL_TICKS))
        if settled and first_det is None:
            first_det = float(t[k])
        if settled and v.t_exact_set is None and set(settled) == set(truth_set):
            v.t_exact_set = float(t[k])
        if settled:
            v.affected_sources = settled
    v.fault_detected = bool(v.affected_sources)
    v.abstained = not v.fault_detected
    v.t_first_detection = first_det
    v.shared_vs_independent = "ABSTAIN"
    v.notes = ("affected set only; no shared-cause inference",)
    return v


# --- System D: rule-based shared-resource detector (KEY BASELINE) ------------

def system_d_shared_rule(t, feats, truth_set) -> BaselineVerdict:
    """>= 2 MAIN_POWER_PACK members degraded within D_WINDOW_S, held DWELL_TICKS.

    Deliberately has NO contradiction handling: it never checks whether a
    strongly coupled member stayed healthy, nor whether degradation appeared
    outside the resource. That absence is the thing CSIA must beat.
    """
    v = BaselineVerdict("D_SHARED_RESOURCE_RULE")
    members = [s for s, w in RESOURCE_TOPOLOGY[RESOURCE].items() if w >= 0.9]
    onset, held, first_det = {}, 0, None
    for k in range(len(t)):
        now = float(t[k])
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in feats.items()}
        sev = _per_source_severity(tick)
        deg = []
        for s in members:
            if sev[s] >= SOURCE_DEGRADED:
                onset.setdefault(s, now)
                deg.append(s)
            elif sev[s] < SOURCE_DEGRADED * RECOVER_FACTOR:
                onset.pop(s, None)
        in_window = [s for s in deg if s in onset]
        ok = False
        if len(in_window) >= D_MIN_SOURCES:
            spread = max(onset[s] for s in in_window) - min(onset[s]
                                                            for s in in_window)
            ok = spread <= D_WINDOW_S
        held = held + 1 if ok else 0
        if ok and first_det is None:
            first_det = now
        if held >= DWELL_TICKS:
            v.fault_detected = True
            v.abstained = False
            v.shared_resource = RESOURCE
            v.shared_vs_independent = "SHARED"
            v.affected_sources = tuple(sorted(in_window))
            if v.t_root_cause is None:
                v.t_root_cause = now
            if v.t_exact_set is None and set(v.affected_sources) == set(truth_set):
                v.t_exact_set = now
    v.t_first_detection = first_det
    return v


# --- System A adapter ---------------------------------------------------------

#: legacy cause -> the single source it accuses (from slice 2's CAUSE_TO_SOURCE)
LEGACY_CAUSE_SOURCE = {
    "nominal": None, "unexpected_maneuver": None, "gps_fault": "gps",
    "imu0_bias_drift": "imu0", "imu1_bias_drift": "imu1",
    "mag_interference": "mag", "power_fault": "battery",
    "vibration_anomaly": "vibration",
}


def system_a_legacy(t, posterior, causes, truth_set,
                    conf: float = 0.60) -> BaselineVerdict:
    """Legacy 1-of-K softmax. Structurally cannot emit a set or a resource."""
    v = BaselineVerdict("A_LEGACY_SINGLE_SOURCE", root_cause_supported=False)
    import numpy as np
    for k in range(len(t)):
        row = posterior[k]
        ci = int(np.argmax(row))
        cause, p = causes[ci], float(row[ci])
        if cause == "nominal" or p < conf:
            continue
        src = LEGACY_CAUSE_SOURCE.get(cause)
        if v.t_first_detection is None:
            v.t_first_detection = float(t[k])
        v.fault_detected = True
        v.abstained = False
        v.affected_sources = (src,) if src else ()
        if v.t_exact_set is None and src and {src} == set(truth_set):
            v.t_exact_set = float(t[k])
    v.shared_vs_independent = "ABSTAIN"
    v.notes = ("UNSUPPORTED: 1-of-K model cannot express a multi-source set "
               "or a shared physical resource",)
    return v


# --- observability (frozen, CSIA-independent) --------------------------------

def observability_qualified(t, feats, truth_sources,
                            min_ticks: int = DWELL_TICKS) -> dict:
    """Every ground-truth affected source must reach SOURCE_DEGRADED for
    min_ticks, computed straight from comparator features."""
    counts = {s: 0 for s in truth_sources}
    peak = {s: 0.0 for s in truth_sources}
    for k in range(len(t)):
        tick = {n: (float(c[k]), float(g[k])) for n, (c, g) in feats.items()}
        sev = _per_source_severity(tick)
        for s in truth_sources:
            val = sev.get(s, 0.0)
            peak[s] = max(peak[s], val)
            if val >= SOURCE_DEGRADED:
                counts[s] += 1
    qualified = bool(truth_sources) and all(counts[s] >= min_ticks
                                            for s in truth_sources)
    return {"qualified": qualified,
            "ticks_degraded": counts,
            "peak_severity": {s: round(v, 4) for s, v in peak.items()},
            "observable_source_count": sum(1 for s in truth_sources
                                           if counts[s] >= min_ticks)}
