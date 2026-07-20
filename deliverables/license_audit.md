# CSIA — Dependency License Audit

Runtime + optional-extra dependencies (measured from the installed
environment via `pip-licenses`). Reviewed for copyleft encumbrance on
proprietary distribution.

| Package | Version | License | Extra | Encumbrance |
|---|---|---|---|---|
| numpy | 2.5.1 | BSD-3-Clause (+ 0BSD/MIT/Zlib/CC0) | core | None (permissive) |
| scipy | 1.18.0 | BSD-3-Clause | core | None |
| networkx | 3.6.1 | BSD-3-Clause | core | None |
| matplotlib | 3.11.0 | PSF (BSD-compatible) | core | None |
| pyulog | 1.2.3 | BSD-3-Clause | `[logs]` | None |
| pymavlink | 2.4.49 | **LGPL-3.0** | `[mavlink]` | **FLAG — see below** |
| pytest | 9.1.1 | MIT | `[dev]` | None (dev-only) |

## Findings

**No GPL / AGPL / SSPL** in the dependency set — nothing forces disclosure
of proprietary source.

**pymavlink is LGPL-3.0 — flagged for review.** LGPL permits proprietary use
when the library is **dynamically linked** and the end user can replace it.
- In this project pymavlink is a pure-Python package imported at runtime
  (dynamic linking by construction) and is an **optional** extra (`[mavlink]`);
  the core trust layer and the entire `interceptor_seeker` profile do **not**
  depend on it.
- Recommended posture: keep pymavlink an optional, dynamically-imported,
  unmodified dependency; do not vendor or statically bundle it; if the
  binary is ever frozen (PyInstaller etc.), preserve the LGPL relink path or
  ship it as a separable shared component. If any pymavlink source is
  modified, those modifications must be offered under LGPL.
- For a fully permissive posture, pymavlink can be replaced by a MAVLink
  parser under a permissive license, or the MAVLink dialect can be code-
  generated and the generated code (MIT-licensed generator output) used
  directly.

**The `interceptor_seeker` deliverable has zero copyleft exposure** — it uses
only numpy/scipy (permissive).
