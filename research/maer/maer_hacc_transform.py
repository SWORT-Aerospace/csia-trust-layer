"""The frozen h_acc receiver-health transform and its validity predicate.

ONE definition, imported by the audits, the tests and (later) the research
sidecar, so those three cannot drift apart.

    u_t   = max(0, log(h_acc_t / h0)) / kappa_h        normalized degradation units
    lam_t = EWMA_0.15( u_t^2 )
    c_t   = consistency(lam_t) = exp(-0.5 max(0, lam_t - 1))

`kappa_h` IS NOT A STANDARD DEVIATION and must not be described as one. It is a
declared LOG SCALE: one doubling of reported horizontal uncertainty above
nominal equals one normalized degradation unit. Calling it sigma implied an
empirical spread that was never estimated, and nothing in the data supports
such an estimate -- clean SITL h_acc is a constant.

Neither constant may be influenced by any fault outcome:

    h0      = SIM_GPS1_ACC * 1000 = 300 mm, the DECLARED nominal receiver
              accuracy of the configuration under test
    kappa_h = log 2, the declared doubling scale

VALIDITY PREDICATE. `h_acc = 0` is not excellent accuracy. Feeding it through
the transform gives `max(0, log 0) = 0`, hence lam 0 and consistency 1.0: a
receiver reporting nothing would score as perfectly healthy.

Measured over the committed jamming captures, zero occurs 900 times in TWO
distinct populations:

    870  fix_type 0, sats 0,  eph 65535, v_acc 0   pre-lock
     30  fix_type 1, sats 3,  eph 121,   v_acc 0   early acquisition

The second is why the `h_acc <= 0` clause is load-bearing rather than
redundant: its eph and satellite count are both valid, so no other clause
rejects it. The predicate makes the relation contribute NOTHING for these
samples rather than false health.

  python research/maer/maer_hacc_transform.py    # self-check
"""

from __future__ import annotations

import math

# ---- frozen constants ----------------------------------------------------
H0_MM = 300.0                     # SIM_GPS1_ACC (0.3 m) x 1000
KAPPA_H = math.log(2.0)           # one doubling above nominal = 1 unit
EW_ALPHA = 0.15                   # the smoother _lam_upd already uses

# MAVLink unknown markers for the fields the predicate consults.
H_ACC_UNKNOWN = 0xFFFFFFFF        # UINT32_MAX
EPH_UNKNOWN = 0xFFFF              # UINT16_MAX


def hacc_valid(msg) -> bool:
    """Is this GPS_RAW_INT sample a usable statement about receiver accuracy?

    Rejects, in order: absent field; the UINT32 unknown marker; zero, which is
    the pre-lock artifact rather than an accuracy; a message whose own eph is
    the UINT16 unknown marker; and a receiver reporting zero satellites, which
    cannot be making an accuracy statement about anything.
    """
    h = msg.get("h_acc")
    if h is None or h == H_ACC_UNKNOWN or h <= 0:
        return False
    if msg.get("eph") == EPH_UNKNOWN:
        return False
    sats = msg.get("satellites_visible")
    if sats is not None and sats <= 0:
        return False
    return True


def degradation_units(h_acc_mm) -> float:
    """u = max(0, log(h_acc/h0)) / kappa_h. Zero at or below nominal."""
    return max(0.0, math.log(float(h_acc_mm) / H0_MM)) / KAPPA_H


def consistency(lam) -> float:
    """The frozen core's lam -> (0,1] map (csia/trust_engine/engine.py)."""
    return math.exp(-0.5 * max(0.0, float(lam) - 1.0))


def lam_stream(messages):
    """Yield (msg, lam, consistency, valid) with the EWMA held across samples.

    Invalid samples do NOT update the smoother and yield lam None: an
    unusable reading must contribute nothing, not a value.
    """
    ew = None
    for m in messages:
        if not hacc_valid(m):
            yield m, None, None, False
            continue
        raw = degradation_units(m["h_acc"]) ** 2
        ew = raw if ew is None else ew + EW_ALPHA * (raw - ew)
        yield m, ew, consistency(ew), True


# ---- solved thresholds, not asserted -------------------------------------
def lam_at_consistency(c: float) -> float:
    """Invert consistency: lam = 1 - 2 ln c, for c <= 1."""
    return 1.0 - 2.0 * math.log(c)


def ratio_at_consistency(c: float) -> float:
    """h_acc / h0 giving that steady-state consistency: 2 ** sqrt(lam)."""
    return 2.0 ** math.sqrt(lam_at_consistency(c))


if __name__ == "__main__":
    for c in (0.5, 0.1, 0.01):
        lam = lam_at_consistency(c)
        print(f"  consistency {c:<5} -> lam {lam:.8f} -> h_acc/h0 "
              f"{ratio_at_consistency(c):.4f}  "
              f"({H0_MM * ratio_at_consistency(c):.0f} mm)")
