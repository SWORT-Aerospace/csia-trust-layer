"""ctypes bindings for the native CSIA core (csia_core.c).

Build once per machine:  csia/native/build.sh   (or: cc -O2 -shared ...)
If the shared library is absent, callers fall back to the pure-Python
implementation — identical algorithm, pinned by tests.
"""

import ctypes
import os

import numpy as np

_dir = os.path.dirname(__file__)
_lib = None
for name in ("libcsia_core.dylib", "libcsia_core.so"):
    p = os.path.join(_dir, name)
    if os.path.exists(p):
        _lib = ctypes.CDLL(p)
        break

available = _lib is not None

if available:
    _d = ctypes.POINTER(ctypes.c_double)
    _i = ctypes.POINTER(ctypes.c_int)
    _u = ctypes.POINTER(ctypes.c_ubyte)
    _lib.csia_trust_step.restype = ctypes.c_int
    _lib.csia_diag_step.restype = ctypes.c_int


def _dp(a):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


def _ip(a):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_int))


def _up(a):
    return a.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))


class NativeTrustState:
    """Preallocated buffers + state for csia_trust_step."""

    def __init__(self, n, m, ea, eb, cfg):
        self.n, self.m = n, m
        self.ea = np.asarray(ea, dtype=np.int32)
        self.eb = np.asarray(eb, dtype=np.int32)
        self.cfg = cfg
        self.alpha = np.full(n, cfg.alpha0)
        self.beta = np.full(n, cfg.beta0)
        self.trust = np.full(n, cfg.alpha0 / (cfg.alpha0 + cfg.beta0))
        z = lambda k: np.zeros(k)
        self.elam, self.egate = z(m), z(m)
        self.plam, self.pgate = z(n), z(n)
        self.phas = np.zeros(n, dtype=np.uint8)
        self.hist, self.vr = z(n), z(n)
        self.hist_has = np.zeros(n, dtype=np.uint8)
        self.vr_has = np.zeros(n, dtype=np.uint8)
        self.fresh = np.zeros(n, dtype=np.uint8)
        self.out_trust, self.out_ev = z(n), z(n)
        self.out_comps = z(4 * n)

    def step(self):
        c = self.cfg
        rc = _lib.csia_trust_step(
            self.n, self.m, _ip(self.ea), _ip(self.eb),
            _dp(self.elam), _dp(self.egate),
            _dp(self.plam), _dp(self.pgate), _up(self.phas),
            _dp(self.hist), _up(self.hist_has),
            _dp(self.vr), _up(self.vr_has), _up(self.fresh),
            ctypes.c_double(c.w_nbr), ctypes.c_double(c.w_phys),
            ctypes.c_double(c.w_temp), ctypes.c_double(c.w_stat),
            ctypes.c_double(c.rho_max), ctypes.c_double(c.rho_min),
            _dp(self.alpha), _dp(self.beta), _dp(self.trust),
            _dp(self.out_trust), _dp(self.out_ev), _dp(self.out_comps))
        if rc != 0:
            raise ValueError(
                f"csia_trust_step: n={self.n} exceeds CSIA_MAX_NODES (64)")


class NativeDiagState:
    def __init__(self, nf, nc, low, log_prior, alpha, mult, eps):
        self.nf, self.nc = nf, nc
        self.low = np.ascontiguousarray(low, dtype=np.uint8)
        self.log_prior = np.asarray(log_prior, dtype=float)
        self.alpha, self.mult, self.eps = alpha, mult, eps
        self.smoothed = np.zeros(nc)
        self.initialized = ctypes.c_int(0)
        self.c = np.zeros(nf)
        self.gate = np.zeros(nf)
        self.out = np.zeros(nc)

    def step(self):
        rc = _lib.csia_diag_step(
            self.nf, self.nc, _dp(self.c), _dp(self.gate), _up(self.low),
            _dp(self.log_prior), ctypes.c_double(self.alpha),
            ctypes.c_double(self.mult), ctypes.c_double(self.eps),
            _dp(self.smoothed), ctypes.byref(self.initialized),
            _dp(self.out))
        if rc != 0:
            raise ValueError(
                f"csia_diag_step: nc={self.nc} exceeds CSIA_MAX_CAUSES (32)")
        return self.out
