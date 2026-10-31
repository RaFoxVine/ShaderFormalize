"""Restricted HLSL to independent binary32 IR; no real-number model is used."""
from fractions import Fraction
import re

from shader_ast import ModelError, literal, parse_tree, quoted, source_header, validate_source
from shader_frontend import Program, callee_reference, swizzle_indices
from shader_flow import GuardedProgram
from shader_packing import uint_literal as packing_uint_literal
from shader_types import (TypeRegistry, component_mask, initialized, numeric_type, operation,
                          read_path, replace_path, value_type)
from shader_validation import lvalue_type


UINT_OPERATORS = {
    "+": "uint_add", "-": "uint_subtract", "*": "uint_multiply",
    "&": "uint_and", "|": "uint_or", "^": "uint_xor",
    "<<": "uint_shift_left", ">>": "uint_shift_right",
}
COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")


class IeeeTypeRegistry(TypeRegistry):
    extra_leaves = ("uint",)

    def node_type(self, node):
        types = quoted(node.text)
        name = types[0].removeprefix("const ") if types else None
        if name in ("uint", "unsigned int"):
            return "uint"
        if name == "literal float" and node.kind == "ConditionalOperator":
            return 1
        return super().node_type(node)

    def named_type(self, name):
        if name in ("uint", "unsigned int"):
            return "uint"
        return super().named_type(name)


def source_token(node, source, unsigned=False):
    lines = source.split("\n")
    if node.line < 1 or node.line > len(lines):
        raise ModelError("Literal source location is unavailable")
    tail = lines[node.line - 1].encode("utf-8")[node.column - 1:].decode("utf-8")
    pattern = r"[0-9]+[uU]?" if unsigned else r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?[fF]?"
    match = re.match(pattern, tail)
    if match is None:
        raise ModelError("Cannot recover numeric spelling from source")
    token = match.group(0)
    if len(tail) > len(token) and (tail[len(token)].isalnum() or tail[len(token)] in "_."):
        raise ModelError("Unsupported numeric token")
    return token


def float_literal(node, source):
    value = literal(node, source)
    value["token"] = source_token(node, source).rstrip("fF")
    return value


def uint_literal(node, source):
    # Shared token reader also checks DXC's value, including hexadecimal input.
    return packing_uint_literal(node, source)


def choose_value(condition, yes, no):
    if value_type(yes) != value_type(no):
        raise ModelError("Conditional arm type mismatch")
    if yes["kind"] == "record":
        fields = {}
        for name in yes["fields"]:
            fields[name] = choose_value(condition, yes["fields"][name], no["fields"][name])
        return dict(yes, fields=fields)
    return operation("choose", value_type(yes), [condition, yes, no])


