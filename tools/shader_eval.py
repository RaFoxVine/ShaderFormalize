"""Finite numeric oracle for regression tests; never used as a formal proof."""
import math


def evaluate(expr, inputs, locals_):
    kind = expr["kind"]
    if kind == "parameter":
        return list(inputs[expr["index"]])
    if kind == "local":
        return list(locals_[expr["index"]])
    if kind == "literal":
        return [expr["numerator"] / expr["denominator"]]
    args = [evaluate(child, inputs, locals_) for child in expr["arguments"]]
    if kind == "construct":
        return [value for arg in args for value in arg]
    if kind == "swizzle":
        return [args[0][i] for i in expr["indices"]]
    if kind == "splat":
        return args[0] * expr["width"]
    if kind == "normalize":
        length = math.sqrt(sum(x * x for x in args[0]))
        if length == 0:
            raise ValueError("normalize(0) has no specified HLSL result")
        return [x / length for x in args[0]]
    if kind == "dot":
        return [sum(x * y for x, y in zip(args[0], args[1]))]
    if kind == "negate":
        return [-x for x in args[0]]
    if kind == "saturate":
        return [min(1, max(0, x)) for x in args[0]]
    if kind == "lerp":
        return [a + (b - a) * t for a, b, t in zip(*args)]
    if kind == "add":
        return [x + y for x, y in zip(*args)]
    if kind == "subtract":
        return [x - y for x, y in zip(*args)]
    if kind == "multiply":
        return [x * y for x, y in zip(*args)]
    raise ValueError(f"Unknown numeric IR operation: {kind}")


def evaluate_model(model, inputs):
    if model["schema"] in (4, 5):
        from shader_control_eval import evaluate_control, no_operations
        lifted = [[value] if item["storage"] == "parameter" else value for item, value in zip(model["interface"], inputs)]
        return evaluate_control(model, lifted, 1, no_operations)[0]
    locals_ = []
    for binding in model["bindings"]:
        locals_.append(evaluate(binding["expression"], inputs, locals_))
    return evaluate(model["expression"], inputs, locals_)
