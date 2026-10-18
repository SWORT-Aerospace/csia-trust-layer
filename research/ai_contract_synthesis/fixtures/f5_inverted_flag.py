"""F5 -- two decoders for one wire format, one of which inverts the flag.

NON-SCORED FIXTURE. Not CSIA code.
"""


def decode_a(msg):
    # here `fault` is asserted when the unit is FAULTED
    return {"usable": not msg["fault"]}


def decode_b(msg):
    # and here the same wire bit is read as a HEALTH bit
    return {"usable": bool(msg["fault"])}
