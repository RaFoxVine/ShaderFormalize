"""Shared typed catalogue for the first real-valued HLSL math operations."""
import math


# Shape describes typed DXC arguments, after its scalar-to-vector splats.
MATH_OPERATIONS = {
    "min": {"arity": 2, "shape": "componentwise", "domain": None},
    "max": {"arity": 2, "shape": "componentwise", "domain": None},
    "abs": {"arity": 1, "shape": "componentwise", "domain": None},
    "clamp": {"arity": 3, "shape": "componentwise", "domain": "ordered_bounds"},
    "divide": {"arity": 2, "shape": "componentwise", "domain": "nonzero_denominator"},
    "sqrt": {"arity": 1, "shape": "componentwise", "domain": "nonnegative"},
    "rcp": {"arity": 1, "shape": "componentwise", "domain": "nonzero"},
    "rsqrt": {"arity": 1, "shape": "componentwise", "domain": "positive"},
    "length": {"arity": 1, "shape": "reduction", "domain": None},
    "distance": {"arity": 2, "shape": "reduction", "domain": None},
    "floor": {"arity": 1, "shape": "componentwise", "domain": None},
    "ceil": {"arity": 1, "shape": "componentwise", "domain": None},
    "frac": {"arity": 1, "shape": "componentwise", "domain": None},
    "step": {"arity": 2, "shape": "componentwise", "domain": None},
    "smoothstep": {"arity": 3, "shape": "componentwise", "domain": "increasing_bounds"},
    "cross": {"arity": 2, "shape": "cross3", "domain": None},
    "reflect": {"arity": 2, "shape": "vector_same", "domain": None},
}
MATH_INTRINSICS = set(MATH_OPERATIONS) - {"divide"}


def valid_math_shape(name, result, arguments):
    spec = MATH_OPERATIONS[name]
    if type(result) is not int or not 1 <= result <= 4 or len(arguments) != spec["arity"]:
        return False
    if any(type(width) is not int or not 1 <= width <= 4 for width in arguments):
        return False
    if spec["shape"] == "reduction":
        return result == 1 and len(set(arguments)) == 1
    if spec["shape"] == "cross3":
        return result == 3 and arguments == [3, 3]
    return arguments == [result] * spec["arity"]


def has_math_domain(name):
    return name in MATH_OPERATIONS and MATH_OPERATIONS[name]["domain"] is not None


def uses_basic_math(root):
    from shader_ast import quoted
    from shader_frontend import callee_reference
    pending = [root]
    while pending:
        node = pending.pop()
        if node.kind == "BinaryOperator" and quoted(node.text)[-1:] == ["/"]:
            return True
        if node.kind == "CallExpr" and callee_reference(node)[1] in MATH_INTRINSICS:
            return True
        pending.extend(node.children)
    return False


def domain_conditions(kind, arguments):
    """Concrete scalar/component obligations; separate from totalized evaluation."""
    if kind == "divide":
        return [value != 0 for value in arguments[1]]
    if kind == "rcp":
        return [value != 0 for value in arguments[0]]
    if kind == "sqrt":
        return [value >= 0 for value in arguments[0]]
    if kind == "rsqrt":
        return [value > 0 for value in arguments[0]]
    if kind == "clamp":
        return [low <= high for low, high in zip(arguments[1], arguments[2])]
    if kind == "smoothstep":
        return [low < high for low, high in zip(arguments[0], arguments[1])]
    return []


