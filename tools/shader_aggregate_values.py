"""Persistent numeric components and conservative constant-index discovery."""
from shader_ast import ModelError, quoted
from shader_packing import UINT_BINARY, uint_literal
from shader_packing_eval import packing_scalar
from shader_types import operation


def components(value, width):
    if value is None:
        return [None] * width
    if value["kind"] == "partial_vector":
        return value["components"]
    if width == 1:
        return [value]
    return [dict(operation("swizzle", 1, [value]), indices=[i]) for i in range(width)]


def vector(values):
    if any(value is None for value in values):
        return {"kind": "partial_vector", "width": len(values), "components": values}
    return values[0] if len(values) == 1 else operation("construct", len(values), values)


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
