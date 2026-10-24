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
    match = re.match(r" 0x[0-9a-fA-F]+ (?:parent cbuffer 0x[0-9a-fA-F]+ )?(?P<range><<invalid sloc>>|<[^<>]*>)(?P<point> (?:line:[0-9]+:[0-9]+|col:[0-9]+))?(?P<tail>.*)$", text)
    if match is None:
        raise ModelError("Unrecognized AST source header")
    return match


def quoted(text):
    return re.findall(r"'([^']*)'", source_header(text).group("tail"))


def width(node):
    types = quoted(node.text)
    if not types:
        raise ModelError(f"Missing type on {node.kind}")
    value_type = types[0].removeprefix("const ")
    if value_type == "float" or (value_type == "literal float" and node.kind in ("FloatingLiteral", "ParenExpr", "BinaryOperator", "UnaryOperator")):
        return 1
    vector = re.fullmatch(r"float([234])|vector<float, ([234])>", value_type)
    if vector is not None:
        return int(vector.group(1) or vector.group(2))
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


def validate_source(source):
    # This subset has no strings, includes or line splicing. Reject these even in
    # comments instead of trying to duplicate the preprocessor's lexical rules.
    forbidden_line_chars = any(c in source for c in ("\v", "\f", "\x85", "\u2028", "\u2029")) or re.search(r"\r(?!\n)", source)
    if len(source.encode("utf-8")) > 65536 or forbidden_line_chars or any(token in source for token in ("#", "\\", "%:", "??=")):
        raise ModelError("Preprocessing, escaped lines and large inputs are outside this prototype")
