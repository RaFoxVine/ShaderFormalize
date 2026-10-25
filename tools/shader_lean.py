"""Explicit input domains and typed Lean emission for the immutable shader model."""
from fractions import Fraction
import json
import re

from shader_ast import ModelError, exact_number


def load_constraints(data, interface):
    if len(interface) != 3 or [item["width"] for item in interface] != [4, 4, 1]:
        raise ModelError("Schema 1 requires the legacy two-vector/scalar interface", "INVALID_INPUT")
    if not isinstance(data, dict) or set(data) != {"schema", "ranges"} or type(data["schema"]) is not int or data["schema"] != 1:
        raise ModelError("Unknown constraint schema or fields", "INVALID_INPUT")
    if not isinstance(data["ranges"], dict) or set(data["ranges"]) != {interface[2]["name"]}:
        raise ModelError("Specify exactly the scalar input's interval", "INVALID_INPUT")
    return bounds(data["ranges"][interface[2]["name"]])


def bounds(value):
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        raise ModelError("Expected min and max", "INVALID_INPUT")
    lower, upper = exact_number(value["min"]), exact_number(value["max"])
    if lower > upper:
        raise ModelError("Contradictory input interval", "INVALID_INPUT")
    return lower, upper


def selector(text, interface):
    if not isinstance(text, str):
        raise ModelError("Nonzero vector selectors must be strings", "INVALID_INPUT")
    inputs = {item["name"]: item for item in interface}
    if text in inputs:
        name, mask = text, None
    else:
        name, separator, mask = text.rpartition(".")
        if not separator or re.fullmatch(r"[xyzw]{1,4}|[rgba]{1,4}", mask) is None:
            raise ModelError("Unknown nonzero vector selector", "INVALID_INPUT")
    if name not in inputs:
        raise ModelError("Unknown nonzero vector selector", "INVALID_INPUT")
    item = inputs[name]
    result = {"kind": "parameter", "width": item["width"], "index": item["index"]}
    if mask:
        alphabet = "xyzw" if mask[0] in "xyzw" else "rgba"
        indices = [alphabet.index(c) for c in mask]
        if item["width"] == 1 or any(i >= item["width"] for i in indices):
            raise ModelError("Nonzero selector is out of bounds", "INVALID_INPUT")
        result = {"kind": "swizzle", "width": len(indices), "indices": indices, "arguments": [result]}
    if result["width"] < 2:
        raise ModelError("Expected a vector, not a scalar nonzero constraint", "INVALID_INPUT")
    return result


def resolve_alias(expr, bindings):
    selection = None
    visited = set()
    while expr["kind"] in ("local", "swizzle"):
        if expr["kind"] == "local":
            index = expr["index"]
            if index in visited:
                raise ModelError("Cyclic local alias")
            visited.add(index)
            expr = bindings[index]["expression"]
        else:
            indices = expr["indices"]
            selection = list(indices) if selection is None else [indices[i] for i in selection]
            expr = expr["arguments"][0]
    if selection is not None:
        return {"kind": "swizzle", "width": len(selection), "indices": selection, "arguments": [expr]}
    return expr


def normalization_inputs(expr, bindings):
    result = []
    if expr["kind"] == "normalize":
        arg = resolve_alias(expr["arguments"][0], bindings)
        if arg["kind"] != "parameter" and not (arg["kind"] == "swizzle" and arg["arguments"][0]["kind"] == "parameter"):
            raise ModelError("normalize currently requires an input vector/swizzle or its local alias")
        result.append(arg)
    for child in expr.get("arguments", []):
        result.extend(normalization_inputs(child, bindings))
    return result


def expression_key(expr):
    return json.dumps(expr, sort_keys=True)


