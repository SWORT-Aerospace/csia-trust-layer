"""Reference implementations for the DEA conformance runner.

`good_minimal` conforms and is NOT CSIA -- it shares no code with this
repository and is not even in the same domain, which is how the profile is
tested for being a standard rather than a description of its author's system.

The `bad_*` modules are the load-bearing half. A conformance runner that
passes everything is indistinguishable from one that tests nothing, and these
eight are how that is measured: each violates a named requirement, and each
must be REJECTED. `tests/test_dea_conformance.py` additionally asserts that
every requirement DEA-1..DEA-10 is violated by at least one of them, so a
requirement nobody can fail cannot quietly enter the profile.
"""
