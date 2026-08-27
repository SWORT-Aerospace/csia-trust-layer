"""F3 -- zero is a legitimate reading, not an absence marker.

NON-SCORED FIXTURE. Not CSIA code.
"""


def decode_throttle(msg):
    # 0 percent throttle is a normal, frequently-observed commanded state.
    # Treating it as "not measured" would silently discard every idle sample.
    return {"throttle_pct": float(msg["throttle"])}
