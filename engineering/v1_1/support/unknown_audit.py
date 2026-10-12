"""Model-adequacy audit for UNKNOWN / UNMODELED. NOT wired into the runtime.

Produces the table in `engineering/v1_1/UNKNOWN_MODEL_ADEQUACY_AUDIT.md`.
The verdict of that audit is UNKNOWN_NOT_IMPLEMENTED; this script is retained
as the evidence behind it, not as a component.

    python engineering/v1_1/support/unknown_audit.py
"""

import sys, numpy as np, collections
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for _p in (ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from csia.scenarios import run_scenario
from csia.diagnosis.bayes import CAUSES
import decompose as D

# Candidate criterion, threshold-free by construction:
#   F_low(k) = { j active : lo_j > hi_j }  ==  { j active : c_j < 0.5 }
# 0.5 is the frozen core's OWN indifference point, where
#   log(1-c+EPS) == log(c+EPS). Not a tuned value.
# h is SET-ADEQUATE iff F_low subset of LOW[h].  UNKNOWN iff no h is.
for name in ("clean","gps_dropout","gps_spoof","imu0_bias_drift","dual_imu_failure"):
    t,f,td,h,diag = run_scenario(name)
    dec = D.decompose(td)
    low = {n:set(CAUSES[n]) for n in dec.names}
    unknown = 0; sizes = collections.Counter()
    for k in range(len(dec.t)):
        act = dec.active_mask(k)
        # lo_j > hi_j  <=>  contribution to a hypothesis with j in LOW exceeds
        # the contribution to one without; recover it from the two columns.
        flow = set()
        for j in np.nonzero(act)[0]:
            fn = dec.features[j]
            in_low  = [i for i,n in enumerate(dec.names) if fn in low[n]]
            not_low = [i for i,n in enumerate(dec.names) if fn not in low[n]]
            if in_low and not_low and dec.contribution[k,j,in_low[0]] > dec.contribution[k,j,not_low[0]]:
                flow.add(fn)
        sizes[len(flow)] += 1
        if not any(flow <= low[n] for n in dec.names):
            unknown += 1
    print(f"{name:<18} ticks={len(dec.t)} UNKNOWN={unknown} "
          f"({100*unknown/len(dec.t):.1f}%)  |F_low| dist={dict(sorted(sizes.items())[:6])}")