def constraint_spec(data, original, optimized):
    interface = original["interface"]
    if isinstance(data, dict) and type(data.get("schema")) is int and data["schema"] == 1:
        lower, upper = load_constraints(data, interface)
        spec = {"ranges": [(2, lower, upper)], "nonzero": []}
    else:
        if not isinstance(data, dict) or set(data) != {"schema", "ranges", "nonzero_vectors"} or type(data["schema"]) is not int or data["schema"] != 2:
            raise ModelError("Unknown constraint schema or fields", "INVALID_INPUT")
        inputs = {item["name"]: item for item in interface}
        if not isinstance(data["ranges"], dict) or any(name not in inputs for name in data["ranges"]):
            raise ModelError("Unknown input range", "INVALID_INPUT")
        ranges = []
        for name, interval in data["ranges"].items():
            ranges.append((inputs[name]["index"], *bounds(interval)))
        if not isinstance(data["nonzero_vectors"], list):
            raise ModelError("nonzero_vectors must be a list", "INVALID_INPUT")
        nonzero = [selector(text, interface) for text in data["nonzero_vectors"]]
        if len({expression_key(expr) for expr in nonzero}) != len(nonzero):
            raise ModelError("Repeated nonzero vector constraint", "INVALID_INPUT")
        spec = {"ranges": sorted(ranges), "nonzero": nonzero}
    covered = {expression_key(expr) for expr in spec["nonzero"]}
    for model in (original, optimized):
        if max(original["schema"], optimized["schema"]) >= 4:
            # New guarded models prove definedness as part of the conclusion.
            continue
        # Visit every executed binding, even if overwritten or unused in return.
        values = [binding["expression"] for binding in model["bindings"]] + [model["expression"]] + model.get("effects", [])
        for value in values:
            for arg in normalization_inputs(value, model["bindings"]):
                if expression_key(arg) not in covered:
                    raise ModelError("normalize requires an explicit matching nonzero_vectors premise", "INVALID_INPUT")
    zero_inputs = {index for index, lo, hi in spec["ranges"] if lo == 0 and hi == 0}
    for expr in spec["nonzero"]:
        base = expr if expr["kind"] == "parameter" else expr["arguments"][0]
        if base["index"] in zero_inputs:
            raise ModelError("Nonzero premise contradicts an all-zero input interval", "INVALID_INPUT")
    return spec


def lean_number(value):
    if value.denominator == 1:
        return f"({value.numerator} : ℝ)"
    return f"({value.numerator} / {value.denominator} : ℝ)"


def fin_index(index):
    return f"⟨{index}, by decide⟩" if isinstance(index, int) else index


def vector_literal(components):
    result = components[-1]
    for index in range(len(components) - 2, -1, -1):
        result = f"if i.val = {index} then {components[index]} else {result}"
    return f"(fun (i : Fin {len(components)}) => {result})"


def lean_components(expr):
    if expr["kind"] == "construct":
        result = []
        for child in expr["arguments"]:
            result.extend(lean_components(child))
        return result
    if expr["kind"] == "swizzle":
        source = lean_components(expr["arguments"][0])
        return [source[i] for i in expr["indices"]]
    if expr["width"] == 1:
        return [lean_element(expr, None)]
    return [lean_element(expr, i) for i in range(expr["width"])]


def lean_value(expr):
    if expr["width"] == 1:
        return lean_element(expr, None)
    if expr["kind"] in ("parameter", "local"):
        return ("p" if expr["kind"] == "parameter" else "l") + str(expr["index"])
    if expr["kind"] == "normalize":
        return f"(ShaderFormalize.Model.normalize {lean_value(expr['arguments'][0])})"
    if expr["kind"] in ("construct", "swizzle"):
        return vector_literal(lean_components(expr))
    return f"(fun i => {lean_element(expr, 'i')})"