def evaluate_math(kind, arguments, active=True):
    if active and not all(domain_conditions(kind, arguments)):
        raise ValueError(f"Executed {kind} is outside the real model domain")
    if kind == "min":
        return [min(a, b) for a, b in zip(*arguments)]
    if kind == "max":
        return [max(a, b) for a, b in zip(*arguments)]
    if kind == "abs":
        return [abs(value) for value in arguments[0]]
    if kind == "clamp":
        return [min(max(value, low), high) for value, low, high in zip(*arguments)]
    if kind == "divide":
        return [a / b if b != 0 else 0 for a, b in zip(*arguments)]
    if kind == "rcp":
        return [1 / value if value != 0 else 0 for value in arguments[0]]
    if kind == "sqrt":
        return [math.sqrt(max(value, 0)) for value in arguments[0]]
    if kind == "rsqrt":
        return [1 / math.sqrt(value) if value > 0 else 0 for value in arguments[0]]
    if kind in ("length", "distance"):
        values = arguments[0] if kind == "length" else [a - b for a, b in zip(*arguments)]
        return [math.sqrt(sum(value * value for value in values))]
    if kind == "floor":
        return [math.floor(value) for value in arguments[0]]
    if kind == "ceil":
        return [math.ceil(value) for value in arguments[0]]
    if kind == "frac":
        return [value - math.floor(value) for value in arguments[0]]
    if kind == "step":
        return [0 if value < edge else 1 for edge, value in zip(*arguments)]
    if kind == "smoothstep":
        result = []
        for low, high, value in zip(*arguments):
            ratio = (value - low) / (high - low) if high != low else 0
            t = min(1, max(0, ratio))
            result.append(t * t * (3 - 2 * t))
        return result
    if kind == "cross":
        a, b = arguments
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    if kind == "reflect":
        incident, normal = arguments
        dot = sum(i * n for i, n in zip(incident, normal))
        return [i - 2 * n * dot for i, n in zip(incident, normal)]
    raise ValueError(f"Unknown math operation: {kind}")


def lean_scalar_math(kind, arguments):
    if kind in ("min", "max", "abs"):
        return f"({kind} {' '.join(arguments)})"
    if kind == "clamp":
        return f"(min (max {arguments[0]} {arguments[1]}) {arguments[2]})"
    if kind == "divide":
        return f"({arguments[0]} / {arguments[1]})"
    if kind == "rcp":
        return f"((1 : ℝ) / {arguments[0]})"
    if kind == "sqrt":
        return f"(Real.sqrt {arguments[0]})"
    if kind == "rsqrt":
        return f"((1 : ℝ) / Real.sqrt {arguments[0]})"
    if kind in ("floor", "ceil"):
        return f"((Int.{kind} {arguments[0]} : ℤ) : ℝ)"
    if kind == "frac":
        return f"({arguments[0]} - ((Int.floor {arguments[0]} : ℤ) : ℝ))"
    if kind == "step":
        return f"(if {arguments[1]} < {arguments[0]} then (0 : ℝ) else 1)"
    if kind == "smoothstep":
        low, high, value = arguments
        t = f"(min 1 (max 0 (({value} - {low}) / ({high} - {low}))))"
        return f"({t} * {t} * (3 - 2 * {t}))"
    raise ValueError(f"Math reduction requires whole-vector emission: {kind}")


def lean_vector_components(kind, arguments):
    """Render whole-vector operations before the emitter selects a component."""
    a, b = arguments
    if kind == "cross":
        return [f"({a[1]} * {b[2]} - {a[2]} * {b[1]})",
                f"({a[2]} * {b[0]} - {a[0]} * {b[2]})",
                f"({a[0]} * {b[1]} - {a[1]} * {b[0]})"]
    if kind == "reflect":
        dot = " + ".join(f"({i} * {n})" for i, n in zip(a, b))
        return [f"({i} - 2 * {n} * ({dot}))" for i, n in zip(a, b)]
    raise ValueError(f"Unknown whole-vector math operation: {kind}")


def math_imports(models):
    """Include helpers as well as entry frames; retain legacy target bytes."""
    pending = list(models)
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if item.get("kind") in ("floor", "ceil", "frac"):
                return "import Mathlib.Data.Real.Archimedean\nimport Mathlib.Algebra.Order.Floor.Ring\n"
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return ""


def lean_domain_condition(kind, arguments):
    if kind == "divide":
        return f"{arguments[1]} ≠ (0 : ℝ)"
    if kind == "rcp":
        return f"{arguments[0]} ≠ (0 : ℝ)"
    if kind == "sqrt":
        return f"(0 : ℝ) ≤ {arguments[0]}"
    if kind == "rsqrt":
        return f"(0 : ℝ) < {arguments[0]}"
    if kind == "clamp":
        return f"{arguments[1]} ≤ {arguments[2]}"
    if kind == "smoothstep":
        return f"{arguments[0]} < {arguments[1]}"
    raise ValueError(f"Math operation has no domain condition: {kind}")
