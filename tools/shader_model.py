"""Restricted, fail-closed adapter for the pinned DXC AST dump, not an HLSL parser."""

from dataclasses import dataclass, field
from fractions import Fraction
import re


class ModelError(Exception):
    def __init__(self, message, status="UNSUPPORTED"):
        super().__init__(message)
        self.status = status


@dataclass
class AstNode:
    kind: str
    text: str
    line: int
    column: int
    children: list = field(default_factory=list)


def source_header(text):
    # Windows paths may contain apostrophes and commas. Source ranges come
    # before type quotes; parse their delimiters rather than scanning a path as code.
    match = re.match(r" 0x[0-9a-fA-F]+ (?P<range><<invalid sloc>>|<[^<>]*>)(?P<point> (?:line:[0-9]+:[0-9]+|col:[0-9]+))?(?P<tail>.*)$", text)
    if match is None:
        raise ModelError("Unrecognized AST source header")
    return match


def quoted(text):
    return re.findall(r"'([^']*)'", source_header(text).group("tail"))


def width(node):
    types = quoted(node.text)
    if not types:
        raise ModelError(f"Missing type on {node.kind}")
    if types[0] == "float" or (types[0] == "literal float" and node.kind in ("FloatingLiteral", "ParenExpr", "BinaryOperator", "UnaryOperator")):
        return 1
    if types[0] in ("float4", "vector<float, 4>"):
        return 4
    raise ModelError(f"Unsupported type: {types[0]}")