class IeeeSemantics:
    control = True
    branching = False
    type_registry = IeeeTypeRegistry

    def validate_statement(self, node, result_type, effects_allowed):
        if node.kind == "IfStmt" and self.branching:
            return None
        if node.kind == "CompoundAssignOperator" and self.types.node_type(node) == "uint":
            self.uint_compound_operator(node)
            if lvalue_type(node.children[0], self) != "uint":
                raise ModelError("Uint compound assignment requires a uint destination")
            self.validate_ieee_expression(node.children[1])
            return False
        if node.kind in ("IfStmt", "ForStmt", "WhileStmt", "DoStmt", "SwitchStmt", "CaseStmt",
                         "DefaultStmt", "BreakStmt", "ContinueStmt", "DiscardStmt"):
            raise ModelError(f"Control flow and effects are outside the IEEE subset: {node.kind}")
        return None

    def uint_compound_operator(self, node):
        pattern = (r" lvalue '(\+=|-=|\*=|&=|\|=|\^=|<<=|>>=)'"
                   r" ComputeLHSTy='(?:uint|unsigned int)'(?::'(?:uint|unsigned int)')?"
                   r" ComputeResultTy='(?:uint|unsigned int)'(?::'(?:uint|unsigned int)')?$")
        match = re.search(pattern, node.text)
        if (match is None or len(node.children) != 2 or self.types.node_type(node) != "uint"
                or any(self.types.node_type(child) != "uint" for child in node.children)):
            raise ModelError("Unsupported uint compound assignment or computation type")
        return UINT_OPERATORS[match.group(1)[:-1]]

    def assign_statement(self, node, symbols):
        if node.kind != "CompoundAssignOperator" or self.types.node_type(node) != "uint":
            return False
        operator = self.uint_compound_operator(node)
        symbol, path, kind = self.lvalue(node.children[0], symbols)
        if not symbol["writable"]:
            raise ModelError("Only locals and by-value helper parameters may be assigned")
        old = initialized(read_path(symbol["value"], path))
        right = self.expression(node.children[1], symbols)
        value = self.snapshot(operation(operator, kind, [old, right]), symbol["name"])
        symbol["value"] = replace_path(symbol["value"], path, value)
        return True

    def zero_value(self, kind):
        if kind == "uint":
            return {"kind": "uint_literal", "width": "uint", "value": 0}
        if kind == "bool":
            return {"kind": "boolean", "width": "bool", "value": False}
        if isinstance(kind, int):
            scalar = operation("asfloat", 1, [self.zero_value("uint")])
            return scalar if kind == 1 else operation("splat", kind, [scalar])
        fields = {field["name"]: self.zero_value(field["type"]) for field in self.types.records[kind]["fields"]}
        return {"kind": "record", "type": kind, "fields": fields}

    def validate_extra_definitions(self):
        if self.resources.layout:
            raise ModelError("Resources and resource effects are outside the IEEE subset")

    def validate_extension(self, node):
        self.validate_ieee_expression(node)
        return True

    def validate_ieee_expression(self, node):
        kind = self.types.node_type(node)
        if node.kind in ("DeclRefExpr", "MemberExpr"):
            lvalue_type(node, self)
            return
        if node.kind == "CallExpr":
            self.checked_call(node)
            for child in node.children[1:]:
                self.validate_ieee_expression(child)
            return
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            match = re.search(r"<([A-Za-z]+)>$", node.text)
            cast = match.group(1) if match else None
            child = node.children[0]
            if cast == "IntegralToFloating" and kind == 1 and child.kind == "IntegerLiteral" and not child.children:
                float_literal(child, self.source)
                return
            self.validate_ieee_expression(child)
            child_type = self.types.node_type(child)
            if cast == "LValueToRValue" and child_type == kind:
                return
            if cast == "FloatingCast" and kind == 1 and quoted(child.text)[:1] == ["literal float"]:
                return
            if cast == "HLSLVectorSplat" and child_type == 1 and isinstance(kind, int):
                return
            raise ModelError(f"Numeric conversion is outside the IEEE subset: {cast}")
        if node.kind in ("ParenExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
            if node.kind == "CXXFunctionalCastExpr" and (not isinstance(kind, int) or not node.text.endswith("<NoOp>")):
                raise ModelError("Only component-preserving vector constructors are supported")
            self.validate_ieee_expression(node.children[0])
            if self.types.node_type(node.children[0]) != kind:
                raise ModelError("Constructor/parenthesis type mismatch")
            return
        if node.kind == "FloatingLiteral" and kind == 1 and not node.children:
            float_literal(node, self.source)
            return
        if node.kind == "IntegerLiteral" and kind == "uint" and not node.children:
            uint_literal(node, self.source)
            return
        if node.kind == "CXXBoolLiteralExpr" and kind == "bool" and not node.children and node.text.endswith((" true", " false")):
            return
        if node.kind == "InitListExpr" and isinstance(kind, int) and kind > 1:
            sizes = []
            for child in node.children:
                self.validate_ieee_expression(child)
                sizes.append(self.types.node_type(child))
            if not all(isinstance(size, int) for size in sizes) or sum(sizes) != kind:
                raise ModelError("Constructor component count mismatch")
            return
        if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
            self.validate_ieee_expression(node.children[0])
            owner = self.types.node_type(node.children[0])
            mask = component_mask(node)
            if not isinstance(owner, int) or owner == 1 or len(mask) != kind:
                raise ModelError("Unsupported vector component expression")
            swizzle_indices(mask, owner)
            return
        if node.kind == "UnaryOperator" and len(node.children) == 1:
            operator = quoted(node.text)[-1]
            self.validate_ieee_expression(node.children[0])
            child_type = self.types.node_type(node.children[0])
            if operator == "-" and child_type == kind and isinstance(kind, int):
                return
            if operator == "!" and child_type == kind == "bool":
                return
            if operator in ("~", "-") and child_type == kind == "uint":
                return
            raise ModelError(f"Unsupported unary operator/types: {operator}")
        if node.kind == "BinaryOperator" and len(node.children) == 2:
            operator = quoted(node.text)[-1]
            for child in node.children:
                self.validate_ieee_expression(child)
            child_types = [self.types.node_type(child) for child in node.children]
            arithmetic = operator in ("+", "-", "*", "/") and isinstance(kind, int) and child_types == [kind, kind]
            uint_arithmetic = kind == "uint" and child_types == ["uint", "uint"] and operator in UINT_OPERATORS
            comparison = kind == "bool" and child_types in ([1, 1], ["uint", "uint"]) and operator in COMPARISONS
            boolean = kind == "bool" and child_types == ["bool", "bool"] and operator in ("&&", "||", "==", "!=")
            if arithmetic or uint_arithmetic or comparison or boolean:
                return
            raise ModelError(f"Unsupported binary operator/types: {operator}")
        if node.kind == "ConditionalOperator" and len(node.children) == 3:
            condition, yes, no = node.children
            for child in node.children:
                self.validate_ieee_expression(child)
            if self.types.node_type(condition) != "bool" or self.types.node_type(yes) != kind or self.types.node_type(no) != kind:
                raise ModelError("Conditional condition/arm type mismatch")
            if kind == "void":
                raise ModelError("Conditional selection cannot produce void")
            return
        raise ModelError(f"Unsupported IEEE expression: {node.kind}")

    def checked_call(self, node):
        key, name, signature = callee_reference(node)
        size = self.types.node_type(node)
        widths = [self.types.node_type(child) for child in node.children[1:]]
        if key in self.functions:
            function = self.functions[key]
            if function["name"] != name or function["signature"] != signature or function is self.main:
                raise ModelError("Function reference identity/signature mismatch")
            if size != function["type"] or widths != [param["type"] for param in function["parameters"]]:
                raise ModelError("Function call argument/result type mismatch")
            return function, name, size
        valid = ((name == "sqrt" and isinstance(size, int) and widths == [size]) or
                 (name == "asfloat" and size == 1 and widths == ["uint"]) or
                 (name == "asuint" and size == "uint" and widths in ([1], ["uint"])))
        if not valid:
            raise ModelError("Only defined helpers, sqrt, asfloat and scalar asuint are supported")
        expected = numeric_type(size) + "(" + ",".join(numeric_type(width) for width in widths) + ")"
        normalized = signature.replace("unsigned int", "uint").replace(" ", "").replace("vector<float,1>", "float")
        for width in (2, 3, 4):
            normalized = normalized.replace(f"vector<float,{width}>", f"float{width}")
        normalized = re.sub(r"\bfloat1\b", "float", normalized)
        if normalized != expected:
            raise ModelError("Unsupported intrinsic overload")
        return None, name, size

    def expression(self, node, symbols):
        kind = self.types.node_type(node)
        if node.kind in ("DeclRefExpr", "MemberExpr"):
            symbol, path, expected = self.lvalue(node, symbols)
            value = initialized(read_path(symbol["value"], path))
            if value_type(value) != expected:
                raise ModelError("Read value type mismatch")
            return value
        if node.kind == "CallExpr":
            function, name, size = self.checked_call(node)
            arguments = [self.expression(child, symbols) for child in node.children[1:]]
            if function is not None:
                return self.invoke(function, arguments)
            if name == "asuint" and value_type(arguments[0]) == "uint":
                return arguments[0]
            return operation(name, size, arguments)
        if node.kind == "ImplicitCastExpr" and len(node.children) == 1:
            match = re.search(r"<([A-Za-z]+)>$", node.text)
            cast = match.group(1) if match else None
            child_node = node.children[0]
            if cast == "IntegralToFloating" and child_node.kind == "IntegerLiteral" and kind == 1:
                return float_literal(child_node, self.source)
            child = self.expression(child_node, symbols)
            if cast == "LValueToRValue" and value_type(child) == kind:
                return child
            if cast == "FloatingCast" and quoted(child_node.text)[:1] == ["literal float"] and kind == 1:
                return child
            if cast == "HLSLVectorSplat" and value_type(child) == 1 and isinstance(kind, int):
                return child if kind == 1 else operation("splat", kind, [child])
            raise ModelError(f"Unsupported IEEE conversion: {cast}")
        if node.kind in ("ParenExpr", "CXXFunctionalCastExpr") and len(node.children) == 1:
            child = self.expression(node.children[0], symbols)
            if value_type(child) != kind:
                raise ModelError("Constructor/parenthesis type mismatch")
            return child
        if node.kind == "FloatingLiteral" and kind == 1 and not node.children:
            return float_literal(node, self.source)
        if node.kind == "IntegerLiteral" and kind == "uint" and not node.children:
            return uint_literal(node, self.source)
        if node.kind == "CXXBoolLiteralExpr" and kind == "bool" and not node.children:
            return {"kind": "boolean", "width": "bool", "value": node.text.endswith(" true")}
        if node.kind == "InitListExpr" and isinstance(kind, int) and kind > 1:
            arguments = [self.expression(child, symbols) for child in node.children]
            if any(not isinstance(value_type(arg), int) for arg in arguments) or sum(arg["width"] for arg in arguments) != kind:
                raise ModelError("Constructor component count mismatch")
            return operation("construct", kind, arguments)
        if node.kind == "HLSLVectorElementExpr" and len(node.children) == 1:
            child = self.expression(node.children[0], symbols)
            indices = swizzle_indices(component_mask(node), child["width"])
            if len(indices) != kind:
                raise ModelError("Component selection type mismatch")
            return dict(operation("swizzle", kind, [child]), indices=indices)
        if node.kind == "UnaryOperator" and len(node.children) == 1:
            operator = quoted(node.text)[-1]
            child = self.expression(node.children[0], symbols)
            if operator == "-" and value_type(child) == kind and isinstance(kind, int):
                return operation("negate", kind, [child])
            if operator == "!" and value_type(child) == kind == "bool":
                return operation("not", kind, [child])
            if value_type(child) == kind == "uint" and operator in ("~", "-"):
                return operation("uint_not" if operator == "~" else "uint_negate", kind, [child])
            raise ModelError(f"Unsupported IEEE unary operator: {operator}")
        if node.kind == "BinaryOperator" and len(node.children) == 2:
            operator = quoted(node.text)[-1]
            arguments = [self.expression(child, symbols) for child in node.children]
            if kind == "uint" and operator in UINT_OPERATORS and all(value_type(arg) == "uint" for arg in arguments):
                return operation(UINT_OPERATORS[operator], kind, arguments)
            if operator in ("+", "-", "*", "/") and isinstance(kind, int):
                if any(value_type(arg) != kind for arg in arguments):
                    raise ModelError("Arithmetic operand type mismatch")
                name = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}[operator]
                return operation(name, kind, arguments)
            if kind == "bool" and ((arguments[0]["width"] == arguments[1]["width"] and
                                    arguments[0]["width"] in (1, "uint") and operator in COMPARISONS) or
                                   (arguments[0]["width"] == arguments[1]["width"] == "bool" and
                                    operator in ("&&", "||", "==", "!="))):
                name = {"&&": "and", "||": "or"}.get(operator, "compare")
                result = operation(name, kind, arguments)
                if name == "compare":
                    result["operator"] = operator
                return result
            raise ModelError(f"Unsupported IEEE binary operator: {operator}")
        if node.kind == "ConditionalOperator" and len(node.children) == 3:
            condition, yes, no = [self.expression(child, symbols) for child in node.children]
            if value_type(condition) != "bool":
                raise ModelError("Conditional condition must be scalar bool")
            return choose_value(condition, yes, no)
        raise ModelError(f"Unsupported IEEE AST node: {node.kind}")

    def model(self):
        model = super().model()
        model["schema"] = "ieee-1"
        model["profile"] = "binary32-rne-preserve-subnormals-separate-ops-v1"
        model.pop("events", None)
        model.pop("effects", None)
        model.pop("resources", None)
        return model


class IeeeProgram(IeeeSemantics, Program):
    def validate_helper_initialization(self):
        names = ("bindings", "events", "effects", "stack", "fragment", "invocations")
        saved = {name: getattr(self, name) for name in names}
        try:
            for function in self.functions.values():
                if function is self.main:
                    continue
                self.bindings, self.events, self.effects, self.stack = [], [], [], []
                self.invocations = 0
                arguments = [self.zero_value(param["type"]) for param in function["parameters"]]
                self.invoke(function, arguments)
        finally:
            for name, value in saved.items():
                setattr(self, name, value)


class IeeeControlProgram(IeeeSemantics, GuardedProgram):
    branching = True


def import_ieee(source, dump):
    validate_source(source)
    nodes = [parse_tree(dump)]
    while nodes:
        node = nodes.pop()
        if node.kind == "IfStmt":
            return IeeeControlProgram(source, dump).model()
        nodes.extend(node.children)
    return IeeeProgram(source, dump).model()
