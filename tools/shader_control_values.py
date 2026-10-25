"""Pure predicates and persistent conditional values used by control-flow import."""
from shader_ast import ModelError, quoted
from shader_types import operation, value_type


def truth(value):
    return {"kind": "boolean", "width": "bool", "value": value}


def logical(kind, *arguments):
    if kind == "not" and arguments[0]["kind"] == "boolean":
        return truth(not arguments[0]["value"])
    if kind in ("and", "or"):
        lhs, rhs = arguments
        if lhs == rhs:
            return lhs
        for value, other in ((lhs, rhs), (rhs, lhs)):
            if value["kind"] == "boolean":
                if kind == "and":
                    return other if value["value"] else value
                return value if value["value"] else other
    return operation(kind, "bool", list(arguments))


def zero_value(kind, types):
    if kind == "bool":
        return truth(False)
    if isinstance(kind, int):
        scalar = {"kind": "literal", "width": 1, "numerator": 0, "denominator": 1}
        return scalar if kind == 1 else operation("splat", kind, [scalar])
    fields = {field["name"]: zero_value(field["type"], types) for field in types.records[kind]["fields"]}
    return {"kind": "record", "type": kind, "fields": fields}


def choose(condition, yes, no):
    if yes is None or no is None:
        return None
    if value_type(yes) != value_type(no):
        raise ModelError("Conditional value type mismatch")
    if yes["kind"] == "record":
        fields = {name: choose(condition, yes["fields"][name], no["fields"][name]) for name in yes["fields"]}
        return dict(yes, fields=fields)
    if yes == no:
        return yes
    return operation("choose", value_type(yes), [condition, yes, no])


def clone_symbols(symbols):
    return {key: dict(symbol) for key, symbol in symbols.items()}


def uses_control(root):
    nodes = [root]
    while nodes:
        node = nodes.pop()
        if node.kind in ("ConditionalOperator", "CXXBoolLiteralExpr"):
            return True
        if node.kind in ("VarDecl", "ParmVarDecl", "FieldDecl", "FunctionDecl") and any(
                item == "bool" or item == "const bool" or item.startswith("bool (") for item in quoted(node.text)):
            return True
        if (node.kind == "ImplicitCastExpr" and node.text.endswith("<IntegralToFloating>")
                and node.children and quoted(node.children[0].text)[:1] in (["bool"], ["const bool"])):
            return True
        if node.kind == "BinaryOperator" and quoted(node.text)[-1:] in (["&&"], ["||"]):
            return True
        if node.kind == "IfStmt":
            if len(node.children) != 4:
                return True
            initializer, condition, body, otherwise = node.children
            if body.kind == "CompoundStmt" and len(body.children) == 1:
                body = body.children[0]
            if (initializer.kind != "Null" or otherwise.kind != "Null" or body.kind != "DiscardStmt"
                    or condition.kind != "BinaryOperator" or quoted(condition.text)[-1:] not in
                    (["<"], ["<="], [">"], [">="], ["=="], ["!="])):
                return True
        nodes.extend(node.children)
    return False
