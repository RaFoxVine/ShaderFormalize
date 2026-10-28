"""Emit ordered FloatLib binary32 models from the independent IEEE IR."""
import re

from shader_ast import ModelError


PROFILE = "binary32-rne-preserve-subnormals-separate-ops-v1"


def empty_constraints(data):
    if (not isinstance(data, dict) or set(data) != {"schema", "ranges", "nonzero_vectors"} or
            type(data["schema"]) is not int or data["schema"] != 2 or
            not isinstance(data["ranges"], dict) or data["ranges"] or
            not isinstance(data["nonzero_vectors"], list) or data["nonzero_vectors"]):
        raise ModelError("IEEE accepts only empty schema 2 ranges and nonzero_vectors", "INVALID_INPUT")
    return {"schema": 2, "ranges": {}, "nonzero_vectors": []}


def scientific_arguments(expr):
    token = expr.get("token")
    if not isinstance(token, str) or re.fullmatch(
            r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token) is None:
        raise ModelError("IEEE literal is missing its exact source spelling")
    mantissa_text, separator, exponent_text = token.lower().partition("e")
    exponent = int(exponent_text) if separator else 0
    whole, point, fraction = mantissa_text.partition(".")
    digits = (whole + fraction).lstrip("0") or "0"
    decimal_exponent = exponent - len(fraction)
    if len(digits) > 1000 or abs(decimal_exponent) > 1000:
        raise ModelError("Numeric literal is too large", "INVALID_INPUT")
    return digits, "true" if decimal_exponent < 0 else "false", abs(decimal_exponent)


def lean_literal(expr):
    mantissa, negative_exponent, exponent = scientific_arguments(expr)
    return f"(OfScientific.ofScientific {mantissa} {negative_exponent} {exponent} : ShaderIeee.Binary32)"


def lean_type(kind):
    if kind == "bool":
        return "Bool"
    if kind == "uint":
        return "UInt32"
    if kind == 1:
        return "ShaderIeee.Binary32"
    if isinstance(kind, int) and 2 <= kind <= 4:
        return f"ShaderIeee.Vec {kind}"
    raise ModelError(f"Unknown IEEE Lean type: {kind}")


def fin_index(index):
    return f"⟨{index}, by decide⟩" if isinstance(index, int) else index


def vector_literal(components):
    result = components[-1]
    for index in range(len(components) - 2, -1, -1):
        result = f"if i.val = {index} then {components[index]} else {result}"
    return f"(fun (i : Fin {len(components)}) => {result})"


class IeeeEmitter:
    def __init__(self, model):
        self.model = model

    def components(self, expr):
        if expr["kind"] == "construct":
            result = []
            for child in expr["arguments"]:
                result.extend(self.components(child))
            return result
        if expr["kind"] == "swizzle":
            source = self.components(expr["arguments"][0])
            return [source[index] for index in expr["indices"]]
        if expr["width"] == 1:
            return [self.value(expr)]
        return [self.element(expr, index) for index in range(expr["width"])]

    def element(self, expr, index):
        kind = expr["kind"]
        if expr["width"] == 1:
            return self.value(expr)
        if kind in ("parameter", "local"):
            name = ("p" if kind == "parameter" else "l") + str(expr["index"])
            return f"({name} {fin_index(index)})"
        if kind in ("construct", "swizzle"):
            components = self.components(expr)
            if isinstance(index, int):
                return components[index]
            return f"({vector_literal(components)} {index})"
        if kind == "splat":
            return self.value(expr["arguments"][0])
        return f"({self.value(expr)} {fin_index(index)})"

    def value(self, expr):
        kind, width = expr["kind"], expr["width"]
        if kind in ("parameter", "local"):
            return ("p" if kind == "parameter" else "l") + str(expr["index"])
        if kind == "literal":
            return lean_literal(expr)
        if kind == "uint_literal":
            return f"({expr['value']} : UInt32)"
        if kind == "boolean":
            return "true" if expr["value"] else "false"
        if kind in ("construct", "swizzle"):
            components = self.components(expr)
            return components[0] if width == 1 else vector_literal(components)
        arguments = expr.get("arguments", [])
        if kind == "splat":
            return f"(fun _ => {self.value(arguments[0])})"
        if kind in ("add", "subtract", "multiply", "divide"):
            function = {"add": "add", "subtract": "subtract", "multiply": "multiply", "divide": "divide"}[kind]
            if width == 1:
                values = [self.value(argument) for argument in arguments]
            else:
                values = [self.element(argument, "i") for argument in arguments]
                return f"(fun i => ShaderIeee.Model.{function} {values[0]} {values[1]})"
            return f"(ShaderIeee.Model.{function} {values[0]} {values[1]})"
        if kind == "negate":
            value = self.value(arguments[0]) if width == 1 else self.element(arguments[0], "i")
            return f"(-{value})" if width == 1 else f"(fun i => -{value})"
        if kind == "sqrt":
            if width == 1:
                return f"(ShaderIeee.Model.sqrt {self.value(arguments[0])})"
            return f"(fun i => ShaderIeee.Model.sqrt {self.element(arguments[0], 'i')})"
        if kind == "compare":
            function = {"<": "compareLess", "<=": "compareLessEqual", ">": "compareGreater",
                        ">=": "compareGreaterEqual", "==": "compareEqual", "!=": "compareNotEqual"}[expr["operator"]]
            if arguments[0]["width"] == "bool":
                symbol = "==" if expr["operator"] == "==" else "!="
                return f"({self.value(arguments[0])} {symbol} {self.value(arguments[1])})"
            return f"(ShaderIeee.Model.{function} {self.value(arguments[0])} {self.value(arguments[1])})"
        if kind in ("and", "or", "not"):
            symbol = {"and": "&&", "or": "||", "not": "!"}[kind]
            values = [self.value(argument) for argument in arguments]
            return f"({symbol}{values[0]})" if kind == "not" else f"({values[0]} {symbol} {values[1]})"
        if kind == "choose":
            condition, yes, no = [self.value(argument) for argument in arguments]
            return f"(if {condition} then {yes} else {no})"
        if kind in ("asfloat", "asuint"):
            return f"(ShaderIeee.Model.{kind} {self.value(arguments[0])})"
        raise ModelError(f"Unknown IEEE IR operation: {kind}")

    def definition(self, name, parameters):
        lines = [f"def {name} {parameters} : ShaderIeee.Vec 4 :="]
        for binding in self.model["bindings"]:
            expression = binding["expression"]
            lines.append(f"  let l{binding['index']} : {lean_type(binding['width'])} := {self.value(expression)}")
        lines.append(f"  {self.value(self.model['expression'])}")
        return "\n".join(lines)


def generate_ieee(original, optimized):
    if original.get("schema") != "ieee-1" or optimized.get("schema") != "ieee-1":
        raise ModelError("Expected independent ieee-1 models", "INVALID_INPUT")
    if original.get("profile") != PROFILE or optimized.get("profile") != PROFILE:
        raise ModelError("Unexpected IEEE profile", "INVALID_INPUT")
    interface = original["interface"]
    parameters = " ".join(f"(p{item['index']} : {lean_type(item['width'])})" for item in interface)
    names = " ".join(f"p{item['index']}" for item in interface)
    expected = f"def expected : Prop := ∀ {parameters},\n  original {names} = optimized {names}"
    return ("import ShaderIeee.Model\n\nnamespace ShaderIeee.Generated\n\n" +
            IeeeEmitter(original).definition("original", parameters) + "\n\n" +
            IeeeEmitter(optimized).definition("optimized", parameters) + "\n\n" + expected +
            "\n\nend ShaderIeee.Generated\n")
