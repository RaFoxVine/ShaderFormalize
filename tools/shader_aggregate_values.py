"""Persistent numeric components and conservative constant-index discovery."""
from shader_ast import ModelError, quoted
from shader_packing import UINT_BINARY, uint_literal
from shader_packing_eval import packing_scalar
from shader_types import operation, lane_count, scalar_type, vector_type, value_type


def components(value, width):
    scalar = scalar_type(width)
    width = lane_count(width)
    if value is None:
        return [None] * width
    if value["kind"] == "partial_vector":
        return value["components"]
    if scalar == "uint" and value["kind"] == "construct":
        return [part for child in value["arguments"] for part in components(child, value_type(child))]
    if scalar == "uint" and value["kind"] == "swizzle":
        source = components(value["arguments"][0], value_type(value["arguments"][0]))
        return [source[i] for i in value["indices"]]
    if width == 1:
        return [value]
    return [dict(operation("swizzle", scalar, [value]), indices=[i]) for i in range(width)]


def vector(values, kind=None):
    known = [v for v in values if v is not None]
    scalar = scalar_type(value_type(known[0])) if known else (scalar_type(kind) if kind is not None else 1)
    if any(value_type(v) != scalar for v in known):
        raise ModelError("Vector components must have one scalar type")
    result_type = vector_type(scalar, len(values))
    if kind is not None and kind != result_type:
        raise ModelError("Vector shape mismatch")
    if any(value is None for value in values):
        return {"kind": "partial_vector", "width": result_type, "components": values}
    return values[0] if len(values) == 1 else operation("construct", result_type, values)


def constant_ast(node, source):
    if node.kind == "IntegerLiteral":
        return uint_literal(node, source)["value"]
    if node.kind == "ParenExpr" and len(node.children) == 1:
        return constant_ast(node.children[0], source)
    if (node.kind == "ImplicitCastExpr" and node.text.endswith("<IntegralCast>")
            and len(node.children) == 1):
        return constant_ast(node.children[0], source)
    if node.kind in ("UnaryOperator", "BinaryOperator"):
        operator = quoted(node.text)[-1]
        kind = ({"~": "uint_not", "-": "uint_neg"}.get(operator) if node.kind == "UnaryOperator"
                else UINT_BINARY.get(operator))
        if kind is None:
            return None
        values = [constant_ast(child, source) for child in node.children]
        if any(value is None for value in values):
            return None
        try:
            return packing_scalar(kind, values, True)
        except ValueError:
            return None
    return None


def constant_value(value, bindings, seen=None):
    if value["kind"] == "uint_literal":
        return value["value"]
    if value["kind"] == "local":
        seen = set() if seen is None else seen
        index = value["index"]
        if index in seen:
            raise ModelError("Cyclic index constant")
        return constant_value(bindings[index]["expression"], bindings, seen | {index})
    if value["kind"].startswith("uint_"):
        values = [constant_value(child, bindings, seen) for child in value["arguments"]]
        if any(item is None for item in values):
            return None
        try:
            return packing_scalar(value["kind"], values, True)
        except ValueError:
            return None
    return None