def parse_tree(dump):
    stack = []
    root = None
    # DXC elides repeated source lines relative to the last printed location,
    # including range ends and declaration-name locations, not to AST parents.
    last_source_line = 1
    for line in dump.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([ |`-]*)([A-Za-z][A-Za-z0-9_]*)(.*)", line)
        if match is None:
            raise ModelError("Unrecognized AST dump line")
        prefix, kind, text = match.groups()
        if len(prefix) % 2:
            raise ModelError("Invalid AST indentation")
        depth = len(prefix) // 2
        if depth > 100 or depth > len(stack):
            raise ModelError("Invalid or excessively deep AST")
        parent = stack[depth - 1] if depth else None
        source_line = last_source_line
        column = 1
        header = source_header(text)
        location_head = header.group("range") + (header.group("point") or "")
        locations = list(re.finditer(r"line:([0-9]+):([0-9]+)|\bcol:([0-9]+)|:([0-9]+):([0-9]+)(?=[,>])", location_head))
        for index, location in enumerate(locations):
            if location.group(3) is not None:
                current_column = int(location.group(3))
            else:
                last_source_line = int(location.group(1) or location.group(4))
                current_column = int(location.group(2) or location.group(5))
            if index == 0:
                source_line, column = last_source_line, current_column
        node = AstNode(kind, text, source_line, column)
        if parent is not None:
            parent.children.append(node)
        elif root is None:
            root = node
        else:
            raise ModelError("Multiple AST roots")
        stack = stack[:depth]
        stack.append(node)
    if root is None or root.kind != "TranslationUnitDecl":
        raise ModelError("Missing translation unit")
    return root


def exact_number(text):
    if not isinstance(text, str) or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text
    ):
        raise ModelError("Numbers must be finite decimal strings", "INVALID_INPUT")
    exponent = 0
    if "e" in text.lower():
        exponent = int(text.lower().split("e")[-1])
    if len(text) > 100 or abs(exponent) > 1000:
        raise ModelError("Numeric literal is too large", "INVALID_INPUT")
    return Fraction(text)


def literal(node, source):
    lines = source.split("\n")
    if node.line < 1 or node.line > len(lines):
        raise ModelError("Literal source location is unavailable")
    # DXC columns are byte offsets; do not substitute its rounded printed value.
    tail = lines[node.line - 1].encode("utf-8")[node.column - 1:].decode("utf-8")
    pattern = r"[0-9]+" if node.kind == "IntegerLiteral" else r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?[fF]?"
    match = re.match(pattern, tail)
    if match is None:
        raise ModelError("Cannot recover numeric spelling from source")
    token = match.group(0)
    if node.kind == "IntegerLiteral" and len(token) > 1 and token.startswith("0"):
        raise ModelError("Octal/leading-zero integer literals are outside this prototype")
    if len(tail) > len(token) and (tail[len(token)].isalnum() or tail[len(token)] in "_."):
        raise ModelError("Unsupported numeric token")
    value = exact_number(token.rstrip("fF"))
    return {"kind": "literal", "width": 1, "numerator": value.numerator, "denominator": value.denominator}


def expression(node, source, parameters):
    result_width = width(node)
    if node.kind == "DeclRefExpr":
        reference = re.search(r"\bParmVar (0x[0-9a-fA-F]+) '([A-Za-z_][A-Za-z0-9_]*)'", node.text)
        if reference is None or reference.group(1) not in parameters or node.children:
            raise ModelError("Only parameter references are supported")
        parameter = parameters[reference.group(1)]
        if parameter["name"] != reference.group(2) or parameter["width"] != result_width:
            raise ModelError("Parameter reference type mismatch")
        return {"kind": "parameter", "width": result_width, "index": parameter["index"]}
    if node.kind == "FloatingLiteral" and result_width == 1 and not node.children:
        return literal(node, source)
    if node.kind == "ImplicitCastExpr":
        conversion = re.search(r"<([A-Za-z]+)>$", node.text)
        if conversion is None or len(node.children) != 1:
            raise ModelError("Unsupported implicit conversion")
        cast = conversion.group(1)
        if cast == "FloatingCast" and quoted(node.children[0].text)[:1] == ["literal float"] and result_width == 1:
            return expression(node.children[0], source, parameters)
        if cast == "IntegralToFloating" and node.children[0].kind == "IntegerLiteral" and result_width == 1:
            return literal(node.children[0], source)
        child = expression(node.children[0], source, parameters)
        if cast == "LValueToRValue" and child["width"] == result_width:
            return child
        if cast == "HLSLVectorSplat" and child["width"] == 1 and result_width == 4:
            return {"kind": "splat", "width": 4, "arguments": [child]}
        raise ModelError(f"Unsupported conversion: {cast}")
    if node.kind == "ParenExpr" and len(node.children) == 1:
        child = expression(node.children[0], source, parameters)
        if child["width"] != result_width:
            raise ModelError("Parenthesis type mismatch")
        return child
    if node.kind == "UnaryOperator" and len(node.children) == 1 and quoted(node.text)[-1] == "-":
        child = expression(node.children[0], source, parameters)
        if child["width"] != result_width:
            raise ModelError("Unary type mismatch")
        return {"kind": "negate", "width": result_width, "arguments": [child]}
    if node.kind == "BinaryOperator" and len(node.children) == 2:
        operator = quoted(node.text)[-1]
        if operator not in ("+", "-", "*"):
            raise ModelError(f"Unsupported operator: {operator}")
        arguments = []
        for child in node.children:
            argument = expression(child, source, parameters)
            if argument["width"] != result_width:
                raise ModelError("Binary operand type mismatch")
            arguments.append(argument)
        return {"kind": {"+": "add", "-": "subtract", "*": "multiply"}[operator], "width": result_width, "arguments": arguments}
    if node.kind == "CallExpr" and node.children:
        callee = node.children[0]
        if callee.kind != "ImplicitCastExpr" or not callee.text.endswith("<FunctionToPointerDecay>") or len(callee.children) != 1:
            raise ModelError("Unsupported callee")
        reference = callee.children[0]
        function = re.search(r"\bFunction 0x[0-9a-fA-F]+ '(lerp|saturate)' '([^']+)'$", reference.text)
        if reference.kind != "DeclRefExpr" or function is None or reference.children:
            raise ModelError("Only compiler-provided lerp and saturate are supported")
        name, signature = function.groups()
        expected_count = 3 if name == "lerp" else 1
        component = "float" if result_width == 1 else "vector<float,4>"
        expected_signature = component + "(" + ",".join([component] * expected_count) + ")"
        if signature.replace(" ", "") != expected_signature or len(node.children) != expected_count + 1:
            raise ModelError("Unsupported intrinsic overload")
        arguments = []
        for child in node.children[1:]:
            argument = expression(child, source, parameters)
            if argument["width"] != result_width:
                raise ModelError("Intrinsic argument type mismatch")
            arguments.append(argument)
        return {"kind": name, "width": result_width, "arguments": arguments}
    raise ModelError(f"Unsupported AST node: {node.kind}")


def validate_source(source):
    # This subset has no strings, includes or line splicing. Reject these even in
    # comments instead of trying to duplicate the preprocessor's lexical rules.
    forbidden_line_chars = any(c in source for c in ("\v", "\f", "\x85", "\u2028", "\u2029")) or re.search(r"\r(?!\n)", source)
    if len(source.encode("utf-8")) > 65536 or forbidden_line_chars or any(token in source for token in ("#", "\\", "%:", "??=")):
        raise ModelError("Preprocessing, escaped lines and large inputs are outside this prototype")


def import_shader(source, dump):
    validate_source(source)
    root = parse_tree(dump)
    if len(root.children) != 1 or root.children[0].kind != "FunctionDecl":
        raise ModelError("Only a single main definition is supported; no other declarations")
    function = root.children[0]
    if re.search(r"\bmain 'float4 \(float4, float4, float\)'$", function.text) is None:
        raise ModelError("Expected float4 main(float4, float4, float)")
    parameters = {}
    interface = []
    body = None
    output_semantic = None
    stage_count = 0
    for node in function.children:
        if node.kind == "ParmVarDecl":
            if len(node.children) != 1 or node.children[0].kind != "SemanticDecl" or node.children[0].children:
                raise ModelError("Each input needs exactly one semantic")
            identity = re.match(r" (0x[0-9a-fA-F]+) ", node.text)
            name = source_header(node.text).group("tail").split("'")[0].strip().split()[-1]
            semantic_match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"$', node.children[0].text)
            if identity is None or semantic_match is None or len(interface) >= 3:
                raise ModelError("Invalid input declaration")
            item = {"index": len(interface), "name": name, "width": width(node), "semantic": semantic_match.group(1).upper()}
            parameters[identity.group(1)] = item
            interface.append(item)
        elif node.kind == "CompoundStmt" and body is None:
            body = node
        elif node.kind == "SemanticDecl" and output_semantic is None:
            semantic_match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"$', node.text)
            if semantic_match is None or node.children:
                raise ModelError("Unsupported output semantic")
            output_semantic = semantic_match.group(1).upper()
        elif node.kind == "HLSLShaderAttr" and node.text.endswith('Implicit "pixel"') and not node.children:
            stage_count += 1
        else:
            raise ModelError(f"Unsupported function declaration child: {node.kind}")
    if [item["width"] for item in interface] != [4, 4, 1] or len({item["name"] for item in interface}) != 3:
        raise ModelError("Expected two float4 inputs and one scalar input")
    if output_semantic not in ("SV_TARGET", "SV_TARGET0") or stage_count != 1:
        raise ModelError("Expected a single pixel color output")
    if body is None or len(body.children) != 1 or body.children[0].kind != "ReturnStmt" or len(body.children[0].children) != 1:
        raise ModelError("Only one return expression is supported")
    value = expression(body.children[0].children[0], source, parameters)
    if value["width"] != 4:
        raise ModelError("Return type is not float4")
    return {"schema": 1, "interface": interface, "output_semantic": output_semantic, "expression": value}


def load_constraints(data, interface):
    scalar_name = interface[2]["name"]
    if not isinstance(data, dict) or set(data) != {"schema", "ranges"} or type(data["schema"]) is not int or data["schema"] != 1:
        raise ModelError("Unknown constraint schema or fields", "INVALID_INPUT")
    ranges = data["ranges"]
    if not isinstance(ranges, dict) or set(ranges) != {scalar_name}:
        raise ModelError("Specify exactly the scalar input's interval", "INVALID_INPUT")
    bounds = ranges[scalar_name]
    if not isinstance(bounds, dict) or set(bounds) != {"min", "max"}:
        raise ModelError("Expected min and max", "INVALID_INPUT")
    lower = exact_number(bounds["min"])
    upper = exact_number(bounds["max"])
    if lower > upper:
        raise ModelError("Contradictory input interval", "INVALID_INPUT")
    return lower, upper


def lean_number(value):
    if value.denominator == 1:
        return f"({value.numerator} : ℝ)"
    return f"({value.numerator} / {value.denominator} : ℝ)"


def lean_expression(expr):
    kind = expr["kind"]
    if kind == "parameter":
        name = f"p{expr['index']}"
        return f"({name} i)" if expr["width"] == 4 else name
    if kind == "literal":
        return lean_number(Fraction(expr["numerator"], expr["denominator"]))
    args = []
    for argument in expr["arguments"]:
        args.append(lean_expression(argument))
    if kind == "splat":
        return args[0]
    if kind == "negate":
        return f"(-{args[0]})"
    if kind in ("add", "subtract", "multiply"):
        operator = {"add": "+", "subtract": "-", "multiply": "*"}[kind]
        return f"({args[0]} {operator} {args[1]})"
    if kind in ("lerp", "saturate"):
        return f"(ShaderFormalize.Model.{kind} {' '.join(args)})"
    raise ModelError(f"Cannot emit IR operation: {kind}")


def generate_lean(original, optimized, lower, upper):
    a = lean_expression(original["expression"])
    b = lean_expression(optimized["expression"])
    return f'''import ShaderFormalize.Model

namespace ShaderFormalize.Generated
open ShaderFormalize.Model

def original (p0 p1 : Vec4) (p2 : ℝ) : Vec4 := fun i => {a}
def optimized (p0 p1 : Vec4) (p2 : ℝ) : Vec4 := fun i => {b}

def expected : Prop := ∀ (p0 p1 : Vec4) (p2 : ℝ),
  {lean_number(lower)} ≤ p2 → p2 ≤ {lean_number(upper)} →
  original p0 p1 p2 = optimized p0 p1 p2

end ShaderFormalize.Generated
'''