def lean_element(expr, index):
    kind, size = expr["kind"], expr["width"]
    if kind in ("parameter", "local"):
        name = ("p" if kind == "parameter" else "l") + str(expr["index"])
        return name if size == 1 else f"({name} {fin_index(index)})"
    if kind == "literal":
        return lean_number(Fraction(expr["numerator"], expr["denominator"]))
    if kind in ("construct", "swizzle"):
        components = lean_components(expr)
        if size == 1:
            return components[0]
        if isinstance(index, int):
            return components[index]
        return f"({vector_literal(components)} {index})"
    arguments = expr["arguments"]
    if kind == "normalize":
        return f"({lean_value(expr)} {fin_index(index)})"
    if kind == "dot":
        return f"(ShaderFormalize.Model.dot {lean_value(arguments[0])} {lean_value(arguments[1])})"
    if kind == "splat":
        return lean_element(arguments[0], None)
    args = [lean_element(child, index if child["width"] > 1 else None) for child in arguments]
    if kind == "negate":
        return f"(-{args[0]})"
    if kind in ("add", "subtract", "multiply"):
        symbol = {"add": "+", "subtract": "-", "multiply": "*"}[kind]
        return f"({args[0]} {symbol} {args[1]})"
    if kind in ("lerp", "saturate"):
        return f"(ShaderFormalize.Model.{kind} {' '.join(args)})"
    raise ModelError(f"Unknown IR operation: {kind}")


def lean_type(size):
    if size == "bool":
        return "Prop"
    if size == 1:
        return "ℝ"
    if size == 4:
        return "Vec4"
    return f"Vec {size}"


def model_definition(name, model, parameters):
    lines = [f"def {name} {parameters} : Vec4 :="]
    for binding in model["bindings"]:
        lines.append(f"  let l{binding['index']} : {lean_type(binding['width'])} := {lean_value(binding['expression'])}")
    lines.append(f"  {lean_value(model['expression'])}")
    return "\n".join(lines)


def generate_lean(original, optimized, lower=None, upper=None, spec=None):
    if any(model["schema"] not in (2, 3, 4, 5, 6) for model in (original, optimized)):
        raise ModelError("Unknown model schema", "INVALID_INPUT")
    if spec is None:
        spec = {"ranges": [(2, lower, upper)], "nonzero": []}
    if original["schema"] == 6 or optimized["schema"] == 6:
        from shader_shared_lean import generate_shared
        return generate_shared(original, optimized, spec)
    if original["schema"] == 5 or optimized["schema"] == 5:
        from shader_packing_lean import PackingEmitter
        from shader_control_lean import generate_control
        return generate_control(original, optimized, spec, PackingEmitter, "import ShaderFormalize.Packing\n")
    if original["schema"] == 4 or optimized["schema"] == 4:
        from shader_control_lean import generate_control
        return generate_control(original, optimized, spec)
    if original["schema"] == 3 or optimized["schema"] == 3:
        from shader_fragment import generate_fragment
        return generate_fragment(original, optimized, spec)
    interface = original["interface"]
    parameters = " ".join(f"(p{x['index']} : {lean_type(x['width'])})" for x in interface)
    names = " ".join(f"p{x['index']}" for x in interface)
    premises = []
    for index, lo, hi in spec["ranges"]:
        size = interface[index]["width"]
        if size == 1:
            premises.extend([f"{lean_number(lo)} ≤ p{index}", f"p{index} ≤ {lean_number(hi)}"])
        else:
            premises.append(f"(∀ i : Fin {size}, {lean_number(lo)} ≤ p{index} i ∧ p{index} i ≤ {lean_number(hi)})")
    for expr in spec["nonzero"]:
        value = lean_value(expr)
        premises.append(f"(0 : ℝ) < ShaderFormalize.Model.dot {value} {value}")
    goal = f"original {names} = optimized {names}"
    implication = " →\n  ".join(premises + [goal])
    return "import ShaderFormalize.Model\n\nnoncomputable section\nnamespace ShaderFormalize.Generated\nopen ShaderFormalize.Model\n\n" + model_definition("original", original, parameters) + "\n\n" + model_definition("optimized", optimized, parameters) + f"\n\ndef expected : Prop := ∀ {parameters},\n  {implication}\n\nend ShaderFormalize.Generated\n"
