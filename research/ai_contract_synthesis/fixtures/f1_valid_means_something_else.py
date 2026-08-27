"""F1 -- a field named `valid` that does not mean the measurement is valid.

NON-SCORED FIXTURE. Not CSIA code.
"""


def decode_range_finder(msg):
    # `valid` here is the SIGNAL QUALITY GATE of the rangefinder's own
    # returned echo, not a statement about whether the distance may be used.
    # A reading with valid=0 is still the best available distance and the
    # vehicle uses it; the flag drives an averaging weight, not admissibility.
    weight = 1.0 if msg["valid"] else 0.25
    return {"distance_m": msg["distance_cm"] / 100.0, "weight": weight}
