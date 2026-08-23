"""Test the proposed construction:  e_t = k * p_t**(k-1),  E_t = prod_s e_s."""
import numpy as np

def calibrator(p, k):  return k * np.power(p, k - 1.0)

# --- (1) is kappa*p^(kappa-1) an admissible p-to-e calibrator? integral must be <=1
for k in (0.2, 0.5, 0.8):
    p = np.linspace(1e-9, 1, 4_000_000)
    print(f"  kappa={k}: integral_0^1 f(p)dp = {np.trapezoid(calibrator(p,k), p):.6f}  (must be <= 1)")

rng = np.random.default_rng(0)
K, T, N = 0.5, 2000, 4000

# --- (2) IID uniform p-values (conditionally valid): does Ville's bound hold?
E = np.ones(N); crossed_iid = np.zeros(N, bool)
for t in range(T):
    E *= calibrator(rng.random(N), K)
    crossed_iid |= (E >= 20.0)          # alpha = 1/20 = 0.05
print(f"\n  IID null      : P(ever E>=20) = {crossed_iid.mean():.4f}   bound 0.0500")

# --- (3) AUTOCORRELATED p-values, marginally uniform but NOT conditionally so.
# CSIA's residuals are EW-smoothed (SMOOTH_ALPHA=0.06 ~ 15-tick memory), so
# adjacent p-values are strongly dependent. Marginal uniformity is preserved
# by construction via the normal CDF.
from scipy.stats import norm
rho = 0.94                               # ~ EW(0.06) lag-1 autocorrelation
E = np.ones(N); crossed_ac = np.zeros(N, bool); x = rng.standard_normal(N)
for t in range(T):
    x = rho * x + np.sqrt(1 - rho**2) * rng.standard_normal(N)
    p = norm.cdf(x)                      # marginally Uniform(0,1) exactly
    E *= calibrator(p, K)
    crossed_ac |= (E >= 20.0)
print(f"  autocorrelated: P(ever E>=20) = {crossed_ac.mean():.4f}   bound 0.0500")

# --- (4) convex combination across dependent residuals (Vovk-Wang)
e1 = calibrator(rng.random(200000), K)
e2 = e1.copy()                           # maximally dependent
print(f"\n  mean of e            = {e1.mean():.4f} (<=1 required)")
print(f"  mean of (e1+e2)/2    = {((e1+e2)/2).mean():.4f} (<=1: valid under ANY dependence)")
print(f"  mean of e1*e2        = {(e1*e2).mean():.4f} (product across dependent residuals)")
