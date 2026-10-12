"""F6 -- a documented sentinel on a field the implementation never receives.

NON-SCORED FIXTURE. Not CSIA code.
"""


def decode_wind(msg):
    # The protocol defines wind_speed_accuracy with UINT16_MAX meaning
    # unknown. This decoder never reads that field -- the message it consumes
    # is a truncated variant that stops before it -- so no trace can ever
    # exercise the sentinel and no conformance question about it is
    # answerable here.
    return {"wind_speed": msg["wind_speed"] / 100.0}
