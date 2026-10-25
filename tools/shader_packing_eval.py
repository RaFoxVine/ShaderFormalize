"""Independent finite uint oracle; float bit patterns are never evaluated."""
import math


def packing_scalar(kind, values, active):
    a = values[0]
    if kind in ("carrier", "recover", "uint_to_real"):
        return a
    if kind == "real_to_uint":
        if not 0 <= a < 2**32:
            if active:
                raise ValueError("Executed real-to-uint conversion is outside its domain")
            return 0
        return math.trunc(a)
    if kind in ("uint_shl", "uint_shr"):
        b = values[1]
        if not 0 <= b < 32:
            if active:
                raise ValueError("Executed uint shift count is outside its domain")
            return 0
        return ((a << b) if kind == "uint_shl" else (a >> b)) & 0xffffffff
    if kind == "uint_not":
        return (~a) & 0xffffffff
    if kind == "uint_neg":
        return (-a) & 0xffffffff
    b = values[1]
    operators = {"uint_add": lambda: a + b, "uint_sub": lambda: a - b,
                 "uint_mul": lambda: a * b, "uint_and": lambda: a & b,
                 "uint_or": lambda: a | b, "uint_xor": lambda: a ^ b}
    return operators[kind]() & 0xffffffff
