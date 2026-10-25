"""Scalar uint32 and explicitly tracked float bit carriers on guarded SSA."""
import re

from shader_ast import ModelError, quoted
from shader_control import ControlProgram
from shader_frontend import callee_reference
from shader_types import TypeRegistry, operation


UINT_BINARY = {"+": "uint_add", "-": "uint_sub", "*": "uint_mul", "&": "uint_and",
               "|": "uint_or", "^": "uint_xor", "<<": "uint_shl", ">>": "uint_shr"}


class PackingTypes(TypeRegistry):
    extra_leaves = ("uint",)

    def node_type(self, node):
        types = quoted(node.text)
        if not types:
            raise ModelError("Missing typed packing expression")
        name = types[0].removeprefix("const ")
        if name in ("uint", "unsigned int"):
            return "uint"
        if name == "literal int" and node.kind == "IntegerLiteral":
            return "literal_int"
        return super().node_type(node)

    def named_type(self, name):
        return "uint" if name in ("uint", "unsigned int") else super().named_type(name)


def uses_packing(root):
    nodes = [root]
    while nodes:
        node = nodes.pop()
        types = [] if node.kind == "Null" else quoted(node.text)
        if any(re.search(r"\b(uint|unsigned int|asuint|asfloat)\b", item) for item in types):
            return True
        nodes.extend(node.children)
    return False


def uint_literal(node, source):
    line = source.split("\n")[node.line - 1].encode("utf-8")
    tail = line[node.column - 1:].decode("utf-8")
    match = re.match(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)[uU]?", tail)
    if match is None:
        raise ModelError("Cannot recover uint literal spelling")
    token = match.group()
    if len(tail) > len(token) and (tail[len(token)].isalnum() or tail[len(token)] in "_."):
        raise ModelError("Unsupported uint literal suffix")
    digits = token.rstrip("uU")
    if len(digits) > 12:
        raise ModelError("Uint literal exceeds 32 bits")
    if not digits.lower().startswith("0x") and len(digits) > 1 and digits.startswith("0"):
        raise ModelError("Octal literals are unsupported")
    value = int(digits, 16 if digits.lower().startswith("0x") else 10)
    printed = re.search(r" ([0-9]+)$", node.text)
    if not 0 <= value < 2**32 or printed is None or int(printed.group(1)) != value:
        raise ModelError("Uint literal exceeds 32 bits or differs from DXC")
    return {"kind": "uint_literal", "width": "uint", "value": value}


def has_payload(value):
    if value["kind"] == "record":
        return any(has_payload(field) for field in value["fields"].values() if field is not None)
    return bool(value.get("payload"))


def check_payload_use(value):
    if value["kind"] == "record":
        for field in value["fields"].values():
            if field is not None:
                check_payload_use(field)
        return
    args = value.get("arguments", [])
    if value["kind"] not in ("choose", "carrier", "recover") and any(has_payload(arg) for arg in args):
        raise ModelError("Bit carriers cannot participate in numeric operations")


