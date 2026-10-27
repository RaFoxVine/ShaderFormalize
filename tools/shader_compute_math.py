"""Explicit real-valued math support for the Compute texture profile.

The whitelist is deliberately independent of the expanding pixel math registry.
"""
from fractions import Fraction

from shader_ast import ModelError
from shader_lean import lean_number


COMPUTE_MATH = frozenset({"min", "max", "saturate", "dot", "divide"})


def integer_type(kind):
    return isinstance(kind, str) and (kind.startswith("uint") or kind.startswith("int"))


def lanes(kind):
    if isinstance(kind, int):
        return kind
    if kind in ("uint", "int", "bool"):
        return 1
    if integer_type(kind) and kind[-1:] in ("2", "3"):
        return int(kind[-1])
    raise ModelError(f"Unknown Compute value type: {kind}")


def scalar_type(kind):
    if isinstance(kind, int):
        return 1
    return "uint" if kind.startswith("uint") else "int" if kind.startswith("int") else kind


def lean_type(kind):
    scalar = "ℝ" if isinstance(kind, int) else "Prop" if kind == "bool" else "BitVec 32"
    return scalar if lanes(kind) == 1 else f"(Fin {lanes(kind)} → {scalar})"


def signed(value):
    return value if value < 2**31 else value - 2**32


def lean_expression(expr, component=None):
    kind, width = expr["kind"], expr["width"]
    size = lanes(width)
    if size > 1 and component is None:
        return f"(fun c => {lean_expression(expr, 'c')})"
    if kind == "local":
        return f"v{expr['index']}" if size == 1 else f"(v{expr['index']} {component})"
    if kind == "uniform":
        return f"uniforms.u{expr['index']}"
    if kind == "load":
        return f"(l{expr['index']} {component})"
    if kind == "dispatch_id":
        values = ["(BitVec.ofNat 32 (thread % extentX))", "(BitVec.ofNat 32 (thread / extentX))", "(0 : BitVec 32)"]
        return values[component] if isinstance(component, int) else f"(![{', '.join(values)}] {component})"
    if kind == "uint_literal":
        return f"(BitVec.ofNat 32 {expr['value']})"
    if kind == "literal":
        return lean_number(Fraction(expr["numerator"], expr["denominator"]))
    if kind == "boolean":
        return "True" if expr["value"] else "False"
    arguments = expr.get("arguments", [])
    if kind == "integer_cast":
        return lean_expression(arguments[0], component)
    if kind == "not":
        return f"(¬ {lean_expression(arguments[0])})"
    if kind in ("and", "or"):
        operator = "∧" if kind == "and" else "∨"
        return f"({lean_expression(arguments[0])} {operator} {lean_expression(arguments[1])})"
    if kind == "compare":
        values = []
        for arg in arguments:
            value = lean_expression(arg)
            if integer_type(arg["width"]):
                value = f"({value}).toInt" if scalar_type(arg["width"]) == "int" else f"({value}).toNat"
            values.append(value)
        operator = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "==": "=", "!=": "≠"}[expr["operator"]]
        return f"({values[0]} {operator} {values[1]})"
    if kind == "choose":
        return f"(if {lean_expression(arguments[0])} then {lean_expression(arguments[1], component)} else {lean_expression(arguments[2], component)})"
    if kind == "splat":
        return lean_expression(arguments[0])
    if kind == "swizzle":
        indices = expr["indices"]
        if size == 1:
            return lean_expression(arguments[0], indices[0])
        values = [lean_expression(arguments[0], index) for index in indices]
        return values[component] if isinstance(component, int) else f"(![{', '.join(values)}] {component})"
    if kind == "construct":
        values = []
        for arg in arguments:
            values.extend(lean_expression(arg, index) for index in range(lanes(arg["width"])))
        return values[component] if isinstance(component, int) else f"(![{', '.join(values)}] {component})"
    if kind in ("negate", "integer_negate"):
        return f"(-{lean_expression(arguments[0], component)})"
    if kind == "dot":
        terms = [f"({lean_expression(arguments[0], i)} * {lean_expression(arguments[1], i)})" for i in range(lanes(arguments[0]["width"]))]
        return "(" + " + ".join(terms) + ")"
    values = [lean_expression(arg, component) for arg in arguments]
    operators = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/", "uint_add": "+", "uint_sub": "-", "uint_mul": "*", "uint_and": "&&&", "uint_or": "|||", "uint_xor": "^^^"}
    if kind in operators:
        return f"({values[0]} {operators[kind]} {values[1]})"
    if kind in ("min", "max"):
        return f"({kind} {values[0]} {values[1]})"
    if kind == "saturate":
        return f"(min (max {values[0]} 0) 1)"
    raise ModelError(f"Unsupported Compute texture IR expression: {kind}")


def evaluate_expression(expr, values, loads, uniforms, thread, extent_x):
    kind, width = expr["kind"], expr["width"]
    if kind == "local":
        return values[expr["index"]]
    if kind == "load":
        return loads[expr["index"]]
    if kind == "uniform":
        return uniforms[expr["name"]]
    if kind == "dispatch_id":
        return (thread % extent_x, thread // extent_x, 0)
    if kind == "uint_literal":
        return expr["value"]
    if kind == "literal":
        return Fraction(expr["numerator"], expr["denominator"])
    if kind == "boolean":
        return expr["value"]
    args = [evaluate_expression(arg, values, loads, uniforms, thread, extent_x) for arg in expr.get("arguments", [])]
    if kind == "integer_cast":
        return args[0]
    if kind == "not":
        return not args[0]
    if kind in ("and", "or"):
        return (args[0] and args[1]) if kind == "and" else (args[0] or args[1])
    if kind == "compare":
        if expr["arguments"][0]["width"] == "int":
            args = [signed(value) for value in args]
        left, right = args
        operator = expr["operator"]
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
        return (left == right) if operator == "==" else (left != right)
    if kind == "choose":
        return args[1] if args[0] else args[2]
    if kind == "splat":
        return tuple(args[0] for _ in range(lanes(width)))
    if kind == "swizzle":
        result = tuple(args[0][index] for index in expr["indices"])
        return result[0] if lanes(width) == 1 else result
    if kind == "construct":
        result = []
        for arg in args:
            result.extend(arg if isinstance(arg, tuple) else [arg])
        return tuple(result)
    if kind == "dot":
        return sum(a * b for a, b in zip(*args))
    components = [arg if isinstance(arg, tuple) else (arg,) for arg in args]
    result = []
    for lane in range(lanes(width)):
        a = components[0][lane]
        b = components[1][lane] if len(components) > 1 else None
        if kind in ("negate", "integer_negate"):
            value = -a
        elif kind in ("add", "uint_add"):
            value = a + b
        elif kind in ("subtract", "uint_sub"):
            value = a - b
        elif kind in ("multiply", "uint_mul"):
            value = a * b
        elif kind == "divide":
            value = a / b if b else Fraction(0)
        elif kind == "min":
            value = min(a, b)
        elif kind == "max":
            value = max(a, b)
        elif kind == "saturate":
            value = min(max(a, 0), 1)
        elif kind == "uint_and":
            value = a & b
        elif kind == "uint_or":
            value = a | b
        elif kind == "uint_xor":
            value = a ^ b
        else:
            raise ModelError(f"Unknown finite Compute texture operation: {kind}")
        result.append(value % 2**32 if integer_type(width) else value)
    return result[0] if lanes(width) == 1 else tuple(result)