class PackingProgram(ControlProgram):
    packing = True
    type_registry = PackingTypes

    def validate_extension(self, node):
        from shader_validation import validate_expression
        kind = self.types.node_type(node)
        children = node.children
        if node.kind == "IntegerLiteral" and kind in ("uint", "literal_int") and not children:
            uint_literal(node, self.source)
            return True
        valid = False
        if node.kind == "InitListExpr" and len(children) == 1 and kind in (1, "uint"):
            valid = self.types.node_type(children[0]) == kind
        if node.kind in ("CStyleCastExpr", "CXXFunctionalCastExpr") and len(children) == 1 and node.text.endswith("<NoOp>"):
            valid = kind in (1, "uint") and self.types.node_type(children[0]) == kind
        if node.kind == "ImplicitCastExpr" and len(children) == 1:
            child_type = self.types.node_type(children[0])
            valid = valid or (node.text.endswith("<FloatingToIntegral>") and kind == "uint" and child_type == 1)
            valid = valid or (node.text.endswith("<IntegralToFloating>") and kind == 1 and child_type == "uint")
            valid = valid or (node.text.endswith("<IntegralCast>") and kind == "uint" and child_type == "literal_int")
            valid = valid or (node.text.endswith("<IntegralToBoolean>") and kind == "bool" and child_type == "uint")
        if node.kind == "UnaryOperator" and len(children) == 1 and kind == "uint":
            valid = quoted(node.text)[-1] in ("~", "-") and self.types.node_type(children[0]) == "uint"
        if node.kind == "BinaryOperator" and len(children) == 2:
            kinds = [self.types.node_type(child) for child in children]
            operator = quoted(node.text)[-1]
            valid = valid or (kind == "uint" and kinds == ["uint", "uint"] and operator in UINT_BINARY)
            valid = valid or (kind == "bool" and kinds == ["uint", "uint"] and operator in ("<", "<=", ">", ">=", "==", "!="))
        if valid:
            for child in children:
                validate_expression(child, self)
            return True
        return False

    def checked_call(self, node):
        key, name, signature = callee_reference(node)
        if key in self.functions or name not in ("asfloat", "asuint"):
            return super().checked_call(node)
        kind = self.types.node_type(node)
        kinds = [self.types.node_type(child) for child in node.children[1:]]
        valid = (name == "asfloat" and kind == 1 and kinds == ["uint"])
        valid = valid or (name == "asuint" and kind == "uint" and kinds in ([1], ["uint"]))
        canonical = signature.replace("unsigned int", "uint").replace(" ", "")
        expected = ("float" if kind == 1 else "uint") + "(" + ("float" if kinds == [1] else "uint") + ")"
        if not valid or canonical != expected:
            raise ModelError("Unsupported bit reinterpretation overload")
        return None, name, kind

    def snapshot(self, value, name):
        check_payload_use(value)
        result = super().snapshot(value, name)
        if value.get("payload"):
            result["payload"] = True
        return result

    def effect(self, value):
        check_payload_use(value)
        return super().effect(value)

    def invoke(self, function, arguments):
        if any(has_payload(argument) for argument in arguments):
            raise ModelError("Bit carriers cannot cross helper parameter boundaries yet")
        result = super().invoke(function, arguments)
        if has_payload(result):
            raise ModelError("Bit carriers cannot cross helper return boundaries yet")
        return result

    def call(self, node, symbols):
        function, name, kind = self.checked_call(node)
        if function is not None:
            arguments = [self.expression(child, symbols) for child in node.children[1:]]
            return self.invoke(function, arguments)
        if name in ("asfloat", "asuint"):
            arg = self.expression(node.children[1], symbols)
            if name == "asfloat":
                return dict(operation("carrier", 1, [arg]), payload=True)
            if arg["width"] == "uint":
                return arg
            if not arg.get("payload"):
                raise ModelError("asuint of an ordinary real requires unsupported float encoding")
            return operation("recover", "uint", [arg])
        # Preserve normal intrinsic effects and guard semantics.
        return super().call(node, symbols)

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        children = node.children
        if node.kind == "IntegerLiteral" and kind == "uint":
            return uint_literal(node, self.source)
        if node.kind == "InitListExpr" and len(children) == 1 and kind in (1, "uint"):
            result = self.expression(children[0], symbols)
        elif node.kind in ("CStyleCastExpr", "CXXFunctionalCastExpr") and len(children) == 1 and node.text.endswith("<NoOp>") and kind in (1, "uint"):
            result = self.expression(children[0], symbols)
        elif node.kind == "ImplicitCastExpr" and len(children) == 1 and node.text.endswith("<IntegralCast>") and kind == "uint":
            result = uint_literal(children[0], self.source)
        elif node.kind == "ImplicitCastExpr" and len(children) == 1 and node.text.endswith("<FloatingToIntegral>"):
            result = self.snapshot(operation("real_to_uint", "uint", [self.expression(children[0], symbols)]), "cast.uint")
        elif node.kind == "ImplicitCastExpr" and len(children) == 1 and node.text.endswith("<IntegralToFloating>") and self.types.node_type(children[0]) == "uint":
            result = operation("uint_to_real", 1, [self.expression(children[0], symbols)])
        elif node.kind == "ImplicitCastExpr" and len(children) == 1 and node.text.endswith("<IntegralToBoolean>"):
            arg = self.expression(children[0], symbols)
            result = dict(operation("compare", "bool", [arg, {"kind": "uint_literal", "width": "uint", "value": 0}]), operator="!=")
        elif node.kind == "BinaryOperator" and kind == "uint" and len(children) == 2:
            op = UINT_BINARY[quoted(node.text)[-1]]
            result = operation(op, "uint", [self.expression(child, symbols) for child in children])
            if op in ("uint_shl", "uint_shr"):
                result = self.snapshot(result, "shift.uint")
        elif node.kind == "UnaryOperator" and kind == "uint":
            result = operation("uint_not" if quoted(node.text)[-1] == "~" else "uint_neg", "uint", [self.expression(children[0], symbols)])
        else:
            result = super().expression(node, symbols)
        check_payload_use(result)
        return result

    def model(self):
        model = super().model()
        if has_payload(model["expression"]):
            raise ModelError("Bit carriers cannot be shader color output")
        model.update(schema=5, integer_semantics="uint32-exact-with-real-conversion-domains")
        return model
